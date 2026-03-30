"""Tests for B5: Corrections store and review workflow."""

from __future__ import annotations

from pathlib import Path

import pytest

from akili.store.corrections import CorrectionStore


@pytest.fixture()
def correction_store(tmp_path: Path) -> CorrectionStore:
    return CorrectionStore(db_path=tmp_path / "test_corrections.db")


class TestCorrectionStore:
    def test_add_confirmation(self, correction_store: CorrectionStore):
        cid = correction_store.add_correction(
            doc_id="doc1",
            canonical_id="u1",
            canonical_type="unit",
            action="confirm",
            original_value="3.3 V",
        )
        assert cid > 0

    def test_add_correction(self, correction_store: CorrectionStore):
        cid = correction_store.add_correction(
            doc_id="doc1",
            canonical_id="u1",
            canonical_type="unit",
            action="correct",
            original_value="3.3 V",
            corrected_value="3.6 V",
            corrected_by="engineer@test.com",
            notes="Value was misread from table",
        )
        assert cid > 0

    def test_get_corrections_by_doc(self, correction_store: CorrectionStore):
        correction_store.add_correction("doc1", "u1", "unit", "confirm", "3.3 V")
        correction_store.add_correction("doc1", "u2", "unit", "correct", "5.0 V", "5.5 V")
        correction_store.add_correction("doc2", "u3", "unit", "confirm", "100 mA")

        corrections = correction_store.get_corrections_by_doc("doc1")
        assert len(corrections) == 2

        corrections_doc2 = correction_store.get_corrections_by_doc("doc2")
        assert len(corrections_doc2) == 1

    def test_correction_fields(self, correction_store: CorrectionStore):
        correction_store.add_correction(
            doc_id="doc1", canonical_id="u1", canonical_type="unit",
            action="correct", original_value="3.3 V", corrected_value="3.6 V",
            corrected_by="engineer", notes="test note",
        )
        corrections = correction_store.get_corrections_by_doc("doc1")
        c = corrections[0]
        assert c.canonical_id == "u1"
        assert c.canonical_type == "unit"
        assert c.action == "correct"
        assert c.original_value == "3.3 V"
        assert c.corrected_value == "3.6 V"
        assert c.corrected_by == "engineer"
        assert c.notes == "test note"
        assert c.created_at is not None


class TestCorrectionStats:
    def test_empty_stats(self, correction_store: CorrectionStore):
        stats = correction_store.get_correction_stats()
        assert stats["total"] == 0
        assert stats["confirmations"] == 0
        assert stats["corrections"] == 0
        assert stats["correction_rate"] == 0

    def test_stats_with_data(self, correction_store: CorrectionStore):
        correction_store.add_correction("doc1", "u1", "unit", "confirm", "3.3 V")
        correction_store.add_correction("doc1", "u2", "unit", "correct", "5.0 V", "5.5 V")
        correction_store.add_correction("doc1", "u3", "unit", "confirm", "100 mA")

        stats = correction_store.get_correction_stats("doc1")
        assert stats["total"] == 3
        assert stats["confirmations"] == 2
        assert stats["corrections"] == 1
        assert abs(stats["correction_rate"] - 1 / 3) < 0.01

    def test_stats_global(self, correction_store: CorrectionStore):
        correction_store.add_correction("doc1", "u1", "unit", "confirm", "3.3 V")
        correction_store.add_correction("doc2", "u2", "unit", "correct", "5.0 V", "5.5 V")

        stats = correction_store.get_correction_stats()
        assert stats["total"] == 2


class TestAuditLog:
    def test_sqlite_audit_log(self, tmp_path: Path):
        from akili.store.repository import Store
        store = Store(db_path=tmp_path / "audit_test.db")
        store._audit("test_action", "doc1", details={"foo": "bar"})

        log = store.get_audit_log()
        assert len(log) == 1
        assert log[0]["action"] == "test_action"
        assert log[0]["details"]["foo"] == "bar"

    def test_store_canonical_creates_audit(self, tmp_path: Path):
        from akili.canonical import Unit
        from akili.canonical.models import Point
        from akili.store.repository import Store

        store = Store(db_path=tmp_path / "audit_test2.db")
        u = Unit(id="u1", label="VCC", value=3.3, unit_of_measure="V",
                 origin=Point(x=0.1, y=0.1), doc_id="doc1", page=0)
        store.store_canonical("doc1", "test.pdf", 1, [u], [], [])

        log = store.get_audit_log("doc1")
        actions = [entry["action"] for entry in log]
        assert "store_canonical" in actions
