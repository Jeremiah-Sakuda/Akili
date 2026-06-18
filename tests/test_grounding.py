"""Coordinate-grounding tests — the product's central claim, exercised against a real PDF.

These render a PDF with PyMuPDF, obtain the TRUE text-box geometry independently (via
``page.search_for``), then assert that grounding snaps an extracted fact's origin to land
inside that true box. A regression that returns systematically wrong coordinates fails here.
"""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from akili.canonical import Point, Unit
from akili.ingest.grounding import ground_objects, ground_text, load_page_words

PAGE_W, PAGE_H = 612, 792


@pytest.fixture()
def datasheet_pdf(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "grounding.pdf"
    doc = fitz.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    page.insert_text((100, 200), "VCC Max: 5.5V", fontsize=11)
    page.insert_text((100, 400), "Clock: 20MHz", fontsize=11)
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def _true_norm_rect(pdf_path: Path, needle: str) -> fitz.Rect:
    """The true normalized (0–1) rect of the first occurrence of ``needle``."""
    doc = fitz.open(pdf_path)
    try:
        page = doc[0]
        rects = page.search_for(needle)
        assert rects, f"{needle!r} not found in test PDF"
        r = rects[0]
        return fitz.Rect(r.x0 / PAGE_W, r.y0 / PAGE_H, r.x1 / PAGE_W, r.y1 / PAGE_H)
    finally:
        doc.close()


def test_load_page_words_normalizes(datasheet_pdf):
    words = load_page_words(datasheet_pdf)
    assert 0 in words
    texts = {w.text for w in words[0]}
    assert "5.5V" in texts
    for w in words[0]:
        assert 0.0 <= w.x0 <= 1.0 and 0.0 <= w.y0 <= 1.0
        assert w.x0 <= w.x1 and w.y0 <= w.y1


def test_ground_text_finds_token(datasheet_pdf):
    words = load_page_words(datasheet_pdf)[0]
    result = ground_text("5.5V", words)
    assert result is not None
    origin, bbox, score = result
    assert score >= 0.9
    true = _true_norm_rect(datasheet_pdf, "5.5V")
    # Grounded origin lands inside the true text box (small tolerance for baseline vs box top).
    assert true.x0 - 0.02 <= origin.x <= true.x1 + 0.02
    assert true.y0 - 0.03 <= origin.y <= true.y1 + 0.03


def test_ground_objects_snaps_and_flags(datasheet_pdf):
    words_by_page = load_page_words(datasheet_pdf)
    # A unit whose value really is on the page, but with a WRONG estimated origin.
    good = Unit(
        id="u1",
        label="VCC max",
        value=5.5,
        unit_of_measure="V",
        origin=Point(x=0.01, y=0.99),  # deliberately bogus estimate
        doc_id="d",
        page=0,
    )
    # A unit whose value does NOT appear anywhere on the page.
    bad = Unit(
        id="u2",
        label="phantom",
        value=999.9,
        unit_of_measure="A",
        origin=Point(x=0.5, y=0.5),
        doc_id="d",
        page=0,
    )
    stats = ground_objects([good, bad], words_by_page)

    assert stats["grounded"] == 1
    assert good.grounded is True and good.grounding_score > 0
    true = _true_norm_rect(datasheet_pdf, "5.5V")
    assert true.x0 - 0.02 <= good.origin.x <= true.x1 + 0.02
    assert true.y0 - 0.03 <= good.origin.y <= true.y1 + 0.03

    # The phantom value cannot be grounded; it stays flagged and its estimate is untouched.
    assert bad.grounded is False and bad.grounding_score == 0.0
    assert bad.origin.x == 0.5 and bad.origin.y == 0.5


def test_no_text_layer_leaves_ungrounded(tmp_path: Path):
    """A page with no extractable text grounds nothing (and does not crash)."""
    pdf_path = tmp_path / "blank.pdf"
    doc = fitz.open()
    doc.new_page(width=PAGE_W, height=PAGE_H)  # empty page, no text
    doc.save(str(pdf_path))
    doc.close()

    words_by_page = load_page_words(pdf_path)
    u = Unit(id="u", value=5.5, unit_of_measure="V", origin=Point(x=0.3, y=0.3), doc_id="d", page=0)
    stats = ground_objects([u], words_by_page)
    assert stats["grounded"] == 0
    assert u.grounded is False
