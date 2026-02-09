"""
Canonical schema: Unit, Bijection, Grid.

Every fact carries (doc_id, page, x, y). No free-form beliefs.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Point(BaseModel):
    """(x, y) in document space (normalized 0–1 or page-relative pixels)."""

    x: float = Field(..., description="x coordinate")
    y: float = Field(..., description="y coordinate")


class BBox(BaseModel):
    """Bounding box for a region in a document."""

    x1: float
    y1: float
    x2: float
    y2: float


class Unit(BaseModel):
    """
    Single measurable or named entity: pin label, voltage value, etc.
    Rejected at ingestion if origin or value is ambiguous.
    """

    id: str = Field(..., description="Unique id within document")
    label: str | None = Field(None, description="Human-readable label")
    value: str | float = Field(..., description="Numeric or string value")
    unit_of_measure: str | None = Field(None, description="e.g. V, A, Ω")
    context: str | None = Field(None, description="What this value refers to (e.g. charge voltage, nominal capacity)")
    origin: Point = Field(..., description="(x,y) location in document")
    doc_id: str = Field(..., description="Source document id")
    page: int = Field(..., ge=0, description="Page number (0-based)")
    bbox: BBox | None = Field(None, description="Optional bounding box")


class Bijection(BaseModel):
    """
    Strict 1:1 mapping between two sets (e.g. pin name ↔ pin number).
    Coordinate ranges indicate where in the doc this mapping holds.
    """

    id: str = Field(..., description="Unique id within document")
    left_set: list[str] = Field(..., description="Left side of mapping")
    right_set: list[str] = Field(..., description="Right side of mapping")
    mapping: dict[str, str] = Field(..., description="Explicit left → right")
    origin: Point = Field(..., description="Reference (x,y) for this mapping")
    doc_id: str = Field(..., description="Source document id")
    page: int = Field(..., ge=0, description="Page number (0-based)")
    bbox: BBox | None = Field(None, description="Optional region")

    def get_right(self, left: str) -> str | None:
        """Return right side for a left key; None if not in mapping."""
        return self.mapping.get(left)

    def get_left(self, right: str) -> str | None:
        """Return left side for a right value; None if not in mapping."""
        inv = {v: k for k, v in self.mapping.items()}
        return inv.get(right)


class GridCell(BaseModel):
    """Single cell in a grid: (row, col) → value, with optional (x,y)."""

    row: int = Field(..., ge=0)
    col: int = Field(..., ge=0)
    value: str | float = Field(...)
    origin: Point | None = Field(None, description="(x,y) of this cell")


class Grid(BaseModel):
    """
    Tabular or schematic region: rows × cols with cell-level coordinates.
    Used for datasheet tables, pinout grids, schematic grids.
    """

    id: str = Field(..., description="Unique id within document")
    rows: int = Field(..., ge=0)
    cols: int = Field(..., ge=0)
    cells: list[GridCell] = Field(..., description="(row,col) → value with optional origin")
    origin: Point = Field(..., description="Grid origin (x,y)")
    doc_id: str = Field(..., description="Source document id")
    page: int = Field(..., ge=0, description="Page number (0-based)")
    bbox: BBox | None = Field(None, description="Optional region")

    def get_cell(self, row: int, col: int) -> GridCell | None:
        """Return cell at (row, col) if present."""
        for c in self.cells:
            if c.row == row and c.col == col:
                return c
        return None

    def as_dict(self) -> dict[tuple[int, int], Any]:
        """(row, col) → value for quick lookup."""
        return {(c.row, c.col): c.value for c in self.cells}
