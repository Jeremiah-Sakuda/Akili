"""
FastAPI app factory: creates app, mounts routers, configures CORS/middleware.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from akili import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

_DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]

_ALLOWED_CORS_METHODS = ["GET", "POST", "DELETE", "OPTIONS"]
_ALLOWED_CORS_HEADERS = [
    "Authorization",
    "Content-Type",
    "Accept",
    "Origin",
    "X-Requested-With",
]


def _cors_origins() -> list[str]:
    origins = config.CORS_ORIGINS
    if not origins:
        return _DEFAULT_CORS_ORIGINS
    validated = []
    for origin in origins:
        if origin == "*":
            logger.warning("Wildcard CORS origin '*' is insecure with credentials; skipping")
            continue
        if origin.startswith("http://") or origin.startswith("https://"):
            validated.append(origin)
        else:
            logger.warning("Skipping invalid CORS origin (must start with http/https): %s", origin)
    return validated or _DEFAULT_CORS_ORIGINS


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

_RATE_LIMIT_ENABLED = config.RATE_LIMIT_ENABLED

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    def _rate_limit_key(request: Request) -> str:
        """Use user UID when auth is enabled, otherwise fall back to IP."""
        from akili.api.auth import is_auth_required
        if is_auth_required():
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer ") and len(auth_header) > 7:
                try:
                    from akili.api.auth import verify_firebase_token
                    claims = verify_firebase_token(auth_header[7:])
                    uid = claims.get("uid")
                    if uid:
                        return uid
                except Exception:
                    pass
        return get_remote_address(request)

    limiter = Limiter(
        key_func=_rate_limit_key,
        default_limits=["60/minute"],
        enabled=_RATE_LIMIT_ENABLED,
    )
except ImportError:

    class _NoOpLimiter:
        """Stub when slowapi is not installed."""
        def limit(self, *args: Any, **kwargs: Any) -> Any:
            def decorator(fn: Any) -> Any:
                return fn
            return decorator

    limiter = _NoOpLimiter()  # type: ignore[assignment]
    if _RATE_LIMIT_ENABLED:
        logger.warning(
            "slowapi not installed — rate limiting disabled. "
            "Install with: pip install slowapi"
        )

# ---------------------------------------------------------------------------
# App creation
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Akili",
    description=(
        "The Reasoning Control Plane for Mission-Critical Engineering — "
        "deterministic verification for technical documentation"
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=_ALLOWED_CORS_METHODS,
    allow_headers=_ALLOWED_CORS_HEADERS,
)

# Mount rate limiter if available
if hasattr(limiter, "init_app"):
    app.state.limiter = limiter
    try:
        from slowapi.errors import RateLimitExceeded
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    except ImportError:
        pass

# ---------------------------------------------------------------------------
# Include routers
# ---------------------------------------------------------------------------

from akili.api.routers.documents import router as documents_router
from akili.api.routers.ingest import router as ingest_router
from akili.api.routers.query import router as query_router
from akili.api.routers.corrections import router as corrections_router
from akili.api.routers.compare import router as compare_router

app.include_router(documents_router)
app.include_router(ingest_router)
app.include_router(query_router)
app.include_router(corrections_router)
app.include_router(compare_router)

# ---------------------------------------------------------------------------
# Top-level endpoints (health, status, startup)
# ---------------------------------------------------------------------------


@app.on_event("startup")
def _log_env() -> None:
    key = os.environ.get("GOOGLE_API_KEY")
    if key and key.strip():
        logger.info("GOOGLE_API_KEY is set (ingest will call Gemini)")
    else:
        logger.warning(
            "GOOGLE_API_KEY is missing or empty — ingest will return 500 until set in .env"
        )
    from akili.api.auth import is_auth_required, _is_production_environment
    if not is_auth_required():
        if _is_production_environment():
            logger.error(
                "SECURITY: Authentication is DISABLED in a production environment "
                "(DATABASE_URL is set). All endpoints are public. "
                "Set AKILI_REQUIRE_AUTH=1 and FIREBASE_PROJECT_ID immediately."
            )
        else:
            logger.warning(
                "Authentication is DISABLED — all endpoints are public. "
                "Set AKILI_REQUIRE_AUTH=1 and FIREBASE_PROJECT_ID to enable auth in production."
            )


@app.get("/status")
def status() -> JSONResponse:
    """Check API and env without running ingest."""
    key = os.environ.get("GOOGLE_API_KEY")
    key_set = bool(key and key.strip())
    db_url = os.environ.get("DATABASE_URL", "")
    using_pg = db_url.startswith("postgresql")
    db_path = config.DB_PATH
    db_exists = Path(db_path).parent.exists() if db_path and not using_pg else False
    return JSONResponse(
        content={
            "ok": True,
            "GOOGLE_API_KEY_set": key_set,
            "message": (
                "GOOGLE_API_KEY is set; ingest can call Gemini."
                if key_set
                else "GOOGLE_API_KEY is missing or empty. Set it in .env and ensure the API container uses env_file: .env"
            ),
            "database": "postgresql" if using_pg else "sqlite",
            "AKILI_DB_PATH": db_path if not using_pg else None,
            "db_dir_exists": db_exists if not using_pg else None,
        }
    )


@app.get("/health")
async def health() -> dict:
    """Health check."""
    return {"status": "ok"}
