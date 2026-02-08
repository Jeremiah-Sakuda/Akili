"""API tests using FastAPI TestClient. Covers health, status, and request validation."""

from fastapi.testclient import TestClient

from akili.api.app import app

client = TestClient(app)


def test_health():
    """GET /health returns 200 and status ok."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_status():
    """GET /status returns 200 and env info (no auth)."""
    r = client.get("/status")
    assert r.status_code == 200
    data = r.json()
    assert "ok" in data
    assert "GOOGLE_API_KEY_set" in data
    assert "AKILI_DB_PATH" in data


def test_query_missing_body():
    """POST /query with no body returns 422."""
    r = client.post("/query")
    assert r.status_code == 422


def test_query_invalid_payload():
    """POST /query with missing required field returns 422."""
    r = client.post(
        "/query",
        json={"doc_id": "doc1"},
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422


def test_documents_invalid_doc_id_canonical():
    """GET /documents/{doc_id}/canonical with invalid doc_id returns 400."""
    # doc_id with space fails _validate_doc_id (only [a-zA-Z0-9_-] allowed)
    r = client.get("/documents/invalid%20id/canonical")
    assert r.status_code == 400
    assert "Invalid doc_id" in (r.json().get("detail") or "")


def test_documents_invalid_doc_id_file():
    """GET /documents/{doc_id}/file with invalid doc_id returns 400."""
    r = client.get("/documents/invalid%20id/file")
    assert r.status_code == 400
