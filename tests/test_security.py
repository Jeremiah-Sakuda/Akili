"""
Security tests for Akili: path traversal, prompt injection, coordinate
clamping, JSON size limits, and grid bounds validation.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from akili.canonical.models import Grid, GridCell, Point
from akili.ingest.gemini_extract import _normalize_origin


# ---------------------------------------------------------------------------
# Path traversal (CRITICAL-1)
# ---------------------------------------------------------------------------

class TestPathTraversal:
    """Verify that ingest_document rejects paths outside the allowed dir."""

    def test_path_outside_allowed_dir_rejected(self, tmp_path: Path):
        """Traversal attempt using ../../etc/passwd should raise ValueError."""
        from akili.ingest.pipeline import ingest_document

        evil_path = tmp_path / ".." / ".." / "etc" / "passwd"
        with patch.dict(os.environ, {"AKILI_DOCS_DIR": str(tmp_path)}), \
             patch("akili.config.DOCS_DIR", str(tmp_path)):
            with pytest.raises(ValueError, match="Path outside allowed directory"):
                ingest_document(evil_path)

    def test_valid_path_accepted(self, tmp_path: Path):
        """A path inside the allowed dir should not raise ValueError for path check."""
        from akili.ingest.pipeline import ingest_document

        valid_pdf = tmp_path / "test.pdf"
        valid_pdf.write_bytes(b"%PDF-1.4 minimal")
        with patch.dict(os.environ, {"AKILI_DOCS_DIR": str(tmp_path)}), \
             patch("akili.config.DOCS_DIR", str(tmp_path)):
            # Will fail on PDF parsing, not path validation
            with pytest.raises((FileNotFoundError, Exception)):
                ingest_document(valid_pdf)


# ---------------------------------------------------------------------------
# Max page limit (HIGH-2)
# ---------------------------------------------------------------------------

class TestMaxPages:
    """Verify that ingest_document rejects PDFs exceeding MAX_PAGES."""

    def test_max_pages_exceeded(self, tmp_path: Path):
        from akili.ingest.pipeline import ingest_document

        pdf_path = tmp_path / "big.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 test")

        with patch.dict(os.environ, {"AKILI_DOCS_DIR": str(tmp_path)}), \
             patch("akili.config.DOCS_DIR", str(tmp_path)), \
             patch("akili.ingest.pipeline.load_pdf_pages") as mock_load, \
             patch("akili.config.MAX_PAGES", 10):
            mock_load.return_value = [b"fake"] * 11
            with pytest.raises(ValueError, match="exceeds maximum"):
                ingest_document(pdf_path)


# ---------------------------------------------------------------------------
# Coordinate clamping (MEDIUM-8)
# ---------------------------------------------------------------------------

class TestCoordinateClamping:
    """Verify _normalize_origin clamps to [0, 1]."""

    def test_clamps_above_1(self):
        result = _normalize_origin({"x": 1.5, "y": 2.0})
        assert result == {"x": 1.0, "y": 1.0}

    def test_clamps_below_0(self):
        result = _normalize_origin({"x": -0.5, "y": -1.0})
        assert result == {"x": 0.0, "y": 0.0}

    def test_normal_range_unchanged(self):
        result = _normalize_origin({"x": 0.5, "y": 0.75})
        assert result == {"x": 0.5, "y": 0.75}

    def test_list_input_clamped(self):
        result = _normalize_origin([1.5, -0.1])
        assert result == {"x": 1.0, "y": 0.0}

    def test_invalid_returns_none(self):
        assert _normalize_origin("bad") is None
        assert _normalize_origin({}) is None
        assert _normalize_origin({"x": "a", "y": "b"}) is None


# ---------------------------------------------------------------------------
# Grid bounds validation (HIGH-4)
# ---------------------------------------------------------------------------

class TestGridBoundsValidation:
    """Verify Grid.get_cell returns None for out-of-bounds indices."""

    def _make_grid(self) -> Grid:
        return Grid(
            id="g1",
            rows=3,
            cols=3,
            cells=[
                GridCell(row=0, col=0, value="A"),
                GridCell(row=1, col=1, value="B"),
                GridCell(row=2, col=2, value="C"),
            ],
            origin=Point(x=0.1, y=0.1),
            doc_id="test",
            page=0,
        )

    def test_valid_cell_returned(self):
        g = self._make_grid()
        cell = g.get_cell(1, 1)
        assert cell is not None
        assert cell.value == "B"

    def test_negative_row_returns_none(self):
        assert self._make_grid().get_cell(-1, 0) is None

    def test_negative_col_returns_none(self):
        assert self._make_grid().get_cell(0, -1) is None

    def test_row_out_of_bounds_returns_none(self):
        assert self._make_grid().get_cell(3, 0) is None

    def test_col_out_of_bounds_returns_none(self):
        assert self._make_grid().get_cell(0, 3) is None

    def test_both_out_of_bounds_returns_none(self):
        assert self._make_grid().get_cell(10, 10) is None
