"""
Cross-document comparison engine (C3).

Supports:
- "Compare the max voltage of Component A vs Component B"
- "Which of these components has the lowest thermal resistance?"
- "Do any of these components exceed the 85°C operating range?"

All queries are executed via SQL JOINs across doc_id — no graph database needed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from akili.canonical import Unit
from akili.verify.models import ConfidenceScore, ProofPoint, ProofPointBBox


@dataclass
class ComparisonRow:
    """One row in a comparison table: one document's value for a given parameter."""

    doc_id: str
    doc_name: str
    parameter: str
    value: float | str | None
    unit_of_measure: str | None
    source_unit_id: str | None
    page: int | None
    proof: ProofPoint | None


@dataclass
class ComparisonResult:
    """Full comparison across multiple documents for one parameter."""

    parameter: str
    rows: list[ComparisonRow] = field(default_factory=list)
    best_doc_id: str | None = None
    best_value: float | str | None = None
    direction: str = "lower"
    summary: str = ""


def _proof_from_unit(u: Unit) -> ProofPoint:
    bbox = None
    if u.bbox:
        bbox = ProofPointBBox(x1=u.bbox.x1, y1=u.bbox.y1, x2=u.bbox.x2, y2=u.bbox.y2)
    return ProofPoint(
        x=u.origin.x, y=u.origin.y, page=u.page,
        bbox=bbox, source_id=u.id, source_type="unit",
    )


def _find_best_unit(
    units: list[Unit],
    context_keywords: list[str],
    label_keywords: list[str] | None = None,
    unit_measures: list[str] | None = None,
) -> Unit | None:
    """Find the best matching unit from a flat list."""
    label_keywords = label_keywords or context_keywords
    for u in units:
        ctx = (u.context or "").lower()
        lbl = (u.label or "").lower()
        uom = (u.unit_of_measure or "").lower()
        ctx_match = any(kw in ctx for kw in context_keywords)
        lbl_match = any(kw in lbl for kw in label_keywords)
        uom_match = not unit_measures or uom in [m.lower() for m in unit_measures]
        if (ctx_match or lbl_match) and uom_match:
            try:
                float(u.value)
                return u
            except (ValueError, TypeError):
                continue
    return None


# Predefined parameter configurations for common cross-doc comparisons
_PARAM_CONFIGS: dict[str, dict] = {
    "max_voltage": {
        "label": "Maximum Voltage",
        "context_kw": ["maximum voltage", "max voltage", "absolute max"],
        "label_kw": ["vmax", "vcc max", "absolute max"],
        "uom": ["V"],
        "direction": "lower",
    },
    "supply_voltage": {
        "label": "Supply Voltage",
        "context_kw": ["supply voltage", "operating voltage"],
        "label_kw": ["vcc", "vdd"],
        "uom": ["V"],
        "direction": "neutral",
    },
    "thermal_resistance": {
        "label": "Thermal Resistance (θJA)",
        "context_kw": ["thermal resistance", "theta", "θja", "junction to ambient"],
        "label_kw": ["θja", "rthja"],
        "uom": ["°C/W", "C/W", "K/W"],
        "direction": "lower",
    },
    "max_current": {
        "label": "Maximum Current",
        "context_kw": ["maximum current", "max current"],
        "label_kw": ["imax", "icc max"],
        "uom": ["A", "mA"],
        "direction": "lower",
    },
    "operating_temperature": {
        "label": "Operating Temperature Range",
        "context_kw": ["operating temperature", "temperature range"],
        "label_kw": ["topr", "ta"],
        "uom": ["°C", "C"],
        "direction": "higher",
    },
    "power_dissipation": {
        "label": "Power Dissipation",
        "context_kw": ["power dissipation", "max power"],
        "label_kw": ["pd", "ptot"],
        "uom": ["W", "mW"],
        "direction": "lower",
    },
}


def _detect_parameters(query: str) -> list[str]:
    """Detect which parameters the user wants to compare based on query text."""
    q = query.lower()
    detected = []

    mappings = {
        "max_voltage": ["max voltage", "maximum voltage", "absolute max"],
        "supply_voltage": ["supply voltage", "operating voltage", "vcc", "vdd"],
        "thermal_resistance": ["thermal resistance", "θja", "theta", "rthja"],
        "max_current": ["max current", "maximum current"],
        "operating_temperature": ["operating temp", "temperature range", "85°c", "85c"],
        "power_dissipation": ["power dissipation", "power consumption"],
    }

    for param, keywords in mappings.items():
        if any(kw in q for kw in keywords):
            detected.append(param)

    if not detected:
        detected = list(_PARAM_CONFIGS.keys())

    return detected


def compare_documents(
    query: str,
    doc_units: dict[str, tuple[str, list[Unit]]],
) -> list[ComparisonResult]:
    """
    Compare parameters across multiple documents.

    Args:
        query: Natural-language comparison question.
        doc_units: Mapping of doc_id -> (doc_name, units) for each document to compare.

    Returns a list of ComparisonResult, one per detected parameter.
    """
    params = _detect_parameters(query)
    results = []

    for param in params:
        config = _PARAM_CONFIGS.get(param)
        if not config:
            continue

        comp = ComparisonResult(
            parameter=config["label"],
            direction=config.get("direction", "lower"),
        )

        numeric_rows: list[tuple[float, ComparisonRow]] = []

        for doc_id, (doc_name, units) in doc_units.items():
            best = _find_best_unit(
                units,
                context_keywords=config["context_kw"],
                label_keywords=config.get("label_kw"),
                unit_measures=config.get("uom"),
            )
            if best is not None:
                try:
                    val = float(best.value)
                except (ValueError, TypeError):
                    val = None
                row = ComparisonRow(
                    doc_id=doc_id,
                    doc_name=doc_name,
                    parameter=config["label"],
                    value=val if val is not None else best.value,
                    unit_of_measure=best.unit_of_measure,
                    source_unit_id=best.id,
                    page=best.page,
                    proof=_proof_from_unit(best),
                )
                comp.rows.append(row)
                if val is not None:
                    numeric_rows.append((val, row))
            else:
                comp.rows.append(ComparisonRow(
                    doc_id=doc_id,
                    doc_name=doc_name,
                    parameter=config["label"],
                    value=None,
                    unit_of_measure=None,
                    source_unit_id=None,
                    page=None,
                    proof=None,
                ))

        if numeric_rows:
            if comp.direction == "lower":
                best_val, best_row = min(numeric_rows, key=lambda t: t[0])
            elif comp.direction == "higher":
                best_val, best_row = max(numeric_rows, key=lambda t: t[0])
            else:
                best_val, best_row = numeric_rows[0]
            comp.best_doc_id = best_row.doc_id
            comp.best_value = best_val

            values_str = ", ".join(
                f"{r.doc_name}: {r.value} {r.unit_of_measure or ''}"
                for r in comp.rows if r.value is not None
            )
            direction_word = "lowest" if comp.direction == "lower" else "highest" if comp.direction == "higher" else ""
            if direction_word:
                comp.summary = (
                    f"{config['label']}: {values_str}. "
                    f"{direction_word.title()}: {best_row.doc_name} ({best_val} {best_row.unit_of_measure or ''})"
                )
            else:
                comp.summary = f"{config['label']}: {values_str}"

        results.append(comp)

    return results


def format_comparison_response(results: list[ComparisonResult]) -> dict:
    """Serialize comparison results for API response."""
    return {
        "comparisons": [
            {
                "parameter": r.parameter,
                "direction": r.direction,
                "best_doc_id": r.best_doc_id,
                "best_value": r.best_value,
                "summary": r.summary,
                "rows": [
                    {
                        "doc_id": row.doc_id,
                        "doc_name": row.doc_name,
                        "value": row.value,
                        "unit_of_measure": row.unit_of_measure,
                        "source_unit_id": row.source_unit_id,
                        "page": row.page,
                    }
                    for row in r.rows
                ],
            }
            for r in results
        ],
    }
