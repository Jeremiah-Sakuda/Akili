"""Tests for audit trail export (C3)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from akili.api.app import app

client = TestClient(app)


class TestAuditExport:
    """Tests for GET /documents/{doc_id}/audit endpoint."""

    @patch("akili.api.routers.audit.get_store")
    def test_json_export_returns_structure(self, mock_get_store):
        """JSON export should include export_info, audit_trail, and signature."""
        mock_store = MagicMock()
        mock_store.get_audit_log.return_value = [
            {
                "id": 1,
                "doc_id": "test-doc-id",
                "action": "store_canonical",
                "actor": "system",
                "details": {"units": 5},
                "created_at": "2026-01-01T00:00:00",
            }
        ]
        mock_store.list_documents.return_value = []
        mock_get_store.return_value = mock_store

        r = client.get("/documents/test-doc-id/audit?format=json")
        assert r.status_code == 200

        data = r.json()
        assert "export_info" in data
        assert "audit_trail" in data
        assert "signature" in data
        assert data["export_info"]["doc_id"] == "test-doc-id"
        assert data["export_info"]["format"] == "json"
        assert len(data["audit_trail"]) == 1

    @patch("akili.api.routers.audit.get_store")
    def test_csv_export_returns_csv(self, mock_get_store):
        """CSV export should return valid CSV content."""
        mock_store = MagicMock()
        mock_store.get_audit_log.return_value = [
            {
                "id": 1,
                "doc_id": "test-doc-id",
                "action": "store_canonical",
                "actor": "system",
                "details": {"units": 5},
                "created_at": "2026-01-01T00:00:00",
            }
        ]
        mock_store.list_documents.return_value = []
        mock_get_store.return_value = mock_store

        r = client.get("/documents/test-doc-id/audit?format=csv")
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        assert "attachment" in r.headers["content-disposition"]

        content = r.text
        assert "id,doc_id,action,actor,details,timestamp" in content
        assert "store_canonical" in content
        assert "HMAC-SHA256" in content

    @patch("akili.api.routers.audit.get_store")
    def test_empty_audit_log(self, mock_get_store):
        """Empty audit log should still return valid export."""
        mock_store = MagicMock()
        mock_store.get_audit_log.return_value = []
        mock_store.list_documents.return_value = []
        mock_get_store.return_value = mock_store

        r = client.get("/documents/test-doc-id/audit?format=json")
        assert r.status_code == 200

        data = r.json()
        assert data["export_info"]["entry_count"] == 0
        assert data["audit_trail"] == []

    @patch("akili.api.routers.audit.get_store")
    def test_limit_parameter(self, mock_get_store):
        """Limit parameter should be passed to store."""
        mock_store = MagicMock()
        mock_store.get_audit_log.return_value = []
        mock_store.list_documents.return_value = []
        mock_get_store.return_value = mock_store

        r = client.get("/documents/test-doc-id/audit?format=json&limit=50")
        assert r.status_code == 200

        mock_store.get_audit_log.assert_called_once_with(doc_id="test-doc-id", limit=50)

    def test_invalid_doc_id_rejected(self):
        """Invalid doc_id should return 400."""
        r = client.get("/documents/invalid%20doc/audit?format=json")
        assert r.status_code == 400

    def test_invalid_format_rejected(self):
        """Invalid format should return 422."""
        r = client.get("/documents/test-doc-id/audit?format=xml")
        assert r.status_code == 422


class TestAuditSignature:
    """Tests for HMAC signature verification."""

    @patch("akili.api.routers.audit.AUDIT_SIGNING_KEY", b"test-key")
    def test_verify_valid_signature(self):
        """Valid signature should verify successfully."""
        import base64
        import hashlib
        import hmac

        data = b"test data"
        signature = hmac.new(b"test-key", data, hashlib.sha256).hexdigest()
        data_b64 = base64.b64encode(data).decode()

        r = client.get(f"/audit/verify?signature={signature}&data={data_b64}")
        assert r.status_code == 200
        assert r.json()["valid"] is True

    @patch("akili.api.routers.audit.AUDIT_SIGNING_KEY", b"test-key")
    def test_verify_invalid_signature(self):
        """Invalid signature should fail verification."""
        import base64

        data = b"test data"
        data_b64 = base64.b64encode(data).decode()

        r = client.get(f"/audit/verify?signature=invalid-signature&data={data_b64}")
        assert r.status_code == 200
        assert r.json()["valid"] is False

    @patch("akili.api.routers.audit.AUDIT_SIGNING_KEY", b"")
    def test_verify_without_key_returns_501(self):
        """Verification without signing key should return 501."""
        import base64

        data_b64 = base64.b64encode(b"test").decode()

        r = client.get(f"/audit/verify?signature=abc&data={data_b64}")
        assert r.status_code == 501

    @patch("akili.api.routers.audit.AUDIT_SIGNING_KEY", b"test-key")
    def test_verify_invalid_base64(self):
        """Invalid base64 should return 400."""
        r = client.get("/audit/verify?signature=abc&data=not-valid-base64!!!")
        assert r.status_code == 400
