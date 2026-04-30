"""
Shared connection management for SQLite and PostgreSQL backends.

SQLite: single persistent connection with WAL mode for concurrent reads.
PostgreSQL: reuses psycopg2 ThreadedConnectionPool.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Unified connection manager for SQLite and PostgreSQL."""

    def __init__(self, db_url: str | None = None, db_path: str | Path = "akili.db"):
        self._use_pg = False
        self._dsn: str | None = None
        self._sqlite_conn: sqlite3.Connection | None = None
        self._sqlite_lock = threading.Lock()
        self._pg_pool: Any = None

        if db_url and db_url.startswith("postgresql"):
            try:
                import psycopg2.pool  # noqa: F401
                self._use_pg = True
                self._dsn = db_url
                self._pg_pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=1, maxconn=10, dsn=db_url,
                )
                logger.info("ConnectionManager using PostgreSQL pool")
            except ImportError:
                logger.warning(
                    "DATABASE_URL is PostgreSQL but psycopg2 not installed; "
                    "falling back to SQLite"
                )

        if not self._use_pg:
            self.db_path = Path(db_path)
            self._sqlite_conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._sqlite_conn.execute("PRAGMA journal_mode=WAL")
            self._sqlite_conn.execute("PRAGMA foreign_keys=ON")

    @property
    def is_postgres(self) -> bool:
        return self._use_pg

    def placeholder(self) -> str:
        """Return the parameter placeholder for the current backend."""
        return "%s" if self._use_pg else "?"

    @contextmanager
    def connection(self) -> Generator[Any, None, None]:
        """Yield a database connection. For SQLite, uses a shared connection with a lock.
        For PostgreSQL, gets a connection from the pool and returns it after use."""
        if self._use_pg:
            conn = self._pg_pool.getconn()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                self._pg_pool.putconn(conn)
        else:
            with self._sqlite_lock:
                assert self._sqlite_conn is not None
                yield self._sqlite_conn
                self._sqlite_conn.commit()

    def close(self) -> None:
        """Close all connections."""
        if self._use_pg and self._pg_pool:
            self._pg_pool.closeall()
        elif self._sqlite_conn:
            self._sqlite_conn.close()
            self._sqlite_conn = None
