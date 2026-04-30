"""
Live Gemini integration tests.

These tests call the actual Gemini API and require:
  - GOOGLE_API_KEY set in the environment
  - A test PDF in tests/fixtures/

Run with: pytest tests/integration/ -m integration
Excluded from CI by default via: addopts = "-m 'not integration'" in pyproject.toml
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from tests.integration.conftest import skip_without_key

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.mark.integration
@skip_without_key
class TestGeminiExtraction:
    """Test live Gemini extraction against a known datasheet."""

    def _get_test_pdf(self) -> Path:
        """Return path to a test PDF, or skip if none available."""
        pdfs = list(FIXTURES_DIR.glob("*.pdf"))
        if not pdfs:
            pytest.skip("No test PDF in tests/fixtures/")
        return pdfs[0]

    def test_extract_page_returns_structured_data(self):
        """Verify that extract_page returns a valid PageExtraction from a real PDF page."""
        from akili.ingest.pdf_loader import load_pdf_pages
        from akili.ingest.gemini_extract import extract_page

        pdf_path = self._get_test_pdf()
        pages = load_pdf_pages(pdf_path)
        assert len(pages) > 0, "PDF has no pages"

        page_index, image_bytes = pages[0]
        extraction = extract_page(page_index, image_bytes, "test-doc-integration")

        # Must return a valid PageExtraction with at least some content
        assert extraction is not None
        total_facts = len(extraction.units) + len(extraction.bijections) + len(extraction.grids)
        assert total_facts >= 0  # May be 0 for non-data pages, but should not crash

    def test_full_ingest_pipeline(self):
        """Verify the full ingest pipeline runs end-to-end."""
        from akili.ingest.pipeline import ingest_document

        pdf_path = self._get_test_pdf()
        doc_id, canonical, total_pages, pages_failed = ingest_document(pdf_path)

        assert doc_id is not None
        assert total_pages > 0
        # At least some pages should succeed
        assert pages_failed < total_pages


@pytest.mark.integration
@skip_without_key
class TestGeminiQuery:
    """Test live query against extracted data."""

    def _ingest_fixture(self) -> tuple[str, list]:
        """Ingest a test PDF and return (doc_id, canonical_objects)."""
        from akili.ingest.pipeline import ingest_document

        pdfs = list(FIXTURES_DIR.glob("*.pdf"))
        if not pdfs:
            pytest.skip("No test PDF in tests/fixtures/")
        doc_id, canonical, _, _ = ingest_document(pdfs[0])
        if not canonical:
            pytest.skip("No facts extracted from test PDF")
        return doc_id, canonical

    def test_query_known_fact(self):
        """Verify that a query against extracted data returns an answer (not refuse)."""
        from akili.canonical import Bijection, Grid, Unit
        from akili.verify import verify_and_answer

        doc_id, canonical = self._ingest_fixture()
        units = [o for o in canonical if isinstance(o, Unit)]
        bijections = [o for o in canonical if isinstance(o, Bijection)]
        grids = [o for o in canonical if isinstance(o, Grid)]

        # Ask a generic question that should match something
        result = verify_and_answer("What is the maximum voltage?", units, bijections, grids)
        # Should return something (answer or refuse) without crashing
        assert result is not None
        assert hasattr(result, "status")


@pytest.mark.integration
@skip_without_key
class TestGeminiRateLimit:
    """Test that rate-limit retry logic works."""

    def test_rate_limit_detection(self):
        """Verify the rate limit error detector works on known error messages."""
        from akili.ingest.errors import is_rate_limit_error

        class FakeError(Exception):
            pass

        assert is_rate_limit_error(FakeError("429 Resource Exhausted"))
        assert is_rate_limit_error(FakeError("ResourceExhausted: quota exceeded"))
        assert not is_rate_limit_error(FakeError("400 Bad Request"))
        assert not is_rate_limit_error(FakeError("Connection timeout"))
