"""
Z3-based quality checks for canonical data.

Three narrow checks:
1. Unit normalization: 4.2V == 4200mV == 0.0042kV
2. Contradiction detection: same parameter, different values across pages
3. Range consistency: min <= typ <= max for all Range objects

Requires z3-solver (pip install z3-solver). Degrades gracefully if not installed.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

try:
    from z3 import Real, Solver, sat
    Z3_AVAILABLE = True
except ImportError:
    Z3_AVAILABLE = False
    logger.info("z3-solver not installed; Z3 checks disabled")

# ---------------------------------------------------------------------------
# Unit conversion table: (unit_string) -> (base_unit, multiplier)
# ---------------------------------------------------------------------------

_UNIT_CONVERSIONS: dict[str, tuple[str, float]] = {
    "V": ("V", 1.0),
    "mV": ("V", 1e-3),
    "uV": ("V", 1e-6),
    "kV": ("V", 1e3),
    "A": ("A", 1.0),
    "mA": ("A", 1e-3),
    "uA": ("A", 1e-6),
    "nA": ("A", 1e-9),
    "W": ("W", 1.0),
    "mW": ("W", 1e-3),
    "Hz": ("Hz", 1.0),
    "kHz": ("Hz", 1e3),
    "MHz": ("Hz", 1e6),
    "GHz": ("Hz", 1e9),
    "s": ("s", 1.0),
    "ms": ("s", 1e-3),
    "us": ("s", 1e-6),
    "ns": ("s", 1e-9),
    "ps": ("s", 1e-12),
    "F": ("F", 1.0),
    "mF": ("F", 1e-3),
    "uF": ("F", 1e-6),
    "nF": ("F", 1e-9),
    "pF": ("F", 1e-12),
    "Ohm": ("Ohm", 1.0),
    "kOhm": ("Ohm", 1e3),
    "MOhm": ("Ohm", 1e6),
    "C": ("C", 1.0),
    "mm": ("mm", 1.0),
    "cm": ("mm", 10.0),
    "m": ("mm", 1000.0),
    "in": ("mm", 25.4),
    "mil": ("mm", 0.0254),
    "mAh": ("mAh", 1.0),
    "Ah": ("mAh", 1000.0),
}

# Aliases for unicode/symbol variants
_UNIT_ALIASES: dict[str, str] = {
    "\u03a9": "Ohm",     # Ω
    "k\u03a9": "kOhm",
    "M\u03a9": "MOhm",
    "\u00b5V": "uV",     # µV
    "\u00b5A": "uA",
    "\u00b5F": "uF",
    "\u00b5s": "us",
    "\u00b0C": "C",       # °C
    "degC": "C",
}


def _normalize_unit(unit_str: str) -> str:
    """Normalize a unit string to a canonical form."""
    unit_str = unit_str.strip()
    return _UNIT_ALIASES.get(unit_str, unit_str)


def _to_base(value: float, unit_str: str) -> tuple[float, str] | None:
    """Convert value+unit to (base_value, base_unit). None if unit unknown."""
    norm = _normalize_unit(unit_str)
    conv = _UNIT_CONVERSIONS.get(norm)
    if conv is None:
        return None
    base_unit, multiplier = conv
    return value * multiplier, base_unit


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class Z3Issue:
    """A single issue found by Z3 checks."""
    check_type: str  # "unit_normalization", "contradiction", "range_consistency"
    severity: str    # "error", "warning"
    message: str
    source_ids: list[str] = field(default_factory=list)
    page: int | None = None


@dataclass
class Z3CheckResult:
    """Aggregate result from all Z3 checks on a document."""
    issues: list[Z3Issue] = field(default_factory=list)
    checks_run: int = 0
    z3_available: bool = Z3_AVAILABLE

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == "warning" for i in self.issues)


# ---------------------------------------------------------------------------
# Check 1: Unit normalization
# ---------------------------------------------------------------------------

def _check_unit_normalization(units: list) -> list[Z3Issue]:
    """Verify that extracted values are dimensionally consistent.

    For each unit with a numeric value and known unit_of_measure, convert to
    base units and verify the conversion is consistent using Z3.
    """
    issues: list[Z3Issue] = []
    if not Z3_AVAILABLE:
        return issues

    for u in units:
        val = u.value if hasattr(u, "value") else None
        uom = getattr(u, "unit_of_measure", None) or getattr(u, "unit", None)
        if val is None or uom is None:
            continue
        try:
            numeric_val = float(val)
        except (ValueError, TypeError):
            continue

        result = _to_base(numeric_val, uom)
        if result is None:
            continue
        base_val, base_unit = result

        s = Solver()
        z_val = Real(f"val_{u.id}")
        z_base = Real(f"base_{u.id}")
        norm = _normalize_unit(uom)
        conv = _UNIT_CONVERSIONS.get(norm)
        if conv is None:
            continue
        _, mult = conv

        s.add(z_val == numeric_val)
        s.add(z_base == z_val * mult)
        s.add(z_base != base_val)

        if s.check() == sat:
            issues.append(Z3Issue(
                check_type="unit_normalization",
                severity="error",
                message=(
                    f"Unit normalization inconsistency for {u.id}: "
                    f"{numeric_val} {uom} should be {base_val} {base_unit} "
                    f"but Z3 found a model where it differs"
                ),
                source_ids=[u.id],
                page=getattr(u, "page", None),
            ))

    return issues


# ---------------------------------------------------------------------------
# Check 2: Contradiction detection
# ---------------------------------------------------------------------------

def _extract_param_key(unit) -> str | None:
    """Build a grouping key from label + context to identify the same parameter."""
    label = (getattr(unit, "label", "") or "").strip().lower()
    context = (getattr(unit, "context", "") or "").strip().lower()
    if not label and not context:
        return None

    qualifier = ""
    for kw in ("minimum", "min", "typical", "typ", "maximum", "max"):
        if kw in context:
            qualifier = kw[:3]
            break

    return f"{label}|{qualifier}" if label else f"ctx:{context[:40]}|{qualifier}"


def _check_contradictions(units: list) -> list[Z3Issue]:
    """Detect contradictions: same parameter extracted with different values across pages."""
    issues: list[Z3Issue] = []
    if not Z3_AVAILABLE:
        return issues

    groups: dict[str, list] = {}
    for u in units:
        key = _extract_param_key(u)
        if key is None:
            continue
        try:
            float(u.value)
        except (ValueError, TypeError):
            continue
        uom = getattr(u, "unit_of_measure", None) or getattr(u, "unit", None)
        if uom is None:
            continue
        groups.setdefault(key, []).append(u)

    for key, group in groups.items():
        if len(group) < 2:
            continue

        base_vals: list[tuple[float, str, object]] = []
        for u in group:
            uom = getattr(u, "unit_of_measure", None) or getattr(u, "unit", None) or ""
            result = _to_base(float(u.value), uom)
            if result is not None:
                base_vals.append((result[0], result[1], u))

        if len(base_vals) < 2:
            continue

        ref_val, ref_base, ref_unit = base_vals[0]
        for bv, bu, u in base_vals[1:]:
            if bu != ref_base:
                continue
            if abs(ref_val - bv) < 1e-9:
                continue

            s = Solver()
            a = Real("a")
            b = Real("b")
            s.add(a == ref_val)
            s.add(b == bv)
            s.add(a == b)

            if s.check() != sat:
                issues.append(Z3Issue(
                    check_type="contradiction",
                    severity="error",
                    message=(
                        f"Contradiction: {key!r} has value {ref_unit.value} {getattr(ref_unit, 'unit_of_measure', '')} "
                        f"on page {getattr(ref_unit, 'page', '?')} but "
                        f"{u.value} {getattr(u, 'unit_of_measure', '')} on page {getattr(u, 'page', '?')}"
                    ),
                    source_ids=[ref_unit.id, u.id],
                    page=getattr(u, "page", None),
                ))

    return issues


# ---------------------------------------------------------------------------
# Check 3: Range consistency
# ---------------------------------------------------------------------------

def _check_range_consistency(ranges: list) -> list[Z3Issue]:
    """Assert min <= typ <= max for all Range objects using Z3."""
    issues: list[Z3Issue] = []
    if not Z3_AVAILABLE:
        return issues

    for r in ranges:
        min_v = getattr(r, "min", None)
        typ_v = getattr(r, "typ", None)
        max_v = getattr(r, "max", None)

        vals: dict[str, float] = {}
        for name, v in [("min", min_v), ("typ", typ_v), ("max", max_v)]:
            if v is not None:
                try:
                    vals[name] = float(v)
                except (ValueError, TypeError):
                    pass

        if len(vals) < 2:
            continue

        s = Solver()
        z_vars = {name: Real(f"{r.id}_{name}") for name in vals}
        for name, v in vals.items():
            s.add(z_vars[name] == v)

        constraints = []
        if "min" in z_vars and "typ" in z_vars:
            constraints.append(z_vars["min"] <= z_vars["typ"])
        if "typ" in z_vars and "max" in z_vars:
            constraints.append(z_vars["typ"] <= z_vars["max"])
        if "min" in z_vars and "max" in z_vars:
            constraints.append(z_vars["min"] <= z_vars["max"])

        for constraint in constraints:
            s_test = Solver()
            for name, v in vals.items():
                s_test.add(z_vars[name] == v)
            from z3 import Not
            s_test.add(Not(constraint))
            if s_test.check() == sat:
                issues.append(Z3Issue(
                    check_type="range_consistency",
                    severity="error",
                    message=(
                        f"Range consistency violation for {r.id} "
                        f"({getattr(r, 'label', '?')}): "
                        f"min={vals.get('min')}, typ={vals.get('typ')}, max={vals.get('max')} "
                        f"({getattr(r, 'unit', '')})"
                    ),
                    source_ids=[r.id],
                    page=getattr(r, "page", None),
                ))
                break

    return issues


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_z3_checks(
    units: list | None = None,
    ranges: list | None = None,
    conditional_units: list | None = None,
) -> Z3CheckResult:
    """Run all Z3 quality checks on canonical data.

    Accepts lists of Unit, Range, and ConditionalUnit objects.
    Returns a Z3CheckResult with any issues found.
    """
    result = Z3CheckResult()

    if not Z3_AVAILABLE:
        logger.warning("Z3 checks skipped: z3-solver not installed")
        return result

    all_units = list(units or [])
    all_units.extend(conditional_units or [])

    result.issues.extend(_check_unit_normalization(all_units))
    result.checks_run += 1

    result.issues.extend(_check_contradictions(all_units))
    result.checks_run += 1

    result.issues.extend(_check_range_consistency(ranges or []))
    result.checks_run += 1

    if result.issues:
        logger.info(
            "Z3 checks found %d issue(s): %d error(s), %d warning(s)",
            len(result.issues),
            sum(1 for i in result.issues if i.severity == "error"),
            sum(1 for i in result.issues if i.severity == "warning"),
        )

    return result
