"""
Sharing and permalink endpoints (FR-SHARE-1, FR-SHARE-2, FR-SHARE-3).

Allows creating and accessing shareable links to verified answers.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from akili.api.auth import get_current_user
from akili.api.deps import get_store, validate_doc_id

logger = logging.getLogger(__name__)

router = APIRouter(tags=["share"])


class ShareRequest(BaseModel):
    """Request to create a shareable link."""

    doc_id: str
    question: str
    answer: str
    status: str = "VERIFIED"
    confidence: float | None = None
    proof_data: dict | None = None
    source_page: int | None = None


@router.post("/share")
async def create_share_link(
    req: ShareRequest,
    user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
    """
    Create a permalink for a verified answer.

    Returns a unique URL that can be shared publicly.
    """
    validate_doc_id(req.doc_id)
    store = get_store()

    # Generate unique question ID from content hash
    content = f"{req.doc_id}:{req.question}:{req.answer}"
    question_id = hashlib.sha256(content.encode()).hexdigest()[:12]

    # Check if store supports sharing (PostgresStore)
    if not hasattr(store, "store_shared_answer"):
        raise HTTPException(
            status_code=501,
            detail="Sharing not supported with current storage backend",
        )

    store.store_shared_answer(
        question_id=question_id,
        doc_id=req.doc_id,
        question=req.question,
        answer=req.answer,
        status=req.status,
        confidence=req.confidence,
        proof_data=req.proof_data,
        source_page=req.source_page,
    )

    # Generate permalink URL
    # In production, this would be the full URL
    permalink = f"/q/{question_id}"

    logger.info(f"Created share link: {question_id} for doc {req.doc_id}")

    return JSONResponse(content={
        "question_id": question_id,
        "permalink": permalink,
        "url": f"https://akili.app/q/{question_id}",
    })


@router.get("/q/{question_id}")
async def get_shared_answer(question_id: str) -> JSONResponse:
    """
    Get a shared answer by question ID.

    This is a public endpoint - no authentication required.
    """
    store = get_store()

    if not hasattr(store, "get_shared_answer"):
        raise HTTPException(
            status_code=501,
            detail="Sharing not supported with current storage backend",
        )

    answer = store.get_shared_answer(question_id)
    if not answer:
        raise HTTPException(
            status_code=404,
            detail="Shared answer not found",
        )

    return JSONResponse(content={
        "question_id": answer["question_id"],
        "question": answer["question"],
        "answer": answer["answer"],
        "status": answer["status"],
        "confidence": answer["confidence"],
        "proof_data": answer["proof_data"],
        "source_page": answer["source_page"],
        "created_at": answer["created_at"],
    })


@router.get("/share/preview/{question_id}")
async def preview_share(question_id: str) -> JSONResponse:
    """
    Get Open Graph metadata for a shared answer.

    Used for social media preview cards.
    """
    store = get_store()

    if not hasattr(store, "get_shared_answer"):
        raise HTTPException(
            status_code=501,
            detail="Sharing not supported with current storage backend",
        )

    answer = store.get_shared_answer(question_id)
    if not answer:
        raise HTTPException(
            status_code=404,
            detail="Shared answer not found",
        )

    # Truncate for preview
    question_preview = answer["question"][:100]
    answer_preview = answer["answer"][:200]

    return JSONResponse(content={
        "title": f"AKILI: {question_preview}",
        "description": answer_preview,
        "url": f"https://akili.app/q/{question_id}",
        "image": "https://akili.app/og-image.png",
        "status": answer["status"],
    })
