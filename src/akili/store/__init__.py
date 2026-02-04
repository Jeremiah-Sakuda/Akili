"""
Persistence for canonical objects (Unit, Bijection, Grid) with provenance.

SQLite for MVP; PostgreSQL optional for scale.
"""

from akili.store.repository import Store

__all__ = ["Store"]
