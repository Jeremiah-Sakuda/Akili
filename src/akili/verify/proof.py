"""
Proof rules: derive answer from canonical facts; deterministic REFUSE if not provable.

Rules are registered via the @rule decorator with a priority (lower = tried first).
verify_and_answer iterates rules in priority order; the first non-None result wins.
"""

from __future__ import annotations

import re
from typing import Callable

from akili.canonical import Bijection, Grid, Unit
from akili.verify.matchers import (
    STOP_WORDS,
    get_unit_text,
    keyword_overlap,
    parse_capacity,
    parse_current,
    parse_dimension,
    parse_frequency,
    parse_power,
    parse_temperature,
    parse_time,
    parse_voltage,
    parse_weight,
)
from akili.verify.models import (
    AnswerWithProof,
    ConfidenceScore,
    ProofPoint,
    ProofPointBBox,
    Refuse,
    compute_canonical_quality,
)

# ---------------------------------------------------------------------------
# Rule registry
# ---------------------------------------------------------------------------

RuleFn = Callable[
    [str, list[Unit], list[Bijection], list[Grid]],
    AnswerWithProof | None,
]

_RULES: list[tuple[int, str, RuleFn]] = []


def rule(priority: int, name: str | None = None):
    """Decorator to register a verification rule at a given priority (lower = tried first)."""

    def decorator(fn: RuleFn) -> RuleFn:
        _RULES.append((priority, name or fn.__name__, fn))
        _RULES.sort(key=lambda t: t[0])
        return fn

    return decorator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _proof_point(
    x: float,
    y: float,
    page: int = 0,
    bbox: ProofPointBBox | None = None,
    source_id: str | None = None,
    source_type: str | None = None,
) -> ProofPoint:
    return ProofPoint(
        x=x, y=y, page=page, bbox=bbox, source_id=source_id, source_type=source_type
    )


def _bbox_from(obj: Unit | Bijection | Grid) -> ProofPointBBox | None:
    b = obj.bbox
    if b is None:
        return None
    return ProofPointBBox(x1=b.x1, y1=b.y1, x2=b.x2, y2=b.y2)


def _unit_canonical_quality(u: Unit) -> float:
    return compute_canonical_quality(
        has_bbox=u.bbox is not None,
        has_origin=True,
        has_unit_of_measure=bool(u.unit_of_measure),
        has_label=bool(u.label),
        has_context=bool(u.context),
    )


def _answer_from_unit(
    u: Unit, answer_str: str | None = None, verification_strength: float = 0.7
) -> AnswerWithProof:
    if answer_str is None:
        answer_str = f"{u.value} {u.unit_of_measure or ''}".strip()
    cq = _unit_canonical_quality(u)
    confidence = ConfidenceScore.compute(
        extraction_agreement=0.5,
        canonical_validation=cq,
        verification_strength=verification_strength,
    )
    return AnswerWithProof(
        answer=answer_str,
        proof=[_proof_point(u.origin.x, u.origin.y, u.page, _bbox_from(u), u.id, "unit")],
        source_id=u.id,
        source_type="unit",
        confidence=confidence,
    )


def _q(question: str) -> str:
    """Lowercase stripped question for matching."""
    return question.lower().strip()


def _has_any(text: str, *keywords: str) -> bool:
    return any(kw in text for kw in keywords)


def _find_units_by_context(
    units: list[Unit],
    context_keywords: list[str],
    label_keywords: list[str] | None = None,
    unit_of_measures: list[str] | None = None,
) -> list[Unit]:
    """Find units whose context/label match keywords and optionally have a specific unit_of_measure."""
    label_keywords = label_keywords or context_keywords
    results: list[Unit] = []
    for u in units:
        ctx = (u.context or "").lower()
        lbl = (u.label or "").lower()
        uom = (u.unit_of_measure or "").upper()

        ctx_match = any(kw in ctx for kw in context_keywords)
        lbl_match = any(kw in lbl for kw in label_keywords)
        uom_match = unit_of_measures is None or uom in [m.upper() for m in unit_of_measures]

        if (ctx_match or lbl_match) and uom_match:
            results.append(u)
    return results


def _best_numeric_unit(
    units: list[Unit],
    maximize: bool = True,
    text_parser: Callable[[str], list[tuple[float, str]]] | None = None,
    unit_of_measures: list[str] | None = None,
) -> tuple[float, Unit, str] | None:
    """Find the unit with the max (or min) numeric value. Optionally parse from text."""
    numeric: list[tuple[float, Unit, str]] = []
    for u in units:
        if u.unit_of_measure and (
            unit_of_measures is None
            or u.unit_of_measure.upper() in [m.upper() for m in unit_of_measures]
        ):
            try:
                v = float(u.value)
                numeric.append((v, u, f"{u.value} {u.unit_of_measure or ''}".strip()))
            except (TypeError, ValueError):
                pass
        if text_parser:
            text = get_unit_text(u)
            for val, uom in text_parser(text):
                numeric.append((val, u, f"{val} {uom}"))
    if not numeric:
        return None
    return max(numeric, key=lambda x: x[0]) if maximize else min(numeric, key=lambda x: x[0])


# ---------------------------------------------------------------------------
# Grid search helpers
# ---------------------------------------------------------------------------


def _search_grid_by_header(
    grids: list[Grid], row_keywords: list[str], col_keywords: list[str] | None = None
) -> AnswerWithProof | None:
    """Search grids for a row whose header cell matches row_keywords, return value cell(s)."""
    for g in grids:
        for row_idx in range(g.rows):
            header_cell = g.get_cell(row_idx, 0)
            if not header_cell:
                continue
            hdr = str(header_cell.value).lower()
            if any(kw in hdr for kw in row_keywords):
                # Return value from col 1+ (skip header col)
                values = []
                for col_idx in range(1, g.cols):
                    cell = g.get_cell(row_idx, col_idx)
                    if cell and str(cell.value).strip():
                        values.append(str(cell.value))
                if values:
                    return AnswerWithProof(
                        answer=", ".join(values),
                        proof=[
                            _proof_point(
                                header_cell.origin.x if header_cell.origin else g.origin.x,
                                header_cell.origin.y if header_cell.origin else g.origin.y,
                                g.page,
                                _bbox_from(g),
                                g.id,
                                "grid",
                            )
                        ],
                        source_id=g.id,
                        source_type="grid",
                    )
    return None


# ===================================================================
# RULE FACTORIES — eliminate duplication across similar rules
# ===================================================================


def _make_best_numeric_rule(
    priority: int,
    name: str,
    question_keywords: list[list[str]],
    context_keywords: list[str],
    uom_list: list[str],
    text_parser: Callable[[str], list[tuple[float, str]]],
    grid_keywords: list[str] | None = None,
    maximize: bool = True,
) -> None:
    """Register a rule that finds the best numeric unit matching context/UOM."""

    @rule(priority, name)
    def _rule(
        question: str, units: list[Unit], bijections: list[Bijection], grids: list[Grid]
    ) -> AnswerWithProof | None:
        q = _q(question)
        for kw_group in question_keywords:
            if not _has_any(q, *kw_group):
                return None
        matches = _find_units_by_context(units, context_keywords, unit_of_measures=uom_list)
        best = _best_numeric_unit(matches, maximize=maximize, text_parser=text_parser)
        if best:
            _, u, answer = best
            return _answer_from_unit(u, answer)
        # Broader fallback: try all units with the text parser
        best = _best_numeric_unit(
            units, maximize=maximize, text_parser=text_parser, unit_of_measures=[m.upper() for m in uom_list]
        )
        if best:
            _, u, answer = best
            return _answer_from_unit(u, answer)
        if grid_keywords:
            result = _search_grid_by_header(grids, grid_keywords)
            if result:
                return result
        return None


def _make_simple_lookup_rule(
    priority: int,
    name: str,
    question_keywords: list[str],
    context_keywords: list[str],
    uom_list: list[str] | None = None,
    grid_keywords: list[str] | None = None,
    post_filter: Callable[[list[Unit]], list[Unit]] | None = None,
) -> None:
    """Register a rule that finds units by context and returns the first match."""

    @rule(priority, name)
    def _rule(
        question: str, units: list[Unit], bijections: list[Bijection], grids: list[Grid]
    ) -> AnswerWithProof | None:
        q = _q(question)
        if not _has_any(q, *question_keywords):
            return None
        matches = _find_units_by_context(units, context_keywords, unit_of_measures=uom_list)
        if post_filter:
            matches = post_filter(matches)
        if matches:
            return _answer_from_unit(matches[0])
        if grid_keywords:
            result = _search_grid_by_header(grids, grid_keywords)
            if result:
                return result
        return None


def _make_multi_value_rule(
    priority: int,
    name: str,
    question_keywords: list[str],
    context_keywords: list[str],
    uom_list: list[str] | None = None,
    grid_keywords: list[str] | None = None,
    max_values: int = 4,
) -> None:
    """Register a rule that returns multiple combined values."""

    @rule(priority, name)
    def _rule(
        question: str, units: list[Unit], bijections: list[Bijection], grids: list[Grid]
    ) -> AnswerWithProof | None:
        q = _q(question)
        if not _has_any(q, *question_keywords):
            return None
        matches = _find_units_by_context(units, context_keywords, unit_of_measures=uom_list)
        if not matches:
            matches = _find_units_by_context(units, context_keywords)
        if matches:
            if len(matches) >= 2:
                parts = [
                    f"{u.label or u.context or ''}: {u.value} {u.unit_of_measure or ''}".strip()
                    for u in matches[:max_values]
                ]
                combined = "; ".join(p for p in parts if p)
                return AnswerWithProof(
                    answer=combined,
                    proof=[
                        _proof_point(u.origin.x, u.origin.y, u.page, _bbox_from(u), u.id, "unit")
                        for u in matches[:max_values]
                    ],
                    source_id=matches[0].id,
                    source_type="unit",
                )
            return _answer_from_unit(matches[0])
        if grid_keywords:
            result = _search_grid_by_header(grids, grid_keywords)
            if result:
                return result
        return None


def _make_range_rule(
    priority: int,
    name: str,
    question_keywords: list[str],
    context_keywords: list[str],
    uom_list: list[str],
    text_parser: Callable[[str], list[tuple[float, str]]],
    range_unit: str = "V",
    grid_keywords: list[str] | None = None,
) -> None:
    """Register a rule that assembles a range (min-max) from matching units."""

    @rule(priority, name)
    def _rule(
        question: str, units: list[Unit], bijections: list[Bijection], grids: list[Grid]
    ) -> AnswerWithProof | None:
        q = _q(question)
        if not _has_any(q, *question_keywords):
            return None
        matches = _find_units_by_context(units, context_keywords, unit_of_measures=uom_list)
        if not matches:
            matches = _find_units_by_context(units, context_keywords)
        if len(matches) >= 2:
            vals: list[tuple[float, Unit]] = []
            for u in matches:
                try:
                    vals.append((float(u.value), u))
                except (TypeError, ValueError):
                    for v, _ in text_parser(get_unit_text(u)):
                        vals.append((v, u))
            if len(vals) >= 2:
                vals.sort(key=lambda x: x[0])
                lo_val, lo_u = vals[0]
                hi_val, hi_u = vals[-1]
                uom = lo_u.unit_of_measure or hi_u.unit_of_measure or range_unit
                return AnswerWithProof(
                    answer=f"{lo_val} to {hi_val} {uom}",
                    proof=[
                        _proof_point(lo_u.origin.x, lo_u.origin.y, lo_u.page, _bbox_from(lo_u), lo_u.id, "unit"),
                        _proof_point(hi_u.origin.x, hi_u.origin.y, hi_u.page, _bbox_from(hi_u), hi_u.id, "unit"),
                    ],
                    source_id=lo_u.id,
                    source_type="unit",
                )
        if matches:
            return _answer_from_unit(matches[0])
        if grid_keywords:
            result = _search_grid_by_header(grids, grid_keywords)
            if result:
                return result
        return None


# ===================================================================
# RULES — unique rules that need custom logic
# ===================================================================


# ---------------------------------------------------------------------------
# 100: Pin lookup (bijection + grid)
# ---------------------------------------------------------------------------
@rule(100, "pin_lookup")
def _try_pin_lookup(
    question: str, units: list[Unit], bijections: list[Bijection], grids: list[Grid]
) -> AnswerWithProof | None:
    q = _q(question)
    pin_num = re.search(r"pin\s+(?:number\s+)?(\d+)", q)
    if not pin_num:
        return None
    n = pin_num.group(1)
    for b in bijections:
        right = b.get_right(n)
        if right is not None:
            return AnswerWithProof(
                answer=right,
                proof=[_proof_point(b.origin.x, b.origin.y, b.page, _bbox_from(b), b.id, "bijection")],
                source_id=b.id,
                source_type="bijection",
            )
        left = b.get_left(n)
        if left is not None:
            return AnswerWithProof(
                answer=left,
                proof=[_proof_point(b.origin.x, b.origin.y, b.page, _bbox_from(b), b.id, "bijection")],
                source_id=b.id,
                source_type="bijection",
            )
    for g in grids:
        for row_i in range(g.rows):
            for col_i in range(g.cols):
                cell = g.get_cell(row_i, col_i)
                if cell and str(cell.value) == n:
                    ox = cell.origin.x if cell.origin else g.origin.x
                    oy = cell.origin.y if cell.origin else g.origin.y
                    name_cell = g.get_cell(row_i, col_i + 1) if col_i + 1 < g.cols else None
                    if not name_cell and col_i > 0:
                        name_cell = g.get_cell(row_i, col_i - 1)
                    answer_val = str(name_cell.value) if name_cell else str(cell.value)
                    return AnswerWithProof(
                        answer=answer_val,
                        proof=[_proof_point(ox, oy, g.page, _bbox_from(g), g.id, "grid")],
                        source_id=g.id,
                        source_type="grid",
                    )
    return None


# ---------------------------------------------------------------------------
# 150: Part number / ordering info
# ---------------------------------------------------------------------------
@rule(150, "part_number")
def _try_part_number(
    question: str, units: list[Unit], bijections: list[Bijection], grids: list[Grid]
) -> AnswerWithProof | None:
    q = _q(question)
    if not _has_any(q, "part number", "ordering", "order code", "mpn", "part no"):
        return None
    matches = _find_units_by_context(
        units, ["part number", "ordering", "order code", "mpn", "part no"]
    )
    if matches:
        return _answer_from_unit(matches[0])
    for b in bijections:
        mapping_text = " ".join(list(b.mapping.keys()) + list(b.mapping.values())).lower()
        if "part" in mapping_text or "order" in mapping_text:
            vals = list(b.mapping.values())
            if vals:
                return AnswerWithProof(
                    answer=vals[0],
                    proof=[_proof_point(b.origin.x, b.origin.y, b.page, _bbox_from(b), b.id, "bijection")],
                    source_id=b.id,
                    source_type="bijection",
                )
    result = _search_grid_by_header(grids, ["part number", "ordering", "order code", "mpn"])
    if result:
        return result
    return None


# ---------------------------------------------------------------------------
# 160: Description / function
# ---------------------------------------------------------------------------
@rule(160, "description")
def _try_description(
    question: str, units: list[Unit], bijections: list[Bijection], grids: list[Grid]
) -> AnswerWithProof | None:
    q = _q(question)
    if not _has_any(q, "what does this do", "what does this component do", "description",
                    "what is this component", "what is this device", "overview"):
        if "what is this" not in q or _has_any(q, "pin", "voltage", "current", "temperature"):
            return None
    matches = _find_units_by_context(
        units, ["description", "function", "overview", "general description", "features"]
    )
    if matches:
        return _answer_from_unit(matches[0])
    result = _search_grid_by_header(grids, ["description", "function", "overview"])
    if result:
        return result
    return None


# ===================================================================
# FACTORY-GENERATED RULES — eliminates ~800 lines of duplication
# ===================================================================

# --- Best-numeric rules (find max/min value matching context + UOM) ---

_make_best_numeric_rule(
    200, "absolute_max_voltage",
    question_keywords=[["absolute max", "absolute maximum"], ["voltage", " v "]],
    context_keywords=["absolute maximum", "absolute max", "abs max"],
    uom_list=["V", "mV", "kV"],
    text_parser=parse_voltage,
    grid_keywords=["absolute max"],
)

_make_best_numeric_rule(
    210, "absolute_max_current",
    question_keywords=[["absolute max", "absolute maximum"], ["current", " a ", "amper"]],
    context_keywords=["absolute maximum", "absolute max", "abs max"],
    uom_list=["A", "mA", "µA"],
    text_parser=parse_current,
)

_make_best_numeric_rule(
    300, "max_voltage",
    question_keywords=[["max", "maximum"], ["voltage", " v ", " v"]],
    context_keywords=["voltage", "vcc", "vdd", "supply"],
    uom_list=["V", "VOLT", "VOLTS", "MV", "KV"],
    text_parser=parse_voltage,
)

_make_best_numeric_rule(
    310, "max_current",
    question_keywords=[["max", "maximum"], ["current", " a ", "amper"]],
    context_keywords=["current", "supply current", "icc"],
    uom_list=["A", "MA", "µA"],
    text_parser=parse_current,
)

_make_best_numeric_rule(
    320, "max_capacity",
    question_keywords=[["max", "maximum", "nominal"], ["capacity", "mah", " ah ", " wh "]],
    context_keywords=["capacity", "nominal capacity"],
    uom_list=["MAH", "AH", "WH"],
    text_parser=parse_capacity,
)

_make_best_numeric_rule(
    500, "power_dissipation",
    question_keywords=[["power dissipation", "max power", "power rating", "power consumption"]],
    context_keywords=["power dissipation", "power rating", "power consumption", "total power"],
    uom_list=["W", "mW"],
    text_parser=parse_power,
    grid_keywords=["power dissipation", "power rating", "power consumption"],
)

_make_best_numeric_rule(
    600, "clock_frequency",
    question_keywords=[["clock", "frequency", "bandwidth", "fmax", "speed", "data rate"]],
    context_keywords=["clock", "frequency", "bandwidth", "fmax", "speed", "data rate", "oscillator"],
    uom_list=["Hz", "kHz", "MHz", "GHz"],
    text_parser=parse_frequency,
    grid_keywords=["clock", "frequency", "bandwidth", "fmax"],
)

# --- Range rules (assemble min-max from matching units) ---

_make_range_rule(
    400, "operating_voltage_range",
    question_keywords=["operating voltage", "supply voltage", "vcc range", "vdd range", "input voltage range"],
    context_keywords=["operating", "supply", "vcc", "vdd", "input voltage"],
    uom_list=["V", "mV", "kV"],
    text_parser=parse_voltage,
    range_unit="V",
    grid_keywords=["operating voltage", "supply voltage", "vcc", "vdd"],
)

_make_range_rule(
    410, "operating_temperature_range",
    question_keywords=["operating temp", "junction temp", "temperature range", "ambient temp"],
    context_keywords=["operating temperature", "junction temperature", "ambient temperature", "operating temp"],
    uom_list=["°C", "℃", "°F", "K"],
    text_parser=parse_temperature,
    range_unit="°C",
    grid_keywords=["operating temperature", "junction temperature", "ambient temperature"],
)

# --- Simple lookup rules (first context match wins) ---

_make_simple_lookup_rule(
    405, "storage_temperature",
    question_keywords=["storage temp", "storage temperature"],
    context_keywords=["storage temperature", "storage temp", "tstg", "storage"],
    post_filter=lambda matches: [
        u for u in matches
        if "storage" in (u.context or "").lower()
        or "tstg" in (u.label or "").lower()
        or "storage" in (u.label or "").lower()
    ],
    grid_keywords=["storage temperature", "storage temp", "tstg"],
)

_make_simple_lookup_rule(
    430, "soldering_temperature",
    question_keywords=["solder", "reflow", "soldering temperature", "reflow temperature"],
    context_keywords=["solder", "reflow", "soldering", "reflow temperature"],
    grid_keywords=["solder", "reflow"],
)

_make_simple_lookup_rule(
    520, "leakage_current",
    question_keywords=["leakage current", "input leakage", "ileak"],
    context_keywords=["leakage", "ileak", "input leakage"],
    uom_list=["A", "mA", "µA", "nA"],
    grid_keywords=["leakage current", "input leakage", "ileak"],
)

_make_simple_lookup_rule(
    610, "propagation_delay",
    question_keywords=["propagation delay", "tpd", "delay time"],
    context_keywords=["propagation delay", "propagation", "tpd", "delay time", "tphl", "tplh"],
    uom_list=["ns", "µs", "ps", "ms"],
    grid_keywords=["propagation delay", "tpd", "tphl", "tplh"],
)

_make_simple_lookup_rule(
    700, "package_type",
    question_keywords=["package", "footprint", "case"],
    context_keywords=["package", "footprint", "case", "package type"],
    grid_keywords=["package", "footprint", "case"],
)

_make_simple_lookup_rule(
    720, "thermal_resistance",
    question_keywords=["thermal resistance", "θja", "theta-ja", "rθja", "θjc", "junction to ambient", "junction-to-ambient"],
    context_keywords=["thermal resistance", "θja", "theta", "junction to ambient", "junction-to-ambient", "θjc", "rθja"],
    uom_list=["°C/W", "K/W"],
    grid_keywords=["thermal resistance", "θja", "theta", "junction to ambient"],
)

_make_simple_lookup_rule(
    750, "moisture_sensitivity",
    question_keywords=["moisture sensitivity", "msl", "msl rating"],
    context_keywords=["moisture sensitivity", "msl"],
    grid_keywords=["moisture sensitivity", "msl"],
)

_make_simple_lookup_rule(
    730, "weight",
    question_keywords=["weight", "mass"],
    context_keywords=["weight", "mass"],
    uom_list=["g", "mg", "kg", "oz"],
    grid_keywords=["weight", "mass"],
)

# --- Multi-value rules (combine multiple matching units) ---

_make_multi_value_rule(
    510, "esd_ratings",
    question_keywords=["esd", "electrostatic", "esd rating"],
    context_keywords=["esd", "electrostatic", "hbm", "cdm"],
    grid_keywords=["esd", "electrostatic", "hbm", "cdm"],
)

_make_multi_value_rule(
    530, "threshold_voltage",
    question_keywords=["threshold", "vil", "vih", "vol", "voh", "logic level"],
    context_keywords=["threshold", "vil", "vih", "vol", "voh", "logic level", "input low", "input high"],
    uom_list=["V", "mV"],
    grid_keywords=["threshold", "vil", "vih", "logic level"],
)

_make_multi_value_rule(
    620, "rise_fall_time",
    question_keywords=["rise time", "fall time", " tr ", " tf ", "slew rate", "rise/fall"],
    context_keywords=["rise time", "fall time", "slew rate", "slew", "tr/tf", "rise/fall"],
    uom_list=["ns", "µs", "ps", "V/µs", "V/ns"],
    grid_keywords=["rise time", "fall time", "slew", "tr", "tf"],
)

_make_multi_value_rule(
    630, "setup_hold_time",
    question_keywords=["setup time", "hold time", "tsu", " th ", "setup/hold", "setup and hold"],
    context_keywords=["setup time", "hold time", "tsu", "setup/hold", "setup and hold"],
    uom_list=["ns", "µs", "ps", "ms"],
    grid_keywords=["setup time", "hold time", "tsu"],
)

_make_multi_value_rule(
    710, "package_dimensions",
    question_keywords=["dimension", "package size", "length", "width", "height", "package dimension"],
    context_keywords=["dimension", "package size", "length", "width", "height", "body size"],
    uom_list=["mm", "mil", "in", "cm"],
    grid_keywords=["dimension", "package size", "body size"],
    max_values=6,
)


# ===================================================================
# CUSTOM RULES — too unique for factories
# ===================================================================


# ---------------------------------------------------------------------------
# 740: Pin count
# ---------------------------------------------------------------------------
@rule(740, "pin_count")
def _try_pin_count(
    question: str, units: list[Unit], bijections: list[Bijection], grids: list[Grid]
) -> AnswerWithProof | None:
    q = _q(question)
    if not _has_any(q, "pin count", "how many pins", "number of pins", "total pins"):
        return None
    matches = _find_units_by_context(units, ["pin count", "number of pins", "total pins"])
    if matches:
        return _answer_from_unit(matches[0])
    for b in bijections:
        lbl = (b.id or "").lower()
        left_text = " ".join(b.left_set).lower()
        right_text = " ".join(b.right_set).lower()
        if "pin" in lbl or "pin" in left_text or "pin" in right_text:
            count = max(len(b.left_set), len(b.right_set))
            return AnswerWithProof(
                answer=str(count),
                proof=[_proof_point(b.origin.x, b.origin.y, b.page, _bbox_from(b), b.id, "bijection")],
                source_id=b.id,
                source_type="bijection",
            )
    return None


# ---------------------------------------------------------------------------
# 800: Recommended operating conditions (table lookup)
# ---------------------------------------------------------------------------
@rule(800, "recommended_operating")
def _try_recommended_operating(
    question: str, units: list[Unit], bijections: list[Bijection], grids: list[Grid]
) -> AnswerWithProof | None:
    q = _q(question)
    if not _has_any(q, "recommended operating", "recommended conditions"):
        return None
    result = _search_grid_by_header(grids, ["recommended operating", "recommended conditions"])
    if result:
        return result
    matches = _find_units_by_context(units, ["recommended operating", "recommended conditions"])
    if matches:
        parts = [f"{u.label or ''}: {u.value} {u.unit_of_measure or ''}".strip() for u in matches[:6]]
        combined = "; ".join(p for p in parts if p)
        return AnswerWithProof(
            answer=combined or str(matches[0].value),
            proof=[_proof_point(u.origin.x, u.origin.y, u.page, _bbox_from(u), u.id, "unit") for u in matches[:6]],
            source_id=matches[0].id,
            source_type="unit",
        )
    return None


# ---------------------------------------------------------------------------
# 900: Unit-by-intent (keyword scoring fallback)
# ---------------------------------------------------------------------------
@rule(900, "unit_by_intent")
def _try_unit_by_intent(
    question: str, units: list[Unit], bijections: list[Bijection], grids: list[Grid]
) -> AnswerWithProof | None:
    q = _q(question)
    # Map intent keywords to UOM sets and optional parsers
    intents: list[tuple[bool, list[str], Callable[[str], list[tuple[float, str]]] | None]] = [
        (_has_any(q, "voltage", "volt", " v ", "charge voltage", "cutoff voltage", "cut-off voltage"),
         ["V", "VOLT", "VOLTS", "MV", "KV"], parse_voltage),
        (_has_any(q, "current", "amper", " a ", "discharge current", "charge current"),
         ["A", "MA", "µA"], parse_current),
        (_has_any(q, "capacity", "mah", " ah ", " wh ", "nominal capacity"),
         ["MAH", "AH", "WH"], parse_capacity),
        (_has_any(q, "power", "watt", " w "),
         ["W", "MW"], parse_power),
        (_has_any(q, "temperature", "temp", "°c", "℃"),
         ["°C", "℃", "°F", "K"], parse_temperature),
        (_has_any(q, "frequency", "clock", "speed", "hz"),
         ["HZ", "KHZ", "MHZ", "GHZ"], parse_frequency),
        (_has_any(q, "resistance", "ohm", "impedance", " ω "),
         ["Ω", "OHM", "OHMS", "KΩ", "MΩ"], None),
    ]

    active = [(uoms, parser) for matched, uoms, parser in intents if matched]
    if not active:
        return None

    candidates: list[tuple[float, str, Unit]] = []
    for u in units:
        text = get_unit_text(u)
        overlap = keyword_overlap(question, text)
        uom = (u.unit_of_measure or "").upper()
        for target_uoms, parser in active:
            if uom in target_uoms:
                candidates.append((overlap + 10, f"{u.value} {u.unit_of_measure or ''}".strip(), u))
            if parser:
                for val, unit_str in parser(text):
                    candidates.append((overlap + 5, f"{val} {unit_str}", u))

    if not candidates:
        return None
    best = max(candidates, key=lambda x: (x[0], x[2].origin.y, x[2].origin.x))
    _, answer_str, best_u = best
    return _answer_from_unit(best_u, answer_str)


# ---------------------------------------------------------------------------
# 950: Grid cell lookup by row/column header matching
# ---------------------------------------------------------------------------
@rule(950, "grid_cell_lookup")
def _try_grid_cell_lookup(
    question: str, units: list[Unit], bijections: list[Bijection], grids: list[Grid]
) -> AnswerWithProof | None:
    """Fallback: search grid cells for header matches from the question."""
    q = _q(question)
    question_words = set(re.findall(r"[a-z0-9.]+", q)) - STOP_WORDS
    if len(question_words) < 1:
        return None

    best_score = 0
    best_result: AnswerWithProof | None = None

    for g in grids:
        if g.rows < 2 or g.cols < 2:
            continue
        for row_idx in range(g.rows):
            header_cell = g.get_cell(row_idx, 0)
            if not header_cell:
                continue
            hdr_text = str(header_cell.value).lower()
            hdr_words = set(re.findall(r"[a-z0-9.]+", hdr_text))
            overlap = len(question_words & hdr_words)
            if overlap > best_score:
                values = []
                for col_idx in range(1, g.cols):
                    cell = g.get_cell(row_idx, col_idx)
                    if cell and str(cell.value).strip():
                        values.append(str(cell.value))
                if values:
                    best_score = overlap
                    ox = header_cell.origin.x if header_cell.origin else g.origin.x
                    oy = header_cell.origin.y if header_cell.origin else g.origin.y
                    best_result = AnswerWithProof(
                        answer=", ".join(values),
                        proof=[_proof_point(ox, oy, g.page, _bbox_from(g), g.id, "grid")],
                        source_id=g.id,
                        source_type="grid",
                    )
    return best_result


# ---------------------------------------------------------------------------
# 1000: Unit lookup by label/value (improved fallback)
# ---------------------------------------------------------------------------
@rule(1000, "unit_lookup")
def _try_unit_lookup(
    question: str, units: list[Unit], bijections: list[Bijection], grids: list[Grid]
) -> AnswerWithProof | None:
    q = _q(question)
    q_normalized = q.replace("temp", "temperature").replace("freq", "frequency").replace("volt", "voltage")

    for u in units:
        if u.label:
            label_lower = u.label.lower()
            label_normalized = label_lower.replace("temp", "temperature").replace("freq", "frequency")
            if label_lower in q or label_normalized in q_normalized:
                return _answer_from_unit(u)
        ctx = (u.context or "").lower()
        if ctx and len(ctx) > 3 and ctx in q:
            return _answer_from_unit(u)
    return None


# ===================================================================
# Main entry point
# ===================================================================


def verify_and_answer(
    question: str,
    units: list[Unit],
    bijections: list[Bijection],
    grids: list[Grid],
) -> AnswerWithProof | Refuse:
    """
    Determine if the question can be answered from canonical facts.

    Same question + same canonical set → same answer or same REFUSE (deterministic).
    Rules are tried in priority order (lower priority number = tried first).
    After all direct-lookup rules, derived-query rules (power, thermal, margin, budget) are tried.
    """
    for _priority, _name, fn in _RULES:
        result = fn(question, units, bijections, grids)
        if result is not None:
            return result

    from akili.verify.derived import try_derived_queries
    derived = try_derived_queries(question, units, bijections, grids)
    if derived is not None:
        return derived

    return Refuse(reason="No canonical fact derives this answer.")
