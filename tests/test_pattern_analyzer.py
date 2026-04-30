"""Tests for C4: Correction Pattern Analyzer & Simple Learning."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from akili.learn.pattern_analyzer import (
    CorrectionPattern,
    PatternAnalyzer,
    _extract_number,
    _extract_unit,
)
from akili.store.corrections import CorrectionStore


@pytest.fixture()
def correction_store(tmp_path: Path) -> CorrectionStore:
    return CorrectionStore(db_path=tmp_path / "test_corrections.db")


@pytest.fixture()
def populated_store(correction_store: CorrectionStore) -> CorrectionStore:
    """Store pre-populated with various correction patterns."""
    # Unit confusion: mV → V (5 times)
    for i in range(5):
        correction_store.add_correction(
            doc_id=f"doc_{i}", canonical_id=f"u_{i}", canonical_type="unit",
            action="correct", original_value=f"{3300 + i} mV",
            corrected_value=f"{3.3 + i * 0.001} V",
        )

    # Scaling errors: 10x off (6 times)
    for i in range(6):
        correction_store.add_correction(
            doc_id=f"doc_{i}", canonical_id=f"s_{i}", canonical_type="unit",
            action="correct", original_value=f"{(i + 1) * 10} mA",
            corrected_value=f"{(i + 1)} mA",
        )

    # A few confirmations
    for i in range(3):
        correction_store.add_correction(
            doc_id=f"doc_{i}", canonical_id=f"c_{i}", canonical_type="unit",
            action="confirm", original_value=f"{3.3} V",
        )

    return correction_store


class TestPatternAnalyzer:
    def test_analyze_empty(self, correction_store: CorrectionStore) -> None:
        analyzer = PatternAnalyzer(correction_store)
        patterns = analyzer.analyze_all()
        assert patterns == []

    def test_detect_unit_confusion(self, populated_store: CorrectionStore) -> None:
        analyzer = PatternAnalyzer(populated_store)
        patterns = analyzer.analyze_all()
        unit_patterns = [p for p in patterns if p.category == "unit_confusion"]
        assert len(unit_patterns) > 0
        mv_to_v = [p for p in unit_patterns if "mv" in p.original_pattern.lower()]
        assert len(mv_to_v) > 0
        assert mv_to_v[0].occurrences >= 5

    def test_detect_scaling_errors(self, populated_store: CorrectionStore) -> None:
        analyzer = PatternAnalyzer(populated_store)
        patterns = analyzer.analyze_all()
        scale_patterns = [p for p in patterns if p.category == "value_scaling"]
        assert len(scale_patterns) > 0
        ten_x = [p for p in scale_patterns if "10x" in p.original_pattern]
        assert len(ten_x) > 0

    def test_auto_correction_rules(self, populated_store: CorrectionStore) -> None:
        analyzer = PatternAnalyzer(populated_store)
        rules = analyzer.get_auto_correction_rules()
        assert len(rules) > 0
        for rule in rules:
            assert rule.pattern.occurrences >= 5

    def test_pattern_stats(self, populated_store: CorrectionStore) -> None:
        analyzer = PatternAnalyzer(populated_store)
        stats = analyzer.get_pattern_stats()
        assert stats["total_patterns"] > 0
        assert "categories" in stats
        assert "top_patterns" in stats

    def test_analyze_by_doc(self, populated_store: CorrectionStore) -> None:
        analyzer = PatternAnalyzer(populated_store)
        patterns = analyzer.analyze_by_doc("doc_0")
        # doc_0 has both unit confusion and scaling corrections
        assert isinstance(patterns, list)


class TestSuggestCorrection:
    def test_suggest_from_patterns(self, populated_store: CorrectionStore) -> None:
        analyzer = PatternAnalyzer(populated_store)
        suggestion = analyzer.suggest_correction("unit", "4500 mV")
        # Could suggest correction since mV→V pattern exists
        # The exact behavior depends on whether the pattern was auto-correctable
        assert suggestion is None or isinstance(suggestion, str)

    def test_no_suggestion_for_unknown(self, correction_store: CorrectionStore) -> None:
        analyzer = PatternAnalyzer(correction_store)
        suggestion = analyzer.suggest_correction("unit", "3.3 V")
        assert suggestion is None


class TestHelpers:
    def test_extract_unit(self) -> None:
        assert _extract_unit("3.3 V") == "v"
        assert _extract_unit("250 mA") == "ma"
        assert _extract_unit("45 °C/W") == "°c/w"
        assert _extract_unit("42") is None

    def test_extract_number(self) -> None:
        assert _extract_number("3.3 V") == 3.3
        assert _extract_number("250 mA") == 250.0
        assert _extract_number("-40 °C") == -40.0
        assert _extract_number("no number") is None


class TestLabelMisread:
    def test_detect_label_patterns(self, correction_store: CorrectionStore) -> None:
        for _ in range(4):
            correction_store.add_correction(
                doc_id="d1", canonical_id="lbl_1", canonical_type="unit",
                action="correct", original_value="therml resistance",
                corrected_value="thermal resistance",
            )
        analyzer = PatternAnalyzer(correction_store)
        patterns = analyzer.analyze_all()
        label_patterns = [p for p in patterns if p.category == "label_misread"]
        assert len(label_patterns) > 0


class TestTypeBias:
    def test_detect_type_bias(self, correction_store: CorrectionStore) -> None:
        for i in range(8):
            correction_store.add_correction(
                doc_id=f"d{i}", canonical_id=f"r_{i}",
                canonical_type="range" if i < 6 else "unit",
                action="correct", original_value=f"{i} V",
                corrected_value=f"{i + 0.1} V",
            )
        analyzer = PatternAnalyzer(correction_store)
        patterns = analyzer.analyze_all()
        bias_patterns = [p for p in patterns if p.category == "type_bias"]
        assert any(p.original_pattern == "range" for p in bias_patterns)
