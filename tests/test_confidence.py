"""Tests for confidence scoring."""

import os

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
            has_bbox=True, has_origin=True, has_unit_of_measure=True,
            has_label=True, has_context=True,
        )
        assert score == pytest.approx(1.0, abs=0.01)

    def test_origin_only(self):
        score = compute_canonical_quality(
            has_bbox=False, has_origin=True, has_unit_of_measure=False,
            has_label=False, has_context=False,
        )
        assert score == pytest.approx(0.30, abs=0.01)

    def test_no_fields(self):
        score = compute_canonical_quality(
            has_bbox=False, has_origin=False, has_unit_of_measure=False,
            has_label=False, has_context=False,
        )
        assert score == pytest.approx(0.0, abs=0.01)


class TestConfidenceInVerification:
    def test_structured_unit_has_confidence(self):
        """A unit with explicit unit_of_measure and label should produce high confidence."""
        u = Unit(
            id="v1", label="VCC", value=5.0, unit_of_measure="V",
            context="supply voltage",
            origin=Point(x=0.1, y=0.1), doc_id="d", page=0,
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
            id="v1", value=5.0, unit_of_measure="V",
            origin=Point(x=0.1, y=0.1), doc_id="d", page=0,
        )
        result = verify_and_answer("What is the maximum voltage?", [u], [], [])
        assert isinstance(result, AnswerWithProof)
        assert result.confidence is not None
        assert result.confidence.canonical_validation < 0.6

    def test_refuse_has_no_confidence(self):
        result = verify_and_answer("What is the fluxgate impedance?", [], [], [])
        assert isinstance(result, Refuse)
