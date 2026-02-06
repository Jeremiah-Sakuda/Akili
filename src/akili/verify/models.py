"""
Verification result types: AnswerWithProof or Refuse.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProofPointBBox(BaseModel):
    """Normalized 0-1 bounding box (x1,y1 = one corner, x2,y2 = opposite). Y increases down (top-left origin)."""

    x1: float = Field(..., description="Left")
    y1: float = Field(..., description="Top")
    x2: float = Field(..., description="Right")
    y2: float = Field(..., description="Bottom")


class ProofPoint(BaseModel):
    """Single coordinate proof: (x, y), page, optional bbox, and optional source id."""

    x: float = Field(..., description="x coordinate (normalized 0-1)")
    y: float = Field(..., description="y coordinate (normalized 0-1, top-left origin)")
    page: int = Field(0, description="Page number (0-based) for overlay")
    bbox: ProofPointBBox | None = Field(None, description="Optional bounding box when fact has region")
    source_id: str | None = Field(None, description="Canonical object id (unit, bijection, grid)")
    source_type: str | None = Field(None, description="unit | bijection | grid")


class AnswerWithProof(BaseModel):
    """Answer that is provable from canonical facts; includes coordinate proof."""

    status: str = Field(default="answer", description="Always 'answer'")
    answer: str = Field(..., description="The proven answer")
    proof: list[ProofPoint] = Field(
        default_factory=list, description="(x,y) coordinates that support the answer"
    )
    source_id: str | None = Field(None, description="Canonical object id")
    source_type: str | None = Field(None, description="unit | bijection | grid")


class Refuse(BaseModel):
    """Deterministic refusal when the answer cannot be proven from canonical structure."""

    status: str = Field(default="refuse", description="Always 'refuse'")
    reason: str = Field(..., description="Short reason for refusal")
