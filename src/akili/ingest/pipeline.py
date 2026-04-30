"""
Orchestrate ingestion: PDF → load pages → Gemini extract → canonicalize → return/store.
Adds a short delay between pages to reduce 429 rate-limit hits (one Gemini call per page).

Supports corpus matching: if an uploaded PDF matches a pre-canonicalized entry in the
public corpus, the canonical data is loaded directly (FR-CORP-2), skipping Gemini calls.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from pathlib import Path
from typing import Callable

from akili import config
from akili.canonical import Bijection, ConditionalUnit, Grid, Range, Unit
from akili.ingest.canonicalize import canonicalize_page
from akili.ingest.consensus import consensus_extract_page, should_use_consensus
from akili.ingest.errors import is_rate_limit_error as _is_rate_limit_error
from akili.ingest.gemini_extract import extract_page as gemini_extract_page
from akili.ingest.multipage import merge_multipage_tables
from akili.ingest.page_classifier import classify_page, get_extraction_hint
from akili.ingest.pdf_loader import load_pdf_pages
from akili.store.repository import Store

logger = logging.getLogger(__name__)


def _check_corpus(pdf_path: Path, store: Store | None) -> tuple[bool, dict | None]:
    """
    Check if PDF matches a corpus entry (FR-CORP-2).

    Returns (is_match, corpus_entry) where corpus_entry contains canonical data.
    """
    if store is None or not hasattr(store, "get_corpus_entry"):
        return False, None

    try:
        from akili.corpus.loader import compute_pdf_hash

        pdf_hash = compute_pdf_hash(pdf_path)
        entry = store.get_corpus_entry(pdf_hash)
        if entry:
            logger.info("Corpus match found for %s (hash=%s...)", pdf_path.name, pdf_hash[:12])
            return True, entry
    except Exception as e:
        logger.debug("Corpus check failed: %s", e)

    return False, None


def _load_canonical_from_corpus(
    corpus_entry: dict,
    doc_id: str,
) -> list[Unit | Bijection | Grid | Range | ConditionalUnit]:
    """Load canonical objects from corpus entry."""
    from akili.corpus.loader import load_from_corpus, CorpusEntry

    entry = CorpusEntry(
        content_hash=corpus_entry["content_hash"],
        mpn=corpus_entry["mpn"],
        chip_name=corpus_entry["chip_name"],
        datasheet_url=corpus_entry.get("datasheet_url"),
        canonical_data=corpus_entry.get("canonical_data") or {},
    )

    units, bijections, grids, ranges, conditional_units = load_from_corpus(entry, doc_id)

    result: list[Unit | Bijection | Grid | Range | ConditionalUnit] = []
    result.extend(units)
    result.extend(bijections)
    result.extend(grids)
    result.extend(ranges)
    result.extend(conditional_units)

    return result


def ingest_document(
    pdf_path: Path | str,
    doc_id: str | None = None,
    store: Store | None = None,
    progress_callback: Callable[[dict], None] | None = None,
    uploaded_by: str | None = None,
) -> tuple[str, list[Unit | Bijection | Grid], int, int]:
    """
    Ingest a PDF: load pages, extract via Gemini, canonicalize.

    Returns (doc_id, list of canonical objects, total_pages, pages_failed).
    doc_id is generated if not provided. If store is provided, canonical objects are persisted.
    pages_failed is the number of pages that raised an exception (e.g. rate limit, validation).
    If progress_callback is set, it is called with dicts: {"phase": "rendering"},
    {"phase": "rendering_done", "total_pages": N}, {"phase": "extracting", "page": i, "total": N},
    {"phase": "canonicalizing", "page": i, "total": N}, {"phase": "storing", "total_pages": N},
    {"phase": "done", ...}.
    """
    def _progress(msg: dict) -> None:
        if progress_callback:
            progress_callback(msg)

    doc_id = doc_id or str(uuid.uuid4())
    pdf_path = Path(pdf_path).resolve()

    # CRITICAL-1: Validate path is within allowed directory to prevent traversal
    allowed_base = Path(os.environ.get("AKILI_DOCS_DIR", config.DOCS_DIR)).resolve()
    if not str(pdf_path).startswith(str(allowed_base)):
        raise ValueError(
            f"Path outside allowed directory: {pdf_path} "
            f"(allowed base: {allowed_base})"
        )

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # FR-CORP-2: Check corpus before ingestion for instant results
    _progress({"phase": "checking_corpus"})
    corpus_match, corpus_entry = _check_corpus(pdf_path, store)

    if corpus_match and corpus_entry:
        logger.info("Loading from corpus (skipping Gemini extraction): %s", corpus_entry.get("chip_name"))
        _progress({"phase": "loading_corpus", "chip": corpus_entry.get("chip_name")})

        all_canonical = _load_canonical_from_corpus(corpus_entry, doc_id)

        if store is not None:
            _progress({"phase": "storing", "total_pages": 1, "from_corpus": True})
            units = [o for o in all_canonical if isinstance(o, Unit)]
            bijections = [o for o in all_canonical if isinstance(o, Bijection)]
            grids = [o for o in all_canonical if isinstance(o, Grid)]
            ranges = [o for o in all_canonical if isinstance(o, Range)]
            conditional_units = [o for o in all_canonical if isinstance(o, ConditionalUnit)]
            store.store_canonical(
                doc_id, pdf_path.name, 1, units, bijections, grids,
                ranges=ranges, conditional_units=conditional_units,
                uploaded_by=uploaded_by,
            )

        result = {
            "phase": "done",
            "doc_id": doc_id,
            "total_pages": 1,
            "pages_failed": 0,
            "units_count": len([o for o in all_canonical if isinstance(o, Unit)]),
            "bijections_count": len([o for o in all_canonical if isinstance(o, Bijection)]),
            "grids_count": len([o for o in all_canonical if isinstance(o, Grid)]),
            "from_corpus": True,
            "chip_name": corpus_entry.get("chip_name"),
        }
        _progress(result)
        return doc_id, all_canonical, 1, 0

    _progress({"phase": "rendering"})
    pages = load_pdf_pages(pdf_path)
    total_pages = len(pages)

    # HIGH-2: Enforce max page limit to prevent memory exhaustion
    if total_pages > config.MAX_PAGES:
        raise ValueError(
            f"PDF has {total_pages} pages, exceeds maximum {config.MAX_PAGES}. "
            "Set AKILI_MAX_PAGES to override."
        )

    _progress({"phase": "rendering_done", "total_pages": total_pages})

    all_canonical: list[Unit | Bijection | Grid] = []
    pages_failed = 0

    for i, (page_index, image_bytes) in enumerate(pages):
        if i > 0 and config.GEMINI_PAGE_DELAY > 0:
            time.sleep(config.GEMINI_PAGE_DELAY)
        _progress({"phase": "extracting", "page": page_index, "total": total_pages})
        try:
            page_type = classify_page(image_bytes)
            hint = get_extraction_hint(page_type)
            page_agreement = 0.5  # default for single-pass
            if should_use_consensus(page_type):
                extraction, page_agreement = consensus_extract_page(
                    page_index, image_bytes, doc_id, page_type_hint=hint,
                )
            else:
                extraction = gemini_extract_page(page_index, image_bytes, doc_id, page_type_hint=hint)
            _progress({"phase": "canonicalizing", "page": page_index, "total": total_pages})
            canonical = canonicalize_page(extraction, doc_id, page_index)
            # Propagate consensus agreement to canonical objects
            for obj in canonical:
                if hasattr(obj, "extraction_agreement"):
                    obj.extraction_agreement = page_agreement
            all_canonical.extend(canonical)
        except Exception as e:
            pages_failed += 1
            logger.warning(
                "Page %s extraction failed (doc_id=%s): %s",
                page_index,
                doc_id,
                e,
                exc_info=True,
            )
            if _is_rate_limit_error(e) and config.GEMINI_429_COOLDOWN > 0:
                logger.info(
                    "Rate limit detected; waiting %.0f s before next page (doc_id=%s).",
                    config.GEMINI_429_COOLDOWN,
                    doc_id,
                )
                time.sleep(config.GEMINI_429_COOLDOWN)
            continue

    all_canonical, merge_candidates = merge_multipage_tables(all_canonical)
    if merge_candidates:
        logger.info(
            "Multi-page merge: %d table(s) merged across page boundaries (doc_id=%s).",
            len(merge_candidates), doc_id,
        )

    if total_pages > 0 and len(all_canonical) == 0:
        logger.warning(
            "Ingest completed but no facts extracted from any of %s page(s) (doc_id=%s). "
            "Check GOOGLE_API_KEY, Gemini model (AKILI_GEMINI_MODEL), and server logs.",
            total_pages,
            doc_id,
        )
    if pages_failed > 0:
        logger.info(
            "Ingest: %s of %s page(s) failed (doc_id=%s). Often rate limits; "
            "try AKILI_GEMINI_PAGE_DELAY_SECONDS=4 or higher.",
            pages_failed,
            total_pages,
            doc_id,
        )

    if store is not None:
        _progress({"phase": "storing", "total_pages": total_pages})
        units = [o for o in all_canonical if isinstance(o, Unit)]
        bijections = [o for o in all_canonical if isinstance(o, Bijection)]
        grids = [o for o in all_canonical if isinstance(o, Grid)]
        store.store_canonical(doc_id, pdf_path.name, total_pages, units, bijections, grids, uploaded_by=uploaded_by)

    result: dict = {
        "phase": "done",
        "doc_id": doc_id,
        "total_pages": total_pages,
        "pages_failed": pages_failed,
        "units_count": len([o for o in all_canonical if isinstance(o, Unit)]),
        "bijections_count": len([o for o in all_canonical if isinstance(o, Bijection)]),
        "grids_count": len([o for o in all_canonical if isinstance(o, Grid)]),
    }
    if (
        result["units_count"] == 0
        and result["bijections_count"] == 0
        and result["grids_count"] == 0
    ):
        result["extraction_warning"] = (
            "No facts extracted from this document. "
            "Check GOOGLE_API_KEY in .env, Gemini model (AKILI_GEMINI_MODEL), "
            "and server logs for errors."
        )
    elif pages_failed > 0:
        result["extraction_note"] = (
            f"Extracted from {total_pages - pages_failed} of {total_pages} pages. "
            f"{pages_failed} page(s) were skipped (often due to rate limits). "
            "Try increasing AKILI_GEMINI_PAGE_DELAY_SECONDS in .env and re-upload."
        )
    _progress(result)
    return doc_id, all_canonical, total_pages, pages_failed
