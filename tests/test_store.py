"""Tests for SQLite storage layer (Store CRUD operations)."""

from __future__ import annotations

from pathlib import Path

import pytest

from akili.canonical import Bijection, Grid, Unit
from akili.canonical.models import BBox, GridCell, Point
from akili.store.repository import Store


class TestStoreDocuments:
    def test_add_and_list_document(self, tmp_store: Store):
        tmp_store.add_document("doc1", "test.pdf", 5)
        docs = tmp_store.list_documents()
        assert len(docs) == 1
        assert docs[0]["doc_id"] == "doc1"
        assert docs[0]["filename"] == "test.pdf"
        assert docs[0]["page_count"] == 5

    def test_add_duplicate_document_replaces(self, tmp_store: Store):
        tmp_store.add_document("doc1", "old.pdf", 3)
        tmp_store.add_document("doc1", "new.pdf", 7)
        docs = tmp_store.list_documents()
        assert len(docs) == 1
        assert docs[0]["filename"] == "new.pdf"
        assert docs[0]["page_count"] == 7

    def test_delete_document(self, tmp_store: Store):
        tmp_store.add_document("doc1", "test.pdf", 5)
        tmp_store.delete_document("doc1")
        assert len(tmp_store.list_documents()) == 0

    def test_delete_removes_canonical_objects(self, tmp_store: Store):
        u = Unit(id="u1", value=3.3, unit_of_measure="V",
                 origin=Point(x=0.1, y=0.1), doc_id="doc1", page=0)
        tmp_store.store_canonical("doc1", "test.pdf", 1, [u], [], [])
        tmp_store.delete_document("doc1")
        assert tmp_store.get_units_by_doc("doc1") == []

    def test_list_documents_with_counts(self, tmp_store: Store):
        u = Unit(id="u1", value=3.3, unit_of_measure="V",
                 origin=Point(x=0.1, y=0.1), doc_id="doc1", page=0)
        b = Bijection(id="b1", left_set=["a"], right_set=["1"],
                      mapping={"a": "1"}, origin=Point(x=0.5, y=0.5),
                      doc_id="doc1", page=0)
        tmp_store.store_canonical("doc1", "test.pdf", 1, [u], [b], [])
        docs = tmp_store.list_documents()
        assert docs[0]["units_count"] == 1
        assert docs[0]["bijections_count"] == 1
        assert docs[0]["grids_count"] == 0


class TestStoreUnits:
    def test_store_and_retrieve_unit(self, tmp_store: Store):
        u = Unit(id="u1", label="VCC", value=3.3, unit_of_measure="V",
                 context="supply voltage",
                 origin=Point(x=0.1, y=0.2), doc_id="doc1", page=0,
                 bbox=BBox(x1=0.05, y1=0.15, x2=0.15, y2=0.25))
        tmp_store.store_canonical("doc1", "test.pdf", 1, [u], [], [])
        units = tmp_store.get_units_by_doc("doc1")
        assert len(units) == 1
        got = units[0]
        assert got.id == "u1"
        assert got.label == "VCC"
        assert float(got.value) == 3.3
        assert got.unit_of_measure == "V"
        assert got.context == "supply voltage"
        assert got.origin.x == pytest.approx(0.1)
        assert got.bbox is not None
        assert got.bbox.x1 == pytest.approx(0.05)

    def test_store_unit_without_optional_fields(self, tmp_store: Store):
        u = Unit(id="u1", value="hello", origin=Point(x=0.0, y=0.0),
                 doc_id="doc1", page=0)
        tmp_store.store_canonical("doc1", "test.pdf", 1, [u], [], [])
        units = tmp_store.get_units_by_doc("doc1")
        assert len(units) == 1
        assert units[0].label is None
        assert units[0].unit_of_measure is None
        assert units[0].bbox is None

    def test_duplicate_unit_replaces(self, tmp_store: Store):
        u1 = Unit(id="u1", value=3.3, unit_of_measure="V",
                  origin=Point(x=0.1, y=0.1), doc_id="doc1", page=0)
        u2 = Unit(id="u1", value=5.0, unit_of_measure="V",
                  origin=Point(x=0.1, y=0.1), doc_id="doc1", page=0)
        tmp_store.store_canonical("doc1", "test.pdf", 1, [u1], [], [])
        tmp_store.store_canonical("doc1", "test.pdf", 1, [u2], [], [])
        units = tmp_store.get_units_by_doc("doc1")
        assert len(units) == 1
        assert float(units[0].value) == 5.0


class TestStoreBijections:
    def test_store_and_retrieve_bijection(self, tmp_store: Store):
        b = Bijection(
            id="b1", left_set=["1", "2"], right_set=["VCC", "GND"],
            mapping={"1": "VCC", "2": "GND"},
            origin=Point(x=0.5, y=0.3), doc_id="doc1", page=0,
        )
        tmp_store.store_canonical("doc1", "test.pdf", 1, [], [b], [])
        bijs = tmp_store.get_bijections_by_doc("doc1")
        assert len(bijs) == 1
        assert bijs[0].mapping == {"1": "VCC", "2": "GND"}


class TestStoreGrids:
    def test_store_and_retrieve_grid(self, tmp_store: Store):
        g = Grid(
            id="g1", rows=2, cols=2,
            cells=[
                GridCell(row=0, col=0, value="A", origin=Point(x=0.1, y=0.1)),
                GridCell(row=0, col=1, value="B"),
                GridCell(row=1, col=0, value="C"),
                GridCell(row=1, col=1, value="D", origin=Point(x=0.5, y=0.5)),
            ],
            origin=Point(x=0.0, y=0.0), doc_id="doc1", page=0,
        )
        tmp_store.store_canonical("doc1", "test.pdf", 1, [], [], [g])
        grids = tmp_store.get_grids_by_doc("doc1")
        assert len(grids) == 1
        assert grids[0].rows == 2
        assert grids[0].cols == 2
        assert grids[0].get_cell(0, 0).value == "A"
        assert grids[0].get_cell(1, 1).value == "D"

    def test_grid_cell_without_origin(self, tmp_store: Store):
        g = Grid(
            id="g1", rows=1, cols=1,
            cells=[GridCell(row=0, col=0, value="X")],
            origin=Point(x=0.0, y=0.0), doc_id="doc1", page=0,
        )
        tmp_store.store_canonical("doc1", "test.pdf", 1, [], [], [g])
        grids = tmp_store.get_grids_by_doc("doc1")
        assert grids[0].get_cell(0, 0).origin is None


class TestStoreGetAllCanonical:
    def test_get_all_canonical_by_doc(self, tmp_store: Store):
        u = Unit(id="u1", value=1.0, origin=Point(x=0, y=0), doc_id="doc1", page=0)
        b = Bijection(id="b1", left_set=["a"], right_set=["1"],
                      mapping={"a": "1"}, origin=Point(x=0, y=0), doc_id="doc1", page=0)
        g = Grid(id="g1", rows=1, cols=1,
                 cells=[GridCell(row=0, col=0, value="X")],
                 origin=Point(x=0, y=0), doc_id="doc1", page=0)
        tmp_store.store_canonical("doc1", "test.pdf", 1, [u], [b], [g])
        all_obj = tmp_store.get_all_canonical_by_doc("doc1")
        assert len(all_obj) == 3

    def test_empty_doc_returns_empty(self, tmp_store: Store):
        assert tmp_store.get_all_canonical_by_doc("nonexistent") == []
