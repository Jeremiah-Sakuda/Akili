"""
Orchestrate ingestion: PDF → load pages → Gemini extract → canonicalize → return/store.
Adds a short delay between pages to reduce 429 rate-limit hits (one Gemini call per page).
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from pathlib import Path
from typing import Callable

from akili.canonical import Bijection, Grid, Unit
from akili.ingest.canonicalize import canonicalize_page
from akili.ingest.gemini_extract import extract_page as gemini_extract_page
from akili.ingest.pdf_loader import load_pdf_pages
from akili.store.repository import Store

logger = logging.getLogger(__name__)

# Seconds to wait between page extractions to avoid bursting Gemini rate limits (default 4)
_PAGE_DELAY = float(os.environ.get("AKILI_GEMINI_PAGE_DELAY_SECONDS", "4.0"))
# After a page fails with 429/rate limit, wait this many seconds before next page (default 60)
_429_COOLDOWN = float(os.environ.get("AKILI_GEMINI_429_COOLDOWN_SECONDS", "60.0"))


def _is_rate_limit_error(e: BaseException) -> bool:
    msg = (getattr(e, "message", None) or str(e)).lower()
    return "429" in msg or "resource exhausted" in msg or "resourceexhausted" in msg


def ingest_document(
    pdf_path: Path | str,
    doc_id: str | None = None,
    store: Store | None = None,
    progress_callback: Callable[[dict], None] | None = None,
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
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    _progress({"phase": "rendering"})
    pages = load_pdf_pages(pdf_path)
    total_pages = len(pages)
    _progress({"phase": "rendering_done", "total_pages": total_pages})

    all_canonical: list[Unit | Bijection | Grid] = []
    pages_failed = 0

    for i, (page_index, image_bytes) in enumerate(pages):
        if i > 0 and _PAGE_DELAY > 0:
            time.sleep(_PAGE_DELAY)
        _progress({"phase": "extracting", "page": page_index, "total": total_pages})
        try:
            extraction = gemini_extract_page(page_index, image_bytes, doc_id)
            _progress({"phase": "canonicalizing", "page": page_index, "total": total_pages})
            canonical = canonicalize_page(extraction, doc_id, page_index)
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
            if _is_rate_limit_error(e) and _429_COOLDOWN > 0:
                logger.info(
                    "Rate limit detected; waiting %.0f s before next page (doc_id=%s).",
                    _429_COOLDOWN,
                    doc_id,
                )
                time.sleep(_429_COOLDOWN)
            continue

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
        store.store_canonical(doc_id, pdf_path.name, total_pages, units, bijections, grids)

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
