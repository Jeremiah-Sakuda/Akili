"""
Query and usage endpoints.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from akili import config
from akili.api.auth import get_current_user
from akili.api.deps import get_store, get_usage_store
from akili.ingest.gemini_format import format_answer, format_refusal
from akili.verify import AnswerWithProof, Refuse, verify_and_answer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["query"])

_FORMAT_EXECUTOR: ThreadPoolExecutor | None = None
_FORMAT_TIMEOUT = config.FORMAT_TIMEOUT


def _get_format_executor() -> ThreadPoolExecutor:
    global _FORMAT_EXECUTOR
    if _FORMAT_EXECUTOR is None:
        _FORMAT_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="akili_format")
    return _FORMAT_EXECUTOR


def _proof_to_coordinates(proof: list[Any]) -> str:
    if not proof:
        return "no coordinates"
    parts = []
    for p in proof:
        x = getattr(p, "x", 0)
        y = getattr(p, "y", 0)
        page = getattr(p, "page", 0)
        parts.append(f"page {page} (x={x:.2f}, y={y:.2f})")
    return "; ".join(parts)


class QueryRequest(BaseModel):
    """Request body for POST /query."""
    doc_id: str = Field(..., description="Document id from ingest")
    question: str = Field(..., description="Question to answer from canonical facts", max_length=2000)
    include_formatted_answer: bool = Field(
        False,
        description="If true, request 1-sentence phrasing from Gemini (best-effort).",
    )


@router.post("/query")
async def query(
    request: Request,
    req: QueryRequest,
    _user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
    """
    Submit a question for a document. Returns coordinate-grounded answer + proof, or REFUSE.
    """
    user_id = (_user or {}).get("uid", request.client.host if request.client else "anonymous")
    usage = get_usage_store()
    allowed, used, limit = usage.check_limit(user_id, "query")
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Free tier limit reached: {used}/{limit} queries. Contact us to upgrade.",
        )

    store = get_store()
    units = store.get_units_by_doc(req.doc_id)
    bijections = store.get_bijections_by_doc(req.doc_id)
    grids = store.get_grids_by_doc(req.doc_id)
    result = verify_and_answer(req.question, units, bijections, grids)
    usage.record(user_id, "query")

    if isinstance(result, Refuse):
        content: dict[str, Any] = result.model_dump()
        content["formatting_source"] = "verified_raw"
        if req.include_formatted_answer:
            loop = asyncio.get_event_loop()
            try:
                formatted_reason = await asyncio.wait_for(
                    loop.run_in_executor(
                        _get_format_executor(),
                        lambda: format_refusal(req.question, len(units), len(bijections), len(grids)),
                    ),
                    timeout=_FORMAT_TIMEOUT,
                )
                if formatted_reason and formatted_reason.strip():
                    content["reason"] = formatted_reason.strip()
                    content["formatting_source"] = "gemini_rephrase"
            except (asyncio.TimeoutError, OSError, RuntimeError, ValueError) as exc:
                logger.debug("Refusal formatting failed (non-critical): %s", exc)
        return JSONResponse(content=content)

    content = result.model_dump()
    content["formatting_source"] = "verified_raw"
    if result.confidence:
        content["confidence_tier"] = result.confidence.tier
    if req.include_formatted_answer and isinstance(result, AnswerWithProof):
        coordinates = _proof_to_coordinates(result.proof)
        loop = asyncio.get_event_loop()
        try:
            formatted = await asyncio.wait_for(
                loop.run_in_executor(
                    _get_format_executor(),
                    lambda: format_answer(req.question, result.answer, coordinates),
                ),
                timeout=_FORMAT_TIMEOUT,
            )
            content["formatted_answer"] = formatted
            if formatted:
                content["formatting_source"] = "gemini_rephrase"
        except (asyncio.TimeoutError, OSError, RuntimeError, ValueError) as exc:
            logger.debug("Answer formatting failed (non-critical): %s", exc)
            content["formatted_answer"] = None
    return JSONResponse(content=content)


@router.get("/usage")
async def get_usage(
    request: Request,
    _user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
    """Get usage summary for the current user (free tier limits)."""
    user_id = (_user or {}).get("uid", request.client.host if request.client else "anonymous")
    usage = get_usage_store()
    summary = usage.get_usage_summary(user_id)
    return JSONResponse(content=summary)
