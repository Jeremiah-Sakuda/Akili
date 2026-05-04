"""
Shared FastAPI dependencies for all routers.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import uuid
from pathlib import Path

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


_LEGACY_DOC_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def validate_doc_id(doc_id: str) -> None:
    """Validate doc_id format. Prefers strict UUID4; allows legacy alphanumeric.

    Raises HTTPException 400 if doc_id is invalid (path traversal risk).
    Logs warning for legacy non-UUID doc_ids.
    """
    if not doc_id:
        raise HTTPException(status_code=400, detail="Invalid doc_id")

    # Try strict UUID4 validation first
    try:
        parsed = uuid.UUID(doc_id, version=4)
        # Ensure it's actually a valid UUID4 string format
        if str(parsed) == doc_id.lower():
            return  # Valid UUID4
    except ValueError:
        pass

    # Fallback: allow legacy alphanumeric doc_ids with warning
    if _LEGACY_DOC_ID_RE.match(doc_id):
        logger.warning(
            "Legacy non-UUID doc_id format: %s (consider migrating to UUID4)",
            doc_id,
        )
        return

    raise HTTPException(status_code=400, detail="Invalid doc_id")


def is_debug() -> bool:
    """Return True if full error messages should be included in API responses."""
    return config.DEBUG


def _is_production_environment() -> bool:
    """Return True if the environment looks like production (DATABASE_URL is set)."""
    return bool(os.environ.get("DATABASE_URL", "").startswith("postgresql"))


def require_doc_access(doc_id: str, user: dict | None) -> None:
    """A2: Verify user has access to document. Raises 403 if denied.

    - When auth is enabled and user exists: checks document ownership
    - When auth is disabled in production: logs security warning
    - When auth is disabled in dev: allows access (development convenience)
    """
    from akili.api.auth import is_auth_required

    if is_auth_required():
        # Auth is enabled - enforce ownership check
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        store = get_store()
        owner = store.get_document_owner(doc_id)
        if owner and owner != user.get("uid"):
            logger.warning(
                "A2: Cross-user document access denied: user=%s tried to access doc=%s owned by %s",
                user.get("uid"),
                doc_id,
                owner,
            )
            raise HTTPException(status_code=403, detail="Not authorized to access this document")
    else:
        # Auth is disabled
        if _is_production_environment():
            logger.error(
                "A2: Document access without authentication in production environment: doc_id=%s",
                doc_id,
            )
