"""
Document comparison endpoint.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from akili.api.auth import get_current_user
from akili.api.deps import get_store, validate_doc_id
from akili.verify.compare import compare_documents, format_comparison_response

router = APIRouter(tags=["compare"])


class CompareRequest(BaseModel):
    doc_ids: list[str] = Field(..., description="2+ document IDs to compare")
    question: str = Field(..., description="What to compare (e.g. 'Compare max voltage')")


@router.post("/compare")
async def compare_docs(
    req: CompareRequest,
    _user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
    """Compare parameters across multiple documents."""
    if len(req.doc_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 doc_ids required")
    store = get_store()
    docs = store.list_documents()
    doc_name_map = {d["doc_id"]: d.get("filename", d["doc_id"]) for d in docs}

    doc_units: dict[str, tuple[str, list]] = {}
    for did in req.doc_ids:
        validate_doc_id(did)
        units = store.get_units_by_doc(did)
        name = doc_name_map.get(did, did)
        doc_units[did] = (name, units)

    results = compare_documents(req.question, doc_units)
    return JSONResponse(content=format_comparison_response(results))
