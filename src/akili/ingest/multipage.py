"""
Multi-page table handling: detect and merge tables that span page boundaries.

Detection heuristics:
- A Grid ending near the bottom of a page (y > 0.85) with another Grid starting near the
  top of the next page (y < 0.15) with similar column counts.
- Column headers/labels are compared between candidate grids for overlap.
- Merged grids are flagged for human review until confidence stabilises.

After merging, original per-page grids are replaced by a single merged Grid whose
page field references the first page and whose cells contain adjusted row numbers.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass

from akili.canonical import Bijection, Grid, Unit
from akili.canonical.models import BBox, GridCell, Point

logger = logging.getLogger(__name__)

_BOTTOM_THRESHOLD = 0.80
_TOP_THRESHOLD = 0.20


@dataclass
class MergeCandidate:
    """A pair of grids on consecutive pages that may be parts of the same table."""

    grid_a: Grid
    grid_b: Grid
    column_similarity: float
    needs_review: bool = True


def _column_headers(grid: Grid) -> list[str]:
    """Extract first-row values as column headers."""
    row0 = sorted(
        [c for c in grid.cells if c.row == 0],
        key=lambda c: c.col,
    )
    return [str(c.value).strip().lower() for c in row0]


def _column_similarity(headers_a: list[str], headers_b: list[str]) -> float:
    """Jaccard similarity between two column header sets."""
    if not headers_a and not headers_b:
        return 1.0
    if not headers_a or not headers_b:
        return 0.0
    set_a, set_b = set(headers_a), set(headers_b)
    if not set_a.union(set_b):
        return 0.0
    return len(set_a.intersection(set_b)) / len(set_a.union(set_b))


def _grid_bottom_y(grid: Grid) -> float:
    """Estimated bottom edge of a grid (using bbox or cell positions)."""
    if grid.bbox:
        return grid.bbox.y2
    if grid.cells:
        return max(c.origin.y for c in grid.cells if c.origin) or grid.origin.y
    return grid.origin.y


def _grid_top_y(grid: Grid) -> float:
    """Estimated top edge of a grid."""
    if grid.bbox:
        return grid.bbox.y1
    return grid.origin.y


def detect_merge_candidates(
    grids: list[Grid],
) -> list[MergeCandidate]:
    """
    Identify grids on consecutive pages that are likely parts of the same table.

    Grids must share the same doc_id. Uses spatial position and column similarity.
    """
    by_doc: dict[str, list[Grid]] = defaultdict(list)
    for g in grids:
        by_doc[g.doc_id].append(g)

    candidates: list[MergeCandidate] = []

    for doc_id, doc_grids in by_doc.items():
        sorted_grids = sorted(doc_grids, key=lambda g: (g.page, g.origin.y))

        by_page: dict[int, list[Grid]] = defaultdict(list)
        for g in sorted_grids:
            by_page[g.page].append(g)

        pages = sorted(by_page.keys())
        for i in range(len(pages) - 1):
            current_page = pages[i]
            next_page = pages[i + 1]
            if next_page != current_page + 1:
                continue

            for ga in by_page[current_page]:
                bottom = _grid_bottom_y(ga)
                if bottom < _BOTTOM_THRESHOLD:
                    continue

                for gb in by_page[next_page]:
                    top = _grid_top_y(gb)
                    if top > _TOP_THRESHOLD:
                        continue
                    if ga.cols != gb.cols and ga.cols > 0 and gb.cols > 0:
                        continue

                    ha = _column_headers(ga)
                    hb = _column_headers(gb)
                    sim = _column_similarity(ha, hb)

                    if sim >= 0.5 or ga.cols == gb.cols:
                        candidates.append(MergeCandidate(
                            grid_a=ga,
                            grid_b=gb,
                            column_similarity=sim,
                            needs_review=sim < 0.8,
                        ))

    return candidates


def merge_grids(candidate: MergeCandidate) -> Grid:
    """
    Merge two grids from consecutive pages into a single Grid.

    The second grid's row indices are offset by grid_a.rows.
    If grid_b has the same column headers as grid_a (row 0 repeated), those rows are skipped.
    """
    ga, gb = candidate.grid_a, candidate.grid_b

    ha = _column_headers(ga)
    hb = _column_headers(gb)
    skip_header_row = ha and hb and ha == hb

    row_offset = ga.rows
    merged_cells = list(ga.cells)

    for cell in gb.cells:
        if skip_header_row and cell.row == 0:
            continue
        adjusted_row = cell.row + row_offset if not skip_header_row else cell.row - 1 + row_offset
        merged_cells.append(GridCell(
            row=adjusted_row,
            col=cell.col,
            value=cell.value,
            origin=cell.origin,
        ))

    extra_rows = gb.rows if not skip_header_row else gb.rows - 1
    merged_rows = ga.rows + extra_rows

    bbox = None
    if ga.bbox and gb.bbox:
        bbox = BBox(
            x1=min(ga.bbox.x1, gb.bbox.x1),
            y1=ga.bbox.y1,
            x2=max(ga.bbox.x2, gb.bbox.x2),
            y2=gb.bbox.y2,
        )

    return Grid(
        id=f"{ga.id}_merged_{gb.id}",
        rows=merged_rows,
        cols=max(ga.cols, gb.cols),
        cells=merged_cells,
        origin=ga.origin,
        doc_id=ga.doc_id,
        page=ga.page,
        bbox=bbox,
    )


def merge_multipage_tables(
    canonical: list[Unit | Bijection | Grid],
) -> tuple[list[Unit | Bijection | Grid], list[MergeCandidate]]:
    """
    Post-process a set of canonical objects: detect and merge multi-page tables.

    Returns the updated canonical list and a list of MergeCandidate records (for audit/review).
    Original per-page grids involved in merges are replaced by the merged version.
    """
    grids = [o for o in canonical if isinstance(o, Grid)]
    non_grids = [o for o in canonical if not isinstance(o, Grid)]

    candidates = detect_merge_candidates(grids)
    if not candidates:
        return canonical, []

    merged_ids: set[str] = set()
    merged_grids: list[Grid] = []

    for cand in candidates:
        if cand.grid_a.id in merged_ids or cand.grid_b.id in merged_ids:
            continue
        merged = merge_grids(cand)
        merged_grids.append(merged)
        merged_ids.add(cand.grid_a.id)
        merged_ids.add(cand.grid_b.id)
        logger.info(
            "Merged grids %s (page %d) + %s (page %d) → %s (%d rows, sim=%.2f, review=%s)",
            cand.grid_a.id, cand.grid_a.page,
            cand.grid_b.id, cand.grid_b.page,
            merged.id, merged.rows,
            cand.column_similarity, cand.needs_review,
        )

    remaining_grids = [g for g in grids if g.id not in merged_ids]
    result = non_grids + remaining_grids + merged_grids
    return result, candidates
