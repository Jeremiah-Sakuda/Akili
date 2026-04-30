"""
Persistence for canonical objects (Unit, Bijection, Grid, Range, ConditionalUnit).

SQLite for development/MVP; PostgreSQL for production/multi-tenant.
Use create_store() factory to get the appropriate backend.
"""

import os

from akili.store.base import BaseStore
from akili.store.repository import Store


def create_store(db_url: str | None = None, org_id: str = "default") -> BaseStore:
    """Factory: return the appropriate store backend.

    If DATABASE_URL or db_url starts with 'postgresql', use PostgresStore.
    Otherwise fall back to SQLite Store.
    """
    url = db_url or os.environ.get("DATABASE_URL", "")
    if url.startswith("postgresql"):
        from akili.store.postgres import PostgresStore
        return PostgresStore(dsn=url, org_id=org_id)
    return Store(db_path=url if url and not url.startswith("postgresql") else "akili.db")


__all__ = ["Store", "BaseStore", "create_store"]
