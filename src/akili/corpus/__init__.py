"""
AKILI Public Corpus Module

Provides pre-canonicalized datasheet data for common chips,
enabling instant results without re-ingestion.
"""

from akili.corpus.loader import (
    COMMON_CHIPS,
    check_corpus_match,
    load_from_corpus,
)

__all__ = [
    "COMMON_CHIPS",
    "check_corpus_match",
    "load_from_corpus",
]
