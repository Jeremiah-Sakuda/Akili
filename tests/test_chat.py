"""Tests for persistent chat endpoints (D2)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from akili.api.app import app

client = TestClient(app)


class TestGetChatHistory:
    """Tests for GET /documents/{doc_id}/chat."""

    @patch("akili.api.routers.chat.get_store")
    def test_get_chat_history_returns_messages(self, mock_get_store):
        """Get chat should return message array."""
        mock_store = MagicMock()
        mock_store.get_document_owner.return_value = None
        mock_store.get_chat_messages.return_value = [
            {
                "id": 1,
                "doc_id": "test-doc-id",
                "project_id": None,
                "user_id": None,
                "role": "user",
                "text": "What is the maximum voltage?",
                "response_json": None,
                "created_at": "2026-01-01T00:00:00",
            },
            {
                "id": 2,
                "doc_id": "test-doc-id",
                "project_id": None,
                "user_id": None,
                "role": "assistant",
                "text": "The maximum voltage is 5.5V",
                "response_json": {"status": "VERIFIED"},
                "created_at": "2026-01-01T00:00:01",
            },
        ]
        mock_get_store.return_value = mock_store

        r = client.get("/documents/test-doc-id/chat")
        assert r.status_code == 200

        data = r.json()
        assert "messages" in data
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][1]["role"] == "assistant"

    @patch("akili.api.routers.chat.get_store")
    def test_get_chat_with_project_id(self, mock_get_store):
        """Get chat with project_id should filter by project."""
        mock_store = MagicMock()
        mock_store.get_document_owner.return_value = None
        mock_store.get_chat_messages.return_value = []
        mock_get_store.return_value = mock_store

        r = client.get("/documents/test-doc-id/chat?project_id=p1")
        assert r.status_code == 200

        mock_store.get_chat_messages.assert_called_once_with(
            doc_id="test-doc-id",
            project_id="p1",
            limit=100,
            offset=0,
        )

    @patch("akili.api.routers.chat.get_store")
    def test_get_chat_pagination(self, mock_get_store):
        """Get chat with limit/offset should paginate."""
        mock_store = MagicMock()
        mock_store.get_document_owner.return_value = None
        mock_store.get_chat_messages.return_value = []
        mock_get_store.return_value = mock_store

        r = client.get("/documents/test-doc-id/chat?limit=50&offset=10")
        assert r.status_code == 200

        mock_store.get_chat_messages.assert_called_once_with(
            doc_id="test-doc-id",
            project_id=None,
            limit=50,
            offset=10,
        )


class TestAddChatMessage:
    """Tests for POST /documents/{doc_id}/chat."""

    @patch("akili.api.routers.chat.get_store")
    def test_add_user_message(self, mock_get_store):
        """Adding a user message should succeed."""
        mock_store = MagicMock()
        mock_store.get_document_owner.return_value = None
        mock_store.add_chat_message.return_value = 1
        mock_get_store.return_value = mock_store

        r = client.post(
            "/documents/test-doc-id/chat",
            json={"text": "What is the voltage?", "role": "user"},
        )
        assert r.status_code == 201

        data = r.json()
        assert data["id"] == 1
        assert data["role"] == "user"
        assert data["text"] == "What is the voltage?"

    @patch("akili.api.routers.chat.get_store")
    def test_add_assistant_message_with_response(self, mock_get_store):
        """Adding an assistant message with response_json should succeed."""
        mock_store = MagicMock()
        mock_store.get_document_owner.return_value = None
        mock_store.add_chat_message.return_value = 2
        mock_get_store.return_value = mock_store

        r = client.post(
            "/documents/test-doc-id/chat",
            json={
                "text": "The maximum voltage is 5.5V",
                "role": "assistant",
                "response_json": {"status": "VERIFIED", "confidence": 0.95},
            },
        )
        assert r.status_code == 201

        data = r.json()
        assert data["role"] == "assistant"

    def test_add_message_empty_text_fails(self):
        """Empty message text should fail validation."""
        r = client.post(
            "/documents/test-doc-id/chat",
            json={"text": "", "role": "user"},
        )
        assert r.status_code == 422

    def test_add_message_invalid_role_fails(self):
        """Invalid role should fail validation."""
        r = client.post(
            "/documents/test-doc-id/chat",
            json={"text": "Hello", "role": "system"},
        )
        assert r.status_code == 422


class TestClearChatHistory:
    """Tests for DELETE /documents/{doc_id}/chat."""

    @patch("akili.api.routers.chat.get_store")
    def test_clear_chat_history(self, mock_get_store):
        """Clear chat should delete messages and return count."""
        mock_store = MagicMock()
        mock_store.get_document_owner.return_value = None
        mock_store.delete_chat_messages.return_value = 5
        mock_get_store.return_value = mock_store

        r = client.delete("/documents/test-doc-id/chat")
        assert r.status_code == 200

        data = r.json()
        assert data["status"] == "cleared"
        assert data["deleted_count"] == 5

    @patch("akili.api.routers.chat.get_store")
    def test_clear_chat_with_project_id(self, mock_get_store):
        """Clear chat with project_id should only clear project messages."""
        mock_store = MagicMock()
        mock_store.get_document_owner.return_value = None
        mock_store.delete_chat_messages.return_value = 3
        mock_get_store.return_value = mock_store

        r = client.delete("/documents/test-doc-id/chat?project_id=p1")
        assert r.status_code == 200

        mock_store.delete_chat_messages.assert_called_once_with("test-doc-id", "p1")
