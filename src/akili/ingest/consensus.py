"""
Consensus extraction: run Gemini twice with varied prompts and compare results.

Agreement -> high confidence. Disagreement -> flag for review or tiebreaker.
Only used for high-risk page types (electrical_specs, absolute_max_ratings)
when AKILIconfig.CONSENSUS_ENABLED=1.
"""

from __future__ import annotations

import logging
from difflib import SequenceMatcher

from akili import config
from akili.ingest.extract_schema import PageExtraction
from akili.ingest.gemini_extract import extract_page

logger = logging.getLogger(__name__)

HIGH_RISK_PAGE_TYPES = {"electrical_specs", "absolute_max_ratings"}

_PRECISION_SUFFIX = (
    "\n\nIMPORTANT: Prioritize PRECISION. Only extract facts you are highly confident about. "
    "Omit any value where you are unsure of the exact number or unit. "
    "It is better to miss a fact than to include an incorrect one."
)

_RECALL_SUFFIX = (
    "\n\nIMPORTANT: Prioritize RECALL. Extract every fact you can find on this page, "
    "even if you are somewhat uncertain about exact coordinates. "
    "Include all parameters, ratings, and specifications visible in tables and text."
)


def _unit_similarity(u1: dict, u2: dict) -> float:
    """Score how similar two extracted units are (0.0 to 1.0)."""
    score = 0.0
    weights = 0.0

    v1, v2 = str(u1.get("value", "")), str(u2.get("value", ""))
    if v1 and v2:
        if v1 == v2:
            score += 0.4
        else:
            try:
                if abs(float(v1) - float(v2)) < 0.01:
                    score += 0.4
            except (ValueError, TypeError):
                score += 0.4 * SequenceMatcher(None, v1, v2).ratio()
        weights += 0.4

    l1 = (u1.get("label") or "").lower().strip()
    l2 = (u2.get("label") or "").lower().strip()
    if l1 and l2:
        if l1 == l2:
            score += 0.3
        else:
            score += 0.3 * SequenceMatcher(None, l1, l2).ratio()
        weights += 0.3

    uom1 = (u1.get("unit_of_measure") or "").lower().strip()
    uom2 = (u2.get("unit_of_measure") or "").lower().strip()
    if uom1 and uom2:
        score += 0.2 if uom1 == uom2 else 0.0
        weights += 0.2

    o1 = u1.get("origin", {})
    o2 = u2.get("origin", {})
    if o1 and o2:
        try:
            dist = ((o1["x"] - o2["x"]) ** 2 + (o1["y"] - o2["y"]) ** 2) ** 0.5
            proximity = max(0, 1.0 - dist * 5)
            score += 0.1 * proximity
        except (KeyError, TypeError):
            pass
        weights += 0.1

    return score / weights if weights > 0 else 0.0


def _match_units(
    units_a: list[dict], units_b: list[dict], threshold: float = 0.6
) -> tuple[list[tuple[dict, dict, float]], list[dict], list[dict]]:
    """Match units from two extractions by similarity.

    Returns (matched_pairs, unmatched_a, unmatched_b).
    Each matched pair is (unit_a, unit_b, similarity_score).
    """
    used_b: set[int] = set()
    matched: list[tuple[dict, dict, float]] = []
    unmatched_a: list[dict] = []

    for ua in units_a:
        best_idx = -1
        best_score = 0.0
        for j, ub in enumerate(units_b):
            if j in used_b:
                continue
            sim = _unit_similarity(ua, ub)
            if sim > best_score:
                best_score = sim
                best_idx = j
        if best_idx >= 0 and best_score >= threshold:
            matched.append((ua, units_b[best_idx], best_score))
            used_b.add(best_idx)
        else:
            unmatched_a.append(ua)

    unmatched_b = [ub for j, ub in enumerate(units_b) if j not in used_b]
    return matched, unmatched_a, unmatched_b


def compute_agreement(
    extraction_a: PageExtraction, extraction_b: PageExtraction
) -> float:
    """Compute agreement score (0.0 to 1.0) between two page extractions."""
    units_a = [u.model_dump() for u in extraction_a.units]
    units_b = [u.model_dump() for u in extraction_b.units]

    if not units_a and not units_b:
        bij_a = len(extraction_a.bijections)
        bij_b = len(extraction_b.bijections)
        grid_a = len(extraction_a.grids)
        grid_b = len(extraction_b.grids)
        total = bij_a + bij_b + grid_a + grid_b
        if total == 0:
            return 1.0
        matched_items = min(bij_a, bij_b) + min(grid_a, grid_b)
        return matched_items / max(max(bij_a, bij_b) + max(grid_a, grid_b), 1)

    matched, unmatched_a, unmatched_b = _match_units(units_a, units_b)
    total_facts = len(units_a) + len(units_b)
    if total_facts == 0:
        return 1.0

    agreement_score = sum(sim for _, _, sim in matched)
    max_possible = max(len(units_a), len(units_b))

    return min(1.0, agreement_score / max_possible) if max_possible > 0 else 1.0


def merge_extractions(
    extraction_a: PageExtraction,
    extraction_b: PageExtraction,
    agreement_threshold: float = 0.6,
) -> PageExtraction:
    """Merge two extractions, keeping agreed facts and flagging disagreements.

    Agreement facts use values from extraction_a (precision-focused).
    Disagreement facts are included but will get lower confidence downstream.
    """
    units_a = [u.model_dump() for u in extraction_a.units]
    units_b = [u.model_dump() for u in extraction_b.units]

    matched, unmatched_a, unmatched_b = _match_units(units_a, units_b, agreement_threshold)

    from akili.ingest.extract_schema import UnitExtract
    merged_units: list[UnitExtract] = []

    for ua, _ub, _sim in matched:
        try:
            merged_units.append(UnitExtract.model_validate(ua))
        except Exception:
            continue

    for ua in unmatched_a:
        try:
            merged_units.append(UnitExtract.model_validate(ua))
        except Exception:
            continue

    for ub in unmatched_b:
        try:
            merged_units.append(UnitExtract.model_validate(ub))
        except Exception:
            continue

    bijections = extraction_a.bijections or extraction_b.bijections
    grids = extraction_a.grids or extraction_b.grids

    return PageExtraction(
        units=merged_units,
        bijections=bijections,
        grids=grids,
    )


def consensus_extract_page(
    page_index: int,
    image_png_bytes: bytes,
    doc_id: str,
    page_type_hint: str = "",
) -> tuple[PageExtraction, float]:
    """Run dual extraction with precision/recall prompts and return merged result + agreement.

    Returns (merged_extraction, agreement_score).
    agreement_score is 0.0-1.0 representing how much the two passes agreed.
    """
    precision_hint = (page_type_hint + _PRECISION_SUFFIX) if page_type_hint else _PRECISION_SUFFIX.strip()
    recall_hint = (page_type_hint + _RECALL_SUFFIX) if page_type_hint else _RECALL_SUFFIX.strip()

    extraction_a = extract_page(page_index, image_png_bytes, doc_id, page_type_hint=precision_hint)
    extraction_b = extract_page(page_index, image_png_bytes, doc_id, page_type_hint=recall_hint)

    agreement = compute_agreement(extraction_a, extraction_b)
    merged = merge_extractions(extraction_a, extraction_b)

    logger.info(
        "Consensus extraction page %d (doc_id=%s): agreement=%.2f, "
        "units_a=%d, units_b=%d, merged=%d",
        page_index, doc_id, agreement,
        len(extraction_a.units), len(extraction_b.units), len(merged.units),
    )

    return merged, agreement


def should_use_consensus(page_type: str) -> bool:
    """Whether consensus extraction should be used for this page type."""
    return config.CONSENSUS_ENABLED and page_type in HIGH_RISK_PAGE_TYPES
