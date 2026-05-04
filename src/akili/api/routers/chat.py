"""
Persistent chat endpoints (D2).

Stores and retrieves chat history per document.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from akili.api.auth import get_current_user
from akili.api.deps import get_store, require_doc_access, validate_doc_id

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


class ChatMessageRequest(BaseModel):
    """Request to add a chat message."""

    text: str = Field(..., min_length=1, max_length=10000, description="Message text")
    role: str = Field("user", pattern="^(user|assistant)$", description="Message role")
    response_json: dict | None = Field(None, description="Response data for assistant messages")


@router.get("/documents/{doc_id}/chat")
async def get_chat_history(
    doc_id: str,
    project_id: str | None = Query(None, description="Optional project context"),
    limit: int = Query(100, ge=1, le=1000, description="Max messages to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
    """
    Get chat history for a document.

    Messages are returned in chronological order (oldest first).
    Use project_id to get chat history within a specific project context.
    """
    validate_doc_id(doc_id)
    require_doc_access(doc_id, user)

    store = get_store()
    messages = store.get_chat_messages(
        doc_id=doc_id,
        project_id=project_id,
        limit=limit,
        offset=offset,
    )

    return JSONResponse(
        content={
            "doc_id": doc_id,
            "project_id": project_id,
            "messages": messages,
            "count": len(messages),
        }
    )


@router.post("/documents/{doc_id}/chat")
async def add_chat_message(
    doc_id: str,
    req: ChatMessageRequest,
    project_id: str | None = Query(None, description="Optional project context"),
    user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
    """
    Add a message to chat history.

    Both user messages and assistant responses are stored.
    For assistant messages, include the response_json with query results.
    """
    validate_doc_id(doc_id)
    require_doc_access(doc_id, user)

    store = get_store()
    user_id = user.get("uid") if user else None

    response_json_str = json.dumps(req.response_json) if req.response_json else None

    message_id = store.add_chat_message(
        doc_id=doc_id,
        role=req.role,
        text=req.text,
        user_id=user_id,
        project_id=project_id,
        response_json=response_json_str,
    )

    logger.debug(f"Added chat message {message_id} to doc {doc_id}")

    return JSONResponse(
        content={
            "id": message_id,
            "doc_id": doc_id,
            "project_id": project_id,
            "role": req.role,
            "text": req.text,
        },
        status_code=201,
    )


@router.delete("/documents/{doc_id}/chat")
async def clear_chat_history(
    doc_id: str,
    project_id: str | None = Query(None, description="Optional project context"),
    user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
    """
    Clear chat history for a document.

    If project_id is specified, only clears messages within that project context.
    """
    validate_doc_id(doc_id)
    require_doc_access(doc_id, user)

    store = get_store()
    deleted_count = store.delete_chat_messages(doc_id, project_id)

    logger.info(f"Cleared {deleted_count} chat messages for doc {doc_id}")

    return JSONResponse(
        content={
            "status": "cleared",
            "doc_id": doc_id,
            "project_id": project_id,
            "deleted_count": deleted_count,
        }
    )
