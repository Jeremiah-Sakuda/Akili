"""
Corpus loader for pre-canonicalized datasheet data.

Enables instant results for common chips by checking if an uploaded PDF
matches an existing corpus entry before running full ingestion.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from akili.canonical import Bijection, ConditionalUnit, Grid, Range, Unit
from akili.canonical.models import BBox, GridCell, Point

logger = logging.getLogger(__name__)

# Common chips for public corpus (FR-CORP-1)
COMMON_CHIPS = [
    "ATmega328P",
    "ATmega2560",
    "ESP32",
    "ESP32-S3",
    "ESP8266",
    "STM32F103",
    "STM32F411",
    "RP2040",
    "NE555",
    "LM7805",
    "LM7812",
    "LM317",
    "LM358",
    "LM386",
    "L293D",
    "ULN2003",
    "74HC595",
    "MAX7219",
    "ADS1115",
    "BME280",
]


@dataclass
class CorpusEntry:
    """A pre-canonicalized corpus entry."""

    content_hash: str
    mpn: str
    chip_name: str
    datasheet_url: str | None
    canonical_data: dict[str, Any]
    created_at: str | None = None


def compute_pdf_hash(pdf_path: Path | str) -> str:
    """Compute SHA-256 hash of PDF content for corpus matching."""
    with open(pdf_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def check_corpus_match(
    pdf_hash: str,
    mpn: str | None = None,
    store: Any = None,
) -> CorpusEntry | None:
    """
    Check if uploaded PDF matches existing corpus entry.

    Args:
        pdf_hash: SHA-256 hash of PDF content
        mpn: Optional manufacturer part number to search by
        store: Database store instance

    Returns:
        CorpusEntry if found, None otherwise
    """
    if store is None:
        return None

    # First try exact hash match
    entry = store.get_corpus_entry(pdf_hash)
    if entry:
        logger.info(f"Corpus hit by hash: {entry['chip_name']}")
        return CorpusEntry(
            content_hash=entry["content_hash"],
            mpn=entry["mpn"],
            chip_name=entry["chip_name"],
            datasheet_url=entry.get("datasheet_url"),
            canonical_data=entry["canonical_data"] or {},
            created_at=entry.get("created_at"),
        )

    # Fall back to MPN lookup if provided
    if mpn:
        entry = store.get_corpus_by_mpn(mpn)
        if entry:
            logger.info(f"Corpus hit by MPN: {entry['chip_name']}")
            return CorpusEntry(
                content_hash=entry["content_hash"],
                mpn=entry["mpn"],
                chip_name=entry["chip_name"],
                datasheet_url=entry.get("datasheet_url"),
                canonical_data=entry["canonical_data"] or {},
                created_at=entry.get("created_at"),
            )

    return None


def _parse_point(d: dict | None) -> Point:
    """Parse Point from dict."""
    if d is None:
        return Point(x=0, y=0)
    return Point(x=d.get("x", 0), y=d.get("y", 0))


def _parse_bbox(d: dict | None) -> BBox | None:
    """Parse BBox from dict."""
    if d is None:
        return None
    return BBox(x1=d["x1"], y1=d["y1"], x2=d["x2"], y2=d["y2"])


def load_from_corpus(
    entry: CorpusEntry,
    doc_id: str,
) -> tuple[list[Unit], list[Bijection], list[Grid], list[Range], list[ConditionalUnit]]:
    """
    Load pre-canonicalized data from corpus entry.

    Args:
        entry: Corpus entry with canonical data
        doc_id: Document ID to assign to loaded objects

    Returns:
        Tuple of (units, bijections, grids, ranges, conditional_units)
    """
    data = entry.canonical_data
    units: list[Unit] = []
    bijections: list[Bijection] = []
    grids: list[Grid] = []
    ranges: list[Range] = []
    conditional_units: list[ConditionalUnit] = []

    # Load units
    for u_data in data.get("units", []):
        units.append(Unit(
            doc_id=doc_id,
            page=u_data.get("page", 0),
            id=u_data.get("id", ""),
            label=u_data.get("label"),
            value=u_data.get("value", ""),
            unit_of_measure=u_data.get("unit_of_measure"),
            context=u_data.get("context"),
            origin=_parse_point(u_data.get("origin")),
            bbox=_parse_bbox(u_data.get("bbox")),
        ))

    # Load bijections
    for b_data in data.get("bijections", []):
        bijections.append(Bijection(
            doc_id=doc_id,
            page=b_data.get("page", 0),
            id=b_data.get("id", ""),
            left_set=b_data.get("left_set", []),
            right_set=b_data.get("right_set", []),
            mapping=b_data.get("mapping", {}),
            origin=_parse_point(b_data.get("origin")),
            bbox=_parse_bbox(b_data.get("bbox")),
        ))

    # Load grids
    for g_data in data.get("grids", []):
        cells = []
        for c in g_data.get("cells", []):
            cells.append(GridCell(
                row=c.get("row", 0),
                col=c.get("col", 0),
                value=c.get("value", ""),
                origin=_parse_point(c.get("origin")) if c.get("origin") else None,
            ))
        grids.append(Grid(
            doc_id=doc_id,
            page=g_data.get("page", 0),
            id=g_data.get("id", ""),
            rows=g_data.get("rows", 0),
            cols=g_data.get("cols", 0),
            cells=cells,
            origin=_parse_point(g_data.get("origin")),
            bbox=_parse_bbox(g_data.get("bbox")),
        ))

    # Load ranges
    for r_data in data.get("ranges", []):
        ranges.append(Range(
            doc_id=doc_id,
            page=r_data.get("page", 0),
            id=r_data.get("id", ""),
            label=r_data.get("label"),
            min=r_data.get("min"),
            typ=r_data.get("typ"),
            max=r_data.get("max"),
            unit=r_data.get("unit", ""),
            conditions=r_data.get("conditions"),
            context=r_data.get("context"),
            origin=_parse_point(r_data.get("origin")),
            bbox=_parse_bbox(r_data.get("bbox")),
        ))

    # Load conditional units
    for cu_data in data.get("conditional_units", []):
        conditional_units.append(ConditionalUnit(
            doc_id=doc_id,
            page=cu_data.get("page", 0),
            id=cu_data.get("id", ""),
            label=cu_data.get("label"),
            value=cu_data.get("value", 0),
            unit=cu_data.get("unit", ""),
            condition_type=cu_data.get("condition_type", ""),
            condition_value=cu_data.get("condition_value", ""),
            derating=cu_data.get("derating"),
            context=cu_data.get("context"),
            origin=_parse_point(cu_data.get("origin")),
            bbox=_parse_bbox(cu_data.get("bbox")),
        ))

    logger.info(
        f"Loaded from corpus: {len(units)} units, {len(bijections)} bijections, "
        f"{len(grids)} grids, {len(ranges)} ranges, {len(conditional_units)} conditional_units"
    )

    return units, bijections, grids, ranges, conditional_units


def serialize_canonical_for_corpus(
    units: list[Unit],
    bijections: list[Bijection],
    grids: list[Grid],
    ranges: list[Range] | None = None,
    conditional_units: list[ConditionalUnit] | None = None,
) -> dict:
    """
    Serialize canonical objects to JSON-compatible dict for corpus storage.

    Args:
        units: List of Unit objects
        bijections: List of Bijection objects
        grids: List of Grid objects
        ranges: Optional list of Range objects
        conditional_units: Optional list of ConditionalUnit objects

    Returns:
        Dict suitable for JSON serialization
    """
    def point_to_dict(p: Point) -> dict:
        return {"x": p.x, "y": p.y}

    def bbox_to_dict(b: BBox | None) -> dict | None:
        if b is None:
            return None
        return {"x1": b.x1, "y1": b.y1, "x2": b.x2, "y2": b.y2}

    return {
        "units": [
            {
                "page": u.page,
                "id": u.id,
                "label": u.label,
                "value": u.value,
                "unit_of_measure": u.unit_of_measure,
                "context": u.context,
                "origin": point_to_dict(u.origin),
                "bbox": bbox_to_dict(u.bbox),
            }
            for u in units
        ],
        "bijections": [
            {
                "page": b.page,
                "id": b.id,
                "left_set": b.left_set,
                "right_set": b.right_set,
                "mapping": b.mapping,
                "origin": point_to_dict(b.origin),
                "bbox": bbox_to_dict(b.bbox),
            }
            for b in bijections
        ],
        "grids": [
            {
                "page": g.page,
                "id": g.id,
                "rows": g.rows,
                "cols": g.cols,
                "cells": [
                    {
                        "row": c.row,
                        "col": c.col,
                        "value": c.value,
                        "origin": point_to_dict(c.origin) if c.origin else None,
                    }
                    for c in g.cells
                ],
                "origin": point_to_dict(g.origin),
                "bbox": bbox_to_dict(g.bbox),
            }
            for g in grids
        ],
        "ranges": [
            {
                "page": r.page,
                "id": r.id,
                "label": r.label,
                "min": r.min,
                "typ": r.typ,
                "max": r.max,
                "unit": r.unit,
                "conditions": r.conditions,
                "context": r.context,
                "origin": point_to_dict(r.origin),
                "bbox": bbox_to_dict(r.bbox),
            }
            for r in (ranges or [])
        ],
        "conditional_units": [
            {
                "page": cu.page,
                "id": cu.id,
                "label": cu.label,
                "value": cu.value,
                "unit": cu.unit,
                "condition_type": cu.condition_type,
                "condition_value": cu.condition_value,
                "derating": cu.derating,
                "context": cu.context,
                "origin": point_to_dict(cu.origin),
                "bbox": bbox_to_dict(cu.bbox),
            }
            for cu in (conditional_units or [])
        ],
    }
