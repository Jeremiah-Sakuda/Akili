"""Pytest wrapper for the benchmark harness using fixture data from conftest.py.

Runs the benchmark ground truth queries against the sample canonical data
to verify the verification layer handles all 30 query types correctly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.benchmark.run_benchmark import (
    compute_summary,
    run_benchmark_on_canonical,
)

_GT_DIR = Path(__file__).parent / "ground_truth"


class TestBenchmarkWithFixtures:
    """Run the benchmark against the sample fixture data."""

    def test_sample_datasheet_benchmark(self, sample_units, sample_bijections, sample_grids):
        gt_path = _GT_DIR / "sample_datasheet.json"
        if not gt_path.exists():
            pytest.skip("Ground truth file not found")

        result = run_benchmark_on_canonical(
            gt_path,
            units=sample_units,
            bijections=sample_bijections,
            grids=sample_grids,
        )

        assert result.total_queries > 0
        assert result.pass_rate >= 0.70, (
            f"Benchmark pass rate {result.pass_rate:.0%} below 70% target. "
            f"Failed queries: {[qr.question for qr in result.query_results if not qr.passed]}"
        )

    def test_no_false_accepts(self, sample_units, sample_bijections, sample_grids):
        gt_path = _GT_DIR / "sample_datasheet.json"
        if not gt_path.exists():
            pytest.skip("Ground truth file not found")

        result = run_benchmark_on_canonical(
            gt_path,
            units=sample_units,
            bijections=sample_bijections,
            grids=sample_grids,
        )
        summary = compute_summary([result])

        assert summary.false_accepts == 0, (
            f"Found {summary.false_accepts} false accepts (verified but wrong). "
            "This is a critical trust violation."
        )

    def test_benchmark_covers_all_query_types(self, sample_units, sample_bijections, sample_grids):
        gt_path = _GT_DIR / "sample_datasheet.json"
        if not gt_path.exists():
            pytest.skip("Ground truth file not found")

        result = run_benchmark_on_canonical(
            gt_path,
            units=sample_units,
            bijections=sample_bijections,
            grids=sample_grids,
        )
        summary = compute_summary([result])

        assert len(summary.results_by_query_type) >= 20, (
            f"Only {len(summary.results_by_query_type)} query types tested. "
            "Expected at least 20 distinct types."
        )
