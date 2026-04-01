"""
Shared error utilities for the ingest package.
"""

from __future__ import annotations


def is_rate_limit_error(e: BaseException) -> bool:
    """Check if an exception indicates a Gemini 429 / resource exhausted error."""
    msg = (getattr(e, "message", None) or str(e)).lower()
    return "429" in msg or "resource exhausted" in msg or "resourceexhausted" in msg
