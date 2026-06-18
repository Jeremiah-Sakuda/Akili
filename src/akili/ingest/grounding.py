"""Coordinate grounding: validate and snap Gemini-reported (x, y) against the PDF.

Gemini self-reports a normalized ``(x, y)``/``bbox`` for every extracted fact, but those
are *estimates* — the model is guessing where on the page a value sits. This module reads
the real word geometry from the PDF text layer (PyMuPDF) and, for each canonical object,
tries to locate the actual text token(s) that match the object's value/label.

When a match is found, the object's ``origin``/``bbox`` are replaced with the true,
normalized geometry of that text and the object is marked ``grounded=True`` with a score.
When no match is found (scanned/vector pages with no text layer, or a hallucinated value),
the object keeps its estimate but is marked ``grounded=False`` with ``grounding_score=0`` —
so downstream confidence and the UI can tell a proven location from a guessed one.

This turns "the model claims this is at (x, y)" into "this value really appears at (x, y)
on the page", which is what "coordinate-grounded proof" is supposed to mean.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

from akili.canonical import BBox, Point

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WordBox:
    """A single text token with its normalized (0–1, top-left origin) box."""

    text: str
    x0: float
    y0: float
    x1: float
    y1: float


def _normalize_token(s: object) -> str:
    """Lowercase and strip everything but [a-z0-9.] for robust matching."""
    return re.sub(r"[^a-z0-9.]", "", str(s).lower())


def load_page_words(pdf_path: Path | str) -> dict[int, list[WordBox]]:
    """Return {page_index: [WordBox, ...]} with normalized coordinates.

    Pages with no extractable text layer (e.g. scanned images) map to an empty list.
    Never raises on a single bad page — grounding is best-effort.
    """
    words_by_page: dict[int, list[WordBox]] = {}
    doc = fitz.open(pdf_path)
    try:
        for page_index in range(len(doc)):
            page_words: list[WordBox] = []
            try:
                page = doc[page_index]
                w = float(page.rect.width) or 1.0
                h = float(page.rect.height) or 1.0
                for x0, y0, x1, y1, text, *_rest in page.get_text("words"):
                    if not str(text).strip():
                        continue
                    page_words.append(
                        WordBox(
                            text=str(text),
                            x0=max(0.0, min(1.0, x0 / w)),
                            y0=max(0.0, min(1.0, y0 / h)),
                            x1=max(0.0, min(1.0, x1 / w)),
                            y1=max(0.0, min(1.0, y1 / h)),
                        )
                    )
            except Exception as exc:  # noqa: BLE001 - one bad page must not abort grounding
                logger.debug("Word extraction failed for page %d: %s", page_index, exc)
            words_by_page[page_index] = page_words
    finally:
        doc.close()
    return words_by_page


def _span_geometry(words: list[WordBox]) -> tuple[Point, BBox]:
    """Top-left origin + union bounding box for a run of matched words."""
    x0 = min(w.x0 for w in words)
    y0 = min(w.y0 for w in words)
    x1 = max(w.x1 for w in words)
    y1 = max(w.y1 for w in words)
    return Point(x=x0, y=y0), BBox(x1=x0, y1=y0, x2=x1, y2=y1)


def ground_text(query: str, words: list[WordBox]) -> tuple[Point, BBox, float] | None:
    """Find where ``query`` appears among ``words``; return (origin, bbox, score) or None.

    Score semantics (0–1): 1.0 exact single-token match, 0.9 query contained in a token,
    0.8 a multi-token span matches, 0.7 the salient numeric token matches. Higher is a
    tighter, more trustworthy grounding.
    """
    qn = _normalize_token(query)
    if not qn or not words:
        return None

    # 1) Exact single-token match.
    for w in words:
        if _normalize_token(w.text) == qn:
            origin, bbox = _span_geometry([w])
            return origin, bbox, 1.0

    # 2) Query fully contained within a single token (e.g. "4.2" in "4.2V").
    best: tuple[float, list[WordBox]] | None = None
    for w in words:
        wn = _normalize_token(w.text)
        if wn and qn in wn:
            if best is None or 0.9 > best[0]:
                best = (0.9, [w])

    # 3) Consecutive-span match: a window of words whose joined text contains the query.
    if best is None:
        for start in range(len(words)):
            joined = ""
            span: list[WordBox] = []
            for w in words[start : start + 5]:
                joined += _normalize_token(w.text)
                span.append(w)
                if qn in joined:
                    best = (0.8, list(span))
                    break
            if best is not None:
                break

    # 4) Fall back to the salient numeric token of the query.
    if best is None:
        nums = re.findall(r"\d+\.?\d*", qn)
        for n in nums:
            if len(n) < 1:
                continue
            for w in words:
                if n in _normalize_token(w.text):
                    best = (0.7, [w])
                    break
            if best is not None:
                break

    if best is None:
        return None
    score, span = best
    origin, bbox = _span_geometry(span)
    return origin, bbox, score


def _candidate_queries(obj: object) -> list[str]:
    """The strings worth searching for, most specific first."""
    queries: list[str] = []
    value = getattr(obj, "value", None)
    uom = getattr(obj, "unit_of_measure", None) or getattr(obj, "unit", None)
    if value is not None and str(value).strip():
        if uom:
            queries.append(f"{value}{uom}")
        queries.append(str(value))
    label = getattr(obj, "label", None)
    if label and str(label).strip():
        queries.append(str(label))
    return queries


def ground_objects(objects: list, words_by_page: dict[int, list[WordBox]]) -> dict:
    """Snap each object's origin/bbox to real page geometry where possible.

    Mutates objects in place: sets ``grounded`` / ``grounding_score`` when those fields
    exist, and overwrites ``origin``/``bbox`` with the matched geometry on a hit.
    Returns summary stats {"total", "grounded", "pages_without_text"}.
    """
    total = 0
    grounded = 0
    pages_without_text = sum(1 for ws in words_by_page.values() if not ws)

    for obj in objects:
        if not hasattr(obj, "grounding_score"):
            continue  # only Units carry grounding fields today
        total += 1
        page = getattr(obj, "page", None)
        words = words_by_page.get(page, []) if page is not None else []
        if not words:
            continue

        result = None
        for query in _candidate_queries(obj):
            result = ground_text(query, words)
            if result is not None:
                break

        if result is None:
            continue
        origin, bbox, score = result
        obj.origin = origin
        obj.bbox = bbox
        obj.grounded = True
        obj.grounding_score = round(score, 3)
        grounded += 1

    return {"total": total, "grounded": grounded, "pages_without_text": pages_without_text}
