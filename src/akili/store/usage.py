"""
Usage tracking for free-tier limits.

Tracks document uploads and queries per user (by Firebase UID or IP fallback).
Default limits: 5 documents, 50 queries per user.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger("akili")

# Configurable limits via env vars
MAX_DOCUMENTS = int(os.environ.get("AKILI_FREE_TIER_DOCS", "5"))
MAX_QUERIES = int(os.environ.get("AKILI_FREE_TIER_QUERIES", "50"))


class UsageStore:
    """Track per-user usage for free tier enforcement."""

    def __init__(self, db_url: str | None = None, db_path: str | Path = "akili.db"):
        self._use_pg = False
        self._dsn: str | None = None

        if db_url and db_url.startswith("postgresql"):
            try:
                import psycopg2  # noqa: F401
                self._use_pg = True
                self._dsn = db_url
            except ImportError:
                pass

        if not self._use_pg:
            self.db_path = Path(db_path)

        self._init_schema()

    def _conn(self) -> Any:
        if self._use_pg:
            import psycopg2
            return psycopg2.connect(self._dsn)
        return sqlite3.connect(self.db_path)

    def _ph(self) -> str:
        return "%s" if self._use_pg else "?"

    def _init_schema(self) -> None:
        conn = self._conn()
        try:
            cur = conn.cursor()
            if self._use_pg:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS usage (
                        id SERIAL PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        action TEXT NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_usage_user ON usage(user_id, action)"
                )
            else:
                cur.executescript("""
                    CREATE TABLE IF NOT EXISTS usage (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        action TEXT NOT NULL,
                        created_at TEXT DEFAULT (datetime('now'))
                    );
                    CREATE INDEX IF NOT EXISTS idx_usage_user ON usage(user_id, action);
                """)
            conn.commit()
        finally:
            conn.close()

    def record(self, user_id: str, action: str) -> None:
        """Record a usage event (action: 'ingest' or 'query')."""
        ph = self._ph()
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO usage (user_id, action) VALUES ({ph}, {ph})",
                (user_id, action),
            )
            conn.commit()
        finally:
            conn.close()

    def count(self, user_id: str, action: str) -> int:
        """Count usage events for a user and action type."""
        ph = self._ph()
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute(
                f"SELECT COUNT(*) FROM usage WHERE user_id = {ph} AND action = {ph}",
                (user_id, action),
            )
            return cur.fetchone()[0]
        finally:
            conn.close()

    def check_limit(self, user_id: str, action: str) -> tuple[bool, int, int]:
        """Check if a user is within limits. Returns (allowed, current_count, max_count)."""
        current = self.count(user_id, action)
        if action == "ingest":
            return current < MAX_DOCUMENTS, current, MAX_DOCUMENTS
        elif action == "query":
            return current < MAX_QUERIES, current, MAX_QUERIES
        return True, current, 0

    def get_usage_summary(self, user_id: str) -> dict[str, Any]:
        """Get full usage summary for a user."""
        docs = self.count(user_id, "ingest")
        queries = self.count(user_id, "query")
        return {
            "documents": {"used": docs, "limit": MAX_DOCUMENTS, "remaining": max(0, MAX_DOCUMENTS - docs)},
            "queries": {"used": queries, "limit": MAX_QUERIES, "remaining": max(0, MAX_QUERIES - queries)},
        }
