"""Pipeline integration test: mock Gemini, run full ingest, verify canonical output.

Uses a synthetic PDF (single page) and a mocked Gemini response to test the full
pipeline from PDF load through canonicalization and storage.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from akili.canonical import Bijection, Grid, Unit
from akili.ingest.extract_schema import PageExtraction
from akili.ingest.pipeline import ingest_document
from akili.store.repository import Store


@pytest.fixture()
def synthetic_pdf(tmp_path: Path) -> Path:
    """Create a minimal valid PDF file for testing.

    Uses PyMuPDF to create a single-page PDF with text content.
    """
    import fitz

    pdf_path = tmp_path / "test_datasheet.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Test Datasheet - AKILI-48Q", fontsize=16)
    page.insert_text((72, 120), "Absolute Maximum Ratings", fontsize=12)
    page.insert_text((72, 150), "VCC Max: 5.5V", fontsize=10)
    page.insert_text((72, 170), "ICC Max: 250mA", fontsize=10)
    page.insert_text((72, 200), "Pin 1: VCC", fontsize=10)
    page.insert_text((72, 220), "Pin 2: GND", fontsize=10)
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


MOCK_EXTRACTION_RESPONSE = {
    "units": [
        {
            "id": "u1",
            "label": "VCC max",
            "value": 5.5,
            "unit_of_measure": "V",
            "context": "Absolute Maximum Ratings - supply voltage",
            "origin": {"x": 0.15, "y": 0.19},
            "bbox": {"x1": 0.1, "y1": 0.18, "x2": 0.5, "y2": 0.2},
        },
        {
            "id": "u2",
            "label": "ICC max",
            "value": 250,
            "unit_of_measure": "mA",
            "context": "Absolute Maximum Ratings - maximum supply current",
            "origin": {"x": 0.15, "y": 0.22},
        },
        {
            "id": "u3",
            "label": "Part Number",
            "value": "AKILI-48Q",
            "context": "part number ordering information",
            "origin": {"x": 0.15, "y": 0.09},
        },
    ],
    "bijections": [
        {
            "id": "b1",
            "left_set": ["1", "2"],
            "right_set": ["VCC", "GND"],
            "mapping": {"1": "VCC", "2": "GND"},
            "origin": {"x": 0.15, "y": 0.25},
        },
    ],
    "grids": [],
}


def _make_mock_gemini_response(data: dict) -> MagicMock:
    """Create a mock Gemini response object that returns the given JSON data."""
    response = MagicMock()
    response.text = json.dumps(data)
    return response


class TestPipelineIntegration:
    """Full pipeline: PDF -> load pages -> extract (mocked) -> canonicalize -> store."""

    @patch("akili.ingest.pipeline.classify_page", return_value="other")
    @patch("akili.ingest.pipeline.get_extraction_hint", return_value="")
    @patch("akili.ingest.gemini_extract.genai")
    def test_full_ingest_produces_canonical_objects(
        self, mock_genai, mock_hint, mock_classify, synthetic_pdf, tmp_store
    ):
        mock_model = MagicMock()
        mock_model.generate_content.return_value = _make_mock_gemini_response(
            MOCK_EXTRACTION_RESPONSE
        )
        mock_genai.GenerativeModel.return_value = mock_model

        import os
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            with patch("akili.config.GEMINI_PAGE_DELAY", 0):
                doc_id, canonical, total_pages, pages_failed = ingest_document(
                    synthetic_pdf, store=tmp_store
                )

        assert total_pages == 1
        assert pages_failed == 0
        assert len(canonical) > 0

        units = [o for o in canonical if isinstance(o, Unit)]
        bijections = [o for o in canonical if isinstance(o, Bijection)]
        grids = [o for o in canonical if isinstance(o, Grid)]

        assert len(units) == 3
        assert len(bijections) == 1
        assert len(grids) == 0

    @patch("akili.ingest.pipeline.classify_page", return_value="other")
    @patch("akili.ingest.pipeline.get_extraction_hint", return_value="")
    @patch("akili.ingest.gemini_extract.genai")
    def test_ingest_stores_to_db(
        self, mock_genai, mock_hint, mock_classify, synthetic_pdf, tmp_store
    ):
        mock_model = MagicMock()
        mock_model.generate_content.return_value = _make_mock_gemini_response(
            MOCK_EXTRACTION_RESPONSE
        )
        mock_genai.GenerativeModel.return_value = mock_model

        import os
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            with patch("akili.config.GEMINI_PAGE_DELAY", 0):
                doc_id, _, _, _ = ingest_document(
                    synthetic_pdf, store=tmp_store
                )

        docs = tmp_store.list_documents()
        assert len(docs) == 1
        assert docs[0]["doc_id"] == doc_id

        units = tmp_store.get_units_by_doc(doc_id)
        assert len(units) == 3

        bijections = tmp_store.get_bijections_by_doc(doc_id)
        assert len(bijections) == 1

    @patch("akili.ingest.pipeline.classify_page", return_value="other")
    @patch("akili.ingest.pipeline.get_extraction_hint", return_value="")
    @patch("akili.ingest.gemini_extract.genai")
    def test_ingest_canonical_data_integrity(
        self, mock_genai, mock_hint, mock_classify, synthetic_pdf, tmp_store
    ):
        mock_model = MagicMock()
        mock_model.generate_content.return_value = _make_mock_gemini_response(
            MOCK_EXTRACTION_RESPONSE
        )
        mock_genai.GenerativeModel.return_value = mock_model

        import os
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            with patch("akili.config.GEMINI_PAGE_DELAY", 0):
                doc_id, canonical, _, _ = ingest_document(synthetic_pdf, store=tmp_store)

        units = [o for o in canonical if isinstance(o, Unit)]
        vcc_max = next((u for u in units if u.label == "VCC max"), None)
        assert vcc_max is not None
        assert vcc_max.value == 5.5 or str(vcc_max.value) == "5.5"
        assert vcc_max.unit_of_measure == "V"
        assert vcc_max.doc_id == doc_id
        assert vcc_max.page == 0
        assert vcc_max.origin is not None
        assert vcc_max.origin.x == pytest.approx(0.15)
        assert vcc_max.origin.y == pytest.approx(0.19)

    @patch("akili.ingest.pipeline.classify_page", return_value="other")
    @patch("akili.ingest.pipeline.get_extraction_hint", return_value="")
    @patch("akili.ingest.gemini_extract.genai")
    def test_ingest_with_empty_extraction(
        self, mock_genai, mock_hint, mock_classify, synthetic_pdf, tmp_store
    ):
        """When Gemini returns empty extraction, pipeline succeeds with no canonical objects."""
        mock_model = MagicMock()
        mock_model.generate_content.return_value = _make_mock_gemini_response(
            {"units": [], "bijections": [], "grids": []}
        )
        mock_genai.GenerativeModel.return_value = mock_model

        import os
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            with patch("akili.config.GEMINI_PAGE_DELAY", 0):
                doc_id, canonical, total_pages, pages_failed = ingest_document(
                    synthetic_pdf, store=tmp_store
                )

        assert total_pages == 1
        assert pages_failed == 0
        assert len(canonical) == 0

    @patch("akili.ingest.pipeline.classify_page", return_value="other")
    @patch("akili.ingest.pipeline.get_extraction_hint", return_value="")
    @patch("akili.ingest.gemini_extract.genai")
    def test_ingest_progress_callback(
        self, mock_genai, mock_hint, mock_classify, synthetic_pdf, tmp_store
    ):
        mock_model = MagicMock()
        mock_model.generate_content.return_value = _make_mock_gemini_response(
            MOCK_EXTRACTION_RESPONSE
        )
        mock_genai.GenerativeModel.return_value = mock_model

        progress_events: list[dict] = []

        import os
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            with patch("akili.config.GEMINI_PAGE_DELAY", 0):
                ingest_document(
                    synthetic_pdf,
                    store=tmp_store,
                    progress_callback=progress_events.append,
                )

        phases = [e["phase"] for e in progress_events]
        assert "rendering" in phases
        assert "rendering_done" in phases
        assert "extracting" in phases
        assert "canonicalizing" in phases
        assert "storing" in phases
        assert "done" in phases

    def test_ingest_nonexistent_pdf_raises(self, tmp_store):
        with pytest.raises(FileNotFoundError):
            ingest_document(Path("/nonexistent/path.pdf"), store=tmp_store)

    @patch("akili.ingest.pipeline.classify_page", return_value="other")
    @patch("akili.ingest.pipeline.get_extraction_hint", return_value="")
    @patch("akili.ingest.gemini_extract.genai")
    def test_ingest_gemini_failure_counts_as_failed_page(
        self, mock_genai, mock_hint, mock_classify, synthetic_pdf, tmp_store
    ):
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = RuntimeError("Gemini API error")
        mock_genai.GenerativeModel.return_value = mock_model

        import os
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            with patch("akili.config.GEMINI_PAGE_DELAY", 0):
                with patch("akili.config.GEMINI_429_COOLDOWN", 0):
                    doc_id, canonical, total_pages, pages_failed = ingest_document(
                        synthetic_pdf, store=tmp_store
                    )

        assert total_pages == 1
        assert pages_failed == 1
        assert len(canonical) == 0
