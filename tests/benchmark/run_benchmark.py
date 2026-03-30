#!/usr/bin/env python3
"""
Akili Extraction Quality Benchmark

Measures precision and recall of the verification layer against hand-labeled
ground truth for a set of datasheets.

Usage:
    python tests/benchmark/run_benchmark.py [--datasheets-dir DIR] [--ground-truth-dir DIR]

Ground truth format (JSON per datasheet):
{
    "filename": "component_datasheet.pdf",
    "queries": [
        {
            "question": "What is the maximum voltage?",
            "query_type": "max_voltage",
            "expected_status": "answer",
            "expected_answer_contains": ["5.5", "V"],
            "expected_answer_not_contains": [],
            "notes": "From Absolute Maximum Ratings table"
        },
        {
            "question": "What is the ESD rating?",
            "query_type": "esd_rating",
            "expected_status": "refuse",
            "notes": "No ESD info in this datasheet"
        }
    ]
}
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Add project root to path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from akili.canonical import Bijection, Grid, Unit  # noqa: E402
from akili.store.repository import Store  # noqa: E402
from akili.verify.models import AnswerWithProof, Refuse  # noqa: E402
from akili.verify.proof import verify_and_answer  # noqa: E402


@dataclass
class QueryResult:
    question: str
    query_type: str
    expected_status: str
    actual_status: str
    expected_contains: list[str]
    actual_answer: str
    passed: bool
    reason: str = ""


@dataclass
class DatasheetResult:
    filename: str
    total_queries: int = 0
    passed: int = 0
    failed: int = 0
    query_results: list[QueryResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total_queries if self.total_queries > 0 else 0.0


@dataclass
class BenchmarkSummary:
    total_datasheets: int = 0
    total_queries: int = 0
    total_passed: int = 0
    total_failed: int = 0
    false_accepts: int = 0
    correct_refuses: int = 0
    incorrect_refuses: int = 0
    results_by_query_type: dict[str, dict[str, int]] = field(default_factory=dict)
    datasheet_results: list[DatasheetResult] = field(default_factory=list)

    @property
    def overall_pass_rate(self) -> float:
        return self.total_passed / self.total_queries if self.total_queries > 0 else 0.0

    @property
    def false_accept_rate(self) -> float:
        answered = sum(
            1 for ds in self.datasheet_results
            for qr in ds.query_results
            if qr.actual_status == "answer"
        )
        return self.false_accepts / answered if answered > 0 else 0.0


def _evaluate_query(
    question: str,
    query_type: str,
    expected_status: str,
    expected_contains: list[str],
    expected_not_contains: list[str],
    units: list[Unit],
    bijections: list[Bijection],
    grids: list[Grid],
) -> QueryResult:
    """Run a single query against canonical data and evaluate the result."""
    result = verify_and_answer(question, units, bijections, grids)

    confidence_tier = "refused"
    if isinstance(result, AnswerWithProof):
        actual_status = "answer"
        actual_answer = str(result.answer)
        if result.confidence:
            confidence_tier = result.confidence.tier
    elif isinstance(result, Refuse):
        actual_status = "refuse"
        actual_answer = result.reason or ""
    else:
        actual_status = "unknown"
        actual_answer = ""

    passed = True
    reason = ""

    if expected_status == "answer" and actual_status == "answer":
        answer_lower = actual_answer.lower()
        for term in expected_contains:
            if term.lower() not in answer_lower:
                passed = False
                reason = f"Expected '{term}' in answer '{actual_answer}'"
                break
        for term in expected_not_contains:
            if term.lower() in answer_lower:
                passed = False
                reason = f"Unexpected '{term}' found in answer '{actual_answer}'"
                break
    elif expected_status == "answer" and actual_status == "refuse":
        passed = False
        reason = f"Expected answer, got REFUSE: {actual_answer}"
    elif expected_status == "refuse" and actual_status == "refuse":
        passed = True
    elif expected_status == "refuse" and actual_status == "answer":
        if confidence_tier == "review":
            passed = False
            reason = f"Expected REFUSE, got REVIEW-tier answer: {actual_answer} (not a false-accept)"
        else:
            passed = False
            reason = f"Expected REFUSE, got answer: {actual_answer}"
    else:
        passed = False
        reason = f"Unexpected status: expected={expected_status}, actual={actual_status}"

    return QueryResult(
        question=question,
        query_type=query_type,
        expected_status=expected_status,
        actual_status=actual_status,
        expected_contains=expected_contains,
        actual_answer=actual_answer,
        passed=passed,
        reason=reason,
    )


def run_benchmark_on_store(
    ground_truth_path: Path,
    store: Store,
    doc_id: str,
) -> DatasheetResult:
    """Run benchmark queries against a document already in the store."""
    gt = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    filename = gt.get("filename", ground_truth_path.stem)
    queries = gt.get("queries", [])

    units = store.get_units_by_doc(doc_id)
    bijections = store.get_bijections_by_doc(doc_id)
    grids = store.get_grids_by_doc(doc_id)

    ds_result = DatasheetResult(filename=filename)

    for q in queries:
        qr = _evaluate_query(
            question=q["question"],
            query_type=q.get("query_type", "unknown"),
            expected_status=q.get("expected_status", "answer"),
            expected_contains=q.get("expected_answer_contains", []),
            expected_not_contains=q.get("expected_answer_not_contains", []),
            units=units,
            bijections=bijections,
            grids=grids,
        )
        ds_result.query_results.append(qr)
        ds_result.total_queries += 1
        if qr.passed:
            ds_result.passed += 1
        else:
            ds_result.failed += 1

    return ds_result


def run_benchmark_on_canonical(
    ground_truth_path: Path,
    units: list[Unit],
    bijections: list[Bijection],
    grids: list[Grid],
) -> DatasheetResult:
    """Run benchmark queries against provided canonical data (no store needed)."""
    gt = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    filename = gt.get("filename", ground_truth_path.stem)
    queries = gt.get("queries", [])

    ds_result = DatasheetResult(filename=filename)

    for q in queries:
        qr = _evaluate_query(
            question=q["question"],
            query_type=q.get("query_type", "unknown"),
            expected_status=q.get("expected_status", "answer"),
            expected_contains=q.get("expected_answer_contains", []),
            expected_not_contains=q.get("expected_answer_not_contains", []),
            units=units,
            bijections=bijections,
            grids=grids,
        )
        ds_result.query_results.append(qr)
        ds_result.total_queries += 1
        if qr.passed:
            ds_result.passed += 1
        else:
            ds_result.failed += 1

    return ds_result


def compute_summary(datasheet_results: list[DatasheetResult]) -> BenchmarkSummary:
    """Aggregate results across all datasheets."""
    summary = BenchmarkSummary()
    summary.datasheet_results = datasheet_results
    summary.total_datasheets = len(datasheet_results)

    for ds in datasheet_results:
        summary.total_queries += ds.total_queries
        summary.total_passed += ds.passed
        summary.total_failed += ds.failed

        for qr in ds.query_results:
            qt = qr.query_type
            if qt not in summary.results_by_query_type:
                summary.results_by_query_type[qt] = {"passed": 0, "failed": 0, "total": 0}
            summary.results_by_query_type[qt]["total"] += 1
            if qr.passed:
                summary.results_by_query_type[qt]["passed"] += 1
            else:
                summary.results_by_query_type[qt]["failed"] += 1

            if qr.expected_status == "refuse" and qr.actual_status == "answer":
                if "not a false-accept" not in qr.reason:
                    summary.false_accepts += 1
            elif qr.expected_status == "refuse" and qr.actual_status == "refuse":
                summary.correct_refuses += 1
            elif qr.expected_status == "answer" and qr.actual_status == "refuse":
                summary.incorrect_refuses += 1

    return summary


def print_report(summary: BenchmarkSummary) -> None:
    """Print a human-readable benchmark report."""
    print("\n" + "=" * 70)
    print("AKILI EXTRACTION QUALITY BENCHMARK")
    print("=" * 70)

    print(f"\nDatasheets tested: {summary.total_datasheets}")
    print(f"Total queries:     {summary.total_queries}")
    print(f"Passed:            {summary.total_passed}")
    print(f"Failed:            {summary.total_failed}")
    print(f"Pass rate:         {summary.overall_pass_rate:.1%}")
    print(f"False-accept rate: {summary.false_accept_rate:.1%}")
    print(f"False accepts:     {summary.false_accepts}")
    print(f"Correct refuses:   {summary.correct_refuses}")
    print(f"Incorrect refuses: {summary.incorrect_refuses}")

    print("\n--- Results by Query Type ---")
    for qt, counts in sorted(summary.results_by_query_type.items()):
        rate = counts["passed"] / counts["total"] if counts["total"] > 0 else 0
        print(f"  {qt:35s}  {counts['passed']}/{counts['total']}  ({rate:.0%})")

    print("\n--- Per-Datasheet Results ---")
    for ds in summary.datasheet_results:
        print(f"\n  {ds.filename} ({ds.passed}/{ds.total_queries} = {ds.pass_rate:.0%})")
        for qr in ds.query_results:
            status = "PASS" if qr.passed else "FAIL"
            print(f"    [{status}] {qr.question}")
            if not qr.passed:
                print(f"           Reason: {qr.reason}")

    print("\n" + "=" * 70)
    stage_a_target = summary.overall_pass_rate >= 0.70
    print(f"Stage A target (>=70% pass rate): {'MET' if stage_a_target else 'NOT MET'}")
    false_accept_ok = summary.false_accept_rate < 0.01
    print(f"False-accept target (<1%):        {'MET' if false_accept_ok else 'NOT MET'}")
    print("=" * 70)


def main() -> None:
    """Run the benchmark against ground truth files and ingested datasheets."""
    import argparse

    parser = argparse.ArgumentParser(description="Akili Extraction Quality Benchmark")
    parser.add_argument(
        "--datasheets-dir",
        type=Path,
        default=Path(__file__).parent / "datasheets",
    )
    parser.add_argument(
        "--ground-truth-dir",
        type=Path,
        default=Path(__file__).parent / "ground_truth",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Path to SQLite DB with ingested datasheets. If not provided, "
        "attempts to ingest PDFs first.",
    )
    args = parser.parse_args()

    gt_dir = args.ground_truth_dir
    if not gt_dir.exists():
        print(f"Ground truth directory not found: {gt_dir}")
        print("Create ground truth JSON files to run the benchmark.")
        print("See the module docstring for the expected format.")
        sys.exit(1)

    gt_files = sorted(gt_dir.glob("*.json"))
    if not gt_files:
        print(f"No ground truth JSON files found in {gt_dir}")
        sys.exit(1)

    print(f"Found {len(gt_files)} ground truth file(s)")

    import tempfile
    db_path = args.db_path or Path(tempfile.mktemp(suffix=".db"))
    store = Store(db_path)

    ds_dir = args.datasheets_dir
    all_results: list[DatasheetResult] = []

    for gt_path in gt_files:
        gt = json.loads(gt_path.read_text(encoding="utf-8"))
        pdf_name = gt.get("filename", "")
        pdf_path = ds_dir / pdf_name

        if pdf_path.exists():
            print(f"\nIngesting {pdf_name}...")
            from akili.ingest.pipeline import ingest_document
            doc_id, _, total, failed = ingest_document(pdf_path, store=store)
            print(f"  Ingested: {total} pages, {failed} failed")
            ds_result = run_benchmark_on_store(gt_path, store, doc_id)
        else:
            print(f"\nPDF not found: {pdf_path} - running with empty canonical data")
            ds_result = run_benchmark_on_canonical(gt_path, [], [], [])

        all_results.append(ds_result)

    summary = compute_summary(all_results)
    print_report(summary)

    if not args.db_path and db_path.exists():
        db_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
