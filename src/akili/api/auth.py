"""
Optional Firebase ID token verification for API routes.

When AKILI_REQUIRE_AUTH=1 and FIREBASE_PROJECT_ID is set, protected routes
require Authorization: Bearer <id_token> and verify the token with Firebase Admin.
/health and /status remain public.
"""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_http_bearer = HTTPBearer(auto_error=False)


def _init_firebase() -> bool:
    """Initialize Firebase Admin if auth is required and project is set. Returns True if active."""
    if os.environ.get("AKILI_REQUIRE_AUTH", "").strip() not in ("1", "true", "yes"):
        return False
    project_id = os.environ.get("FIREBASE_PROJECT_ID") or os.environ.get("VITE_FIREBASE_PROJECT_ID")
    if not project_id or not project_id.strip():
        return False
    try:
        import firebase_admin
        from firebase_admin import credentials
    except ImportError:
        return False
    try:
        try:
            firebase_admin.get_app()
        except ValueError:
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred, options={"projectId": project_id.strip()})
        return True
    except Exception:
        return False


_auth_active: bool | None = None


def is_auth_required() -> bool:
    """Return True if API auth is required (Firebase ID token)."""
    global _auth_active
    if _auth_active is None:
        _auth_active = _init_firebase()
    return _auth_active


def verify_firebase_token(token: str) -> dict:
    """Verify Firebase ID token and return decoded claims. Raises HTTPException on failure."""
    try:
        from firebase_admin import auth as fb_auth
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth not available (firebase-admin not installed)",
        )
    try:
        return fb_auth.verify_id_token(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from e


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_http_bearer)],
) -> dict | None:
    """
    Dependency: when auth is required, verify Bearer token and return claims; otherwise return None.
    Raises 401 if auth is required and token is missing or invalid.
    """
    if not is_auth_required():
        return None
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_firebase_token(credentials.credentials)
