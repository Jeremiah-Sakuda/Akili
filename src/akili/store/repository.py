"""
SQLite persistence for canonical objects (Unit, Bijection, Grid) with provenance.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from akili.canonical import Bijection, ConditionalUnit, Grid, Range, Unit
from akili.canonical.models import BBox, GridCell, Point
from akili.store.base import BaseStore


def _point_to_json(p: Point) -> str:
    return json.dumps({"x": p.x, "y": p.y})


def _bbox_to_json(b: BBox | None) -> str | None:
    if b is None:
        return None
    return json.dumps({"x1": b.x1, "y1": b.y1, "x2": b.x2, "y2": b.y2})


def _json_to_point(s: str) -> Point:
    d = json.loads(s)
    return Point(x=d["x"], y=d["y"])


def _json_to_bbox(s: str | None) -> BBox | None:
    if s is None:
        return None
    d = json.loads(s)
    return BBox(x1=d["x1"], y1=d["y1"], x2=d["x2"], y2=d["y2"])


class Store(BaseStore):
    """SQLite-backed store for canonical objects."""

    def __init__(self, db_path: Path | str = "akili.db"):
        self.db_path = Path(db_path)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_schema(self) -> None:
        with self._conn() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    filename TEXT,
                    page_count INTEGER,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS units (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id TEXT NOT NULL,
                    page INTEGER NOT NULL,
                    unit_id TEXT NOT NULL,
                    label TEXT,
                    value TEXT NOT NULL,
                    unit_of_measure TEXT,
                    context TEXT,
                    origin_json TEXT NOT NULL,
                    bbox_json TEXT,
                    UNIQUE(doc_id, page, unit_id),
                    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
                );
            """)
            # Migration: add context column to existing units tables
            try:
                c.execute("ALTER TABLE units ADD COLUMN context TEXT")
            except sqlite3.OperationalError:
                pass  # column already exists
            c.executescript("""
                CREATE TABLE IF NOT EXISTS bijections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id TEXT NOT NULL,
                    page INTEGER NOT NULL,
                    bijection_id TEXT NOT NULL,
                    left_set_json TEXT NOT NULL,
                    right_set_json TEXT NOT NULL,
                    mapping_json TEXT NOT NULL,
                    origin_json TEXT NOT NULL,
                    bbox_json TEXT,
                    UNIQUE(doc_id, page, bijection_id),
                    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
                );
                CREATE TABLE IF NOT EXISTS grids (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id TEXT NOT NULL,
                    page INTEGER NOT NULL,
                    grid_id TEXT NOT NULL,
                    rows INTEGER NOT NULL,
                    cols INTEGER NOT NULL,
                    cells_json TEXT NOT NULL,
                    origin_json TEXT NOT NULL,
                    bbox_json TEXT,
                    UNIQUE(doc_id, page, grid_id),
                    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
                );
                CREATE TABLE IF NOT EXISTS ranges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id TEXT NOT NULL,
                    page INTEGER NOT NULL,
                    range_id TEXT NOT NULL,
                    label TEXT,
                    min_val REAL,
                    typ_val REAL,
                    max_val REAL,
                    unit TEXT NOT NULL,
                    conditions TEXT,
                    context TEXT,
                    origin_json TEXT NOT NULL,
                    bbox_json TEXT,
                    UNIQUE(doc_id, page, range_id),
                    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
                );
                CREATE TABLE IF NOT EXISTS conditional_units (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id TEXT NOT NULL,
                    page INTEGER NOT NULL,
                    cunit_id TEXT NOT NULL,
                    label TEXT,
                    value REAL NOT NULL,
                    unit TEXT NOT NULL,
                    condition_type TEXT NOT NULL,
                    condition_value TEXT NOT NULL,
                    derating TEXT,
                    context TEXT,
                    origin_json TEXT NOT NULL,
                    bbox_json TEXT,
                    UNIQUE(doc_id, page, cunit_id),
                    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
                );
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id TEXT,
                    action TEXT NOT NULL,
                    actor TEXT,
                    details_json TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );
            """)

    def _audit(self, action: str, doc_id: str | None, actor: str | None = None, details: dict | None = None) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO audit_log (doc_id, action, actor, details_json) VALUES (?, ?, ?, ?)",
                (doc_id, action, actor, json.dumps(details) if details else None),
            )

    def get_audit_log(self, doc_id: str | None = None, limit: int = 100) -> list[dict]:
        """Return audit log entries, optionally filtered by doc_id."""
        with self._conn() as c:
            if doc_id:
                rows = c.execute(
                    "SELECT id, doc_id, action, actor, details_json, created_at "
                    "FROM audit_log WHERE doc_id = ? ORDER BY created_at DESC LIMIT ?",
                    (doc_id, limit),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT id, doc_id, action, actor, details_json, created_at "
                    "FROM audit_log ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [
            {
                "id": r[0], "doc_id": r[1], "action": r[2], "actor": r[3],
                "details": json.loads(r[4]) if r[4] else None,
                "created_at": r[5],
            }
            for r in rows
        ]

    def add_document(self, doc_id: str, filename: str | None = None, page_count: int = 0) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO documents (doc_id, filename, page_count) VALUES (?, ?, ?)",
                (doc_id, filename or "", page_count),
            )

    def store_canonical(
        self,
        doc_id: str,
        filename: str | None,
        page_count: int,
        units: list[Unit],
        bijections: list[Bijection],
        grids: list[Grid],
        ranges: list[Range] | None = None,
        conditional_units: list[ConditionalUnit] | None = None,
    ) -> None:
        """Persist canonical objects for a document (single transaction)."""
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO documents (doc_id, filename, page_count) VALUES (?, ?, ?)",
                (doc_id, filename or "", page_count),
            )
            for u in units:
                c.execute(
                    """INSERT OR REPLACE INTO units (doc_id, page, unit_id, label, value,
                       unit_of_measure, context, origin_json, bbox_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        u.doc_id,
                        u.page,
                        u.id,
                        u.label,
                        str(u.value),
                        u.unit_of_measure,
                        u.context,
                        _point_to_json(u.origin),
                        _bbox_to_json(u.bbox),
                    ),
                )
            for b in bijections:
                c.execute(
                    """INSERT OR REPLACE INTO bijections (doc_id, page, bijection_id,
                       left_set_json, right_set_json, mapping_json, origin_json, bbox_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        b.doc_id,
                        b.page,
                        b.id,
                        json.dumps(b.left_set),
                        json.dumps(b.right_set),
                        json.dumps(b.mapping),
                        _point_to_json(b.origin),
                        _bbox_to_json(b.bbox),
                    ),
                )
            for g in grids:
                cells_json = json.dumps(
                    [
                        {
                            "row": c_.row,
                            "col": c_.col,
                            "value": c_.value,
                            "origin": {"x": c_.origin.x, "y": c_.origin.y} if c_.origin else None,
                        }
                        for c_ in g.cells
                    ]
                )
                c.execute(
                    """INSERT OR REPLACE INTO grids (doc_id, page, grid_id, rows, cols,
                       cells_json, origin_json, bbox_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        g.doc_id,
                        g.page,
                        g.id,
                        g.rows,
                        g.cols,
                        cells_json,
                        _point_to_json(g.origin),
                        _bbox_to_json(g.bbox),
                    ),
                )
            for r in (ranges or []):
                c.execute(
                    """INSERT OR REPLACE INTO ranges (doc_id, page, range_id, label,
                       min_val, typ_val, max_val, unit, conditions, context,
                       origin_json, bbox_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        r.doc_id, r.page, r.id, r.label,
                        r.min, r.typ, r.max, r.unit,
                        r.conditions, r.context,
                        _point_to_json(r.origin), _bbox_to_json(r.bbox),
                    ),
                )
            for cu in (conditional_units or []):
                c.execute(
                    """INSERT OR REPLACE INTO conditional_units (doc_id, page, cunit_id,
                       label, value, unit, condition_type, condition_value,
                       derating, context, origin_json, bbox_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        cu.doc_id, cu.page, cu.id, cu.label,
                        cu.value, cu.unit, cu.condition_type, cu.condition_value,
                        cu.derating, cu.context,
                        _point_to_json(cu.origin), _bbox_to_json(cu.bbox),
                    ),
                )
        self._audit("store_canonical", doc_id, details={
            "units": len(units), "bijections": len(bijections), "grids": len(grids),
            "ranges": len(ranges or []), "conditional_units": len(conditional_units or []),
        })

    def get_units_by_doc(self, doc_id: str) -> list[Unit]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT doc_id, page, unit_id, label, value, unit_of_measure, context, "
                "origin_json, bbox_json FROM units WHERE doc_id = ?",
                (doc_id,),
            ).fetchall()
        out: list[Unit] = []
        for r in rows:
            val: str | float = r[4]
            try:
                if "." in str(r[4]):
                    val = float(r[4])
                else:
                    val = int(r[4])  # type: ignore[assignment]
            except (ValueError, TypeError):
                pass
            out.append(
                Unit(
                    doc_id=r[0],
                    page=r[1],
                    id=r[2],
                    label=r[3],
                    value=val,
                    unit_of_measure=r[5],
                    context=r[6] if len(r) > 6 else None,
                    origin=_json_to_point(r[7]),
                    bbox=_json_to_bbox(r[8]),
                )
            )
        return out

    def get_bijections_by_doc(self, doc_id: str) -> list[Bijection]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT doc_id, page, bijection_id, left_set_json, right_set_json, "
                "mapping_json, origin_json, bbox_json FROM bijections WHERE doc_id = ?",
                (doc_id,),
            ).fetchall()
        out: list[Bijection] = []
        for r in rows:
            out.append(
                Bijection(
                    doc_id=r[0],
                    page=r[1],
                    id=r[2],
                    left_set=json.loads(r[3]),
                    right_set=json.loads(r[4]),
                    mapping=json.loads(r[5]),
                    origin=_json_to_point(r[6]),
                    bbox=_json_to_bbox(r[7]),
                )
            )
        return out

    def get_grids_by_doc(self, doc_id: str) -> list[Grid]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT doc_id, page, grid_id, rows, cols, cells_json, origin_json, bbox_json "
                "FROM grids WHERE doc_id = ?",
                (doc_id,),
            ).fetchall()
        out: list[Grid] = []
        for r in rows:
            cells_raw = json.loads(r[5])
            cells = [
                GridCell(
                    row=cell["row"],
                    col=cell["col"],
                    value=cell["value"],
                    origin=(
                        Point(x=cell["origin"]["x"], y=cell["origin"]["y"])
                        if cell.get("origin")
                        else None
                    ),
                )
                for cell in cells_raw
            ]
            out.append(
                Grid(
                    doc_id=r[0],
                    page=r[1],
                    id=r[2],
                    rows=r[3],
                    cols=r[4],
                    cells=cells,
                    origin=_json_to_point(r[6]),
                    bbox=_json_to_bbox(r[7]),
                )
            )
        return out

    def get_ranges_by_doc(self, doc_id: str) -> list[Range]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT doc_id, page, range_id, label, min_val, typ_val, max_val, "
                "unit, conditions, context, origin_json, bbox_json "
                "FROM ranges WHERE doc_id = ?",
                (doc_id,),
            ).fetchall()
        return [
            Range(
                doc_id=r[0], page=r[1], id=r[2], label=r[3],
                min=r[4], typ=r[5], max=r[6], unit=r[7],
                conditions=r[8], context=r[9],
                origin=_json_to_point(r[10]), bbox=_json_to_bbox(r[11]),
            )
            for r in rows
        ]

    def get_conditional_units_by_doc(self, doc_id: str) -> list[ConditionalUnit]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT doc_id, page, cunit_id, label, value, unit, "
                "condition_type, condition_value, derating, context, "
                "origin_json, bbox_json "
                "FROM conditional_units WHERE doc_id = ?",
                (doc_id,),
            ).fetchall()
        return [
            ConditionalUnit(
                doc_id=r[0], page=r[1], id=r[2], label=r[3],
                value=r[4], unit=r[5], condition_type=r[6],
                condition_value=r[7], derating=r[8], context=r[9],
                origin=_json_to_point(r[10]), bbox=_json_to_bbox(r[11]),
            )
            for r in rows
        ]

    def get_all_canonical_by_doc(
        self, doc_id: str
    ) -> list[Unit | Bijection | Grid | Range | ConditionalUnit]:
        """Return all canonical objects for a document."""
        result: list[Unit | Bijection | Grid | Range | ConditionalUnit] = []
        result.extend(self.get_units_by_doc(doc_id))
        result.extend(self.get_bijections_by_doc(doc_id))
        result.extend(self.get_grids_by_doc(doc_id))
        result.extend(self.get_ranges_by_doc(doc_id))
        result.extend(self.get_conditional_units_by_doc(doc_id))
        return result

    def delete_document(self, doc_id: str) -> None:
        """Remove a document and all its canonical objects from the store."""
        with self._conn() as c:
            c.execute("DELETE FROM units WHERE doc_id = ?", (doc_id,))
            c.execute("DELETE FROM bijections WHERE doc_id = ?", (doc_id,))
            c.execute("DELETE FROM grids WHERE doc_id = ?", (doc_id,))
            c.execute("DELETE FROM ranges WHERE doc_id = ?", (doc_id,))
            c.execute("DELETE FROM conditional_units WHERE doc_id = ?", (doc_id,))
            c.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
        self._audit("delete_document", doc_id)

    def list_documents(self) -> list[dict[str, Any]]:
        """List ingested documents with counts."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT d.doc_id, d.filename, d.page_count, d.created_at, "
                "(SELECT COUNT(*) FROM units u WHERE u.doc_id = d.doc_id), "
                "(SELECT COUNT(*) FROM bijections b WHERE b.doc_id = d.doc_id), "
                "(SELECT COUNT(*) FROM grids g WHERE g.doc_id = d.doc_id) FROM documents d"
            ).fetchall()
        return [
            {
                "doc_id": r[0],
                "filename": r[1],
                "page_count": r[2],
                "created_at": r[3],
                "units_count": r[4],
                "bijections_count": r[5],
                "grids_count": r[6],
            }
            for r in rows
        ]
