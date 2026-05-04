"""
Project workspace endpoints (D1).

Allows users to organize documents into projects for multi-document workflows.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from akili.api.auth import get_current_user, is_auth_required
from akili.api.deps import get_store, require_doc_access, validate_doc_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    """Request to create a new project."""

    name: str = Field(..., min_length=1, max_length=200, description="Project name")


class AddDocumentRequest(BaseModel):
    """Request to add a document to a project."""

    doc_id: str = Field(..., description="Document ID to add")


def _require_project_access(project_id: str, user: dict | None) -> None:
    """Verify user has access to project. Raises 403 if denied."""
    if not is_auth_required():
        return

    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    store = get_store()
    owner = store.get_project_owner(project_id)
    if owner and owner != user.get("uid"):
        raise HTTPException(status_code=403, detail="Not authorized to access this project")


@router.post("")
async def create_project(
    req: CreateProjectRequest,
    user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
    """
    Create a new project workspace.

    Returns the created project with its generated ID.
    """
    store = get_store()
    project_id = str(uuid.uuid4())
    owner_uid = user.get("uid") if user else None

    project = store.create_project(project_id, req.name, owner_uid)
    logger.info(f"Created project {project_id}: {req.name}")

    return JSONResponse(content=project, status_code=201)


@router.get("")
async def list_projects(
    user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
    """
    List all projects for the current user.

    When auth is enabled, returns only projects owned by the user.
    When auth is disabled, returns all projects.
    """
    store = get_store()
    owner_uid = user.get("uid") if user and is_auth_required() else None
    projects = store.list_projects(owner_uid)
    return JSONResponse(content={"projects": projects})


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
    """
    Get project details by ID.
    """
    _require_project_access(project_id, user)
    store = get_store()
    project = store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return JSONResponse(content=project)


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
    """
    Delete a project.

    Note: This removes the project and document associations,
    but does not delete the documents themselves.
    """
    _require_project_access(project_id, user)
    store = get_store()

    project = store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    store.delete_project(project_id)
    logger.info(f"Deleted project {project_id}")

    return JSONResponse(content={"status": "deleted", "project_id": project_id})


@router.get("/{project_id}/documents")
async def get_project_documents(
    project_id: str,
    user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
    """
    List all documents in a project.
    """
    _require_project_access(project_id, user)
    store = get_store()

    project = store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    documents = store.get_project_documents(project_id)
    return JSONResponse(content={"project_id": project_id, "documents": documents})


@router.post("/{project_id}/documents")
async def add_document_to_project(
    project_id: str,
    req: AddDocumentRequest,
    user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
    """
    Add a document to a project.

    The user must have access to both the project and the document.
    """
    _require_project_access(project_id, user)
    validate_doc_id(req.doc_id)
    require_doc_access(req.doc_id, user)

    store = get_store()

    project = store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    store.add_document_to_project(project_id, req.doc_id)
    logger.info(f"Added document {req.doc_id} to project {project_id}")

    return JSONResponse(
        content={"status": "added", "project_id": project_id, "doc_id": req.doc_id},
        status_code=201,
    )


@router.delete("/{project_id}/documents/{doc_id}")
async def remove_document_from_project(
    project_id: str,
    doc_id: str,
    user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
    """
    Remove a document from a project.

    Note: This only removes the association; the document itself is not deleted.
    """
    _require_project_access(project_id, user)
    validate_doc_id(doc_id)

    store = get_store()

    project = store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    store.remove_document_from_project(project_id, doc_id)
    logger.info(f"Removed document {doc_id} from project {project_id}")

    return JSONResponse(content={"status": "removed", "project_id": project_id, "doc_id": doc_id})
