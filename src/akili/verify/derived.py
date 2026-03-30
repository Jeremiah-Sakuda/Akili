"""
Derived query engine: compute answers from multiple canonical facts with full proof chains.

Supported derivations:
1. Power dissipation: P = V × I
2. Thermal check: T_junction = T_ambient + (P × θ_JA)
3. Voltage margin: (V_abs_max - V_operating) / V_abs_max × 100%
4. Current budget: Total supply current vs. sum of pin currents

Each derivation returns an AnswerWithProof with a ProofChain showing every step.
"""

from __future__ import annotations

import logging
import re

from akili.canonical import Bijection, Grid, Unit
from akili.verify.models import (
    AnswerWithProof,
    ConfidenceScore,
    ProofChain,
    ProofPoint,
    ProofPointBBox,
    ProofStep,
    compute_canonical_quality,
)

logger = logging.getLogger(__name__)


def _proof_point_from_unit(u: Unit) -> ProofPoint:
    bbox = None
    if u.bbox:
        bbox = ProofPointBBox(x1=u.bbox.x1, y1=u.bbox.y1, x2=u.bbox.x2, y2=u.bbox.y2)
    return ProofPoint(
        x=u.origin.x, y=u.origin.y, page=u.page,
        bbox=bbox, source_id=u.id, source_type="unit",
    )


def _numeric_value(u: Unit) -> float | None:
    try:
        return float(u.value)
    except (ValueError, TypeError):
        return None


def _find_unit(
    units: list[Unit],
    context_keywords: list[str],
    label_keywords: list[str] | None = None,
    unit_measures: list[str] | None = None,
) -> Unit | None:
    """Find the best matching unit by context/label keywords and optional unit_of_measure."""
    label_keywords = label_keywords or context_keywords
    for u in units:
        ctx = (u.context or "").lower()
        lbl = (u.label or "").lower()
        uom = (u.unit_of_measure or "").lower()

        ctx_match = any(kw in ctx for kw in context_keywords)
        lbl_match = any(kw in lbl for kw in label_keywords)
        uom_match = not unit_measures or uom in [m.lower() for m in unit_measures]

        if (ctx_match or lbl_match) and uom_match and _numeric_value(u) is not None:
            return u
    return None


def _find_units_by(
    units: list[Unit],
    context_keywords: list[str],
    label_keywords: list[str] | None = None,
    unit_measures: list[str] | None = None,
) -> list[Unit]:
    """Find all matching units."""
    label_keywords = label_keywords or context_keywords
    results = []
    for u in units:
        ctx = (u.context or "").lower()
        lbl = (u.label or "").lower()
        uom = (u.unit_of_measure or "").lower()
        ctx_match = any(kw in ctx for kw in context_keywords)
        lbl_match = any(kw in lbl for kw in label_keywords)
        uom_match = not unit_measures or uom in [m.lower() for m in unit_measures]
        if (ctx_match or lbl_match) and uom_match and _numeric_value(u) is not None:
            results.append(u)
    return results


# ---------------------------------------------------------------------------
# Derivation 1: Power Dissipation (P = V × I)
# ---------------------------------------------------------------------------

_POWER_PATTERNS = re.compile(
    r"(power\s+dissipat|calculate.*power|compute.*power|what.*power|p\s*=\s*v\s*[×x*]\s*i)",
    re.IGNORECASE,
)


def derive_power_dissipation(
    question: str, units: list[Unit]
) -> AnswerWithProof | None:
    """P = V × I from extracted voltage and current specs."""
    if not _POWER_PATTERNS.search(question):
        return None

    voltage_unit = _find_unit(
        units,
        context_keywords=["supply voltage", "operating voltage", "vcc", "vdd"],
        label_keywords=["vcc", "vdd", "supply"],
        unit_measures=["V", "mV"],
    )
    current_unit = _find_unit(
        units,
        context_keywords=["supply current", "operating current", "icc", "idd"],
        label_keywords=["icc", "idd", "supply current"],
        unit_measures=["A", "mA", "uA"],
    )

    if voltage_unit is None or current_unit is None:
        return None

    v = _numeric_value(voltage_unit)
    i = _numeric_value(current_unit)
    if v is None or i is None:
        return None

    v_volts = v if (voltage_unit.unit_of_measure or "").upper() == "V" else v / 1000.0
    i_amps = i
    i_uom = (current_unit.unit_of_measure or "").lower()
    if i_uom == "ma":
        i_amps = i / 1000.0
    elif i_uom == "ua" or i_uom == "\u00b5a":
        i_amps = i / 1_000_000.0

    power_w = v_volts * i_amps
    power_mw = power_w * 1000.0

    if power_mw < 1.0:
        power_str = f"{power_mw:.3f} mW"
    elif power_mw < 1000.0:
        power_str = f"{power_mw:.1f} mW"
    else:
        power_str = f"{power_w:.2f} W"

    steps = [
        ProofStep(
            description=f"Voltage: {v} {voltage_unit.unit_of_measure} from {voltage_unit.id}",
            source_facts=[_proof_point_from_unit(voltage_unit)],
            result=f"{v_volts} V",
        ),
        ProofStep(
            description=f"Current: {i} {current_unit.unit_of_measure} from {current_unit.id}",
            source_facts=[_proof_point_from_unit(current_unit)],
            result=f"{i_amps} A",
        ),
        ProofStep(
            description="Compute power dissipation",
            formula="P = V × I",
            source_facts=[
                _proof_point_from_unit(voltage_unit),
                _proof_point_from_unit(current_unit),
            ],
            result=power_str,
        ),
    ]

    chain = ProofChain(
        steps=steps,
        final_result=power_str,
        formula_summary=f"P = {v_volts}V × {i_amps}A = {power_str}",
    )

    all_proofs = [_proof_point_from_unit(voltage_unit), _proof_point_from_unit(current_unit)]

    min_cq = min(
        compute_canonical_quality(
            has_bbox=u.bbox is not None, has_origin=True,
            has_unit_of_measure=u.unit_of_measure is not None,
            has_label=u.label is not None, has_context=u.context is not None,
        )
        for u in [voltage_unit, current_unit]
    )

    confidence = ConfidenceScore.compute(
        extraction_agreement=0.5,
        canonical_validation=min_cq,
        verification_strength=0.85,
    )

    return AnswerWithProof(
        answer=f"Power dissipation: {power_str} (P = V × I = {v} {voltage_unit.unit_of_measure} × {i} {current_unit.unit_of_measure})",
        proof=all_proofs,
        source_type="derived",
        confidence=confidence,
        derivation=chain,
    )


# ---------------------------------------------------------------------------
# Derivation 2: Thermal Check (T_j = T_a + P × θ_JA)
# ---------------------------------------------------------------------------

_THERMAL_PATTERNS = re.compile(
    r"(thermal\s+check|junction\s+temp.*safe|within.*thermal|t_?junction|calculate.*temperature|thermal\s+margin)",
    re.IGNORECASE,
)


def derive_thermal_check(
    question: str, units: list[Unit]
) -> AnswerWithProof | None:
    """T_junction = T_ambient + (P × θ_JA). Check if within max junction temp."""
    if not _THERMAL_PATTERNS.search(question):
        return None

    theta_unit = _find_unit(
        units,
        context_keywords=["thermal resistance", "theta", "\u03b8ja", "junction to ambient"],
        label_keywords=["\u03b8ja", "theta", "rthja", "thermal"],
        unit_measures=["°C/W", "C/W", "K/W"],
    )

    power_unit = _find_unit(
        units,
        context_keywords=["power dissipation", "total power"],
        label_keywords=["pd", "power"],
        unit_measures=["W", "mW"],
    )

    max_tj_unit = _find_unit(
        units,
        context_keywords=["maximum junction temperature", "junction temp"],
        label_keywords=["tj max", "tjmax"],
        unit_measures=["°C", "C"],
    )

    if theta_unit is None:
        return None

    theta_val = _numeric_value(theta_unit)
    if theta_val is None:
        return None

    t_ambient = 25.0
    steps: list[ProofStep] = []
    proofs: list[ProofPoint] = []

    steps.append(ProofStep(
        description=f"Thermal resistance: {theta_val} {theta_unit.unit_of_measure}",
        source_facts=[_proof_point_from_unit(theta_unit)],
        result=f"{theta_val} °C/W",
    ))
    proofs.append(_proof_point_from_unit(theta_unit))

    if power_unit is not None:
        p_val = _numeric_value(power_unit)
        if p_val is not None:
            p_watts = p_val
            p_uom = (power_unit.unit_of_measure or "").lower()
            if p_uom == "mw":
                p_watts = p_val / 1000.0
            steps.append(ProofStep(
                description=f"Power dissipation: {p_val} {power_unit.unit_of_measure}",
                source_facts=[_proof_point_from_unit(power_unit)],
                result=f"{p_watts} W",
            ))
            proofs.append(_proof_point_from_unit(power_unit))
        else:
            return None
    else:
        voltage = _find_unit(units, ["supply voltage", "vcc"], ["vcc", "vdd"], ["V", "mV"])
        current = _find_unit(units, ["supply current", "icc"], ["icc", "idd"], ["A", "mA"])
        if voltage and current:
            v = _numeric_value(voltage)
            i = _numeric_value(current)
            if v is not None and i is not None:
                v_volts = v if (voltage.unit_of_measure or "").upper() == "V" else v / 1000.0
                i_amps = i
                if (current.unit_of_measure or "").lower() == "ma":
                    i_amps = i / 1000.0
                p_watts = v_volts * i_amps
                steps.append(ProofStep(
                    description=f"Derived power: P = {v_volts}V × {i_amps}A",
                    formula="P = V × I",
                    source_facts=[_proof_point_from_unit(voltage), _proof_point_from_unit(current)],
                    result=f"{p_watts} W",
                ))
                proofs.extend([_proof_point_from_unit(voltage), _proof_point_from_unit(current)])
            else:
                return None
        else:
            return None

    p_watts = float(steps[-1].result.replace(" W", ""))
    t_junction = t_ambient + (p_watts * theta_val)

    steps.append(ProofStep(
        description=f"Junction temperature at {t_ambient}°C ambient",
        formula=f"T_j = T_a + (P × θ_JA) = {t_ambient} + ({p_watts} × {theta_val})",
        source_facts=proofs.copy(),
        result=f"{t_junction:.1f} °C",
    ))

    answer_parts = [f"T_junction = {t_junction:.1f}°C at {t_ambient}°C ambient"]

    if max_tj_unit is not None:
        max_tj = _numeric_value(max_tj_unit)
        if max_tj is not None:
            safe = t_junction <= max_tj
            margin = max_tj - t_junction
            answer_parts.append(
                f"{'SAFE' if safe else 'EXCEEDS LIMIT'}: max T_j = {max_tj}°C, margin = {margin:.1f}°C"
            )
            steps.append(ProofStep(
                description=f"Max junction temperature: {max_tj}°C",
                source_facts=[_proof_point_from_unit(max_tj_unit)],
                result=f"{'SAFE' if safe else 'EXCEEDS'} (margin: {margin:.1f}°C)",
            ))
            proofs.append(_proof_point_from_unit(max_tj_unit))

    chain = ProofChain(
        steps=steps,
        final_result=answer_parts[0],
        formula_summary=f"T_j = {t_ambient} + ({p_watts:.4f}W × {theta_val}°C/W) = {t_junction:.1f}°C",
    )

    confidence = ConfidenceScore.compute(
        extraction_agreement=0.5,
        canonical_validation=0.7,
        verification_strength=0.80,
    )

    return AnswerWithProof(
        answer="; ".join(answer_parts),
        proof=proofs,
        source_type="derived",
        confidence=confidence,
        derivation=chain,
    )


# ---------------------------------------------------------------------------
# Derivation 3: Voltage Margin
# ---------------------------------------------------------------------------

_VOLTAGE_MARGIN_PATTERNS = re.compile(
    r"(voltage\s+margin|how\s+close.*abs.*max|margin.*voltage|voltage.*headroom|operating.*vs.*max)",
    re.IGNORECASE,
)


def derive_voltage_margin(
    question: str, units: list[Unit]
) -> AnswerWithProof | None:
    """margin = (V_abs_max - V_operating) / V_abs_max × 100%."""
    if not _VOLTAGE_MARGIN_PATTERNS.search(question):
        return None

    v_operating = _find_unit(
        units,
        context_keywords=["supply voltage", "operating voltage", "typical supply"],
        label_keywords=["vcc", "vdd", "supply"],
        unit_measures=["V"],
    )

    v_abs_max = _find_unit(
        units,
        context_keywords=["absolute maximum voltage", "absolute max voltage"],
        label_keywords=["absolute max", "vcc max", "abs max"],
        unit_measures=["V"],
    )
    if v_abs_max is None:
        v_abs_max = _find_unit(
            units,
            context_keywords=["maximum voltage", "max voltage"],
            label_keywords=["vcc max", "vmax"],
            unit_measures=["V"],
        )

    if v_operating is None or v_abs_max is None:
        return None

    v_op = _numeric_value(v_operating)
    v_max = _numeric_value(v_abs_max)
    if v_op is None or v_max is None or v_max == 0:
        return None

    margin_pct = ((v_max - v_op) / v_max) * 100.0
    margin_v = v_max - v_op

    steps = [
        ProofStep(
            description=f"Operating voltage: {v_op} V",
            source_facts=[_proof_point_from_unit(v_operating)],
            result=f"{v_op} V",
        ),
        ProofStep(
            description=f"Absolute maximum voltage: {v_max} V",
            source_facts=[_proof_point_from_unit(v_abs_max)],
            result=f"{v_max} V",
        ),
        ProofStep(
            description="Compute voltage margin",
            formula=f"margin = ({v_max} - {v_op}) / {v_max} × 100%",
            source_facts=[
                _proof_point_from_unit(v_operating),
                _proof_point_from_unit(v_abs_max),
            ],
            result=f"{margin_pct:.1f}%",
        ),
    ]

    chain = ProofChain(
        steps=steps,
        final_result=f"{margin_pct:.1f}% ({margin_v:.2f} V headroom)",
        formula_summary=f"margin = ({v_max}V - {v_op}V) / {v_max}V × 100% = {margin_pct:.1f}%",
    )

    proofs = [_proof_point_from_unit(v_operating), _proof_point_from_unit(v_abs_max)]
    confidence = ConfidenceScore.compute(
        extraction_agreement=0.5,
        canonical_validation=0.75,
        verification_strength=0.85,
    )

    return AnswerWithProof(
        answer=f"Voltage margin: {margin_pct:.1f}% ({margin_v:.2f} V headroom). Operating: {v_op} V, Max: {v_max} V.",
        proof=proofs,
        source_type="derived",
        confidence=confidence,
        derivation=chain,
    )


# ---------------------------------------------------------------------------
# Derivation 4: Current Budget
# ---------------------------------------------------------------------------

_CURRENT_BUDGET_PATTERNS = re.compile(
    r"(current\s+budget|total.*current|sum.*current|current.*sum)",
    re.IGNORECASE,
)


def derive_current_budget(
    question: str, units: list[Unit]
) -> AnswerWithProof | None:
    """Sum of output/pin currents vs. total supply current."""
    if not _CURRENT_BUDGET_PATTERNS.search(question):
        return None

    supply_current = _find_unit(
        units,
        context_keywords=["supply current", "total current", "icc max", "maximum supply"],
        label_keywords=["icc", "idd", "supply current"],
        unit_measures=["A", "mA"],
    )
    if supply_current is None:
        return None

    output_currents = _find_units_by(
        units,
        context_keywords=["output current", "pin current", "io"],
        label_keywords=["io", "iout", "output"],
        unit_measures=["A", "mA"],
    )

    i_supply = _numeric_value(supply_current)
    if i_supply is None:
        return None

    i_uom = (supply_current.unit_of_measure or "").lower()

    steps = [
        ProofStep(
            description=f"Total supply current: {i_supply} {supply_current.unit_of_measure}",
            source_facts=[_proof_point_from_unit(supply_current)],
            result=f"{i_supply} {supply_current.unit_of_measure}",
        ),
    ]
    proofs = [_proof_point_from_unit(supply_current)]

    if output_currents:
        total_out = 0.0
        for oc in output_currents:
            val = _numeric_value(oc)
            if val is not None:
                oc_uom = (oc.unit_of_measure or "").lower()
                if oc_uom == i_uom:
                    total_out += val
                elif oc_uom == "ma" and i_uom == "a":
                    total_out += val / 1000.0
                elif oc_uom == "a" and i_uom == "ma":
                    total_out += val * 1000.0
                else:
                    total_out += val
                steps.append(ProofStep(
                    description=f"Output current: {val} {oc.unit_of_measure} ({oc.id})",
                    source_facts=[_proof_point_from_unit(oc)],
                    result=f"{val} {oc.unit_of_measure}",
                ))
                proofs.append(_proof_point_from_unit(oc))

        remaining = i_supply - total_out
        steps.append(ProofStep(
            description="Current budget summary",
            formula=f"Remaining = {i_supply} - {total_out:.1f} = {remaining:.1f} {supply_current.unit_of_measure}",
            source_facts=proofs.copy(),
            result=f"{remaining:.1f} {supply_current.unit_of_measure} remaining",
        ))

        chain = ProofChain(
            steps=steps,
            final_result=f"Supply: {i_supply} {supply_current.unit_of_measure}, Used: {total_out:.1f}, Remaining: {remaining:.1f}",
            formula_summary=f"Budget = {i_supply} - {total_out:.1f} = {remaining:.1f} {supply_current.unit_of_measure}",
        )

        answer = (
            f"Current budget: {i_supply} {supply_current.unit_of_measure} supply, "
            f"{total_out:.1f} {supply_current.unit_of_measure} allocated across {len(output_currents)} outputs, "
            f"{remaining:.1f} {supply_current.unit_of_measure} remaining."
        )
    else:
        chain = ProofChain(
            steps=steps,
            final_result=f"Total supply: {i_supply} {supply_current.unit_of_measure}",
            formula_summary=f"Supply current = {i_supply} {supply_current.unit_of_measure}",
        )
        answer = f"Total supply current: {i_supply} {supply_current.unit_of_measure}. No individual output currents found to sum."

    confidence = ConfidenceScore.compute(
        extraction_agreement=0.5,
        canonical_validation=0.7,
        verification_strength=0.80,
    )

    return AnswerWithProof(
        answer=answer,
        proof=proofs,
        source_type="derived",
        confidence=confidence,
        derivation=chain,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_DERIVATIONS = [
    derive_power_dissipation,
    derive_thermal_check,
    derive_voltage_margin,
    derive_current_budget,
]


def try_derived_queries(
    question: str,
    units: list[Unit],
    bijections: list[Bijection],
    grids: list[Grid],
) -> AnswerWithProof | None:
    """Try all derivation rules. Returns the first successful derivation, or None."""
    for derive_fn in _DERIVATIONS:
        result = derive_fn(question, units)
        if result is not None:
            return result
    return None
