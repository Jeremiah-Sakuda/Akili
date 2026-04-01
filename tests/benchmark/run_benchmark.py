#!/usr/bin/env python3
"""
Benchmark runner: ingest datasheets, run Q&A, compare to ground truth.

Usage:
    python tests/benchmark/run_benchmark.py

Requires:
    - GOOGLE_API_KEY set in environment
    - PDF files in tests/fixtures/ matching names in ground_truth.json

Reports:
    - Per-datasheet accuracy and false-refuse rate
    - Overall accuracy across all datasheets
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

# Ensure src/ is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from akili.canonical import Bijection, Grid, Unit
from akili.ingest.pipeline import ingest_document
from akili.verify import Refuse, verify_and_answer

GROUND_TRUTH_PATH = Path(__file__).parent / "ground_truth.json"
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def load_ground_truth() -> dict:
    with open(GROUND_TRUTH_PATH) as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def normalize_value(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def values_match(actual: str, expected: str, expected_unit: str | None) -> bool:
    actual_lower = normalize_value(actual)
    expected_lower = normalize_value(expected)

    if expected_lower in actual_lower:
        return True

    try:
        actual_nums = re.findall(r"[-+]?\d*\.?\d+", actual_lower)
        expected_nums = re.findall(r"[-+]?\d*\.?\d+", expected_lower)
        if actual_nums and expected_nums:
            for a_num in actual_nums:
                for e_num in expected_nums:
                    if abs(float(a_num) - float(e_num)) < 0.01:
                        return True
                    if float(e_num) != 0 and abs(float(a_num) - float(e_num)) / abs(float(e_num)) < 0.1:
                        return True
    except (ValueError, ZeroDivisionError):
        pass

    if expected_unit and expected_unit.lower() in actual_lower:
        for e_num in re.findall(r"[-+]?\d*\.?\d+", expected_lower):
            if e_num in actual_lower:
                return True

    return False


def run_benchmark() -> dict:
    ground_truth = load_ground_truth()
    results: dict = {
        "datasheets": {},
        "overall": {"total": 0, "correct": 0, "refused": 0, "wrong": 0},
    }

    for pdf_name, qa_pairs in ground_truth.items():
        pdf_path = FIXTURES_DIR / pdf_name
        if not pdf_path.exists():
            print(f"  SKIP {pdf_name} -- not found in {FIXTURES_DIR}")
            results["datasheets"][pdf_name] = {"status": "skipped", "reason": "PDF not found"}
            continue

        print(f"\n{'='*60}")
        print(f"  Ingesting: {pdf_name}")
        print(f"{'='*60}")

        start = time.time()
        try:
            doc_id, canonical, total_pages, pages_failed = ingest_document(pdf_path)
        except Exception as e:
            print(f"  FAIL: Ingest error: {e}")
            results["datasheets"][pdf_name] = {"status": "error", "reason": str(e)}
            continue
        ingest_time = time.time() - start

        units = [o for o in canonical if isinstance(o, Unit)]
        bijections = [o for o in canonical if isinstance(o, Bijection)]
        grids = [o for o in canonical if isinstance(o, Grid)]

        print(f"  Ingested in {ingest_time:.1f}s: {len(units)} units, "
              f"{len(bijections)} bijections, {len(grids)} grids")
        print(f"  Pages: {total_pages} total, {pages_failed} failed\n")

        sheet_results = {
            "ingest_time_s": round(ingest_time, 1),
            "total_pages": total_pages,
            "pages_failed": pages_failed,
            "facts_extracted": len(canonical),
            "questions": [],
            "correct": 0,
            "refused": 0,
            "wrong": 0,
        }

        for qa in qa_pairs:
            question = qa["question"]
            expected = qa["expected_answer"]
            expected_unit = qa.get("expected_unit")

            result = verify_and_answer(question, units, bijections, grids)

            if isinstance(result, Refuse):
                status = "refused"
                sheet_results["refused"] += 1
                results["overall"]["refused"] += 1
                actual = f"REFUSED: {result.reason}"
            else:
                actual = result.answer
                if values_match(actual, expected, expected_unit):
                    status = "correct"
                    sheet_results["correct"] += 1
                    results["overall"]["correct"] += 1
                else:
                    status = "wrong"
                    sheet_results["wrong"] += 1
                    results["overall"]["wrong"] += 1

            results["overall"]["total"] += 1
            icon = {"correct": "v", "refused": "o", "wrong": "x"}[status]
            print(f"  [{icon}] Q: {question}")
            print(f"      Expected: {expected} {expected_unit or ''}")
            print(f"      Got:      {actual}")
            print()

            sheet_results["questions"].append({
                "question": question,
                "expected": f"{expected} {expected_unit or ''}".strip(),
                "actual": actual,
                "status": status,
            })

        total_q = len(qa_pairs)
        accuracy = sheet_results["correct"] / total_q if total_q > 0 else 0
        refuse_rate = sheet_results["refused"] / total_q if total_q > 0 else 0
        sheet_results["accuracy"] = round(accuracy, 3)
        sheet_results["refuse_rate"] = round(refuse_rate, 3)
        results["datasheets"][pdf_name] = sheet_results

        print(f"  Summary for {pdf_name}: "
              f"{sheet_results['correct']}/{total_q} correct "
              f"({accuracy:.0%} accuracy), "
              f"{sheet_results['refused']} refused ({refuse_rate:.0%})")

    total = results["overall"]["total"]
    if total > 0:
        results["overall"]["accuracy"] = round(results["overall"]["correct"] / total, 3)
        results["overall"]["refuse_rate"] = round(results["overall"]["refused"] / total, 3)
    else:
        results["overall"]["accuracy"] = 0
        results["overall"]["refuse_rate"] = 0

    return results


def main() -> None:
    print("\n" + "=" * 60)
    print("  Akili Datasheet Benchmark Suite")
    print("=" * 60)

    results = run_benchmark()

    print("\n" + "=" * 60)
    print("  OVERALL RESULTS")
    print("=" * 60)
    o = results["overall"]
    print(f"  Total questions: {o['total']}")
    print(f"  Correct:         {o['correct']} ({o['accuracy']:.0%})")
    print(f"  Refused:         {o['refused']} ({o['refuse_rate']:.0%})")
    print(f"  Wrong:           {o['wrong']}")
    print()

    output_path = Path(__file__).parent / "results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"  Results saved to: {output_path}")


if __name__ == "__main__":
    main()
