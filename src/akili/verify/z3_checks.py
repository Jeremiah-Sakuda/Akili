"""
Quality / consistency checks for canonical data.

Two flavors:

Deterministic consistency checks (no solver needed):
1. Unit normalization — flag numeric facts whose unit can't be dimensionally validated.
2. Contradiction detection — same parameter, different values (all pairs within a group).
3. Range consistency — min <= typ <= max for Range objects.

Z3-backed constraint checks (genuinely combine multiple extracted values):
4. Power: P_max >= V_max * I_max
5. Thermal viability: T_j = T_ambient + P * theta_JA <= Tj_max
6. Regulator dropout margin.

The constraint checks use z3-solver when installed and degrade gracefully otherwise.
run_z3_checks() is invoked during ingestion (see ingest/pipeline.py); error-severity
issues lower the confidence of the facts involved so they surface for human REVIEW.
"""

from __future__ import annotations

import logging
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
    "\u03a9": "Ohm",  # Ω
    "k\u03a9": "kOhm",
    "M\u03a9": "MOhm",
    "\u00b5V": "uV",  # µV
    "\u00b5A": "uA",
    "\u00b5F": "uF",
    "\u00b5s": "us",
    "\u00b0C": "C",  # °C
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
    severity: str  # "error", "warning"
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
    """Dimensional-validity check: flag numeric facts we cannot dimensionally validate.

    A numeric value whose unit_of_measure is non-finite or not in the conversion table
    (e.g. a bare SI prefix like "k" extracted as a unit) can't be normalized to a base
    unit, so no downstream consistency check can vouch for it. We surface that as a
    warning. (This deliberately replaces a previous Z3 'check' that asserted x != x and
    could therefore never fire — verification theater. The genuine constraint-solving
    lives in the cross-parameter checks below.)
    """
    import math

    issues: list[Z3Issue] = []
    for u in units:
        val = u.value if hasattr(u, "value") else None
        uom = getattr(u, "unit_of_measure", None) or getattr(u, "unit", None)
        if val is None or uom is None:
            continue
        try:
            numeric_val = float(val)
        except (ValueError, TypeError):
            continue

        if not math.isfinite(numeric_val):
            issues.append(
                Z3Issue(
                    check_type="unit_normalization",
                    severity="error",
                    message=f"Non-finite numeric value for {u.id}: {numeric_val} {uom}",
                    source_ids=[u.id],
                    page=getattr(u, "page", None),
                )
            )
            continue

        if _to_base(numeric_val, uom) is None:
            issues.append(
                Z3Issue(
                    check_type="unit_normalization",
                    severity="warning",
                    message=(
                        f"Cannot dimensionally validate {u.id}: unrecognized unit {uom!r} "
                        f"(value {numeric_val}). It will not participate in consistency checks."
                    ),
                    source_ids=[u.id],
                    page=getattr(u, "page", None),
                )
            )

    return issues


# ---------------------------------------------------------------------------
# Check 2: Contradiction detection
# ---------------------------------------------------------------------------


def _qualifier_of(unit) -> str:
    """The min/typ/max qualifier mentioned in a unit's context, if any."""
    context = (getattr(unit, "context", "") or "").strip().lower()
    for kw in ("minimum", "min", "typical", "typ", "maximum", "max"):
        if kw in context:
            return kw[:3]
    return ""


def _extract_param_key(unit) -> str | None:
    """Build a grouping key from label + context to identify the same parameter."""
    label = (getattr(unit, "label", "") or "").strip().lower()
    context = (getattr(unit, "context", "") or "").strip().lower()
    if not label and not context:
        return None
    qualifier = _qualifier_of(unit)
    return f"{label}|{qualifier}" if label else f"ctx:{context[:40]}|{qualifier}"


def _check_contradictions(units: list) -> list[Z3Issue]:
    """Detect contradictions: same parameter, different values (all pairs within a group).

    Compares every pair within a group (not just against the first element), so a 3-way
    group with a disagreement between elements 1 and 2 is not missed. When the group has
    an explicit min/typ/max qualifier the conflict is an error; without one the two values
    may legitimately be distinct rails sharing a label, so it is reported as a warning.
    """
    issues: list[Z3Issue] = []

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
        base_vals: list[tuple[float, str, object]] = []
        for u in group:
            uom = getattr(u, "unit_of_measure", None) or getattr(u, "unit", None) or ""
            result = _to_base(float(u.value), uom)
            if result is not None:
                base_vals.append((result[0], result[1], u))

        if len(base_vals) < 2:
            continue

        # A qualifier (max/min/typ) means these really are the same spec; disagreement
        # is then a hard error. Without a qualifier, treat as a softer warning.
        has_qualifier = bool(_qualifier_of(base_vals[0][2]))
        severity = "error" if has_qualifier else "warning"

        seen_pairs: set[tuple[str, str]] = set()
        for i in range(len(base_vals)):
            ai, abase, au = base_vals[i]
            for j in range(i + 1, len(base_vals)):
                bj, bbase, bu = base_vals[j]
                if abase != bbase or abs(ai - bj) < 1e-9:
                    continue
                pair = tuple(sorted((au.id, bu.id)))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                msg = (
                    f"Contradiction: {key!r} has value "
                    f"{au.value} {getattr(au, 'unit_of_measure', '')} on page "
                    f"{getattr(au, 'page', '?')} but "
                    f"{bu.value} {getattr(bu, 'unit_of_measure', '')} on page "
                    f"{getattr(bu, 'page', '?')}"
                )
                issues.append(
                    Z3Issue(
                        check_type="contradiction",
                        severity=severity,
                        message=msg,
                        source_ids=[au.id, bu.id],
                        page=getattr(bu, "page", None),
                    )
                )

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
        s.set("timeout", 5000)
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
            s_test.set("timeout", 5000)
            for name, v in vals.items():
                s_test.add(z_vars[name] == v)
            from z3 import Not

            s_test.add(Not(constraint))
            if s_test.check() == sat:
                issues.append(
                    Z3Issue(
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
                    )
                )
                break

    return issues


# ---------------------------------------------------------------------------
# Check 4: Cross-parameter power constraint (P_max >= V * I)
# ---------------------------------------------------------------------------


def _check_power_constraint(units: list) -> list[Z3Issue]:
    """Verify that the rated max power is >= V_max * I_max.

    If a document specifies max voltage, max current, AND max power,
    then P_max should be >= V_max * I_max. If not, the datasheet may
    have an internal inconsistency.
    """
    issues: list[Z3Issue] = []
    if not Z3_AVAILABLE:
        return issues

    # Gather candidate values by matching context/UOM.
    voltage_units: list[tuple[float, str, object]] = []
    current_units: list[tuple[float, str, object]] = []
    power_units: list[tuple[float, str, object]] = []

    for u in units:
        val = getattr(u, "value", None)
        uom = getattr(u, "unit_of_measure", None) or getattr(u, "unit", None)
        ctx = (getattr(u, "context", "") or "").lower()
        lbl = (getattr(u, "label", "") or "").lower()
        if val is None or uom is None:
            continue
        try:
            numeric = float(val)
        except (ValueError, TypeError):
            continue

        base = _to_base(numeric, uom)
        if base is None:
            continue
        base_val, base_unit = base

        is_max = any(kw in ctx or kw in lbl for kw in ("max", "maximum", "absolute"))
        if not is_max:
            continue

        if base_unit == "V":
            voltage_units.append((base_val, u.id, u))
        elif base_unit == "A":
            current_units.append((base_val, u.id, u))
        elif base_unit == "W":
            power_units.append((base_val, u.id, u))

    if not voltage_units or not current_units or not power_units:
        return issues

    # Use the highest V, highest I, and highest rated P
    v_max, v_id, v_unit = max(voltage_units, key=lambda x: x[0])
    i_max, i_id, i_unit = max(current_units, key=lambda x: x[0])
    p_max, p_id, p_unit = max(power_units, key=lambda x: x[0])

    # Z3: assert p_max < v_max * i_max  →  if SAT, P_max is insufficient
    s = Solver()
    s.set("timeout", 5000)
    z_p = Real("p_max")
    z_v = Real("v_max")
    z_i = Real("i_max")
    s.add(z_p == p_max)
    s.add(z_v == v_max)
    s.add(z_i == i_max)
    s.add(z_p < z_v * z_i)

    if s.check() == sat:
        vi_product = v_max * i_max
        issues.append(
            Z3Issue(
                check_type="power_constraint",
                severity="warning",
                message=(
                    f"Power constraint concern: rated P_max={p_max:.3f}W but "
                    f"V_max × I_max = {v_max}V × {i_max}A = {vi_product:.3f}W. "
                    f"P_max should be >= V × I."
                ),
                source_ids=[v_id, i_id, p_id],
            )
        )

    return issues


# ---------------------------------------------------------------------------
# Check 5: Thermal viability (T_ambient + P * θJA <= Tj_max)
# ---------------------------------------------------------------------------


def _check_thermal_viability(units: list, ambient_temp: float = 25.0) -> list[Z3Issue]:
    """Verify that junction temperature at rated power stays within limits.

    T_j = T_ambient + P × θ_JA. If T_j > T_j_max, the design is thermally
    infeasible at rated power.
    """
    issues: list[Z3Issue] = []
    if not Z3_AVAILABLE:
        return issues

    theta_ja: tuple[float, str] | None = None
    p_max_w: tuple[float, str] | None = None
    tj_max: tuple[float, str] | None = None

    for u in units:
        val = getattr(u, "value", None)
        uom = getattr(u, "unit_of_measure", None) or getattr(u, "unit", None)
        ctx = (getattr(u, "context", "") or "").lower()
        lbl = (getattr(u, "label", "") or "").lower()
        if val is None or uom is None:
            continue
        try:
            numeric = float(val)
        except (ValueError, TypeError):
            continue

        # Match thermal resistance
        uom_upper = (uom or "").upper().replace(" ", "")
        if ("thermal" in ctx or "θja" in lbl or "theta" in lbl or "rthja" in lbl) and uom_upper in (
            "°C/W",
            "C/W",
            "K/W",
        ):
            theta_ja = (numeric, u.id)
        # Match power dissipation
        elif (
            ("power" in ctx or "dissipation" in ctx or lbl in ("pd", "power"))
            and _normalize_unit(uom) in _UNIT_CONVERSIONS
            and _to_base(numeric, uom) is not None
        ):
            base = _to_base(numeric, uom)
            if base and base[1] == "W":
                if p_max_w is None or base[0] > p_max_w[0]:
                    p_max_w = (base[0], u.id)
        # Match max junction temperature
        elif "junction" in ctx and ("max" in ctx or "max" in lbl):
            norm = _normalize_unit(uom)
            if norm == "C" or uom_upper in ("°C", "℃", "C"):
                tj_max = (numeric, u.id)

    if theta_ja is None or p_max_w is None or tj_max is None:
        return issues

    theta_val, theta_id = theta_ja
    p_val, p_id = p_max_w
    tj_max_val, tj_id = tj_max

    t_junction = ambient_temp + p_val * theta_val

    s = Solver()
    s.set("timeout", 5000)
    z_tj = Real("t_junction")
    z_tj_max = Real("tj_max")
    s.add(z_tj == t_junction)
    s.add(z_tj_max == tj_max_val)
    s.add(z_tj > z_tj_max)

    if s.check() == sat:
        issues.append(
            Z3Issue(
                check_type="thermal_viability",
                severity="error",
                message=(
                    f"Thermal viability FAIL: T_j = {ambient_temp}°C + "
                    f"{p_val:.3f}W × {theta_val}°C/W = {t_junction:.1f}°C, "
                    f"exceeds T_j_max = {tj_max_val}°C by {t_junction - tj_max_val:.1f}°C"
                ),
                source_ids=[theta_id, p_id, tj_id],
            )
        )

    return issues


# ---------------------------------------------------------------------------
# Check 6: Dropout margin for voltage regulators
# ---------------------------------------------------------------------------


def _check_dropout_margin(units: list) -> list[Z3Issue]:
    """For regulators: verify V_in_min - V_out >= V_dropout."""
    issues: list[Z3Issue] = []
    if not Z3_AVAILABLE:
        return issues

    v_in_min: tuple[float, str] | None = None
    v_out: tuple[float, str] | None = None
    v_dropout: tuple[float, str] | None = None

    for u in units:
        val = getattr(u, "value", None)
        uom = getattr(u, "unit_of_measure", None) or getattr(u, "unit", None)
        ctx = (getattr(u, "context", "") or "").lower()
        lbl = (getattr(u, "label", "") or "").lower()
        if val is None or uom is None:
            continue
        try:
            numeric = float(val)
        except (ValueError, TypeError):
            continue

        base = _to_base(numeric, uom)
        if base is None or base[1] != "V":
            continue
        base_val = base[0]

        if "dropout" in ctx or "dropout" in lbl or "vdo" in lbl:
            v_dropout = (base_val, u.id)
        elif ("input" in ctx and "min" in ctx) or ("vin" in lbl and "min" in lbl):
            v_in_min = (base_val, u.id)
        elif "output voltage" in ctx or "vout" in lbl:
            v_out = (base_val, u.id)

    if v_in_min is None or v_out is None or v_dropout is None:
        return issues

    vin_val, vin_id = v_in_min
    vout_val, vout_id = v_out
    vdo_val, vdo_id = v_dropout

    margin = vin_val - vout_val

    s = Solver()
    s.set("timeout", 5000)
    z_margin = Real("margin")
    z_dropout = Real("dropout")
    s.add(z_margin == margin)
    s.add(z_dropout == vdo_val)
    s.add(z_margin < z_dropout)

    if s.check() == sat:
        issues.append(
            Z3Issue(
                check_type="dropout_margin",
                severity="warning",
                message=(
                    f"Dropout margin insufficient: V_in_min({vin_val}V) - V_out({vout_val}V) "
                    f"= {margin:.3f}V < V_dropout({vdo_val}V)"
                ),
                source_ids=[vin_id, vout_id, vdo_id],
            )
        )

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

    # Cross-parameter constraint checks
    result.issues.extend(_check_power_constraint(all_units))
    result.checks_run += 1

    result.issues.extend(_check_thermal_viability(all_units))
    result.checks_run += 1

    result.issues.extend(_check_dropout_margin(all_units))
    result.checks_run += 1

    if result.issues:
        logger.info(
            "Z3 checks found %d issue(s): %d error(s), %d warning(s)",
            len(result.issues),
            sum(1 for i in result.issues if i.severity == "error"),
            sum(1 for i in result.issues if i.severity == "warning"),
        )

    return result
