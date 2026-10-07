"""Shared color tokens for email and the web archive.

`emails/tokens.json` is the only copy of these values. F2 fills in a real
light palette; until then light matches dark so existing pages stay put.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict

TOKENS_PATH = Path(__file__).resolve().parents[1] / "emails" / "tokens.json"


@lru_cache(maxsize=1)
def load_design_tokens() -> Dict[str, Dict[str, str]]:
    payload = json.loads(TOKENS_PATH.read_text(encoding="utf-8"))
    dark = payload.get("dark")
    light = payload.get("light")
    if not isinstance(dark, dict) or not isinstance(light, dict):
        raise ValueError(f"Design tokens at {TOKENS_PATH} need dark and light objects")
    return {"dark": {str(k): str(v) for k, v in dark.items()}, "light": {str(k): str(v) for k, v in light.items()}}


def archive_root_css(theme: str = "dark") -> str:
    """CSS variables for generated issue pages. Names match the archive template."""
    tokens = load_design_tokens()[theme]
    return "\n".join(
        [
            "    :root {",
            f"      --bg: {tokens['bg']};",
            f"      --bg-raised: {tokens['bgRaised']};",
            f"      --card: {tokens['card']};",
            f"      --line: {tokens['border']};",
            f"      --line-soft: {tokens['borderSoft']};",
            f"      --fg: {tokens['text']};",
            f"      --muted: {tokens['textMute']};",
            f"      --dim: {tokens['textDim']};",
            f"      --brand: {tokens['accent']};",
            f"      --brand-ink: {tokens['accentInk']};",
            "    }",
        ]
    )
