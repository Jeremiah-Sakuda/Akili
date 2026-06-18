"""Tests for confidence scoring."""

import pytest

from akili.verify.models import ConfidenceScore, compute_canonical_quality
from akili.verify import verify_and_answer, AnswerWithProof, Refuse
from akili.canonical import Unit
from akili.canonical.models import BBox, Point


class TestConfidenceScore:
    def test_compute_defaults(self):
        c = ConfidenceScore.compute()
        assert c.overall == pytest.approx(0.5, abs=0.01)

    def test_compute_perfect(self):
        c = ConfidenceScore.compute(1.0, 1.0, 1.0)
        assert c.overall == pytest.approx(1.0, abs=0.01)
        assert c.tier == "verified"

    def test_compute_low(self):
        c = ConfidenceScore.compute(0.1, 0.1, 0.1)
        assert c.overall < 0.50
        assert c.tier == "refused"

    def test_review_band(self):
        c = ConfidenceScore.compute(0.6, 0.6, 0.6)
        assert 0.50 <= c.overall < 0.85
        assert c.tier == "review"

    def test_verified_threshold(self):
        c = ConfidenceScore.compute(0.9, 0.9, 0.9)
        assert c.overall >= 0.85
        assert c.tier == "verified"


class TestCanonicalQuality:
    def test_all_fields(self):
        score = compute_canonical_quality(
            has_bbox=True,
            has_origin=True,
            has_unit_of_measure=True,
            has_label=True,
            has_context=True,
        )
        assert score == pytest.approx(1.0, abs=0.01)

    def test_origin_only(self):
        score = compute_canonical_quality(
            has_bbox=False,
            has_origin=True,
            has_unit_of_measure=False,
            has_label=False,
            has_context=False,
        )
        assert score == pytest.approx(0.30, abs=0.01)

    def test_no_fields(self):
        score = compute_canonical_quality(
            has_bbox=False,
            has_origin=False,
            has_unit_of_measure=False,
            has_label=False,
            has_context=False,
        )
        assert score == pytest.approx(0.0, abs=0.01)


class TestConfidenceInVerification:
    def test_structured_unit_has_confidence(self):
        """A unit with explicit unit_of_measure and label should produce high confidence."""
        u = Unit(
            id="v1",
            label="VCC",
            value=5.0,
            unit_of_measure="V",
            context="supply voltage",
            origin=Point(x=0.1, y=0.1),
            doc_id="d",
            page=0,
            bbox=BBox(x1=0.05, y1=0.05, x2=0.15, y2=0.15),
        )
        result = verify_and_answer("What is the maximum voltage?", [u], [], [])
        assert isinstance(result, AnswerWithProof)
        assert result.confidence is not None
        assert result.confidence.overall > 0.5
        assert result.confidence.canonical_validation > 0.8

    def test_bare_unit_lower_confidence(self):
        """A unit without label, context, bbox should produce lower canonical validation."""
        u = Unit(
            id="v1",
            value=5.0,
            unit_of_measure="V",
            origin=Point(x=0.1, y=0.1),
            doc_id="d",
            page=0,
        )
        result = verify_and_answer("What is the maximum voltage?", [u], [], [])
        assert isinstance(result, AnswerWithProof)
        assert result.confidence is not None
        assert result.confidence.canonical_validation < 0.6

    def test_refuse_has_no_confidence(self):
        result = verify_and_answer("What is the fluxgate impedance?", [], [], [])
        assert isinstance(result, Refuse)

    def test_grounded_unit_reaches_verified(self):
        """A grounded, well-formed fact should reach the VERIFIED tier; ungrounded should not."""
        common = dict(
            id="g1",
            label="VCC",
            value=5.0,
            unit_of_measure="V",
            context="supply voltage",
            origin=Point(x=0.2, y=0.3),
            doc_id="d",
            page=0,
            bbox=BBox(x1=0.2, y1=0.3, x2=0.3, y2=0.32),
        )
        grounded = Unit(**common, grounded=True, grounding_score=1.0)
        ungrounded = Unit(**common)

        gr = verify_and_answer("What is the maximum voltage?", [grounded], [], [])
        ur = verify_and_answer("What is the maximum voltage?", [ungrounded], [], [])
        assert isinstance(gr, AnswerWithProof) and gr.confidence.tier == "verified"
        assert isinstance(ur, AnswerWithProof) and ur.confidence.tier != "verified"

    def test_flagged_fact_cannot_be_verified(self):
        """A fact flagged by a consistency check is capped below VERIFIED even if grounded."""
        u = Unit(
            id="f1",
            label="VCC",
            value=5.0,
            unit_of_measure="V",
            context="supply voltage",
            origin=Point(x=0.2, y=0.3),
            doc_id="d",
            page=0,
            bbox=BBox(x1=0.2, y1=0.3, x2=0.3, y2=0.32),
            grounded=True,
            grounding_score=1.0,
            flagged_for_review=True,
        )
        result = verify_and_answer("What is the maximum voltage?", [u], [], [])
        assert isinstance(result, AnswerWithProof)
        assert result.confidence.tier != "verified"

    def test_bijection_answer_carries_confidence(self):
        """Structural (pin) answers must also carry a confidence score and tier."""
        from akili.canonical import Bijection

        b = Bijection(
            id="b1",
            left_set=["1"],
            right_set=["VCC"],
            mapping={"1": "VCC"},
            origin=Point(x=0.1, y=0.1),
            doc_id="d",
            page=0,
        )
        result = verify_and_answer("What is pin 1?", [], [b], [])
        assert isinstance(result, AnswerWithProof)
        assert result.confidence is not None
        assert result.confidence.tier in ("verified", "review", "refused")
