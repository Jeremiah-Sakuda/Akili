"""
Corrections store: track human corrections to extracted/verified facts.

When confidence is in the REVIEW band (0.50-0.85), engineers can:
- CONFIRM: fact enters canonical store as human-verified
- CORRECT: engineer provides the right value; both original + correction stored

Corrections are logged with provenance: who corrected, when, original extraction.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
    """SQLite-backed storage for human corrections/confirmations."""

    def __init__(self, db_path: Path | str = "akili.db"):
        self.db_path = Path(db_path)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_schema(self) -> None:
        with self._conn() as c:
            c.executescript("""
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
        with self._conn() as c:
            cursor = c.execute(
                """INSERT INTO corrections (doc_id, canonical_id, canonical_type,
                   action, original_value, corrected_value, corrected_by, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (doc_id, canonical_id, canonical_type, action,
                 original_value, corrected_value, corrected_by, notes),
            )
            return cursor.lastrowid or 0

    def get_corrections_by_doc(self, doc_id: str) -> list[Correction]:
        """Get all corrections for a document."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, doc_id, canonical_id, canonical_type, action, "
                "original_value, corrected_value, corrected_by, notes, created_at "
                "FROM corrections WHERE doc_id = ? ORDER BY created_at DESC",
                (doc_id,),
            ).fetchall()
        return [
            Correction(
                id=r[0], doc_id=r[1], canonical_id=r[2], canonical_type=r[3],
                action=r[4], original_value=r[5], corrected_value=r[6],
                corrected_by=r[7], notes=r[8], created_at=r[9],
            )
            for r in rows
        ]

    def get_correction_stats(self, doc_id: str | None = None) -> dict[str, Any]:
        """Get correction statistics, optionally filtered by doc."""
        with self._conn() as c:
            if doc_id:
                total = c.execute("SELECT COUNT(*) FROM corrections WHERE doc_id = ?", (doc_id,)).fetchone()[0]
                confirms = c.execute("SELECT COUNT(*) FROM corrections WHERE doc_id = ? AND action = 'confirm'", (doc_id,)).fetchone()[0]
                corrects = c.execute("SELECT COUNT(*) FROM corrections WHERE doc_id = ? AND action = 'correct'", (doc_id,)).fetchone()[0]
            else:
                total = c.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]
                confirms = c.execute("SELECT COUNT(*) FROM corrections WHERE action = 'confirm'").fetchone()[0]
                corrects = c.execute("SELECT COUNT(*) FROM corrections WHERE action = 'correct'").fetchone()[0]
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
        with self._conn() as c:
            if doc_id:
                rows = c.execute(
                    "SELECT DISTINCT canonical_id, canonical_type FROM corrections "
                    "WHERE doc_id = ? ORDER BY canonical_id LIMIT ?",
                    (doc_id, limit),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT DISTINCT canonical_id, canonical_type FROM corrections "
                    "ORDER BY canonical_id LIMIT ?",
                    (limit,),
                ).fetchall()
        return [{"canonical_id": r[0], "canonical_type": r[1]} for r in rows]
