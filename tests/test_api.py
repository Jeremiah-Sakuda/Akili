"""API tests using FastAPI TestClient.

Covers health, status, request validation, document operations, and query flow.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from akili.api.app import app

client = TestClient(app)


class TestHealthAndStatus:
    def test_health(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_status(self):
        r = client.get("/status")
        assert r.status_code == 200
        data = r.json()
        assert "ok" in data
        assert "GOOGLE_API_KEY_set" in data
        assert "AKILI_DB_PATH" in data


class TestQueryValidation:
    def test_query_missing_body(self):
        r = client.post("/query")
        assert r.status_code == 422

    def test_query_missing_question(self):
        r = client.post(
            "/query",
            json={"doc_id": "doc1"},
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 422

    def test_query_missing_doc_id(self):
        r = client.post(
            "/query",
            json={"question": "What is pin 5?"},
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 422


class TestDocumentValidation:
    def test_invalid_doc_id_canonical(self):
        r = client.get("/documents/invalid%20id/canonical")
        assert r.status_code == 400
        assert "Invalid doc_id" in (r.json().get("detail") or "")

    def test_invalid_doc_id_file(self):
        r = client.get("/documents/invalid%20id/file")
        assert r.status_code == 400

    def test_documents_list(self):
        r = client.get("/documents")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict) or isinstance(data, list)
        if isinstance(data, dict):
            assert "documents" in data

    def test_nonexistent_doc_canonical_returns_empty(self):
        r = client.get("/documents/nonexistent-doc-id-12345/canonical")
        assert r.status_code == 200
        data = r.json()
        assert "units" in data
        assert "bijections" in data
        assert "grids" in data

    def test_nonexistent_doc_file_returns_404(self):
        r = client.get("/documents/nonexistent-doc-id-12345/file")
        assert r.status_code == 404


class TestQueryFlow:
    """Test the query endpoint with known data via the store."""

    def test_query_nonexistent_doc_returns_refuse(self):
        r = client.post(
            "/query",
            json={
                "doc_id": "no-such-doc-99999",
                "question": "What is pin 5?",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "refuse"
        assert "formatting_source" in data

    def test_query_response_has_formatting_source(self):
        r = client.post(
            "/query",
            json={
                "doc_id": "no-such-doc-99999",
                "question": "What is the maximum voltage?",
                "include_formatted_answer": False,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data.get("formatting_source") == "verified_raw"


class TestIngestValidation:
    def test_ingest_no_file(self):
        r = client.post("/ingest")
        assert r.status_code == 422

    def test_ingest_non_pdf(self):
        r = client.post(
            "/ingest",
            files={"file": ("test.txt", b"not a pdf", "text/plain")},
        )
        assert r.status_code == 400
