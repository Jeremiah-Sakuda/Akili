"""Tests for project workspace endpoints (D1)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from akili.api.app import app

client = TestClient(app)


class TestCreateProject:
    """Tests for POST /projects."""

    @patch("akili.api.routers.projects.get_store")
    def test_create_project_success(self, mock_get_store):
        """Creating a project should return 201 with project data."""
        mock_store = MagicMock()
        mock_store.create_project.return_value = {
            "project_id": "test-project-id",
            "name": "My Project",
            "owner_uid": None,
        }
        mock_get_store.return_value = mock_store

        r = client.post("/projects", json={"name": "My Project"})
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "My Project"
        assert "project_id" in data

    def test_create_project_empty_name_fails(self):
        """Empty project name should fail validation."""
        r = client.post("/projects", json={"name": ""})
        assert r.status_code == 422

    def test_create_project_missing_name_fails(self):
        """Missing name should fail validation."""
        r = client.post("/projects", json={})
        assert r.status_code == 422


class TestListProjects:
    """Tests for GET /projects."""

    @patch("akili.api.routers.projects.get_store")
    @patch("akili.api.routers.projects.is_auth_required")
    def test_list_projects_returns_array(self, mock_auth, mock_get_store):
        """List projects should return array of projects."""
        mock_auth.return_value = False
        mock_store = MagicMock()
        mock_store.list_projects.return_value = [
            {
                "project_id": "p1",
                "name": "Project 1",
                "owner_uid": None,
                "created_at": "2026-01-01",
                "doc_count": 2,
            }
        ]
        mock_get_store.return_value = mock_store

        r = client.get("/projects")
        assert r.status_code == 200
        data = r.json()
        assert "projects" in data
        assert len(data["projects"]) == 1


class TestGetProject:
    """Tests for GET /projects/{project_id}."""

    @patch("akili.api.routers.projects.get_store")
    @patch("akili.api.routers.projects.is_auth_required")
    def test_get_project_success(self, mock_auth, mock_get_store):
        """Get project should return project data."""
        mock_auth.return_value = False
        mock_store = MagicMock()
        mock_store.get_project.return_value = {
            "project_id": "p1",
            "name": "Project 1",
            "owner_uid": None,
            "created_at": "2026-01-01",
        }
        mock_get_store.return_value = mock_store

        r = client.get("/projects/p1")
        assert r.status_code == 200
        data = r.json()
        assert data["project_id"] == "p1"

    @patch("akili.api.routers.projects.get_store")
    @patch("akili.api.routers.projects.is_auth_required")
    def test_get_project_not_found(self, mock_auth, mock_get_store):
        """Get non-existent project should return 404."""
        mock_auth.return_value = False
        mock_store = MagicMock()
        mock_store.get_project.return_value = None
        mock_get_store.return_value = mock_store

        r = client.get("/projects/nonexistent")
        assert r.status_code == 404


class TestDeleteProject:
    """Tests for DELETE /projects/{project_id}."""

    @patch("akili.api.routers.projects.get_store")
    @patch("akili.api.routers.projects.is_auth_required")
    def test_delete_project_success(self, mock_auth, mock_get_store):
        """Delete project should return success."""
        mock_auth.return_value = False
        mock_store = MagicMock()
        mock_store.get_project.return_value = {"project_id": "p1", "name": "Test"}
        mock_get_store.return_value = mock_store

        r = client.delete("/projects/p1")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "deleted"
        mock_store.delete_project.assert_called_once_with("p1")


class TestProjectDocuments:
    """Tests for project document management."""

    @patch("akili.api.routers.projects.get_store")
    @patch("akili.api.routers.projects.is_auth_required")
    def test_list_project_documents(self, mock_auth, mock_get_store):
        """List project documents should return document array."""
        mock_auth.return_value = False
        mock_store = MagicMock()
        mock_store.get_project.return_value = {"project_id": "p1", "name": "Test"}
        mock_store.get_project_documents.return_value = [
            {"doc_id": "d1", "filename": "test.pdf"}
        ]
        mock_get_store.return_value = mock_store

        r = client.get("/projects/p1/documents")
        assert r.status_code == 200
        data = r.json()
        assert "documents" in data
        assert len(data["documents"]) == 1

    @patch("akili.api.routers.projects.get_store")
    @patch("akili.api.routers.projects.is_auth_required")
    def test_add_document_to_project(self, mock_auth, mock_get_store):
        """Add document to project should succeed."""
        mock_auth.return_value = False
        mock_store = MagicMock()
        mock_store.get_project.return_value = {"project_id": "p1", "name": "Test"}
        mock_store.get_document_owner.return_value = None
        mock_get_store.return_value = mock_store

        r = client.post("/projects/p1/documents", json={"doc_id": "valid-doc-id-123"})
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "added"
        mock_store.add_document_to_project.assert_called_once()

    @patch("akili.api.routers.projects.get_store")
    @patch("akili.api.routers.projects.is_auth_required")
    def test_remove_document_from_project(self, mock_auth, mock_get_store):
        """Remove document from project should succeed."""
        mock_auth.return_value = False
        mock_store = MagicMock()
        mock_store.get_project.return_value = {"project_id": "p1", "name": "Test"}
        mock_get_store.return_value = mock_store

        r = client.delete("/projects/p1/documents/valid-doc-id-123")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "removed"
        mock_store.remove_document_from_project.assert_called_once()


class TestProjectAuthorization:
    """Tests for project access control."""

    @patch("akili.api.routers.projects.get_store")
    @patch("akili.api.routers.projects.is_auth_required")
    def test_unauthorized_access_denied(self, mock_auth, mock_get_store):
        """Cross-user project access should be denied when auth enabled."""
        mock_auth.return_value = True
        mock_store = MagicMock()
        mock_store.get_project_owner.return_value = "user-a"
        mock_get_store.return_value = mock_store

        # No auth header = no user
        r = client.get("/projects/p1")
        assert r.status_code == 401
