"""
Public corpus library endpoints (FR-CORP-3).

Allows browsing pre-canonicalized chips without authentication.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from akili.api.deps import get_store
from akili.corpus import COMMON_CHIPS

logger = logging.getLogger(__name__)

router = APIRouter(tags=["library"])


@router.get("/library")
async def list_corpus() -> JSONResponse:
    """
    List all chips in the public corpus.

    Returns pre-canonicalized chip data that enables instant results.
    No authentication required.
    """
    store = get_store()

    # Check if store has corpus methods (PostgresStore)
    if hasattr(store, "list_corpus"):
        corpus_entries = store.list_corpus()
    else:
        # SQLite fallback - return empty list
        corpus_entries = []

    # Add available chips from COMMON_CHIPS that might not be in corpus yet
    corpus_mpns = {e["mpn"].lower() for e in corpus_entries}
    available_chips = []

    for chip in COMMON_CHIPS:
        in_corpus = chip.lower() in corpus_mpns
        available_chips.append(
            {
                "chip": chip,
                "available": in_corpus,
            }
        )

    return JSONResponse(
        content={
            "corpus": corpus_entries,
            "common_chips": available_chips,
            "total_in_corpus": len(corpus_entries),
            "total_common": len(COMMON_CHIPS),
        }
    )


@router.get("/library/{mpn}")
async def get_corpus_entry(mpn: str) -> JSONResponse:
    """
    Get details for a specific chip in the corpus.

    Returns canonical data summary (not full data) for the chip.
    No authentication required.
    """
    store = get_store()

    if not hasattr(store, "get_corpus_by_mpn"):
        return JSONResponse(
            status_code=404,
            content={"error": "Corpus not available"},
        )

    entry = store.get_corpus_by_mpn(mpn)
    if not entry:
        return JSONResponse(
            status_code=404,
            content={"error": f"Chip '{mpn}' not found in corpus"},
        )

    # Return summary, not full canonical data
    canonical = entry.get("canonical_data") or {}
    return JSONResponse(
        content={
            "mpn": entry["mpn"],
            "chip_name": entry["chip_name"],
            "datasheet_url": entry.get("datasheet_url"),
            "created_at": entry.get("created_at"),
            "summary": {
                "units": len(canonical.get("units", [])),
                "bijections": len(canonical.get("bijections", [])),
                "grids": len(canonical.get("grids", [])),
                "ranges": len(canonical.get("ranges", [])),
                "conditional_units": len(canonical.get("conditional_units", [])),
            },
        }
    )
