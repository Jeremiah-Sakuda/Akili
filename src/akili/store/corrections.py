"""
Corrections store: track human corrections to extracted/verified facts.

When confidence is in the REVIEW band (0.50-0.85), engineers can:
- CONFIRM: fact enters canonical store as human-verified
- CORRECT: engineer provides the right value; both original + correction stored

Corrections are logged with provenance: who corrected, when, original extraction.

Supports both SQLite (local dev) and PostgreSQL (production via DATABASE_URL).
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("akili")


@dataclass
class Correction:
    """A single human correction record."""
    id: int | None
    doc_id: str
    canonical_id: str
    canonical_type: str  # "unit" | "bijection" | "grid" | "range" | "conditional_unit"
    action: str  # "confirm" | "correct"
    original_value: str
    corrected_value: str | None
    corrected_by: str | None
    notes: str | None
    created_at: str | None


class CorrectionStore:
    """Storage for human corrections/confirmations. Supports SQLite and PostgreSQL."""

    def __init__(
        self,
        db_path: Path | str = "akili.db",
        db_url: str | None = None,
    ):
        self._use_pg = False
        self._dsn: str | None = None

        if db_url and db_url.startswith("postgresql"):
            try:
                import psycopg2  # noqa: F401
                self._use_pg = True
                self._dsn = db_url
                logger.info("CorrectionStore using PostgreSQL")
            except ImportError:
                logger.warning(
                    "DATABASE_URL is PostgreSQL but psycopg2 not installed; "
                    "falling back to SQLite"
                )

        if not self._use_pg:
            self.db_path = Path(db_path)

        self._init_schema()

    def _conn(self) -> Any:
        if self._use_pg:
            import psycopg2
            return psycopg2.connect(self._dsn)
        return sqlite3.connect(self.db_path)

    def _placeholder(self) -> str:
        """Return the parameter placeholder for the current backend."""
        return "%s" if self._use_pg else "?"

    def _init_schema(self) -> None:
        conn = self._conn()
        try:
            cur = conn.cursor()
            if self._use_pg:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS corrections (
                        id SERIAL PRIMARY KEY,
                        doc_id TEXT NOT NULL,
                        canonical_id TEXT NOT NULL,
                        canonical_type TEXT NOT NULL,
                        action TEXT NOT NULL CHECK (action IN ('confirm', 'correct')),
                        original_value TEXT NOT NULL,
                        corrected_value TEXT,
                        corrected_by TEXT,
                        notes TEXT,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_corrections_doc ON corrections(doc_id)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_corrections_canonical ON corrections(canonical_id)"
                )
            else:
                cur.executescript("""
                    CREATE TABLE IF NOT EXISTS corrections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        doc_id TEXT NOT NULL,
                        canonical_id TEXT NOT NULL,
                        canonical_type TEXT NOT NULL,
                        action TEXT NOT NULL CHECK (action IN ('confirm', 'correct')),
                        original_value TEXT NOT NULL,
                        corrected_value TEXT,
                        corrected_by TEXT,
                        notes TEXT,
                        created_at TEXT DEFAULT (datetime('now'))
                    );
                    CREATE INDEX IF NOT EXISTS idx_corrections_doc ON corrections(doc_id);
                    CREATE INDEX IF NOT EXISTS idx_corrections_canonical ON corrections(canonical_id);
                """)
            conn.commit()
        finally:
            conn.close()

    def add_correction(
        self,
        doc_id: str,
        canonical_id: str,
        canonical_type: str,
        action: str,
        original_value: str,
        corrected_value: str | None = None,
        corrected_by: str | None = None,
        notes: str | None = None,
    ) -> int:
        """Record a correction or confirmation. Returns the correction id."""
        ph = self._placeholder()
        conn = self._conn()
        try:
            cur = conn.cursor()
            if self._use_pg:
                cur.execute(
                    f"""INSERT INTO corrections (doc_id, canonical_id, canonical_type,
                       action, original_value, corrected_value, corrected_by, notes)
                       VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                       RETURNING id""",
                    (doc_id, canonical_id, canonical_type, action,
                     original_value, corrected_value, corrected_by, notes),
                )
                row = cur.fetchone()
                conn.commit()
                return row[0] if row else 0
            else:
                cur.execute(
                    f"""INSERT INTO corrections (doc_id, canonical_id, canonical_type,
                       action, original_value, corrected_value, corrected_by, notes)
                       VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})""",
                    (doc_id, canonical_id, canonical_type, action,
                     original_value, corrected_value, corrected_by, notes),
                )
                conn.commit()
                return cur.lastrowid or 0
        finally:
            conn.close()

    def get_corrections_by_doc(self, doc_id: str) -> list[Correction]:
        """Get all corrections for a document."""
        ph = self._placeholder()
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute(
                f"SELECT id, doc_id, canonical_id, canonical_type, action, "
                f"original_value, corrected_value, corrected_by, notes, created_at "
                f"FROM corrections WHERE doc_id = {ph} ORDER BY created_at DESC",
                (doc_id,),
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        return [
            Correction(
                id=r[0], doc_id=r[1], canonical_id=r[2], canonical_type=r[3],
                action=r[4], original_value=r[5], corrected_value=r[6],
                corrected_by=r[7], notes=r[8],
                created_at=str(r[9]) if r[9] else None,
            )
            for r in rows
        ]

    def get_correction_stats(self, doc_id: str | None = None) -> dict[str, Any]:
        """Get correction statistics, optionally filtered by doc."""
        ph = self._placeholder()
        conn = self._conn()
        try:
            cur = conn.cursor()
            if doc_id:
                cur.execute(f"SELECT COUNT(*) FROM corrections WHERE doc_id = {ph}", (doc_id,))
                total = cur.fetchone()[0]
                cur.execute(f"SELECT COUNT(*) FROM corrections WHERE doc_id = {ph} AND action = 'confirm'", (doc_id,))
                confirms = cur.fetchone()[0]
                cur.execute(f"SELECT COUNT(*) FROM corrections WHERE doc_id = {ph} AND action = 'correct'", (doc_id,))
                corrects = cur.fetchone()[0]
            else:
                cur.execute("SELECT COUNT(*) FROM corrections")
                total = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM corrections WHERE action = 'confirm'")
                confirms = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM corrections WHERE action = 'correct'")
                corrects = cur.fetchone()[0]
        finally:
            conn.close()
        return {
            "total": total,
            "confirmations": confirms,
            "corrections": corrects,
            "correction_rate": corrects / total if total > 0 else 0,
        }

    def get_review_queue(self, doc_id: str | None = None, limit: int = 50) -> list[dict]:
        """Get canonical objects that are in the REVIEW tier but haven't been corrected yet.

        This is a placeholder that returns corrections metadata; the actual queue
        is assembled at the API layer by cross-referencing confidence tiers.
        """
        ph = self._placeholder()
        conn = self._conn()
        try:
            cur = conn.cursor()
            if doc_id:
                cur.execute(
                    f"SELECT DISTINCT canonical_id, canonical_type FROM corrections "
                    f"WHERE doc_id = {ph} ORDER BY canonical_id LIMIT {ph}",
                    (doc_id, limit),
                )
            else:
                cur.execute(
                    f"SELECT DISTINCT canonical_id, canonical_type FROM corrections "
                    f"ORDER BY canonical_id LIMIT {ph}",
                    (limit,),
                )
            rows = cur.fetchall()
        finally:
            conn.close()
        return [{"canonical_id": r[0], "canonical_type": r[1]} for r in rows]
