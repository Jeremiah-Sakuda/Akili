"""
Correction pattern analyzer (C4).

Analyses the correction log to identify systematic extraction errors:
- Manufacturer-specific biases (e.g. "Gemini consistently misreads thermal resistance in AD datasheets")
- Parameter-specific errors (e.g. "max current values are often off by 10x due to unit confusion")
- Auto-correction rules: when a correction pattern is seen N+ times, apply automatically

The pattern data is the foundation for any future learning mechanism (ART or otherwise).
"""

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from akili.store.corrections import Correction, CorrectionStore

logger = logging.getLogger(__name__)

_MIN_PATTERN_OCCURRENCES = 3
_AUTO_CORRECT_CONFIDENCE_THRESHOLD = 5


@dataclass
class CorrectionPattern:
    """A systematic error pattern detected in the correction log."""

    pattern_id: str
    description: str
    category: str
    original_pattern: str
    corrected_pattern: str
    occurrences: int
    doc_ids: list[str] = field(default_factory=list)
    canonical_types: list[str] = field(default_factory=list)
    confidence: float = 0.0
    auto_correctable: bool = False

    @property
    def is_reliable(self) -> bool:
        return self.occurrences >= _MIN_PATTERN_OCCURRENCES


@dataclass
class AutoCorrectionRule:
    """A rule derived from repeated correction patterns for automatic application."""

    rule_id: str
    pattern: CorrectionPattern
    match_fn_description: str
    times_applied: int = 0


class PatternAnalyzer:
    """Analyze correction logs to find systematic errors and build auto-correction rules."""

    def __init__(self, correction_store: CorrectionStore):
        self.store = correction_store

    def analyze_all(self) -> list[CorrectionPattern]:
        """Analyze all corrections across all documents for patterns."""
        corrections = self._get_all_corrections()
        if not corrections:
            return []

        patterns: list[CorrectionPattern] = []
        patterns.extend(self._analyze_unit_confusion(corrections))
        patterns.extend(self._analyze_value_scaling(corrections))
        patterns.extend(self._analyze_label_misread(corrections))
        patterns.extend(self._analyze_by_canonical_type(corrections))

        patterns.sort(key=lambda p: p.occurrences, reverse=True)
        return patterns

    def analyze_by_doc(self, doc_id: str) -> list[CorrectionPattern]:
        """Analyze corrections for a specific document."""
        corrections = self.store.get_corrections_by_doc(doc_id)
        active = [c for c in corrections if c.action == "correct"]
        if not active:
            return []

        patterns: list[CorrectionPattern] = []
        patterns.extend(self._analyze_unit_confusion(active))
        patterns.extend(self._analyze_value_scaling(active))
        patterns.extend(self._analyze_label_misread(active))
        return patterns

    def get_auto_correction_rules(self) -> list[AutoCorrectionRule]:
        """Build auto-correction rules from high-confidence patterns."""
        patterns = self.analyze_all()
        rules = []
        for p in patterns:
            if p.occurrences >= _AUTO_CORRECT_CONFIDENCE_THRESHOLD and p.auto_correctable:
                rules.append(AutoCorrectionRule(
                    rule_id=f"auto_{p.pattern_id}",
                    pattern=p,
                    match_fn_description=f"When original matches '{p.original_pattern}', correct to '{p.corrected_pattern}'",
                ))
        return rules

    def suggest_correction(
        self,
        canonical_type: str,
        original_value: str,
    ) -> str | None:
        """
        Given an extracted value, check if any auto-correction rule applies.
        Returns corrected value or None if no rule matches.
        """
        rules = self.get_auto_correction_rules()
        for rule in rules:
            pat = rule.pattern
            if pat.category == "unit_confusion" and canonical_type in pat.canonical_types:
                if _is_unit_confusion_match(original_value, pat.original_pattern):
                    return _apply_unit_correction(original_value, pat.corrected_pattern)
            if pat.category == "value_scaling" and canonical_type in pat.canonical_types:
                if _is_scaling_match(original_value, pat.original_pattern):
                    return _apply_scaling_correction(original_value, pat.original_pattern, pat.corrected_pattern)
        return None

    def get_pattern_stats(self) -> dict:
        """Summary statistics of detected patterns."""
        patterns = self.analyze_all()
        return {
            "total_patterns": len(patterns),
            "auto_correctable": sum(1 for p in patterns if p.auto_correctable),
            "reliable_patterns": sum(1 for p in patterns if p.is_reliable),
            "categories": dict(Counter(p.category for p in patterns)),
            "top_patterns": [
                {
                    "id": p.pattern_id,
                    "description": p.description,
                    "occurrences": p.occurrences,
                    "auto_correctable": p.auto_correctable,
                }
                for p in patterns[:10]
            ],
        }

    def _get_all_corrections(self) -> list[Correction]:
        """Retrieve all corrections from the store."""
        with self.store._conn() as c:
            rows = c.execute(
                "SELECT id, doc_id, canonical_id, canonical_type, action, "
                "original_value, corrected_value, corrected_by, notes, created_at "
                "FROM corrections WHERE action = 'correct' ORDER BY created_at",
            ).fetchall()
        return [
            Correction(
                id=r[0], doc_id=r[1], canonical_id=r[2], canonical_type=r[3],
                action=r[4], original_value=r[5], corrected_value=r[6],
                corrected_by=r[7], notes=r[8], created_at=r[9],
            )
            for r in rows
        ]

    def _analyze_unit_confusion(self, corrections: list[Correction]) -> list[CorrectionPattern]:
        """Detect when the same unit confusion occurs repeatedly (e.g. mV → V)."""
        unit_swaps: dict[str, list[Correction]] = defaultdict(list)

        for c in corrections:
            orig_unit = _extract_unit(c.original_value)
            corr_unit = _extract_unit(c.corrected_value or "")
            if orig_unit and corr_unit and orig_unit != corr_unit:
                key = f"{orig_unit}->{corr_unit}"
                unit_swaps[key].append(c)

        patterns = []
        for swap, corrs in unit_swaps.items():
            orig_u, corr_u = swap.split("->")
            patterns.append(CorrectionPattern(
                pattern_id=f"unit_swap_{orig_u}_{corr_u}",
                description=f"Unit confusion: {orig_u} extracted as {corr_u} ({len(corrs)} times)",
                category="unit_confusion",
                original_pattern=orig_u,
                corrected_pattern=corr_u,
                occurrences=len(corrs),
                doc_ids=list({c.doc_id for c in corrs}),
                canonical_types=list({c.canonical_type for c in corrs}),
                confidence=min(1.0, len(corrs) / 10.0),
                auto_correctable=len(corrs) >= _AUTO_CORRECT_CONFIDENCE_THRESHOLD,
            ))
        return patterns

    def _analyze_value_scaling(self, corrections: list[Correction]) -> list[CorrectionPattern]:
        """Detect consistent scaling errors (e.g. values off by 10x or 1000x)."""
        scale_factors: dict[str, list[Correction]] = defaultdict(list)

        for c in corrections:
            orig_num = _extract_number(c.original_value)
            corr_num = _extract_number(c.corrected_value or "")
            if orig_num is not None and corr_num is not None and corr_num != 0:
                ratio = orig_num / corr_num
                for factor_label, factor_range in [
                    ("10x", (9.0, 11.0)),
                    ("100x", (90.0, 110.0)),
                    ("1000x", (900.0, 1100.0)),
                    ("0.1x", (0.09, 0.11)),
                    ("0.01x", (0.009, 0.011)),
                    ("0.001x", (0.0009, 0.0011)),
                ]:
                    if factor_range[0] <= ratio <= factor_range[1]:
                        scale_factors[factor_label].append(c)
                        break

        patterns = []
        for factor, corrs in scale_factors.items():
            patterns.append(CorrectionPattern(
                pattern_id=f"scale_{factor}",
                description=f"Value off by {factor} ({len(corrs)} times)",
                category="value_scaling",
                original_pattern=factor,
                corrected_pattern=f"divide_by_{factor}" if "x" in factor and not factor.startswith("0.") else f"multiply_by_{factor}",
                occurrences=len(corrs),
                doc_ids=list({c.doc_id for c in corrs}),
                canonical_types=list({c.canonical_type for c in corrs}),
                confidence=min(1.0, len(corrs) / 10.0),
                auto_correctable=len(corrs) >= _AUTO_CORRECT_CONFIDENCE_THRESHOLD,
            ))
        return patterns

    def _analyze_label_misread(self, corrections: list[Correction]) -> list[CorrectionPattern]:
        """Detect when the same label is consistently misread."""
        label_swaps: dict[str, list[Correction]] = defaultdict(list)

        for c in corrections:
            orig = c.original_value.strip().lower()
            corr = (c.corrected_value or "").strip().lower()
            if orig and corr and orig != corr:
                if not _extract_number(orig) and not _extract_number(corr):
                    key = f"{orig}|{corr}"
                    label_swaps[key].append(c)

        patterns = []
        for swap, corrs in label_swaps.items():
            orig, corr = swap.split("|")
            if len(corrs) >= 2:
                patterns.append(CorrectionPattern(
                    pattern_id=f"label_swap_{orig[:20]}_{corr[:20]}",
                    description=f"Label misread: '{orig}' → '{corr}' ({len(corrs)} times)",
                    category="label_misread",
                    original_pattern=orig,
                    corrected_pattern=corr,
                    occurrences=len(corrs),
                    doc_ids=list({c.doc_id for c in corrs}),
                    canonical_types=list({c.canonical_type for c in corrs}),
                    confidence=min(1.0, len(corrs) / 8.0),
                    auto_correctable=len(corrs) >= _AUTO_CORRECT_CONFIDENCE_THRESHOLD,
                ))
        return patterns

    def _analyze_by_canonical_type(self, corrections: list[Correction]) -> list[CorrectionPattern]:
        """Detect if certain canonical types have disproportionately high correction rates."""
        by_type: dict[str, int] = Counter(c.canonical_type for c in corrections)
        total = len(corrections)
        if total < 5:
            return []

        patterns = []
        for ctype, count in by_type.items():
            rate = count / total
            if rate > 0.3 and count >= 3:
                patterns.append(CorrectionPattern(
                    pattern_id=f"type_bias_{ctype}",
                    description=f"High correction rate for {ctype}: {count}/{total} ({rate:.0%})",
                    category="type_bias",
                    original_pattern=ctype,
                    corrected_pattern="",
                    occurrences=count,
                    doc_ids=list({c.doc_id for c in corrections if c.canonical_type == ctype}),
                    canonical_types=[ctype],
                    confidence=rate,
                    auto_correctable=False,
                ))
        return patterns


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UNIT_RE = re.compile(r"[a-zA-Z°µ]+/?[a-zA-Z°]*$")
_NUM_RE = re.compile(r"[-+]?\d*\.?\d+")


def _extract_unit(value: str) -> str | None:
    m = _UNIT_RE.search(value.strip())
    return m.group(0).lower() if m else None


def _extract_number(value: str) -> float | None:
    m = _NUM_RE.search(value.strip())
    if m:
        try:
            return float(m.group(0))
        except ValueError:
            return None
    return None


def _is_unit_confusion_match(value: str, orig_unit: str) -> bool:
    extracted = _extract_unit(value)
    return extracted == orig_unit.lower() if extracted else False


def _apply_unit_correction(value: str, correct_unit: str) -> str:
    m = _UNIT_RE.search(value.strip())
    if m:
        return value[:m.start()] + correct_unit + value[m.end():]
    return value


def _is_scaling_match(value: str, factor_label: str) -> bool:
    return _extract_number(value) is not None


def _apply_scaling_correction(value: str, orig_factor: str, correction_desc: str) -> str:
    num = _extract_number(value)
    if num is None:
        return value

    factor_map = {"10x": 10, "100x": 100, "1000x": 1000, "0.1x": 0.1, "0.01x": 0.01, "0.001x": 0.001}
    factor = factor_map.get(orig_factor, 1)

    if "divide" in correction_desc:
        corrected = num / factor
    else:
        corrected = num * factor

    unit = _extract_unit(value) or ""
    if corrected == int(corrected):
        return f"{int(corrected)} {unit}".strip()
    return f"{corrected:.6g} {unit}".strip()
