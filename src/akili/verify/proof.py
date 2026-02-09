"""
Proof rules: derive answer from canonical facts; deterministic REFUSE if not provable.
"""

from __future__ import annotations

import re

from akili.canonical import Bijection, Grid, Unit
from akili.verify.models import AnswerWithProof, ProofPoint, ProofPointBBox, Refuse


# Regex patterns for parsing (numeric_value, unit_symbol) from text.
# Order matters: longer units first (e.g. mAh before A).
_VOLTAGE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:V|VOLT|VOLTS)\b", re.IGNORECASE
)
_CURRENT_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:µA|mA|A)\b", re.IGNORECASE
)
_CAPACITY_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:mAh|Ah|Wh)\b", re.IGNORECASE
)
_RESISTANCE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:Ω|ohm|ohms)\b", re.IGNORECASE
)


def _proof_point(
    x: float,
    y: float,
    page: int = 0,
    bbox: ProofPointBBox | None = None,
    source_id: str | None = None,
    source_type: str | None = None,
) -> ProofPoint:
    return ProofPoint(x=x, y=y, page=page, bbox=bbox, source_id=source_id, source_type=source_type)


def _parse_voltage_from_text(text: str) -> list[tuple[float, str]]:
    """Return [(numeric_value, unit_str), ...] for voltages found in text."""
    out: list[tuple[float, str]] = []
    for m in _VOLTAGE_PATTERN.finditer(text):
        try:
            out.append((float(m.group(1)), "V"))
        except (TypeError, ValueError):
            continue
    return out


def _parse_current_from_text(text: str) -> list[tuple[float, str]]:
    """Return [(numeric_value, unit_str), ...] for currents found in text."""
    out: list[tuple[float, str]] = []
    for m in _CURRENT_PATTERN.finditer(text):
        try:
            unit = m.group(0).split()[-1] if m.group(0) else "A"
            if "µ" in unit or "u" in unit.lower():
                unit = "µA"
            elif "m" in unit.lower():
                unit = "mA"
            else:
                unit = "A"
            out.append((float(m.group(1)), unit))
        except (TypeError, ValueError, IndexError):
            continue
    return out


def _parse_capacity_from_text(text: str) -> list[tuple[float, str]]:
    """Return [(numeric_value, unit_str), ...] for capacity/energy found in text."""
    out: list[tuple[float, str]] = []
    for m in _CAPACITY_PATTERN.finditer(text):
        try:
            unit = m.group(0).split()[-1] if m.group(0) else "mAh"
            out.append((float(m.group(1)), unit))
        except (TypeError, ValueError, IndexError):
            continue
    return out


def _get_unit_text(u: Unit) -> str:
    """Concatenate value, label, and context for parsing and intent matching."""
    parts = [str(u.value), u.label or "", getattr(u, "context", None) or ""]
    return " ".join(p for p in parts if p)


def _try_pin_lookup(
    question: str, bijections: list[Bijection], grids: list[Grid]
) -> AnswerWithProof | None:
    """Look for 'pin N', 'pin number N', 'what is pin X' and resolve via bijection or grid."""
    question_lower = question.lower().strip()
    # Match "pin 5", "pin number 5", "what is pin 5"
    pin_num = re.search(r"pin\s+(?:number\s+)?(\d+)", question_lower)
    if pin_num:
        n = pin_num.group(1)
        for b in bijections:
            right = b.get_right(n)
            if right is not None:
                bbox = (
                    ProofPointBBox(x1=b.bbox.x1, y1=b.bbox.y1, x2=b.bbox.x2, y2=b.bbox.y2)
                    if b.bbox
                    else None
                )
                return AnswerWithProof(
                    answer=right,
                    proof=[_proof_point(b.origin.x, b.origin.y, b.page, bbox, b.id, "bijection")],
                    source_id=b.id,
                    source_type="bijection",
                )
            left = b.get_left(n)
            if left is not None:
                bbox = (
                    ProofPointBBox(x1=b.bbox.x1, y1=b.bbox.y1, x2=b.bbox.x2, y2=b.bbox.y2)
                    if b.bbox
                    else None
                )
                return AnswerWithProof(
                    answer=left,
                    proof=[_proof_point(b.origin.x, b.origin.y, b.page, bbox, b.id, "bijection")],
                    source_id=b.id,
                    source_type="bijection",
                )
        for g in grids:
            # Try row 0 as header; row N as pin N; col 0 = number, col 1 = name (pinout table)
            for row in range(g.rows):
                for col in range(g.cols):
                    cell = g.get_cell(row, col)
                    if cell and str(cell.value) == n:
                        ox = cell.origin.x if cell.origin else g.origin.x
                        oy = cell.origin.y if cell.origin else g.origin.y
                        # Prefer pin name from same row, next col (col+1); else col-1
                        name_cell = g.get_cell(row, col + 1) if col + 1 < g.cols else None
                        if not name_cell and col > 0:
                            name_cell = g.get_cell(row, col - 1)
                        answer_val = str(name_cell.value) if name_cell else str(cell.value)
                        bbox = (
                            ProofPointBBox(x1=g.bbox.x1, y1=g.bbox.y1, x2=g.bbox.x2, y2=g.bbox.y2)
                            if g.bbox
                            else None
                        )
                        return AnswerWithProof(
                            answer=answer_val,
                            proof=[_proof_point(ox, oy, g.page, bbox, g.id, "grid")],
                            source_id=g.id,
                            source_type="grid",
                        )
    return None


def _try_voltage_max(question: str, units: list[Unit]) -> AnswerWithProof | None:
    """Look for 'max voltage', 'maximum voltage' and return max V from units."""
    question_lower = question.lower()
    if "max" not in question_lower and "maximum" not in question_lower:
        return None
    if (
        "voltage" not in question_lower
        and "v " not in question_lower
        and " v" not in question_lower
    ):
        return None

    # Primary: units with explicit unit_of_measure V and numeric value
    voltage_units = [
        u
        for u in units
        if u.unit_of_measure and u.unit_of_measure.upper() in ("V", "VOLT", "VOLTS")
    ]
    numeric: list[tuple[float, Unit]] = []
    for u in voltage_units:
        try:
            v = float(u.value)
            numeric.append((v, u))
        except (TypeError, ValueError):
            continue

    # Fallback: parse voltage from value/label text when no structured V units
    if not numeric:
        for u in units:
            text = _get_unit_text(u)
            for val, _ in _parse_voltage_from_text(text):
                numeric.append((val, u))

    if not numeric:
        return None
    max_u = max(numeric, key=lambda x: x[0])[1]
    max_val = max(numeric, key=lambda x: x[0])[0]
    bbox = (
        ProofPointBBox(x1=max_u.bbox.x1, y1=max_u.bbox.y1, x2=max_u.bbox.x2, y2=max_u.bbox.y2)
        if max_u.bbox
        else None
    )
    answer_str = f"{max_u.value} {max_u.unit_of_measure or ''}".strip() if max_u.unit_of_measure else f"{max_val} V"
    if not answer_str.strip().endswith("V"):
        answer_str = f"{max_val} V"
    return AnswerWithProof(
        answer=answer_str,
        proof=[_proof_point(max_u.origin.x, max_u.origin.y, max_u.page, bbox, max_u.id, "unit")],
        source_id=max_u.id,
        source_type="unit",
    )


def _try_max_current(question: str, units: list[Unit]) -> AnswerWithProof | None:
    """Look for 'max current', 'maximum current' and return max A/mA from units."""
    question_lower = question.lower()
    if "max" not in question_lower and "maximum" not in question_lower:
        return None
    if "current" not in question_lower and " a " not in question_lower and " amper" not in question_lower:
        return None

    numeric: list[tuple[float, Unit, str]] = []
    for u in units:
        if u.unit_of_measure and u.unit_of_measure.upper() in ("A", "MA", "µA"):
            try:
                v = float(u.value)
                numeric.append((v, u, u.unit_of_measure or "A"))
            except (TypeError, ValueError):
                pass
        text = _get_unit_text(u)
        for val, uom in _parse_current_from_text(text):
            numeric.append((val, u, uom))

    if not numeric:
        return None
    best = max(numeric, key=lambda x: x[0])
    max_val, max_u, uom = best
    bbox = (
        ProofPointBBox(x1=max_u.bbox.x1, y1=max_u.bbox.y1, x2=max_u.bbox.x2, y2=max_u.bbox.y2)
        if max_u.bbox
        else None
    )
    return AnswerWithProof(
        answer=f"{max_val} {uom}".strip(),
        proof=[_proof_point(max_u.origin.x, max_u.origin.y, max_u.page, bbox, max_u.id, "unit")],
        source_id=max_u.id,
        source_type="unit",
    )


def _try_max_capacity(question: str, units: list[Unit]) -> AnswerWithProof | None:
    """Look for 'max capacity', 'maximum capacity', 'nominal capacity' and return max mAh/Ah/Wh."""
    question_lower = question.lower()
    if "max" not in question_lower and "maximum" not in question_lower and "nominal" not in question_lower:
        return None
    if "capacity" not in question_lower and "mah" not in question_lower and " ah " not in question_lower and " wh " not in question_lower:
        return None

    numeric: list[tuple[float, Unit, str]] = []
    for u in units:
        text = _get_unit_text(u)
        for val, uom in _parse_capacity_from_text(text):
            numeric.append((val, u, uom))
        if u.unit_of_measure and u.unit_of_measure.upper() in ("MAH", "AH", "WH"):
            try:
                v = float(u.value)
                numeric.append((v, u, u.unit_of_measure or "mAh"))
            except (TypeError, ValueError):
                pass

    if not numeric:
        return None
    best = max(numeric, key=lambda x: x[0])
    max_val, max_u, uom = best
    bbox = (
        ProofPointBBox(x1=max_u.bbox.x1, y1=max_u.bbox.y1, x2=max_u.bbox.x2, y2=max_u.bbox.y2)
        if max_u.bbox
        else None
    )
    return AnswerWithProof(
        answer=f"{max_val} {uom}".strip(),
        proof=[_proof_point(max_u.origin.x, max_u.origin.y, max_u.page, bbox, max_u.id, "unit")],
        source_id=max_u.id,
        source_type="unit",
    )


def _try_unit_by_intent(question: str, units: list[Unit]) -> AnswerWithProof | None:
    """
    Match question intent (voltage, current, capacity, charge, cutoff, etc.) to units
    by type and by words in label/value. Return best-matching unit as answer.
    """
    question_lower = question.lower().strip()
    # Keywords that map to quantity types
    wants_voltage = any(w in question_lower for w in ("voltage", "volt", " v ", "charge voltage", "cutoff voltage", "cut-off voltage", "max voltage"))
    wants_current = any(w in question_lower for w in ("current", " amper", " a ", "discharge current", "charge current"))
    wants_capacity = any(w in question_lower for w in ("capacity", "mah", " ah ", " wh ", "nominal capacity"))

    candidates: list[tuple[float, str, Unit, str]] = []  # (score, answer_str, unit, match_type)

    for u in units:
        text = _get_unit_text(u)
        text_lower = text.lower()

        # Score by keyword overlap (question words in unit text)
        question_words = set(re.findall(r"[a-z0-9.]+", question_lower))
        question_words.discard("what")
        question_words.discard("is")
        question_words.discard("the")
        question_words.discard("of")
        question_words.discard("this")
        question_words.discard("document")
        overlap = sum(1 for w in question_words if len(w) > 1 and w in text_lower)

        if wants_voltage:
            if u.unit_of_measure and u.unit_of_measure.upper() in ("V", "VOLT", "VOLTS"):
                try:
                    v = float(u.value)
                    candidates.append((overlap + 10, f"{u.value} {u.unit_of_measure or ''}".strip(), u, "structured"))
                except (TypeError, ValueError):
                    pass
            for val, _ in _parse_voltage_from_text(text):
                candidates.append((overlap + 5, f"{val} V", u, "parsed"))

        if wants_current:
            if u.unit_of_measure and u.unit_of_measure.upper() in ("A", "MA", "µA"):
                try:
                    v = float(u.value)
                    candidates.append((overlap + 10, f"{u.value} {u.unit_of_measure or ''}".strip(), u, "structured"))
                except (TypeError, ValueError):
                    pass
            for val, uom in _parse_current_from_text(text):
                candidates.append((overlap + 5, f"{val} {uom}", u, "parsed"))

        if wants_capacity:
            if u.unit_of_measure and u.unit_of_measure.upper() in ("MAH", "AH", "WH"):
                try:
                    v = float(u.value)
                    candidates.append((overlap + 10, f"{u.value} {u.unit_of_measure or ''}".strip(), u, "structured"))
                except (TypeError, ValueError):
                    pass
            for val, uom in _parse_capacity_from_text(text):
                candidates.append((overlap + 5, f"{val} {uom}", u, "parsed"))

    if not candidates:
        return None
    # Best: highest score, then origin for determinism
    best = max(candidates, key=lambda x: (x[0], x[2].origin.y, x[2].origin.x))
    _score, answer_str, best_u, _ = best
    bbox = (
        ProofPointBBox(x1=best_u.bbox.x1, y1=best_u.bbox.y1, x2=best_u.bbox.x2, y2=best_u.bbox.y2)
        if best_u.bbox
        else None
    )
    return AnswerWithProof(
        answer=answer_str,
        proof=[_proof_point(best_u.origin.x, best_u.origin.y, best_u.page, bbox, best_u.id, "unit")],
        source_id=best_u.id,
        source_type="unit",
    )


def _try_unit_lookup(question: str, units: list[Unit]) -> AnswerWithProof | None:
    """Look for label or value mention in question and match a unit."""
    question_lower = question.lower()
    for u in units:
        bbox = (
            ProofPointBBox(x1=u.bbox.x1, y1=u.bbox.y1, x2=u.bbox.x2, y2=u.bbox.y2)
            if u.bbox
            else None
        )
        if u.label and u.label.lower() in question_lower:
            return AnswerWithProof(
                answer=f"{u.value} {u.unit_of_measure or ''}".strip(),
                proof=[_proof_point(u.origin.x, u.origin.y, u.page, bbox, u.id, "unit")],
                source_id=u.id,
                source_type="unit",
            )
        if str(u.value).lower() in question_lower:
            return AnswerWithProof(
                answer=f"{u.value} {u.unit_of_measure or ''}".strip(),
                proof=[_proof_point(u.origin.x, u.origin.y, u.page, bbox, u.id, "unit")],
                source_id=u.id,
                source_type="unit",
            )
    return None


def verify_and_answer(
    question: str,
    units: list[Unit],
    bijections: list[Bijection],
    grids: list[Grid],
) -> AnswerWithProof | Refuse:
    """
    Determine if the question can be answered from canonical facts.

    Same question + same canonical set → same answer or same REFUSE (deterministic).
    """
    # Order of rules matters for determinism
    result = _try_pin_lookup(question, bijections, grids)
    if result is not None:
        return result
    result = _try_voltage_max(question, units)
    if result is not None:
        return result
    result = _try_max_current(question, units)
    if result is not None:
        return result
    result = _try_max_capacity(question, units)
    if result is not None:
        return result
    result = _try_unit_by_intent(question, units)
    if result is not None:
        return result
    result = _try_unit_lookup(question, units)
    if result is not None:
        return result
    return Refuse(reason="No canonical fact derives this answer.")
