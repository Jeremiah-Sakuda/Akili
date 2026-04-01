"""Pytest wrapper for the benchmark suite.

Tests the benchmark utilities (value matching, ground truth loading)
without requiring live Gemini API access.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.benchmark.run_benchmark import load_ground_truth, values_match

GROUND_TRUTH_PATH = Path(__file__).parent / "ground_truth.json"


class TestBenchmarkUtilities:
    """Test benchmark helper functions."""

    def test_ground_truth_loads(self):
        gt = load_ground_truth()
        assert len(gt) >= 5, "Expected at least 5 datasheets in ground truth"
        for pdf_name, qa_pairs in gt.items():
            assert len(qa_pairs) == 10, f"{pdf_name} should have 10 Q&A pairs"
            for qa in qa_pairs:
                assert "question" in qa
                assert "expected_answer" in qa

    def test_values_match_exact(self):
        assert values_match("3.3 V", "3.3", "V")
        assert values_match("5 V", "5", "V")
        assert values_match("TO-220", "TO-220", None)

    def test_values_match_substring(self):
        assert values_match("Maximum output current: 1.5 A", "1.5", "A")
        assert values_match("0 to 125 °C", "0 to 125", "°C")

    def test_values_match_numeric_tolerance(self):
        assert values_match("3.29 V", "3.3", "V")  # within 10%
        assert not values_match("5.0 V", "3.3", "V")  # too far

    def test_values_no_match(self):
        assert not values_match("completely different", "3.3", "V")
        assert not values_match("no numbers here", "5", "V")
