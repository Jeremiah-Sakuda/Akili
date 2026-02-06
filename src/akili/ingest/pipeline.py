"""
Orchestrate ingestion: PDF → load pages → Gemini extract → canonicalize → return/store.
Adds a short delay between pages to reduce 429 rate-limit hits (one Gemini call per page).
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

from akili.canonical import Bijection, Grid, Unit
from akili.ingest.canonicalize import canonicalize_page
from akili.ingest.gemini_extract import extract_page as gemini_extract_page
from akili.ingest.pdf_loader import load_pdf_pages
from akili.store.repository import Store

# Seconds to wait between page extractions to avoid bursting Gemini rate limits (default 2)
_PAGE_DELAY = float(os.environ.get("AKILI_GEMINI_PAGE_DELAY_SECONDS", "2.0"))


def ingest_document(
    pdf_path: Path | str,
    doc_id: str | None = None,
    store: Store | None = None,
) -> tuple[str, list[Unit | Bijection | Grid]]:
    """
    Ingest a PDF: load pages, extract via Gemini, canonicalize.

    Returns (doc_id, list of canonical objects). doc_id is generated if not provided.
    If store is provided, canonical objects are persisted.
    """
    doc_id = doc_id or str(uuid.uuid4())
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pages = load_pdf_pages(pdf_path)
    all_canonical: list[Unit | Bijection | Grid] = []

    for i, (page_index, image_bytes) in enumerate(pages):
        if i > 0 and _PAGE_DELAY > 0:
            time.sleep(_PAGE_DELAY)
        try:
            extraction = gemini_extract_page(page_index, image_bytes, doc_id)
            canonical = canonicalize_page(extraction, doc_id, page_index)
            all_canonical.extend(canonical)
        except Exception:
            continue

    if store is not None:
        units = [o for o in all_canonical if isinstance(o, Unit)]
        bijections = [o for o in all_canonical if isinstance(o, Bijection)]
        grids = [o for o in all_canonical if isinstance(o, Grid)]
        store.store_canonical(doc_id, pdf_path.name, len(pages), units, bijections, grids)

    return doc_id, all_canonical
