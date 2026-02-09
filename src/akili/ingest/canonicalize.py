"""
Convert extraction output into canonical models (Unit, Bijection, Grid).

Validates and rejects any entry that fails or lacks coordinates.
"""

from __future__ import annotations

from akili.canonical import Bijection, Grid, Point, Unit
from akili.canonical.models import BBox, GridCell
from akili.ingest.extract_schema import (
    BijectionExtract,
    GridExtract,
    PageExtraction,
    UnitExtract,
)


def _point(origin: object) -> Point:
    return Point(x=origin.x, y=origin.y)


def _bbox(bbox: object | None) -> BBox | None:
    if bbox is None:
        return None
    return BBox(x1=bbox.x1, y1=bbox.y1, x2=bbox.x2, y2=bbox.y2)


def canonicalize_units(extracts: list[UnitExtract], doc_id: str, page: int) -> list[Unit]:
    """Convert extracted units to canonical Unit; skip invalid."""
    out: list[Unit] = []
    for e in extracts:
        try:
            out.append(
                Unit(
                    id=e.id,
                    label=e.label,
                    value=e.value,
                    unit_of_measure=e.unit_of_measure,
                    context=getattr(e, "context", None),
                    origin=_point(e.origin),
                    doc_id=doc_id,
                    page=page,
                    bbox=_bbox(e.bbox),
                )
            )
        except Exception:
            continue
    return out


def canonicalize_bijections(
    extracts: list[BijectionExtract], doc_id: str, page: int
) -> list[Bijection]:
    """Convert extracted bijections to canonical Bijection; skip invalid."""
    out: list[Bijection] = []
    for e in extracts:
        try:
            out.append(
                Bijection(
                    id=e.id,
                    left_set=e.left_set,
                    right_set=e.right_set,
                    mapping=e.mapping,
                    origin=_point(e.origin),
                    doc_id=doc_id,
                    page=page,
                    bbox=_bbox(e.bbox),
                )
            )
        except Exception:
            continue
    return out


def canonicalize_grids(extracts: list[GridExtract], doc_id: str, page: int) -> list[Grid]:
    """Convert extracted grids to canonical Grid; skip invalid."""
    out: list[Grid] = []
    for e in extracts:
        try:
            cells: list[GridCell] = []
            for c in e.cells:
                cells.append(
                    GridCell(
                        row=c.row,
                        col=c.col,
                        value=c.value,
                        origin=Point(x=c.origin.x, y=c.origin.y) if c.origin else None,
                    )
                )
            out.append(
                Grid(
                    id=e.id,
                    rows=e.rows,
                    cols=e.cols,
                    cells=cells,
                    origin=_point(e.origin),
                    doc_id=doc_id,
                    page=page,
                    bbox=_bbox(e.bbox),
                )
            )
        except Exception:
            continue
    return out


def canonicalize_page(
    extraction: PageExtraction, doc_id: str, page: int
) -> list[Unit | Bijection | Grid]:
    """
    Convert one page's extraction into canonical objects.

    Returns a flat list of Unit, Bijection, Grid. Invalid entries are skipped.
    """
    result: list[Unit | Bijection | Grid] = []
    result.extend(canonicalize_units(extraction.units, doc_id, page))
    result.extend(canonicalize_bijections(extraction.bijections, doc_id, page))
    result.extend(canonicalize_grids(extraction.grids, doc_id, page))
    return result
