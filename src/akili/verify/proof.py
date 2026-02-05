"""
Proof rules: derive answer from canonical facts; deterministic REFUSE if not provable.
"""

from __future__ import annotations

import re
from typing import Any

from akili.canonical import Bijection, Grid, Unit
from akili.verify.models import AnswerWithProof, ProofPoint, Refuse


def _proof_point(
    x: float,
    y: float,
    page: int = 0,
    source_id: str | None = None,
    source_type: str | None = None,
) -> ProofPoint:
    return ProofPoint(x=x, y=y, page=page, source_id=source_id, source_type=source_type)


def _try_pin_lookup(question: str, bijections: list[Bijection], grids: list[Grid]) -> AnswerWithProof | None:
    """Look for 'pin N', 'pin number N', 'what is pin X' and resolve via bijection or grid."""
    question_lower = question.lower().strip()
    # Match "pin 5", "pin number 5", "what is pin 5"
    pin_num = re.search(r"pin\s+(?:number\s+)?(\d+)", question_lower)
    if pin_num:
        n = pin_num.group(1)
        for b in bijections:
            right = b.get_right(n)
            if right is not None:
                return AnswerWithProof(
                    answer=right,
                    proof=[_proof_point(b.origin.x, b.origin.y, b.page, b.id, "bijection")],
                    source_id=b.id,
                    source_type="bijection",
                )
            left = b.get_left(n)
            if left is not None:
                return AnswerWithProof(
                    answer=left,
                    proof=[_proof_point(b.origin.x, b.origin.y, b.page, b.id, "bijection")],
                    source_id=b.id,
                    source_type="bijection",
                )
        for g in grids:
            # Try row 0 as header; row N as pin N; col 0 = number, col 1 = name (typical pinout table)
            for row in range(g.rows):
                for col in range(g.cols):
                    cell = g.get_cell(row, col)
                    if cell and str(cell.value) == n:
                        ox = cell.origin.x if cell.origin else g.origin.x
                        oy = cell.origin.y if cell.origin else g.origin.y
                        # Prefer pin name from same row, next column (col+1); else same row col-1; else pin number
                        name_cell = g.get_cell(row, col + 1) if col + 1 < g.cols else None
                        if not name_cell and col > 0:
                            name_cell = g.get_cell(row, col - 1)
                        answer_val = str(name_cell.value) if name_cell else str(cell.value)
                        return AnswerWithProof(
                            answer=answer_val,
                            proof=[_proof_point(ox, oy, g.page, g.id, "grid")],
                            source_id=g.id,
                            source_type="grid",
                        )
    return None


def _try_voltage_max(question: str, units: list[Unit]) -> AnswerWithProof | None:
    """Look for 'max voltage', 'maximum voltage' and return max V from units."""
    question_lower = question.lower()
    if "max" not in question_lower and "maximum" not in question_lower:
        return None
    if "voltage" not in question_lower and "v " not in question_lower and " v" not in question_lower:
        return None
    voltage_units = [u for u in units if u.unit_of_measure and u.unit_of_measure.upper() in ("V", "VOLT", "VOLTS")]
    if not voltage_units:
        return None
    numeric = []
    for u in voltage_units:
        try:
            v = float(u.value)
            numeric.append((v, u))
        except (TypeError, ValueError):
            continue
    if not numeric:
        return None
    max_u = max(numeric, key=lambda x: x[0])[1]
    return AnswerWithProof(
        answer=f"{max_u.value} {max_u.unit_of_measure or ''}".strip(),
        proof=[_proof_point(max_u.origin.x, max_u.origin.y, max_u.page, max_u.id, "unit")],
        source_id=max_u.id,
        source_type="unit",
    )


def _try_unit_lookup(question: str, units: list[Unit]) -> AnswerWithProof | None:
    """Look for label or value mention in question and match a unit."""
    question_lower = question.lower()
    for u in units:
        if u.label and u.label.lower() in question_lower:
            return AnswerWithProof(
                answer=f"{u.value} {u.unit_of_measure or ''}".strip(),
                proof=[_proof_point(u.origin.x, u.origin.y, u.page, u.id, "unit")],
                source_id=u.id,
                source_type="unit",
            )
        if str(u.value).lower() in question_lower:
            return AnswerWithProof(
                answer=f"{u.value} {u.unit_of_measure or ''}".strip(),
                proof=[_proof_point(u.origin.x, u.origin.y, u.page, u.id, "unit")],
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
    result = _try_unit_lookup(question, units)
    if result is not None:
        return result
    return Refuse(reason="No canonical fact derives this answer.")
