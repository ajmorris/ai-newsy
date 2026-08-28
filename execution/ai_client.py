import os
from typing import Optional

import requests


ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-opus-5"
ALLOWED_EFFORTS = ("low", "medium", "high")
DEFAULT_EFFORT = "low"
JSON_COMPLETION_MAX_TOKENS = 8192
TEXT_COMPLETION_MAX_TOKENS = 4096
REQUEST_TIMEOUT_SECONDS = 120


def _response_preview(response: requests.Response, max_len: int = 500) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = response.text or ""
    text = str(payload).strip()
    if len(text) <= max_len:
        return text
    return f"{text[:max_len]}..."


def _extract_anthropic_text(payload: dict) -> str:
    blocks = payload.get("content", [])
    parts = []
    for block in blocks:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts).strip()


def resolve_model(model: Optional[str] = None) -> str:
    chosen = (model or os.getenv("ANTHROPIC_MODEL") or DEFAULT_MODEL).strip()
    return chosen or DEFAULT_MODEL


def resolve_effort() -> str:
    raw = (os.getenv("ANTHROPIC_EFFORT") or DEFAULT_EFFORT).strip().lower()
    if raw not in ALLOWED_EFFORTS:
        allowed = ", ".join(ALLOWED_EFFORTS)
        raise RuntimeError(f"ANTHROPIC_EFFORT must be one of: {allowed}")
    return raw


def generate_text(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.2,
    json_mode: bool = False,
) -> str:
    """
    Generate text with Claude Opus 5 via the Anthropic Messages API.

    Thinking is on by default for Opus 5; max_tokens covers thinking plus
    visible text. Effort defaults to low for short structured digest tasks.
    Temperature is omitted so it does not conflict with default thinking.
    """
    del temperature  # unused: Opus 5 thinking rejects custom temperature
    anthropic_key = (os.getenv("ANTHROPIC_KEY") or "").strip()
    if not anthropic_key:
        raise RuntimeError("ANTHROPIC_KEY is not configured")

    chosen_model = resolve_model(model)
    effort = resolve_effort()
    max_tokens = JSON_COMPLETION_MAX_TOKENS if json_mode else TEXT_COMPLETION_MAX_TOKENS

    response = requests.post(
        ANTHROPIC_API_URL,
        headers={
            "x-api-key": anthropic_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": chosen_model,
            "max_tokens": max_tokens,
            "output_config": {"effort": effort},
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if not response.ok:
        detail = _response_preview(response)
        raise RuntimeError(
            "Anthropic request failed "
            f"(status={response.status_code}, model={chosen_model}, "
            f"url={ANTHROPIC_API_URL}, response={detail})"
        )
    text = _extract_anthropic_text(response.json())
    print(f"    LLM provider selected: anthropic (model={chosen_model}, effort={effort})")
    return text


def generate_text_with_fallback(*args, **kwargs) -> str:
    """Backward-compatible alias. Prefer generate_text()."""
    if "gemini_model" in kwargs and "model" not in kwargs:
        kwargs["model"] = kwargs.pop("gemini_model")
    kwargs.pop("anthropic_model", None)
    kwargs.pop("openai_model", None)
    return generate_text(*args, **kwargs)
