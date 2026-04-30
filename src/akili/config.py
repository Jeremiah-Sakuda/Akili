"""
Centralized configuration for the Akili project.

All environment variable reads happen here. Other modules import from this module
instead of reading os.environ directly, ensuring consistent defaults and single
source of truth.
"""

from __future__ import annotations

import os


def _bool_env(key: str, default: str = "0") -> bool:
    return os.environ.get(key, default).strip().lower() in ("1", "true", "yes")


def _float_env(key: str, default: str) -> float:
    return float(os.environ.get(key, default))


def _int_env(key: str, default: str) -> int:
    return int(os.environ.get(key, default))


# ---------------------------------------------------------------------------
# Gemini / LLM
# ---------------------------------------------------------------------------
GEMINI_MODEL: str = os.environ.get("AKILI_GEMINI_MODEL", "gemini-3-pro-preview")
GEMINI_MAX_RETRIES: int = _int_env("AKILI_GEMINI_MAX_RETRIES", "6")
GEMINI_BACKOFF_BASE: float = _float_env("AKILI_GEMINI_BACKOFF_BASE", "8.0")
GEMINI_PAGE_DELAY: float = _float_env("AKILI_GEMINI_PAGE_DELAY_SECONDS", "4.0")
GEMINI_429_COOLDOWN: float = _float_env("AKILI_GEMINI_429_COOLDOWN_SECONDS", "60.0")
FORMAT_TIMEOUT: float = _float_env("AKILI_FORMAT_TIMEOUT_SEC", "2.5")

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
DB_PATH: str = os.environ.get("AKILI_DB_PATH", "akili.db")

# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------
MAX_UPLOAD_BYTES: int = _int_env("AKILI_MAX_UPLOAD_BYTES", "104857600")  # 100 MB
MAX_PAGES: int = _int_env("AKILI_MAX_PAGES", "500")
CONSENSUS_ENABLED: bool = _bool_env("AKILI_CONSENSUS_ENABLED")
PAGE_CLASSIFY_ENABLED: bool = _bool_env("AKILI_PAGE_CLASSIFY_ENABLED")

# ---------------------------------------------------------------------------
# Verification thresholds
# ---------------------------------------------------------------------------
VERIFY_THRESHOLD: float = _float_env("AKILI_VERIFY_THRESHOLD", "0.85")
REVIEW_THRESHOLD: float = _float_env("AKILI_REVIEW_THRESHOLD", "0.50")

# Confidence weights
W_EXTRACTION: float = 0.30
W_CANONICAL: float = 0.30
W_VERIFICATION: float = 0.40

# ---------------------------------------------------------------------------
# API / Auth
# ---------------------------------------------------------------------------
DEBUG: bool = _bool_env("AKILI_DEBUG")
REQUIRE_AUTH: bool = _bool_env("AKILI_REQUIRE_AUTH")
RATE_LIMIT_ENABLED: bool = _bool_env("AKILI_RATE_LIMIT", "1")

CORS_ORIGINS: list[str] = [
    o.strip()
    for o in os.environ.get("AKILI_CORS_ORIGINS", "").split(",")
    if o.strip() and o.strip().startswith("http")
]
if not CORS_ORIGINS:
    CORS_ORIGINS = ["http://localhost:3000", "http://localhost:3001"]
