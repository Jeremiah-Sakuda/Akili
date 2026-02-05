"""
Pydantic schema for Gemini extraction response.

One JSON object per page: units, bijections, grids.
Coordinates are required; we reject entries without them at canonicalize.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PointSchema(BaseModel):
    """(x, y) in document space."""

    x: float = Field(..., description="x coordinate")
    y: float = Field(..., description="y coordinate")


class BBoxSchema(BaseModel):
    """Bounding box (x1,y1,x2,y2)."""

    x1: float
    y1: float
    x2: float
    y2: float


class UnitExtract(BaseModel):
    """Extracted unit: single fact with coordinates."""

    id: str = Field(..., description="Unique id within this page")
    label: str | None = Field(None, description="Human-readable label")
    value: str | float = Field(..., description="Numeric or string value")
    unit_of_measure: str | None = Field(None, description="e.g. V, A, Ω")
    origin: PointSchema = Field(..., description="(x,y) location in document")
    bbox: BBoxSchema | None = Field(None, description="Optional bounding box")


class BijectionExtract(BaseModel):
    """Extracted 1:1 mapping with coordinates."""

    id: str = Field(..., description="Unique id within this page")
    left_set: list[str] = Field(..., description="Left side labels")
    right_set: list[str] = Field(..., description="Right side labels")
    mapping: dict[str, str] = Field(..., description="left -> right")
    origin: PointSchema = Field(..., description="Reference (x,y)")
    bbox: BBoxSchema | None = Field(None, description="Optional region")


class GridCellExtract(BaseModel):
    """Single cell: row, col, value, optional origin."""

    row: int = Field(..., ge=0)
    col: int = Field(..., ge=0)
    value: str | float = Field(...)
    origin: PointSchema | None = Field(None, description="(x,y) of this cell")


class GridExtract(BaseModel):
    """Extracted table/grid with cells and origin."""

    id: str = Field(..., description="Unique id within this page")
    rows: int = Field(..., ge=0)
    cols: int = Field(..., ge=0)
    cells: list[GridCellExtract] = Field(..., description="Cell list")
    origin: PointSchema = Field(..., description="Grid origin (x,y)")
    bbox: BBoxSchema | None = Field(None, description="Optional region")


class PageExtraction(BaseModel):
    """Full extraction for one page: units, bijections, grids."""

    units: list[UnitExtract] = Field(
        default_factory=list, description="Discrete facts with coordinates"
    )
    bijections: list[BijectionExtract] = Field(default_factory=list, description="1:1 mappings")
    grids: list[GridExtract] = Field(
        default_factory=list, description="Tables/grids with cell coordinates"
    )
