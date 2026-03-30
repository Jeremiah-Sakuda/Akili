"""Tests for C2: Multi-Page Table Handling."""

from __future__ import annotations

import pytest

from akili.canonical import Grid, Unit
from akili.canonical.models import BBox, GridCell, Point
from akili.ingest.multipage import (
    MergeCandidate,
    detect_merge_candidates,
    merge_grids,
    merge_multipage_tables,
)


def _make_grid(
    grid_id: str,
    page: int,
    rows: int,
    cols: int,
    origin_y: float,
    doc_id: str = "d1",
    headers: list[str] | None = None,
    bbox_y1: float | None = None,
    bbox_y2: float | None = None,
) -> Grid:
    cells = []
    for r in range(rows):
        for c in range(cols):
            if r == 0 and headers and c < len(headers):
                val = headers[c]
            else:
                val = f"r{r}c{c}"
            cells.append(GridCell(
                row=r, col=c, value=val,
                origin=Point(x=0.1 + c * 0.2, y=origin_y + r * 0.05),
            ))
    bbox = None
    if bbox_y1 is not None and bbox_y2 is not None:
        bbox = BBox(x1=0.05, y1=bbox_y1, x2=0.95, y2=bbox_y2)
    return Grid(
        id=grid_id, rows=rows, cols=cols, cells=cells,
        origin=Point(x=0.1, y=origin_y), doc_id=doc_id, page=page, bbox=bbox,
    )


class TestDetectMergeCandidates:
    def test_consecutive_pages_with_bbox(self) -> None:
        ga = _make_grid("g1", page=0, rows=5, cols=3, origin_y=0.6,
                        headers=["Param", "Min", "Max"], bbox_y1=0.6, bbox_y2=0.95)
        gb = _make_grid("g2", page=1, rows=3, cols=3, origin_y=0.05,
                        headers=["Param", "Min", "Max"], bbox_y1=0.05, bbox_y2=0.20)
        candidates = detect_merge_candidates([ga, gb])
        assert len(candidates) == 1
        assert candidates[0].grid_a.id == "g1"
        assert candidates[0].grid_b.id == "g2"
        assert candidates[0].column_similarity == 1.0

    def test_non_consecutive_pages_no_merge(self) -> None:
        ga = _make_grid("g1", page=0, rows=5, cols=3, origin_y=0.6,
                        bbox_y1=0.6, bbox_y2=0.95)
        gb = _make_grid("g2", page=3, rows=3, cols=3, origin_y=0.05,
                        bbox_y1=0.05, bbox_y2=0.20)
        candidates = detect_merge_candidates([ga, gb])
        assert len(candidates) == 0

    def test_different_column_count_no_merge(self) -> None:
        ga = _make_grid("g1", page=0, rows=5, cols=3, origin_y=0.6,
                        bbox_y1=0.6, bbox_y2=0.95)
        gb = _make_grid("g2", page=1, rows=3, cols=5, origin_y=0.05,
                        bbox_y1=0.05, bbox_y2=0.20)
        candidates = detect_merge_candidates([ga, gb])
        assert len(candidates) == 0

    def test_grid_not_near_bottom(self) -> None:
        ga = _make_grid("g1", page=0, rows=5, cols=3, origin_y=0.2,
                        bbox_y1=0.2, bbox_y2=0.5)
        gb = _make_grid("g2", page=1, rows=3, cols=3, origin_y=0.05,
                        bbox_y1=0.05, bbox_y2=0.20)
        candidates = detect_merge_candidates([ga, gb])
        assert len(candidates) == 0

    def test_different_docs_no_merge(self) -> None:
        ga = _make_grid("g1", page=0, rows=5, cols=3, origin_y=0.6,
                        doc_id="d1", bbox_y1=0.6, bbox_y2=0.95)
        gb = _make_grid("g2", page=1, rows=3, cols=3, origin_y=0.05,
                        doc_id="d2", bbox_y1=0.05, bbox_y2=0.20)
        candidates = detect_merge_candidates([ga, gb])
        assert len(candidates) == 0


class TestMergeGrids:
    def test_merge_with_matching_headers(self) -> None:
        headers = ["Param", "Min", "Max"]
        ga = _make_grid("g1", page=0, rows=3, cols=3, origin_y=0.6,
                        headers=headers, bbox_y1=0.6, bbox_y2=0.95)
        gb = _make_grid("g2", page=1, rows=3, cols=3, origin_y=0.05,
                        headers=headers, bbox_y1=0.05, bbox_y2=0.20)
        cand = MergeCandidate(grid_a=ga, grid_b=gb, column_similarity=1.0)
        merged = merge_grids(cand)
        assert merged.id == "g1_merged_g2"
        assert merged.page == 0
        assert merged.rows == 5  # 3 + (3-1) since header row is skipped
        assert merged.cols == 3

    def test_merge_without_matching_headers(self) -> None:
        ga = _make_grid("g1", page=0, rows=3, cols=3, origin_y=0.6,
                        headers=["A", "B", "C"], bbox_y1=0.6, bbox_y2=0.95)
        gb = _make_grid("g2", page=1, rows=2, cols=3, origin_y=0.05,
                        headers=["X", "Y", "Z"], bbox_y1=0.05, bbox_y2=0.20)
        cand = MergeCandidate(grid_a=ga, grid_b=gb, column_similarity=0.0)
        merged = merge_grids(cand)
        assert merged.rows == 5  # 3 + 2

    def test_merged_bbox(self) -> None:
        headers = ["A", "B"]
        ga = _make_grid("g1", page=0, rows=3, cols=2, origin_y=0.6,
                        headers=headers, bbox_y1=0.6, bbox_y2=0.95)
        gb = _make_grid("g2", page=1, rows=2, cols=2, origin_y=0.05,
                        headers=headers, bbox_y1=0.05, bbox_y2=0.20)
        cand = MergeCandidate(grid_a=ga, grid_b=gb, column_similarity=1.0)
        merged = merge_grids(cand)
        assert merged.bbox is not None
        assert merged.bbox.y1 == 0.6
        assert merged.bbox.y2 == 0.20


class TestMergeMultipageTables:
    def test_integration(self) -> None:
        headers = ["Param", "Min", "Max"]
        ga = _make_grid("g1", page=0, rows=5, cols=3, origin_y=0.6,
                        headers=headers, bbox_y1=0.6, bbox_y2=0.95)
        gb = _make_grid("g2", page=1, rows=3, cols=3, origin_y=0.05,
                        headers=headers, bbox_y1=0.05, bbox_y2=0.20)
        unit = Unit(id="u1", label="V", value=3.3, unit_of_measure="V",
                    context="supply", origin=Point(x=0.1, y=0.1), doc_id="d1", page=0)
        canonical: list = [unit, ga, gb]
        result, candidates = merge_multipage_tables(canonical)
        assert len(candidates) == 1
        grids = [o for o in result if isinstance(o, Grid)]
        assert len(grids) == 1
        assert grids[0].id == "g1_merged_g2"
        units = [o for o in result if isinstance(o, Unit)]
        assert len(units) == 1

    def test_no_merge_needed(self) -> None:
        ga = _make_grid("g1", page=0, rows=5, cols=3, origin_y=0.2,
                        bbox_y1=0.2, bbox_y2=0.5)
        result, candidates = merge_multipage_tables([ga])
        assert len(candidates) == 0
        assert len(result) == 1
