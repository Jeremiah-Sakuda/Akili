"""Tests for B2: Extended canonical model (Range, ConditionalUnit)."""

from __future__ import annotations

import pytest

from akili.canonical import ConditionalUnit, Range
from akili.canonical.models import BBox, Point


class TestRange:
    def test_create_full_range(self):
        r = Range(
            id="r1", label="VCC", min=2.7, typ=3.3, max=3.6, unit="V",
            conditions="TA = 25C", context="Electrical Characteristics",
            origin=Point(x=0.5, y=0.3), doc_id="d1", page=0,
        )
        assert r.min == 2.7
        assert r.typ == 3.3
        assert r.max == 3.6
        assert r.unit == "V"
        assert r.conditions == "TA = 25C"

    def test_range_with_nulls(self):
        r = Range(
            id="r2", label="ICC", min=None, typ=5.0, max=10.0, unit="mA",
            origin=Point(x=0.5, y=0.4), doc_id="d1", page=0,
        )
        assert r.min is None
        assert r.typ == 5.0

    def test_range_min_only(self):
        r = Range(
            id="r3", label="TOPR", min=-40, typ=None, max=None, unit="C",
            origin=Point(x=0.5, y=0.5), doc_id="d1", page=0,
        )
        assert r.min == -40
        assert r.typ is None
        assert r.max is None

    def test_range_with_bbox(self):
        r = Range(
            id="r4", label="VCC", min=2.7, typ=3.3, max=3.6, unit="V",
            origin=Point(x=0.5, y=0.3), doc_id="d1", page=0,
            bbox=BBox(x1=0.1, y1=0.2, x2=0.9, y2=0.4),
        )
        assert r.bbox is not None
        assert r.bbox.x1 == 0.1


class TestConditionalUnit:
    def test_create(self):
        cu = ConditionalUnit(
            id="cu1", label="VCC max", value=4.2, unit="V",
            condition_type="temperature", condition_value="85C",
            derating="20mV/C above 85C",
            context="Absolute Maximum Ratings",
            origin=Point(x=0.5, y=0.5), doc_id="d1", page=0,
        )
        assert cu.value == 4.2
        assert cu.condition_type == "temperature"
        assert cu.condition_value == "85C"
        assert cu.derating == "20mV/C above 85C"

    def test_without_derating(self):
        cu = ConditionalUnit(
            id="cu2", label="ICC", value=50, unit="mA",
            condition_type="voltage", condition_value="3.3V",
            origin=Point(x=0.5, y=0.5), doc_id="d1", page=0,
        )
        assert cu.derating is None


class TestStoreRangeAndConditionalUnit:
    def test_store_and_retrieve_range(self, tmp_store):
        r = Range(
            id="r1", label="VCC", min=2.7, typ=3.3, max=3.6, unit="V",
            conditions="TA=25C", context="Electrical Characteristics",
            origin=Point(x=0.5, y=0.3), doc_id="test-doc", page=0,
        )
        tmp_store.store_canonical("test-doc", "test.pdf", 1, [], [], [], ranges=[r])

        ranges = tmp_store.get_ranges_by_doc("test-doc")
        assert len(ranges) == 1
        assert ranges[0].min == 2.7
        assert ranges[0].typ == 3.3
        assert ranges[0].max == 3.6

    def test_store_and_retrieve_conditional_unit(self, tmp_store):
        cu = ConditionalUnit(
            id="cu1", label="VCC max", value=4.2, unit="V",
            condition_type="temperature", condition_value="85C",
            derating="20mV/C above 85C",
            origin=Point(x=0.5, y=0.5), doc_id="test-doc", page=0,
        )
        tmp_store.store_canonical("test-doc", "test.pdf", 1, [], [], [], conditional_units=[cu])

        cunits = tmp_store.get_conditional_units_by_doc("test-doc")
        assert len(cunits) == 1
        assert cunits[0].value == 4.2
        assert cunits[0].condition_type == "temperature"

    def test_get_all_canonical_includes_new_types(self, tmp_store):
        from akili.canonical import Unit
        u = Unit(id="u1", label="VCC", value=3.3, unit_of_measure="V",
                 origin=Point(x=0.1, y=0.1), doc_id="test-doc", page=0)
        r = Range(id="r1", label="VCC", min=2.7, typ=3.3, max=3.6, unit="V",
                  origin=Point(x=0.5, y=0.3), doc_id="test-doc", page=0)
        cu = ConditionalUnit(id="cu1", label="VCC", value=4.2, unit="V",
                             condition_type="temperature", condition_value="85C",
                             origin=Point(x=0.5, y=0.5), doc_id="test-doc", page=0)

        tmp_store.store_canonical("test-doc", "test.pdf", 1, [u], [], [], ranges=[r], conditional_units=[cu])
        all_objs = tmp_store.get_all_canonical_by_doc("test-doc")
        types = {type(o).__name__ for o in all_objs}
        assert "Unit" in types
        assert "Range" in types
        assert "ConditionalUnit" in types
