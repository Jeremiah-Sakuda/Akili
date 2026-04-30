"""
Load PDF and yield (page_index, image_bytes) for each page.

Uses PyMuPDF to render pages as PNG bytes for Gemini vision.
"""

from __future__ import annotations

import logging
from pathlib import Path

import fitz  # PyMuPDF

from akili import config

logger = logging.getLogger(__name__)


def load_pdf_pages(pdf_path: Path) -> list[tuple[int, bytes]]:
    """
    Load a PDF and return a list of (page_index, png_bytes) for each page.

    Page indices are 0-based. PNG bytes are suitable for Gemini image input.
    Skips pages that fail to render (e.g. corrupted) so one bad page does not fail the whole PDF.
    Raises ValueError if the PDF exceeds AKILIconfig.MAX_PAGES.
    """
    pages: list[tuple[int, bytes]] = []
    doc = fitz.open(pdf_path)
    try:
        total = len(doc)
        if config.MAX_PAGES > 0 and total > config.MAX_PAGES:
            raise ValueError(
                f"PDF has {total} pages, exceeding the limit of {config.MAX_PAGES}. "
                f"Set AKILIconfig.MAX_PAGES to increase the limit."
            )
        for page_index in range(total):
            try:
                page = doc[page_index]
                pix = page.get_pixmap(dpi=150, alpha=False)
                png_bytes = pix.tobytes(output="png")
                pages.append((page_index, png_bytes))
            except (RuntimeError, ValueError, TypeError) as exc:
                logger.warning("Failed to render page %d: %s", page_index, exc)
                continue
    finally:
        doc.close()
    return pages
