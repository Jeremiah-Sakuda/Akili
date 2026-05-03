"""API tests using FastAPI TestClient.

Covers health, status, request validation, document operations, and query flow.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from akili.api.app import app

client = TestClient(app)


class TestHealthAndStatus:
    def test_health(self):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "auth_required" in data  # A7: health includes auth flag

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


class TestDocIdValidation:
    """Tests for strict UUID doc_id validation (A4)."""

    def test_validate_doc_id_accepts_valid_uuid4(self):
        """Valid UUID4 should be accepted."""
        # Use a valid UUID4 format
        r = client.get("/documents/550e8400-e29b-41d4-a716-446655440000/canonical")
        # Should return 200 (doc doesn't exist but ID is valid)
        assert r.status_code == 200

    def test_validate_doc_id_rejects_non_uuid(self):
        """Non-UUID strings with special chars should be rejected."""
        # Path with spaces should be rejected
        r = client.get("/documents/doc%20id/canonical")
        assert r.status_code == 400

        # Path with @ should be rejected
        r = client.get("/documents/doc%40id/canonical")
        assert r.status_code == 400

    def test_validate_doc_id_allows_legacy_alphanumeric(self):
        """Legacy alphanumeric doc_ids should still work (with warning)."""
        # Legacy format: alphanumeric with dashes/underscores
        r = client.get("/documents/legacy-doc-id-12345/canonical")
        assert r.status_code == 200

    def test_validate_doc_id_rejects_empty(self):
        """Empty doc_id should be rejected."""
        r = client.get("/documents//canonical")
        assert r.status_code in (400, 404, 307)  # 404 or redirect for empty path

    def test_validate_doc_id_rejects_special_chars(self):
        """Special characters should be rejected."""
        r = client.get("/documents/doc@id/canonical")
        assert r.status_code == 400

        r = client.get("/documents/doc%20id/canonical")
        assert r.status_code == 400


class TestQueryFlow:
    """Test the query endpoint with known data via the store."""

    @patch("akili.api.routers.query.get_usage_store")
    def test_query_nonexistent_doc_returns_refuse(self, mock_usage):
        mock_usage.return_value.check_limit.return_value = (True, 0, 100)
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

    @patch("akili.api.routers.query.get_usage_store")
    def test_query_response_has_formatting_source(self, mock_usage):
        mock_usage.return_value.check_limit.return_value = (True, 0, 100)
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


class TestFailClosedAuth:
    """A7: Tests for fail-closed auth in production-like environments."""

    def test_health_includes_auth_required_flag(self):
        """Health endpoint should include auth_required flag for deploy verification."""
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "auth_required" in data
        assert isinstance(data["auth_required"], bool)

    @patch.dict(
        "os.environ",
        {"DATABASE_URL": "postgresql://test", "AKILI_REQUIRE_AUTH": "0"},
        clear=False,
    )
    @patch("akili.api.auth._auth_active", None)  # Reset cached auth state
    @patch("akili.config.ALLOW_OPEN_PROD", False)
    def test_prod_env_without_auth_fails_startup(self):
        """Production environment without auth should fail startup unless explicitly allowed."""
        import asyncio

        import pytest

        from akili.api.app import AuthDisabledInProductionError, lifespan
        from fastapi import FastAPI

        test_app = FastAPI()

        async def run_lifespan():
            async with lifespan(test_app):
                pass

        with pytest.raises(AuthDisabledInProductionError):
            asyncio.run(run_lifespan())

    @patch.dict(
        "os.environ",
        {
            "DATABASE_URL": "postgresql://test",
            "AKILI_REQUIRE_AUTH": "0",
            "AKILI_ALLOW_OPEN_PROD": "1",
        },
        clear=False,
    )
    @patch("akili.api.auth._auth_active", None)  # Reset cached auth state
    @patch("akili.config.ALLOW_OPEN_PROD", True)
    def test_prod_env_with_allow_open_prod_starts(self):
        """Production environment without auth should start when ALLOW_OPEN_PROD=1."""
        import asyncio

        from akili.api.app import lifespan
        from fastapi import FastAPI

        test_app = FastAPI()

        async def run_lifespan():
            async with lifespan(test_app):
                pass

        # Should not raise - explicit override allows open access
        asyncio.run(run_lifespan())
