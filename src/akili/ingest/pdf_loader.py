"""
Load PDF and yield (page_index, image_bytes) for each page.

Uses PyMuPDF to render pages as PNG bytes for Gemini vision.
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF


def load_pdf_pages(pdf_path: Path) -> list[tuple[int, bytes]]:
    """
    Load a PDF and return a list of (page_index, png_bytes) for each page.

    Page indices are 0-based. PNG bytes are suitable for Gemini image input.
    Skips pages that fail to render (e.g. corrupted) so one bad page does not fail the whole PDF.
    """
    pages: list[tuple[int, bytes]] = []
    doc = fitz.open(pdf_path)
    try:
        for page_index in range(len(doc)):
            try:
                page = doc[page_index]
                pix = page.get_pixmap(dpi=150, alpha=False)
                png_bytes = pix.tobytes(output="png")
                pages.append((page_index, png_bytes))
            except Exception:
                continue
    finally:
        doc.close()
    return pages
