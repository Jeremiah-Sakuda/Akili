"""
Document management endpoints: list, delete, get file, get canonical.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, JSONResponse

from akili.api.auth import get_current_user, is_auth_required
from akili.api.deps import docs_dir, get_store, validate_doc_id
from akili.canonical import Bijection, Grid, Unit

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])


@router.get("/documents")
async def list_documents(
    _user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
    """List ingested documents with canonical object counts."""
    store = get_store()
    docs = store.list_documents()
    return JSONResponse(content={"documents": docs})


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    _user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
    """Delete an ingested document (canonical store and PDF file)."""
    validate_doc_id(doc_id)
    store = get_store()
    store.delete_document(doc_id)
    try:
        dest = docs_dir() / f"{doc_id}.pdf"
        if dest.is_file():
            dest.unlink()
    except OSError:
        logger.warning("Failed to delete PDF file for doc_id=%s", doc_id)
    return JSONResponse(content={"doc_id": doc_id, "deleted": True})


from fastapi import HTTPException


@router.get("/documents/{doc_id}/file")
async def get_document_file(
    doc_id: str,
    _user: dict[str, Any] | None = Depends(get_current_user),
) -> FileResponse:
    """Return the ingested PDF file for a document (for viewer / Show on document)."""
    validate_doc_id(doc_id)
    if _user is not None:
        if is_auth_required():
            store = get_store()
            owner = store.get_document_owner(doc_id)
            if owner and owner != _user.get("uid"):
                raise HTTPException(status_code=403, detail="Not authorized to access this document")
    dest = docs_dir() / f"{doc_id}.pdf"
    if not dest.is_file():
        raise HTTPException(
            status_code=404,
            detail="Document file not found (ingested before PDF storage was added)",
        )
    return FileResponse(dest, media_type="application/pdf", filename=f"{doc_id}.pdf")


@router.get("/documents/{doc_id}/canonical")
async def get_canonical(
    doc_id: str,
    _user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
    """Return canonical objects (units, bijections, grids) for a document."""
    validate_doc_id(doc_id)
    store = get_store()
    units = store.get_units_by_doc(doc_id)
    bijections = store.get_bijections_by_doc(doc_id)
    grids = store.get_grids_by_doc(doc_id)

    def ser_unit(u: object) -> dict:
        return {
            "type": "unit",
            "id": getattr(u, "id", None),
            "label": getattr(u, "label", None),
            "value": getattr(u, "value", None),
            "unit_of_measure": getattr(u, "unit_of_measure", None),
            "context": u.context,
            "origin": {
                "x": getattr(getattr(u, "origin", None), "x", 0),
                "y": getattr(getattr(u, "origin", None), "y", 0),
            },
            "page": getattr(u, "page", 0),
        }

    def ser_bijection(b: object) -> dict:
        return {
            "type": "bijection",
            "id": getattr(b, "id", None),
            "mapping": getattr(b, "mapping", {}),
            "origin": {
                "x": getattr(getattr(b, "origin", None), "x", 0),
                "y": getattr(getattr(b, "origin", None), "y", 0),
            },
            "page": getattr(b, "page", 0),
        }

    def ser_grid(g: object) -> dict:
        return {
            "type": "grid",
            "id": getattr(g, "id", None),
            "rows": getattr(g, "rows", 0),
            "cols": getattr(g, "cols", 0),
            "cells_count": len(getattr(g, "cells", [])),
            "origin": {
                "x": getattr(getattr(g, "origin", None), "x", 0),
                "y": getattr(getattr(g, "origin", None), "y", 0),
            },
            "page": getattr(g, "page", 0),
        }

    return JSONResponse(
        content={
            "doc_id": doc_id,
            "units": [ser_unit(u) for u in units],
            "bijections": [ser_bijection(b) for b in bijections],
            "grids": [ser_grid(g) for g in grids],
        }
    )
