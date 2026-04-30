"""
Verification result types: AnswerWithProof or Refuse, with confidence scoring.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from akili import config


class ProofPointBBox(BaseModel):
    """Normalized 0-1 bbox (x1,y1 one corner, x2,y2 opposite). Y down, top-left origin."""

    x1: float = Field(..., description="Left")
    y1: float = Field(..., description="Top")
    x2: float = Field(..., description="Right")
    y2: float = Field(..., description="Bottom")


class ProofPoint(BaseModel):
    """Single coordinate proof: (x, y), page, optional bbox, and optional source id."""

    x: float = Field(..., description="x coordinate (normalized 0-1)")
    y: float = Field(..., description="y coordinate (normalized 0-1, top-left origin)")
    page: int = Field(0, description="Page number (0-based) for overlay")
    bbox: ProofPointBBox | None = Field(None, description="Optional bbox when fact has region")
    source_id: str | None = Field(None, description="Canonical object id (unit, bijection, grid)")
    source_type: str | None = Field(None, description="unit | bijection | grid")


# ---------------------------------------------------------------------------
# Confidence scoring (thresholds & weights from centralized config)
# ---------------------------------------------------------------------------


class ConfidenceScore(BaseModel):
    """Three-component confidence score for a verified answer."""

    extraction_agreement: float = Field(
        default=0.5,
        ge=0.0, le=1.0,
        description="How consistent the extraction was (1.0 = consensus, 0.5 = single-pass default)",
    )
    canonical_validation: float = Field(
        default=0.5,
        ge=0.0, le=1.0,
        description="Schema completeness: has bbox, origin, unit_of_measure, label, context",
    )
    verification_strength: float = Field(
        default=0.5,
        ge=0.0, le=1.0,
        description="How directly the proof supports the answer (1.0 = exact structured, 0.4 = keyword-only)",
    )
    overall: float = Field(
        default=0.5,
        ge=0.0, le=1.0,
        description="Weighted average of the three components",
    )

    @staticmethod
    def compute(
        extraction_agreement: float = 0.5,
        canonical_validation: float = 0.5,
        verification_strength: float = 0.5,
    ) -> ConfidenceScore:
        overall = (
            config.W_EXTRACTION * extraction_agreement
            + config.W_CANONICAL * canonical_validation
            + config.W_VERIFICATION * verification_strength
        )
        return ConfidenceScore(
            extraction_agreement=extraction_agreement,
            canonical_validation=canonical_validation,
            verification_strength=verification_strength,
            overall=round(overall, 4),
        )

    @property
    def tier(self) -> str:
        """Return 'verified', 'review', or 'refused' based on configurable thresholds."""
        if self.overall >= config.VERIFY_THRESHOLD:
            return "verified"
        if self.overall >= config.REVIEW_THRESHOLD:
            return "review"
        return "refused"


def compute_canonical_quality(
    has_bbox: bool,
    has_origin: bool,
    has_unit_of_measure: bool,
    has_label: bool,
    has_context: bool,
) -> float:
    """Score a canonical object's completeness (0.0–1.0)."""
    score = 0.0
    if has_origin:
        score += 0.30
    if has_bbox:
        score += 0.20
    if has_unit_of_measure:
        score += 0.20
    if has_label:
        score += 0.15
    if has_context:
        score += 0.15
    return round(score, 4)


class ProofStep(BaseModel):
    """Single step in a derived-query proof chain."""

    description: str = Field(..., description="Human-readable description of this step")
    formula: str | None = Field(None, description="Mathematical formula applied (e.g. 'P = V × I')")
    source_facts: list[ProofPoint] = Field(default_factory=list, description="Source facts used in this step")
    result: str = Field(..., description="Result of this step")


class ProofChain(BaseModel):
    """Full derivation chain for a computed answer."""

    steps: list[ProofStep] = Field(default_factory=list, description="Ordered derivation steps")
    final_result: str = Field(..., description="Final computed answer")
    formula_summary: str = Field(..., description="Overall formula (e.g. 'P = V × I = 4.2V × 1.0A = 4.2W')")


class AnswerWithProof(BaseModel):
    """Answer that is provable from canonical facts; includes coordinate proof and confidence."""

    status: str = Field(default="answer", description="Always 'answer'")
    answer: str = Field(..., description="The proven answer")
    proof: list[ProofPoint] = Field(
        default_factory=list, description="(x,y) coordinates that support the answer"
    )
    source_id: str | None = Field(None, description="Canonical object id")
    source_type: str | None = Field(None, description="unit | bijection | grid")
    confidence: ConfidenceScore | None = Field(None, description="Confidence breakdown")
    derivation: ProofChain | None = Field(None, description="Derivation chain for computed answers")


class Refuse(BaseModel):
    """Deterministic refusal when the answer cannot be proven from canonical structure."""

    status: str = Field(default="refuse", description="Always 'refuse'")
    reason: str = Field(..., description="Short reason for refusal")
