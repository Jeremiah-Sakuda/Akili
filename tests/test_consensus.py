"""Tests for B1: Consensus extraction — agreement scoring and merging."""

from __future__ import annotations

import pytest

from akili.ingest.consensus import (
    _match_units,
    _unit_similarity,
    compute_agreement,
    merge_extractions,
    should_use_consensus,
)
from akili.ingest.extract_schema import (
    BijectionExtract,
    GridExtract,
    PageExtraction,
    PointSchema,
    UnitExtract,
)


def _unit(uid: str, label: str, value: float, uom: str, x: float = 0.5, y: float = 0.5) -> UnitExtract:
    return UnitExtract(id=uid, label=label, value=value, unit_of_measure=uom, origin=PointSchema(x=x, y=y))


class TestUnitSimilarity:
    def test_identical_units(self):
        u = {"value": "3.3", "label": "VCC", "unit_of_measure": "V", "origin": {"x": 0.5, "y": 0.5}}
        assert _unit_similarity(u, u) > 0.9

    def test_different_values_same_label(self):
        u1 = {"value": "3.3", "label": "VCC", "unit_of_measure": "V", "origin": {"x": 0.5, "y": 0.5}}
        u2 = {"value": "5.0", "label": "VCC", "unit_of_measure": "V", "origin": {"x": 0.5, "y": 0.5}}
        sim = _unit_similarity(u1, u2)
        assert 0.3 < sim < 0.8

    def test_completely_different(self):
        u1 = {"value": "3.3", "label": "VCC", "unit_of_measure": "V", "origin": {"x": 0.1, "y": 0.1}}
        u2 = {"value": "100", "label": "FCLK", "unit_of_measure": "MHz", "origin": {"x": 0.9, "y": 0.9}}
        sim = _unit_similarity(u1, u2)
        assert sim < 0.5


class TestMatchUnits:
    def test_perfect_match(self):
        units = [
            {"value": "3.3", "label": "VCC", "unit_of_measure": "V", "origin": {"x": 0.5, "y": 0.5}},
            {"value": "100", "label": "FCLK", "unit_of_measure": "MHz", "origin": {"x": 0.5, "y": 0.6}},
        ]
        matched, unmatched_a, unmatched_b = _match_units(units, units)
        assert len(matched) == 2
        assert len(unmatched_a) == 0
        assert len(unmatched_b) == 0

    def test_partial_match(self):
        a = [{"value": "3.3", "label": "VCC", "unit_of_measure": "V", "origin": {"x": 0.5, "y": 0.5}}]
        b = [
            {"value": "3.3", "label": "VCC", "unit_of_measure": "V", "origin": {"x": 0.5, "y": 0.5}},
            {"value": "100", "label": "FCLK", "unit_of_measure": "MHz", "origin": {"x": 0.5, "y": 0.6}},
        ]
        matched, unmatched_a, unmatched_b = _match_units(a, b)
        assert len(matched) == 1
        assert len(unmatched_a) == 0
        assert len(unmatched_b) == 1


class TestComputeAgreement:
    def test_identical_extractions(self):
        units = [_unit("u1", "VCC", 3.3, "V"), _unit("u2", "ICC", 100, "mA")]
        ext = PageExtraction(units=units, bijections=[], grids=[])
        assert compute_agreement(ext, ext) > 0.9

    def test_empty_extractions(self):
        ext = PageExtraction(units=[], bijections=[], grids=[])
        assert compute_agreement(ext, ext) == 1.0

    def test_one_empty_one_populated(self):
        ext_a = PageExtraction(units=[_unit("u1", "VCC", 3.3, "V")], bijections=[], grids=[])
        ext_b = PageExtraction(units=[], bijections=[], grids=[])
        agreement = compute_agreement(ext_a, ext_b)
        assert agreement < 0.5


class TestMergeExtractions:
    def test_merge_identical(self):
        units = [_unit("u1", "VCC", 3.3, "V")]
        ext = PageExtraction(units=units, bijections=[], grids=[])
        merged = merge_extractions(ext, ext)
        assert len(merged.units) >= 1

    def test_merge_different(self):
        ext_a = PageExtraction(units=[_unit("u1", "VCC", 3.3, "V")], bijections=[], grids=[])
        ext_b = PageExtraction(units=[_unit("u2", "ICC", 100, "mA")], bijections=[], grids=[])
        merged = merge_extractions(ext_a, ext_b)
        assert len(merged.units) == 2


class TestShouldUseConsensus:
    def test_disabled_by_default(self):
        assert not should_use_consensus("electrical_specs")

    def test_non_high_risk(self):
        assert not should_use_consensus("pinout_table")
