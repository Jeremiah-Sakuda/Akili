"""
PostgreSQL store implementation with multi-tenant org_id isolation and audit logging.

Requires psycopg2 (pip install psycopg2-binary) and a running PostgreSQL instance.
Connection config via DATABASE_URL env var or individual PG* vars.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus

from akili.canonical import Bijection, ConditionalUnit, Grid, Range, Unit
from akili.canonical.models import BBox, GridCell, Point
from akili.store.base import BaseStore

logger = logging.getLogger(__name__)

try:
    import psycopg2
    import psycopg2.extras
    import psycopg2.pool
    from psycopg2 import sql as pgsql
    PG_AVAILABLE = True
except ImportError:
    PG_AVAILABLE = False
    pgsql = None  # type: ignore[assignment]
    logger.info("psycopg2 not installed; PostgreSQL store unavailable")


def _point_dict(p: Point) -> str:
    return json.dumps({"x": p.x, "y": p.y})


def _bbox_dict(b: BBox | None) -> str | None:
    if b is None:
        return None
    return json.dumps({"x1": b.x1, "y1": b.y1, "x2": b.x2, "y2": b.y2})


def _parse_point(s: str) -> Point:
    d = json.loads(s)
    return Point(x=d["x"], y=d["y"])


def _parse_bbox(s: str | None) -> BBox | None:
    if s is None:
        return None
    d = json.loads(s)
    return BBox(x1=d["x1"], y1=d["y1"], x2=d["x2"], y2=d["y2"])


def _get_dsn() -> str:
    """Build PostgreSQL DSN from env vars."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    host = os.environ.get("PGHOST", "localhost")
    port = os.environ.get("PGPORT", "5432")
    db = os.environ.get("PGDATABASE", "akili")
    user = os.environ.get("PGUSER", "akili")
    password = os.environ.get("PGPASSWORD", "")
    return f"postgresql://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{db}"


_CANONICAL_TABLES = ("units", "bijections", "grids", "ranges", "conditional_units")


class PostgresStore(BaseStore):
    """PostgreSQL-backed store with org_id multi-tenancy and immutable audit log."""

    def __init__(self, dsn: str | None = None, org_id: str = "default"):
        if not PG_AVAILABLE:
            raise ImportError("psycopg2 is required for PostgresStore. Install with: pip install psycopg2-binary")
        self._dsn = dsn or _get_dsn()
        self._org_id = org_id
        self._pool = psycopg2.pool.ThreadedConnectionPool(minconn=1, maxconn=10, dsn=self._dsn)
        self._init_schema()

    class _PooledConnection:
        """Context manager that commits on success and returns connection to pool."""
        def __init__(self, pool: Any):
            self._pool = pool
            self._conn = pool.getconn()
        def __enter__(self):
            return self._conn
        def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any):
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
            self._pool.putconn(self._conn)
            return False

    def _conn(self):
        return self._PooledConnection(self._pool)

    def _init_schema(self) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS documents (
                        doc_id TEXT NOT NULL,
                        org_id TEXT NOT NULL DEFAULT 'default',
                        filename TEXT,
                        page_count INTEGER,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        PRIMARY KEY (doc_id, org_id)
                    );
                    CREATE TABLE IF NOT EXISTS units (
                        id SERIAL PRIMARY KEY,
                        doc_id TEXT NOT NULL,
                        org_id TEXT NOT NULL DEFAULT 'default',
                        page INTEGER NOT NULL,
                        unit_id TEXT NOT NULL,
                        label TEXT,
                        value TEXT NOT NULL,
                        unit_of_measure TEXT,
                        context TEXT,
                        origin_json TEXT NOT NULL,
                        bbox_json TEXT,
                        UNIQUE(doc_id, org_id, page, unit_id)
                    );
                    CREATE TABLE IF NOT EXISTS bijections (
                        id SERIAL PRIMARY KEY,
                        doc_id TEXT NOT NULL,
                        org_id TEXT NOT NULL DEFAULT 'default',
                        page INTEGER NOT NULL,
                        bijection_id TEXT NOT NULL,
                        left_set_json TEXT NOT NULL,
                        right_set_json TEXT NOT NULL,
                        mapping_json TEXT NOT NULL,
                        origin_json TEXT NOT NULL,
                        bbox_json TEXT,
                        UNIQUE(doc_id, org_id, page, bijection_id)
                    );
                    CREATE TABLE IF NOT EXISTS grids (
                        id SERIAL PRIMARY KEY,
                        doc_id TEXT NOT NULL,
                        org_id TEXT NOT NULL DEFAULT 'default',
                        page INTEGER NOT NULL,
                        grid_id TEXT NOT NULL,
                        rows INTEGER NOT NULL,
                        cols INTEGER NOT NULL,
                        cells_json TEXT NOT NULL,
                        origin_json TEXT NOT NULL,
                        bbox_json TEXT,
                        UNIQUE(doc_id, org_id, page, grid_id)
                    );
                    CREATE TABLE IF NOT EXISTS ranges (
                        id SERIAL PRIMARY KEY,
                        doc_id TEXT NOT NULL,
                        org_id TEXT NOT NULL DEFAULT 'default',
                        page INTEGER NOT NULL,
                        range_id TEXT NOT NULL,
                        label TEXT,
                        min_val DOUBLE PRECISION,
                        typ_val DOUBLE PRECISION,
                        max_val DOUBLE PRECISION,
                        unit TEXT NOT NULL,
                        conditions TEXT,
                        context TEXT,
                        origin_json TEXT NOT NULL,
                        bbox_json TEXT,
                        UNIQUE(doc_id, org_id, page, range_id)
                    );
                    CREATE TABLE IF NOT EXISTS conditional_units (
                        id SERIAL PRIMARY KEY,
                        doc_id TEXT NOT NULL,
                        org_id TEXT NOT NULL DEFAULT 'default',
                        page INTEGER NOT NULL,
                        cunit_id TEXT NOT NULL,
                        label TEXT,
                        value DOUBLE PRECISION NOT NULL,
                        unit TEXT NOT NULL,
                        condition_type TEXT NOT NULL,
                        condition_value TEXT NOT NULL,
                        derating TEXT,
                        context TEXT,
                        origin_json TEXT NOT NULL,
                        bbox_json TEXT,
                        UNIQUE(doc_id, org_id, page, cunit_id)
                    );
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id SERIAL PRIMARY KEY,
                        org_id TEXT NOT NULL DEFAULT 'default',
                        doc_id TEXT,
                        action TEXT NOT NULL,
                        actor TEXT,
                        details_json TEXT,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                    CREATE INDEX IF NOT EXISTS idx_audit_log_doc ON audit_log(doc_id);
                    CREATE INDEX IF NOT EXISTS idx_audit_log_org ON audit_log(org_id);
                """)

    def _audit(self, action: str, doc_id: str | None, actor: str | None = None, details: dict | None = None) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO audit_log (org_id, doc_id, action, actor, details_json) VALUES (%s, %s, %s, %s, %s)",
                    (self._org_id, doc_id, action, actor, json.dumps(details) if details else None),
                )

    def add_document(self, doc_id: str, filename: str | None = None, page_count: int = 0) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO documents (doc_id, org_id, filename, page_count)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (doc_id, org_id) DO UPDATE SET filename=EXCLUDED.filename, page_count=EXCLUDED.page_count""",
                    (doc_id, self._org_id, filename or "", page_count),
                )
        self._audit("add_document", doc_id, details={"filename": filename, "page_count": page_count})

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
        self.add_document(doc_id, filename, page_count)
        with self._conn() as conn:
            with conn.cursor() as cur:
                for u in units:
                    cur.execute(
                        """INSERT INTO units (doc_id, org_id, page, unit_id, label, value,
                           unit_of_measure, context, origin_json, bbox_json)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT (doc_id, org_id, page, unit_id) DO UPDATE SET
                           label=EXCLUDED.label, value=EXCLUDED.value,
                           unit_of_measure=EXCLUDED.unit_of_measure, context=EXCLUDED.context,
                           origin_json=EXCLUDED.origin_json, bbox_json=EXCLUDED.bbox_json""",
                        (u.doc_id, self._org_id, u.page, u.id, u.label, str(u.value),
                         u.unit_of_measure, u.context,
                         _point_dict(u.origin), _bbox_dict(u.bbox)),
                    )
                for b in bijections:
                    cur.execute(
                        """INSERT INTO bijections (doc_id, org_id, page, bijection_id,
                           left_set_json, right_set_json, mapping_json, origin_json, bbox_json)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT (doc_id, org_id, page, bijection_id) DO UPDATE SET
                           left_set_json=EXCLUDED.left_set_json, right_set_json=EXCLUDED.right_set_json,
                           mapping_json=EXCLUDED.mapping_json, origin_json=EXCLUDED.origin_json,
                           bbox_json=EXCLUDED.bbox_json""",
                        (b.doc_id, self._org_id, b.page, b.id,
                         json.dumps(b.left_set), json.dumps(b.right_set),
                         json.dumps(b.mapping), _point_dict(b.origin), _bbox_dict(b.bbox)),
                    )
                for g in grids:
                    cells_j = json.dumps([
                        {"row": c.row, "col": c.col, "value": c.value,
                         "origin": {"x": c.origin.x, "y": c.origin.y} if c.origin else None}
                        for c in g.cells
                    ])
                    cur.execute(
                        """INSERT INTO grids (doc_id, org_id, page, grid_id, rows, cols,
                           cells_json, origin_json, bbox_json)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT (doc_id, org_id, page, grid_id) DO UPDATE SET
                           rows=EXCLUDED.rows, cols=EXCLUDED.cols, cells_json=EXCLUDED.cells_json,
                           origin_json=EXCLUDED.origin_json, bbox_json=EXCLUDED.bbox_json""",
                        (g.doc_id, self._org_id, g.page, g.id, g.rows, g.cols,
                         cells_j, _point_dict(g.origin), _bbox_dict(g.bbox)),
                    )
                for r in (ranges or []):
                    cur.execute(
                        """INSERT INTO ranges (doc_id, org_id, page, range_id, label,
                           min_val, typ_val, max_val, unit, conditions, context,
                           origin_json, bbox_json)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT (doc_id, org_id, page, range_id) DO UPDATE SET
                           label=EXCLUDED.label, min_val=EXCLUDED.min_val, typ_val=EXCLUDED.typ_val,
                           max_val=EXCLUDED.max_val, unit=EXCLUDED.unit, conditions=EXCLUDED.conditions,
                           context=EXCLUDED.context, origin_json=EXCLUDED.origin_json, bbox_json=EXCLUDED.bbox_json""",
                        (r.doc_id, self._org_id, r.page, r.id, r.label,
                         r.min, r.typ, r.max, r.unit, r.conditions, r.context,
                         _point_dict(r.origin), _bbox_dict(r.bbox)),
                    )
                for cu in (conditional_units or []):
                    cur.execute(
                        """INSERT INTO conditional_units (doc_id, org_id, page, cunit_id,
                           label, value, unit, condition_type, condition_value,
                           derating, context, origin_json, bbox_json)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT (doc_id, org_id, page, cunit_id) DO UPDATE SET
                           label=EXCLUDED.label, value=EXCLUDED.value, unit=EXCLUDED.unit,
                           condition_type=EXCLUDED.condition_type, condition_value=EXCLUDED.condition_value,
                           derating=EXCLUDED.derating, context=EXCLUDED.context,
                           origin_json=EXCLUDED.origin_json, bbox_json=EXCLUDED.bbox_json""",
                        (cu.doc_id, self._org_id, cu.page, cu.id, cu.label,
                         cu.value, cu.unit, cu.condition_type, cu.condition_value,
                         cu.derating, cu.context, _point_dict(cu.origin), _bbox_dict(cu.bbox)),
                    )
        self._audit("store_canonical", doc_id, details={
            "units": len(units), "bijections": len(bijections), "grids": len(grids),
            "ranges": len(ranges or []), "conditional_units": len(conditional_units or []),
        })

    def get_units_by_doc(self, doc_id: str) -> list[Unit]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT doc_id, page, unit_id, label, value, unit_of_measure, context, "
                    "origin_json, bbox_json FROM units WHERE doc_id = %s AND org_id = %s",
                    (doc_id, self._org_id),
                )
                rows = cur.fetchall()
        out: list[Unit] = []
        for r in rows:
            val: str | float = r[4]
            try:
                val = float(r[4]) if "." in str(r[4]) else int(r[4])
            except (ValueError, TypeError):
                pass
            out.append(Unit(
                doc_id=r[0], page=r[1], id=r[2], label=r[3], value=val,
                unit_of_measure=r[5], context=r[6],
                origin=_parse_point(r[7]), bbox=_parse_bbox(r[8]),
            ))
        return out

    def get_bijections_by_doc(self, doc_id: str) -> list[Bijection]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT doc_id, page, bijection_id, left_set_json, right_set_json, "
                    "mapping_json, origin_json, bbox_json FROM bijections WHERE doc_id = %s AND org_id = %s",
                    (doc_id, self._org_id),
                )
                rows = cur.fetchall()
        return [
            Bijection(
                doc_id=r[0], page=r[1], id=r[2],
                left_set=json.loads(r[3]), right_set=json.loads(r[4]),
                mapping=json.loads(r[5]), origin=_parse_point(r[6]), bbox=_parse_bbox(r[7]),
            )
            for r in rows
        ]

    def get_grids_by_doc(self, doc_id: str) -> list[Grid]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT doc_id, page, grid_id, rows, cols, cells_json, origin_json, bbox_json "
                    "FROM grids WHERE doc_id = %s AND org_id = %s",
                    (doc_id, self._org_id),
                )
                rows = cur.fetchall()
        out: list[Grid] = []
        for r in rows:
            cells_raw = json.loads(r[5])
            cells = [
                GridCell(
                    row=cell["row"], col=cell["col"], value=cell["value"],
                    origin=Point(x=cell["origin"]["x"], y=cell["origin"]["y"]) if cell.get("origin") else None,
                )
                for cell in cells_raw
            ]
            out.append(Grid(
                doc_id=r[0], page=r[1], id=r[2], rows=r[3], cols=r[4],
                cells=cells, origin=_parse_point(r[6]), bbox=_parse_bbox(r[7]),
            ))
        return out

    def get_ranges_by_doc(self, doc_id: str) -> list[Range]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT doc_id, page, range_id, label, min_val, typ_val, max_val, "
                    "unit, conditions, context, origin_json, bbox_json "
                    "FROM ranges WHERE doc_id = %s AND org_id = %s",
                    (doc_id, self._org_id),
                )
                rows = cur.fetchall()
        return [
            Range(
                doc_id=r[0], page=r[1], id=r[2], label=r[3],
                min=r[4], typ=r[5], max=r[6], unit=r[7],
                conditions=r[8], context=r[9],
                origin=_parse_point(r[10]), bbox=_parse_bbox(r[11]),
            )
            for r in rows
        ]

    def get_conditional_units_by_doc(self, doc_id: str) -> list[ConditionalUnit]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT doc_id, page, cunit_id, label, value, unit, "
                    "condition_type, condition_value, derating, context, "
                    "origin_json, bbox_json "
                    "FROM conditional_units WHERE doc_id = %s AND org_id = %s",
                    (doc_id, self._org_id),
                )
                rows = cur.fetchall()
        return [
            ConditionalUnit(
                doc_id=r[0], page=r[1], id=r[2], label=r[3],
                value=r[4], unit=r[5], condition_type=r[6],
                condition_value=r[7], derating=r[8], context=r[9],
                origin=_parse_point(r[10]), bbox=_parse_bbox(r[11]),
            )
            for r in rows
        ]

    def get_all_canonical_by_doc(
        self, doc_id: str
    ) -> list[Unit | Bijection | Grid | Range | ConditionalUnit]:
        result: list[Unit | Bijection | Grid | Range | ConditionalUnit] = []
        result.extend(self.get_units_by_doc(doc_id))
        result.extend(self.get_bijections_by_doc(doc_id))
        result.extend(self.get_grids_by_doc(doc_id))
        result.extend(self.get_ranges_by_doc(doc_id))
        result.extend(self.get_conditional_units_by_doc(doc_id))
        return result

    def delete_document(self, doc_id: str) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                for table in _CANONICAL_TABLES:
                    cur.execute(
                        pgsql.SQL("DELETE FROM {} WHERE doc_id = %s AND org_id = %s").format(
                            pgsql.Identifier(table)
                        ),
                        (doc_id, self._org_id),
                    )
                cur.execute("DELETE FROM documents WHERE doc_id = %s AND org_id = %s", (doc_id, self._org_id))
        self._audit("delete_document", doc_id)

    def list_documents(self) -> list[dict[str, Any]]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT d.doc_id, d.filename, d.page_count, d.created_at,
                       (SELECT COUNT(*) FROM units u WHERE u.doc_id = d.doc_id AND u.org_id = d.org_id),
                       (SELECT COUNT(*) FROM bijections b WHERE b.doc_id = d.doc_id AND b.org_id = d.org_id),
                       (SELECT COUNT(*) FROM grids g WHERE g.doc_id = d.doc_id AND g.org_id = d.org_id)
                       FROM documents d WHERE d.org_id = %s""",
                    (self._org_id,),
                )
                rows = cur.fetchall()
        return [
            {
                "doc_id": r[0], "filename": r[1], "page_count": r[2],
                "created_at": str(r[3]) if r[3] else None,
                "units_count": r[4], "bijections_count": r[5], "grids_count": r[6],
            }
            for r in rows
        ]

    def get_audit_log(self, doc_id: str | None = None, limit: int = 100) -> list[dict]:
        """Return audit log entries, optionally filtered by doc_id."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                if doc_id:
                    cur.execute(
                        "SELECT id, org_id, doc_id, action, actor, details_json, created_at "
                        "FROM audit_log WHERE org_id = %s AND doc_id = %s "
                        "ORDER BY created_at DESC LIMIT %s",
                        (self._org_id, doc_id, limit),
                    )
                else:
                    cur.execute(
                        "SELECT id, org_id, doc_id, action, actor, details_json, created_at "
                        "FROM audit_log WHERE org_id = %s ORDER BY created_at DESC LIMIT %s",
                        (self._org_id, limit),
                    )
                rows = cur.fetchall()
        return [
            {
                "id": r[0], "org_id": r[1], "doc_id": r[2], "action": r[3],
                "actor": r[4], "details": json.loads(r[5]) if r[5] else None,
                "created_at": str(r[6]) if r[6] else None,
            }
            for r in rows
        ]
