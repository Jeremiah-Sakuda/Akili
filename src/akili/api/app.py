"""
FastAPI app factory: creates app, mounts routers, configures CORS/middleware.
"""

from __future__ import annotations

import json as _json_mod
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from akili import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structured logging (Phase 3: Observability)
# ---------------------------------------------------------------------------


class _JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON for structured log pipelines."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exc"] = self.formatException(record.exc_info)
        return _json_mod.dumps(log_entry, default=str)


def _configure_logging() -> None:
    """Configure root logger based on AKILI_LOG_FORMAT."""
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        if config.LOG_FORMAT == "json":
            handler.setFormatter(_JSONFormatter())
        else:
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
            )
        root.addHandler(handler)
        root.setLevel(logging.INFO)


_configure_logging()


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

_ALLOWED_CORS_METHODS = ["GET", "POST", "DELETE", "OPTIONS"]
_ALLOWED_CORS_HEADERS = [
    "Authorization",
    "Content-Type",
    "Accept",
    "Origin",
    "X-Requested-With",
]


def _cors_origins() -> list[str]:
    """Validate CORS origins from centralized config (already parsed in config.py)."""
    validated = []
    for origin in config.CORS_ORIGINS:
        if origin == "*":
            logger.warning("Wildcard CORS origin '*' is insecure with credentials; skipping")
            continue
        if not (origin.startswith("http://") or origin.startswith("https://")):
            logger.warning("Skipping invalid CORS origin (must start with http/https): %s", origin)
            continue
        validated.append(origin)
    return validated or config.CORS_ORIGINS


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

_RATE_LIMIT_ENABLED = config.RATE_LIMIT_ENABLED

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
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
            "slowapi not installed — rate limiting disabled. Install with: pip install slowapi"
        )

# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------


class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""

    _HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self'"
        ),
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        response: Response = await call_next(request)
        for header, value in self._HEADERS.items():
            response.headers[header] = value
        return response


# ---------------------------------------------------------------------------
# Lifespan (replaces deprecated @app.on_event("startup"))
# ---------------------------------------------------------------------------


class AuthDisabledInProductionError(Exception):
    """Raised when auth is disabled in a production environment without explicit override."""

    pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle for the FastAPI app."""
    # -- startup --
    key = config.GOOGLE_API_KEY
    if key and key.strip():
        logger.info("GOOGLE_API_KEY is set (ingest will call Gemini)")
    else:
        logger.warning(
            "GOOGLE_API_KEY is missing or empty — ingest will return 500 until set in .env"
        )
    from akili.api.auth import is_auth_required, _is_production_environment

    if not is_auth_required():
        if _is_production_environment():
            # A7: Fail-closed auth in production-like environments
            if not config.ALLOW_OPEN_PROD:
                raise AuthDisabledInProductionError(
                    "SECURITY FAILURE: Authentication is DISABLED in a production environment "
                    "(DATABASE_URL is set). This deployment is fully open to the internet. "
                    "Either (1) set AKILI_REQUIRE_AUTH=1 and FIREBASE_PROJECT_ID to enable auth, "
                    "or (2) set AKILI_ALLOW_OPEN_PROD=1 to explicitly allow open access."
                )
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
    yield
    # -- shutdown -- (nothing to clean up currently)


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
    lifespan=lifespan,
)

# Warn if using a preview model
if "preview" in config.GEMINI_MODEL.lower():
    logger.warning(
        "Running with preview Gemini model '%s'. Pin to a stable release "
        "for production (set AKILI_GEMINI_MODEL).",
        config.GEMINI_MODEL,
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=_ALLOWED_CORS_METHODS,
    allow_headers=_ALLOWED_CORS_HEADERS,
)

app.add_middleware(_SecurityHeadersMiddleware)

# Mount rate limiter if available
if hasattr(limiter, "init_app"):
    app.state.limiter = limiter
    try:
        from slowapi.middleware import SlowAPIMiddleware
        from slowapi.errors import RateLimitExceeded as RLE

        app.add_middleware(SlowAPIMiddleware)
        app.add_exception_handler(
            RLE,
            _rate_limit_exceeded_handler,  # type: ignore[arg-type]
        )
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
from akili.api.routers.library import router as library_router
from akili.api.routers.share import router as share_router

app.include_router(documents_router)
app.include_router(ingest_router)
app.include_router(query_router)
app.include_router(corrections_router)
app.include_router(compare_router)
app.include_router(library_router)
app.include_router(share_router)

# ---------------------------------------------------------------------------
# Top-level endpoints (health, status, startup)
# ---------------------------------------------------------------------------


@app.get("/status")
def status() -> JSONResponse:
    """Check API and env without running ingest."""
    key = config.GOOGLE_API_KEY
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
                else "GOOGLE_API_KEY is missing or empty. Set it in .env "
                "and ensure the API container uses env_file: .env"
            ),
            "database": "postgresql" if using_pg else "sqlite",
            "AKILI_DB_PATH": db_path if not using_pg else None,
            "db_dir_exists": db_exists if not using_pg else None,
        }
    )


@app.get("/health")
async def health() -> dict:
    """Health check. Includes auth_required flag for deploy verification (A7)."""
    from akili.api.auth import is_auth_required

    return {"status": "ok", "auth_required": is_auth_required()}
