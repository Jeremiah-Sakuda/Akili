"""
Human-in-the-Loop corrections and pattern analysis endpoints.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from akili.api.auth import get_current_user
from akili.api.deps import get_correction_store, validate_doc_id
from akili.learn.pattern_analyzer import PatternAnalyzer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["corrections"])

CanonicalType = Literal["unit", "bijection", "grid", "range", "conditional_unit"]
CorrectionAction = Literal["confirm", "correct"]


class CorrectionRequest(BaseModel):
    doc_id: str
    canonical_id: str
    canonical_type: CanonicalType
    action: CorrectionAction
    original_value: str = Field(..., max_length=10000)
    corrected_value: str | None = Field(None, max_length=10000)
    corrected_by: str | None = Field(None, max_length=500)
    notes: str | None = Field(None, max_length=5000)


from fastapi import HTTPException


@router.post("/corrections")
async def submit_correction(
    req: CorrectionRequest,
    user: dict = Depends(get_current_user),
) -> JSONResponse:
    """Submit a human correction or confirmation for a canonical fact."""
    if req.action not in ("confirm", "correct"):
        raise HTTPException(status_code=400, detail="action must be 'confirm' or 'correct'")
    if req.action == "correct" and not req.corrected_value:
        raise HTTPException(status_code=400, detail="corrected_value required for 'correct' action")

    cs = get_correction_store()
    correction_id = cs.add_correction(
        doc_id=req.doc_id,
        canonical_id=req.canonical_id,
        canonical_type=req.canonical_type,
        action=req.action,
        original_value=req.original_value,
        corrected_value=req.corrected_value,
        corrected_by=req.corrected_by or user.get("uid"),
        notes=req.notes,
    )
    return JSONResponse(content={"correction_id": correction_id, "status": "recorded"})


@router.get("/corrections/{doc_id}")
async def get_corrections(
    doc_id: str,
    user: dict = Depends(get_current_user),
) -> JSONResponse:
    """Get all corrections for a document."""
    cs = get_correction_store()
    corrections = cs.get_corrections_by_doc(doc_id)
    return JSONResponse(content={
        "doc_id": doc_id,
        "corrections": [
            {
                "id": c.id,
                "canonical_id": c.canonical_id,
                "canonical_type": c.canonical_type,
                "action": c.action,
                "original_value": c.original_value,
                "corrected_value": c.corrected_value,
                "corrected_by": c.corrected_by,
                "notes": c.notes,
                "created_at": c.created_at,
            }
            for c in corrections
        ],
    })


@router.get("/corrections/stats/{doc_id}")
async def correction_stats(
    doc_id: str,
    user: dict = Depends(get_current_user),
) -> JSONResponse:
    """Get correction statistics for a document."""
    cs = get_correction_store()
    stats = cs.get_correction_stats(doc_id)
    return JSONResponse(content=stats)


# ---------------------------------------------------------------------------
# Pattern Analysis
# ---------------------------------------------------------------------------

@router.get("/patterns")
async def get_patterns(
    _user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
    """Analyze correction patterns across all documents."""
    analyzer = PatternAnalyzer(get_correction_store())
    stats = analyzer.get_pattern_stats()
    return JSONResponse(content=stats)


@router.get("/patterns/{doc_id}")
async def get_doc_patterns(
    doc_id: str,
    _user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
    """Analyze correction patterns for a specific document."""
    validate_doc_id(doc_id)
    analyzer = PatternAnalyzer(get_correction_store())
    patterns = analyzer.analyze_by_doc(doc_id)
    return JSONResponse(content={
        "doc_id": doc_id,
        "patterns": [
            {
                "id": p.pattern_id,
                "description": p.description,
                "category": p.category,
                "occurrences": p.occurrences,
                "auto_correctable": p.auto_correctable,
                "confidence": p.confidence,
            }
            for p in patterns
        ],
    })


class SuggestCorrectionRequest(BaseModel):
    canonical_type: CanonicalType
    original_value: str = Field(..., max_length=10000)


@router.post("/patterns/suggest")
async def suggest_correction(
    req: SuggestCorrectionRequest,
    _user: dict[str, Any] | None = Depends(get_current_user),
) -> JSONResponse:
    """Suggest an auto-correction based on learned patterns."""
    analyzer = PatternAnalyzer(get_correction_store())
    suggestion = analyzer.suggest_correction(req.canonical_type, req.original_value)
    return JSONResponse(content={
        "original_value": req.original_value,
        "suggested_correction": suggestion,
        "has_suggestion": suggestion is not None,
    })
