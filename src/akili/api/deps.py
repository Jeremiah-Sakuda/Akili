"""
Shared FastAPI dependencies for all routers.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from akili import config
from akili.store import Store, create_store
from akili.store.corrections import CorrectionStore
from akili.store.usage import UsageStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton stores (thread-safe lazy init)
# ---------------------------------------------------------------------------

_store: Store | None = None
_store_lock = threading.Lock()


def get_store() -> Store:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                db_url = os.environ.get("DATABASE_URL", "")
                _store = create_store(db_url=db_url or None)
    return _store


_usage_store: UsageStore | None = None
_usage_store_lock = threading.Lock()


def get_usage_store() -> UsageStore:
    global _usage_store
    if _usage_store is None:
        with _usage_store_lock:
            if _usage_store is None:
                db_url = os.environ.get("DATABASE_URL", "")
                _usage_store = UsageStore(db_url=db_url or None)
    return _usage_store


_correction_store: CorrectionStore | None = None
_correction_store_lock = threading.Lock()


def get_correction_store() -> CorrectionStore:
    global _correction_store
    if _correction_store is None:
        with _correction_store_lock:
            if _correction_store is None:
                db_url = os.environ.get("DATABASE_URL", "")
                _correction_store = CorrectionStore(db_url=db_url or None)
    return _correction_store


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def docs_dir() -> Path:
    """Directory where ingested PDFs are stored (next to DB)."""
    db_path = config.DB_PATH
    return Path(db_path).resolve().parent / "docs"


def validate_doc_id(doc_id: str) -> None:
    """Raise 400 if doc_id is invalid (path traversal)."""
    if not doc_id or not re.match(r"^[a-zA-Z0-9_-]+$", doc_id):
        raise HTTPException(status_code=400, detail="Invalid doc_id")


def is_debug() -> bool:
    """Return True if full error messages should be included in API responses."""
    return config.DEBUG
