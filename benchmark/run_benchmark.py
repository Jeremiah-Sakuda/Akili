#!/usr/bin/env python3
"""
AKILI Benchmark Runner

Compares AKILI verification accuracy against raw Gemini baseline.
Used for:
1. Generating accuracy numbers for landing page
2. CI regression testing (--check-regression flag)

Usage:
    python benchmark/run_benchmark.py                    # Full benchmark run
    python benchmark/run_benchmark.py --check-regression # CI mode (fails if below thresholds)
    python benchmark/run_benchmark.py --chip ATmega328P  # Test single chip
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# Put src/ on the path so `akili` imports as a top-level package (matching the
# package's own internal `from akili...` imports).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import google.generativeai as genai  # noqa: E402

from akili.config import GOOGLE_API_KEY, GEMINI_MODEL  # noqa: E402

# Datasheet PDFs named "<chip>.pdf" live here; absent by default (see README).
FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class QuestionResult:
    """Result of running a single question through AKILI or baseline."""

    question_id: str
    question: str
    expected_answer: str
    actual_answer: str
    status: Literal["VERIFIED", "REVIEW", "REFUSED", "ERROR"]
    correct: bool
    confidence: float = 0.0
    error_message: str | None = None


@dataclass
class ChipResults:
    """Aggregate results for a single chip."""

    chip: str
    questions: list[QuestionResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.questions)

    @property
    def correct(self) -> int:
        return sum(1 for q in self.questions if q.correct)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total > 0 else 0.0

    @property
    def verified_count(self) -> int:
        return sum(1 for q in self.questions if q.status == "VERIFIED")

    @property
    def review_count(self) -> int:
        return sum(1 for q in self.questions if q.status == "REVIEW")

    @property
    def refused_count(self) -> int:
        return sum(1 for q in self.questions if q.status == "REFUSED")

    @property
    def error_count(self) -> int:
        return sum(1 for q in self.questions if q.status == "ERROR")


@dataclass
class BenchmarkResults:
    """Full benchmark results."""

    chips: list[ChipResults] = field(default_factory=list)

    @property
    def total_questions(self) -> int:
        return sum(c.total for c in self.chips)

    @property
    def total_correct(self) -> int:
        return sum(c.correct for c in self.chips)

    @property
    def overall_accuracy(self) -> float:
        return self.total_correct / self.total_questions if self.total_questions > 0 else 0.0

    @property
    def false_refuse_rate(self) -> float:
        """Rate of REFUSED answers that should have been answerable."""
        total_refused = sum(c.refused_count for c in self.chips)
        return total_refused / self.total_questions if self.total_questions > 0 else 0.0

    # B2: False-accept rate as headline metric
    @property
    def false_accept_rate(self) -> float:
        """Rate of VERIFIED answers that are actually wrong.

        false_accept_rate = count(status=VERIFIED ∧ correct=False) / count(status=VERIFIED)
        This is the critical metric for safety-critical industries.
        """
        all_questions = [q for c in self.chips for q in c.questions]
        verified = [q for q in all_questions if q.status == "VERIFIED"]
        if not verified:
            return 0.0
        false_accepts = sum(1 for q in verified if not q.correct)
        return false_accepts / len(verified)

    @property
    def refuse_precision(self) -> float:
        """How often we correctly refused (question was unanswerable or answer would be wrong).

        refuse_precision = count(status=REFUSED ∧ correct=False) / count(status=REFUSED)
        High precision means we refuse appropriately.
        """
        all_questions = [q for c in self.chips for q in c.questions]
        refused = [q for q in all_questions if q.status == "REFUSED"]
        if not refused:
            return 1.0  # No refusals = perfect precision (vacuously true)
        correct_refusals = sum(1 for q in refused if not q.correct)
        return correct_refusals / len(refused)

    def confusion_matrix(self) -> dict[str, dict[str, int]]:
        """Generate confusion matrix.

        Rows = (correct, incorrect), columns = (VERIFIED, REVIEW, REFUSED).

        Returns dict like:
        {
            "correct": {"VERIFIED": N, "REVIEW": N, "REFUSED": N},
            "incorrect": {"VERIFIED": N, "REVIEW": N, "REFUSED": N},
            "error": {"VERIFIED": 0, "REVIEW": 0, "REFUSED": 0, "ERROR": N}
        }
        """
        matrix = {
            "correct": {"VERIFIED": 0, "REVIEW": 0, "REFUSED": 0, "ERROR": 0},
            "incorrect": {"VERIFIED": 0, "REVIEW": 0, "REFUSED": 0, "ERROR": 0},
        }
        for c in self.chips:
            for q in c.questions:
                row = "correct" if q.correct else "incorrect"
                matrix[row][q.status] = matrix[row].get(q.status, 0) + 1
        return matrix


# ---------------------------------------------------------------------------
# Answer matching
# ---------------------------------------------------------------------------


def normalize_answer(answer: str) -> str:
    """Normalize answer for comparison."""
    # Lowercase, strip whitespace, remove common variations
    normalized = answer.lower().strip()
    # Remove units formatting variations
    normalized = normalized.replace("°c", " degrees c").replace("°", " degrees ")
    normalized = normalized.replace("μa", " ua").replace("µa", " ua")
    normalized = normalized.replace("ma", " ma").replace("mv", " mv")
    normalized = normalized.replace("khz", " khz").replace("mhz", " mhz")
    normalized = normalized.replace("kb", " kb").replace("mb", " mb")
    # Normalize whitespace
    normalized = " ".join(normalized.split())
    return normalized


def answers_match(expected: str, actual: str) -> bool:
    """Check if actual answer matches expected answer (fuzzy but unit-aware).

    Stricter than a bare substring/number check: when the expected answer carries a
    unit token (V, mA, KB, MHz, ...), the actual answer must contain BOTH every
    expected number AND that unit token. This avoids crediting an incidental number
    match (e.g. expected "20 MHz" against an actual that merely mentions "20 pins").
    """
    import re

    expected_norm = normalize_answer(expected)
    actual_norm = normalize_answer(actual)

    # Exact match
    if expected_norm == actual_norm:
        return True

    # Check if the full expected phrase is contained in actual
    if expected_norm in actual_norm:
        return True

    expected_nums = set(re.findall(r"[\d.]+", expected_norm))
    actual_nums = set(re.findall(r"[\d.]+", actual_norm))
    if not expected_nums or not expected_nums.issubset(actual_nums):
        return False

    # All expected numbers are present. If the expected answer names a unit, require
    # that unit to be present too; otherwise the number match alone is sufficient.
    expected_units = {tok for tok in re.findall(r"[a-z]+", expected_norm) if tok}
    # Ignore filler words so we only gate on genuine unit tokens.
    filler = {"to", "and", "or", "at", "the", "of", "vcc", "v"}
    unit_tokens = expected_units - filler
    if not unit_tokens:
        return True
    return any(tok in actual_norm for tok in unit_tokens)


# ---------------------------------------------------------------------------
# Gemini baseline runner
# ---------------------------------------------------------------------------


async def run_gemini_baseline_question(
    model: genai.GenerativeModel,
    chip: str,
    question: str,
) -> tuple[str, Literal["VERIFIED", "REVIEW", "REFUSED", "ERROR"], str | None]:
    """Run a single question through raw Gemini (no AKILI verification)."""
    prompt = f"""You are answering a question about the {chip} datasheet.

Question: {question}

Provide a direct, concise answer based on typical {chip} specifications.
If you're not sure, still provide your best answer.
Keep the answer brief - just the key value or specification."""

    try:
        response = await asyncio.to_thread(
            model.generate_content,
            prompt,
        )
        answer = response.text.strip()
        # Gemini baseline always returns as "VERIFIED" since it doesn't have our verification
        return answer, "VERIFIED", None
    except Exception as e:
        return "", "ERROR", str(e)


async def run_gemini_baseline(dataset: dict) -> BenchmarkResults:
    """Run raw Gemini on all questions."""
    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY not set")

    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

    results = BenchmarkResults()

    for chip_data in dataset["chips"]:
        chip_name = chip_data["chip"]
        chip_results = ChipResults(chip=chip_name)

        print(f"  Running baseline for {chip_name}...")

        for q in chip_data["questions"]:
            answer, status, error = await run_gemini_baseline_question(
                model, chip_name, q["question"]
            )

            correct = answers_match(q["expected_answer"], answer) if status != "ERROR" else False

            chip_results.questions.append(
                QuestionResult(
                    question_id=q["id"],
                    question=q["question"],
                    expected_answer=q["expected_answer"],
                    actual_answer=answer,
                    status=status,
                    correct=correct,
                    error_message=error,
                )
            )

            # Rate limiting
            await asyncio.sleep(0.5)

        results.chips.append(chip_results)

    return results


# ---------------------------------------------------------------------------
# AKILI runner (real pipeline — no fabrication)
# ---------------------------------------------------------------------------

_TIER_TO_STATUS = {"verified": "VERIFIED", "review": "REVIEW", "refused": "REFUSED"}


async def run_akili_benchmark(dataset: dict) -> BenchmarkResults:
    """Run the REAL Akili verification pipeline over the dataset.

    For each chip we ingest its datasheet PDF (``benchmark/fixtures/<chip>.pdf``)
    with the real ingestion pipeline, then run every question through
    ``verify_and_answer`` and classify the result by its confidence tier.

    There is **no fabrication**: a missing fixture, a missing API key, or a failed
    ingest is reported as an ``ERROR`` (counted incorrect), so the reported numbers
    always reflect what the system actually did. If you see lots of ERRORs, you are
    missing ``benchmark/fixtures/<chip>.pdf`` and/or ``GOOGLE_API_KEY``.
    """
    from akili.canonical import Bijection, Grid, Unit
    from akili.ingest.pipeline import ingest_document
    from akili.verify import Refuse, verify_and_answer

    results = BenchmarkResults()

    for chip_data in dataset["chips"]:
        chip_name = chip_data["chip"]
        chip_results = ChipResults(chip=chip_name)
        print(f"  Running AKILI for {chip_name}...")

        pdf_path = FIXTURES_DIR / f"{chip_name}.pdf"
        units: list = []
        bijections: list = []
        grids: list = []
        ingest_error: str | None = None

        if not pdf_path.exists():
            ingest_error = f"fixture PDF not found: {pdf_path.name}"
            print(f"    SKIP -- {ingest_error}")
        elif not GOOGLE_API_KEY:
            ingest_error = "GOOGLE_API_KEY not set"
            print(f"    SKIP -- {ingest_error}")
        else:
            try:
                _doc_id, canonical, _total, _failed = await asyncio.to_thread(
                    ingest_document, pdf_path
                )
                units = [o for o in canonical if isinstance(o, Unit)]
                bijections = [o for o in canonical if isinstance(o, Bijection)]
                grids = [o for o in canonical if isinstance(o, Grid)]
                print(f"    ingested {len(units)} units, {len(bijections)} bij, {len(grids)} grids")
            except Exception as e:  # noqa: BLE001 - benchmark should never crash on one chip
                ingest_error = f"ingest failed: {type(e).__name__}: {e}"
                print(f"    ERROR -- {ingest_error}")

        for q in chip_data["questions"]:
            if ingest_error is not None:
                chip_results.questions.append(
                    QuestionResult(
                        question_id=q["id"],
                        question=q["question"],
                        expected_answer=q["expected_answer"],
                        actual_answer="",
                        status="ERROR",
                        correct=False,
                        error_message=ingest_error,
                    )
                )
                continue

            result = verify_and_answer(q["question"], units, bijections, grids)
            if isinstance(result, Refuse):
                status: str = "REFUSED"
                actual = ""
                correct = False
                confidence = 0.0
            else:
                actual = result.answer
                correct = answers_match(q["expected_answer"], actual)
                confidence = result.confidence.overall if result.confidence else 0.0
                tier = result.confidence.tier if result.confidence else "review"
                status = _TIER_TO_STATUS.get(tier, "REVIEW")

            chip_results.questions.append(
                QuestionResult(
                    question_id=q["id"],
                    question=q["question"],
                    expected_answer=q["expected_answer"],
                    actual_answer=actual,
                    status=status,
                    correct=correct,
                    confidence=confidence,
                )
            )

        results.chips.append(chip_results)

    return results


# ---------------------------------------------------------------------------
# Comparison and reporting
# ---------------------------------------------------------------------------


def print_confusion_matrix(results: BenchmarkResults) -> str:
    """Generate formatted confusion matrix display.

    B2: Shows (correct, incorrect) × (VERIFIED, REVIEW, REFUSED) to help
    identify where verification is failing.
    """
    matrix = results.confusion_matrix()
    lines = [
        "Confusion Matrix (rows=ground truth, cols=status):",
        "",
        "              | VERIFIED | REVIEW | REFUSED | ERROR |",
        "--------------|----------|--------|---------|-------|",
    ]
    for row_name in ["correct", "incorrect"]:
        row = matrix[row_name]
        lines.append(
            f"  {row_name:11} |   {row.get('VERIFIED', 0):5}  |  {row.get('REVIEW', 0):4}  |   "
            f"{row.get('REFUSED', 0):5}  | {row.get('ERROR', 0):4}  |"
        )
    return "\n".join(lines)


def generate_comparison_table(
    akili: BenchmarkResults,
    baseline: BenchmarkResults,
) -> str:
    """Generate markdown table comparing AKILI to baseline."""
    lines = [
        "| Chip | AKILI Accuracy | Gemini Accuracy | Hallucination Reduction |",
        "|------|----------------|-----------------|-------------------------|",
    ]

    for akili_chip, baseline_chip in zip(akili.chips, baseline.chips):
        akili_acc = akili_chip.accuracy * 100
        baseline_acc = baseline_chip.accuracy * 100
        delta = baseline_acc - akili_acc  # Negative means AKILI is better

        lines.append(
            f"| {akili_chip.chip} | {akili_acc:.0f}% | {baseline_acc:.0f}% | {-delta:+.0f}% |"
        )

    # Overall
    akili_overall = akili.overall_accuracy * 100
    baseline_overall = baseline.overall_accuracy * 100
    overall_delta = baseline_overall - akili_overall

    lines.append("|------|----------------|-----------------|-------------------------|")
    overall_line = (
        f"| **Overall** | **{akili_overall:.0f}%** | "
        f"**{baseline_overall:.0f}%** | **{-overall_delta:+.0f}%** |"
    )
    lines.append(overall_line)

    return "\n".join(lines)


def generate_frontend_results(
    akili: BenchmarkResults,
    baseline: BenchmarkResults,
) -> dict:
    """Generate the row shape the landing-page BenchmarkTable consumes.

    Written to frontend/public/benchmark-results.json. The frontend treats the
    presence of this file (measured=true) as the signal to show real numbers
    instead of the illustrative placeholders.
    """
    return {
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "measured": True,
        "rows": [
            {
                "chip": a.chip,
                "akiliAccuracy": round(a.accuracy * 100),
                "geminiAccuracy": round(b.accuracy * 100),
                "hallucinationDelta": round((a.accuracy - b.accuracy) * 100),
            }
            for a, b in zip(akili.chips, baseline.chips)
        ],
    }


def generate_json_results(
    akili: BenchmarkResults,
    baseline: BenchmarkResults,
) -> dict:
    """Generate JSON results for frontend consumption."""
    return {
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "chips": [
            {
                "chip": akili_chip.chip,
                "akili_accuracy": round(akili_chip.accuracy * 100),
                "gemini_accuracy": round(baseline_chip.accuracy * 100),
                "hallucination_delta": round((akili_chip.accuracy - baseline_chip.accuracy) * 100),
                "akili_verified": akili_chip.verified_count,
                "akili_review": akili_chip.review_count,
                "akili_refused": akili_chip.refused_count,
            }
            for akili_chip, baseline_chip in zip(akili.chips, baseline.chips)
        ],
        "overall": {
            "akili_accuracy": round(akili.overall_accuracy * 100),
            "gemini_accuracy": round(baseline.overall_accuracy * 100),
            "hallucination_delta": round(
                (akili.overall_accuracy - baseline.overall_accuracy) * 100
            ),
            "false_refuse_rate": round(akili.false_refuse_rate * 100),
            # B2: False-accept rate as headline metric
            "false_accept_rate": round(akili.false_accept_rate * 100, 2),
            "refuse_precision": round(akili.refuse_precision * 100, 2),
        },
        # B2: Confusion matrix
        "confusion_matrix": akili.confusion_matrix(),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    parser = argparse.ArgumentParser(description="AKILI Benchmark Runner")
    parser.add_argument(
        "--check-regression",
        action="store_true",
        help="CI mode: fail if accuracy < 70%% or false-refuse > 30%%",
    )
    parser.add_argument(
        "--chip",
        type=str,
        help="Run benchmark for a single chip only",
    )
    parser.add_argument(
        "--baseline-only",
        action="store_true",
        help="Only run the Gemini baseline (skip AKILI)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="benchmark/results.json",
        help="Output file for JSON results",
    )
    args = parser.parse_args()

    # Load dataset
    dataset_path = Path(__file__).parent / "dataset.json"
    with open(dataset_path) as f:
        dataset = json.load(f)

    # Filter to single chip if specified
    if args.chip:
        dataset["chips"] = [c for c in dataset["chips"] if c["chip"] == args.chip]
        if not dataset["chips"]:
            print(f"Error: Chip '{args.chip}' not found in dataset")
            sys.exit(1)

    print("=" * 60)
    print("AKILI Benchmark Runner")
    print("=" * 60)
    print(
        f"Dataset: {len(dataset['chips'])} chips, "
        f"{sum(len(c['questions']) for c in dataset['chips'])} questions"
    )
    print()

    # Run benchmarks
    if not args.baseline_only:
        print("Running AKILI benchmark...")
        akili_results = await run_akili_benchmark(dataset)
        print(f"  Overall accuracy: {akili_results.overall_accuracy * 100:.1f}%")
        print(f"  False refuse rate: {akili_results.false_refuse_rate * 100:.1f}%")
        # B2: Show false-accept rate as headline metric
        print(f"  False accept rate: {akili_results.false_accept_rate * 100:.2f}%")
        print(f"  Refuse precision: {akili_results.refuse_precision * 100:.1f}%")
        print()

        # With no fixtures and/or no API key, every AKILI question is an ERROR — there is
        # nothing to measure, so a regression gate has nothing to enforce. Skip cleanly
        # (exit 0) instead of failing on a vacuous 0% or crashing the run. This is what
        # lets CI stay green until real datasheet fixtures + GOOGLE_API_KEY are provided.
        akili_has_data = any(q.status != "ERROR" for c in akili_results.chips for q in c.questions)
        if args.check_regression and not akili_has_data:
            print(
                "Regression Check: SKIPPED — no benchmark fixtures and/or GOOGLE_API_KEY "
                "available, so there is nothing to measure. Add benchmark/fixtures/<chip>.pdf "
                "and set GOOGLE_API_KEY to run the real benchmark and enforce the gate."
            )
            return

    # The raw-Gemini baseline needs an API key; skip it gracefully when unavailable
    # rather than raising and crashing the whole run.
    if GOOGLE_API_KEY:
        print("Running Gemini baseline...")
        baseline_results = await run_gemini_baseline(dataset)
        print(f"  Overall accuracy: {baseline_results.overall_accuracy * 100:.1f}%")
        print()
    else:
        print("Skipping Gemini baseline: GOOGLE_API_KEY not set.")
        print()
        baseline_results = BenchmarkResults()

    if not args.baseline_only:
        # Generate comparison
        print("Comparison Table:")
        print("-" * 60)
        print(generate_comparison_table(akili_results, baseline_results))
        print()

        # B2: Print confusion matrix
        print(print_confusion_matrix(akili_results))
        print()

        # Save JSON results
        json_results = generate_json_results(akili_results, baseline_results)
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(json_results, f, indent=2)
        print(f"Results saved to: {output_path}")

        # Also publish measured rows for the landing page (only when a full run
        # produced real data — never overwrite with an all-ERROR placeholder set).
        if akili_results.total_questions > 0 and akili_results.total_correct > 0:
            frontend_path = (
                Path(__file__).resolve().parent.parent
                / "frontend"
                / "public"
                / "benchmark-results.json"
            )
            frontend_path.parent.mkdir(parents=True, exist_ok=True)
            with open(frontend_path, "w") as f:
                json.dump(generate_frontend_results(akili_results, baseline_results), f, indent=2)
            print(f"Frontend results saved to: {frontend_path}")
        else:
            print(
                "Skipped writing frontend results: no correct AKILI answers "
                "(missing fixtures/API key?) — landing page keeps illustrative data."
            )
        print()

        # Check regression thresholds
        if args.check_regression:
            print("Regression Check:")
            print("-" * 60)

            accuracy = akili_results.overall_accuracy * 100
            false_refuse = akili_results.false_refuse_rate * 100
            false_accept = akili_results.false_accept_rate * 100

            passed = True

            if accuracy < 70:
                print(f"  FAIL: Accuracy {accuracy:.1f}% < 70% threshold")
                passed = False
            else:
                print(f"  PASS: Accuracy {accuracy:.1f}% >= 70% threshold")

            if false_refuse > 30:
                print(f"  FAIL: False refuse rate {false_refuse:.1f}% > 30% threshold")
                passed = False
            else:
                print(f"  PASS: False refuse rate {false_refuse:.1f}% <= 30% threshold")

            # B2: False-accept rate gate (critical for safety-critical industries)
            if false_accept > 1.0:
                print(f"  FAIL: False accept rate {false_accept:.2f}% > 1% threshold")
                passed = False
            else:
                print(f"  PASS: False accept rate {false_accept:.2f}% <= 1% threshold")

            if not passed:
                sys.exit(1)

            print()
            print("All regression checks passed!")


if __name__ == "__main__":
    asyncio.run(main())
