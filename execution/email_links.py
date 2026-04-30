"""Helpers for building subscriber email action links."""

from __future__ import annotations

import os
from urllib.parse import quote


DEFAULT_APP_URL = "https://your-app.vercel.app"


def get_app_url() -> str:
    """Return normalized APP_URL without trailing slash."""
    raw_value = (os.getenv("APP_URL") or "").strip()
    if not raw_value:
        return DEFAULT_APP_URL
    return raw_value.rstrip("/")


def build_confirm_url(token: str) -> str:
    """Build a confirmation URL for a subscriber token."""
    safe_token = quote(str(token or ""), safe="")
    return f"{get_app_url()}/api/confirm?token={safe_token}"


def build_unsubscribe_url(token: str) -> str:
    """Build an unsubscribe URL for a subscriber token."""
    safe_token = quote(str(token or ""), safe="")
    return f"{get_app_url()}/api/unsubscribe?token={safe_token}"
