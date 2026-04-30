"""
Shared fixtures for integration tests.

These tests require a live GOOGLE_API_KEY and are excluded from CI by default.
Run with: pytest tests/integration/ -m integration
"""

import os

import pytest

INTEGRATION_REASON = "GOOGLE_API_KEY not set — skipping live Gemini tests"


def has_api_key() -> bool:
    key = os.environ.get("GOOGLE_API_KEY", "").strip()
    return bool(key)


skip_without_key = pytest.mark.skipif(
    not has_api_key(), reason=INTEGRATION_REASON
)
