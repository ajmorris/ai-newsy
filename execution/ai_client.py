import os
from typing import Optional

import requests
from google import genai


ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_ANTHROPIC_MODEL = "claude-3-5-haiku-latest"


def _response_preview(response: requests.Response, max_len: int = 500) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = response.text or ""
    text = str(payload).strip()
    if len(text) <= max_len:
        return text
    return f"{text[:max_len]}..."


def _is_rate_limit_error(error: Exception) -> bool:
    message = str(error).lower()
    return (
        "429" in message
        or "resource_exhausted" in message
        or "rate limit" in message
        or "too many requests" in message
    )


def _extract_anthropic_text(payload: dict) -> str:
    blocks = payload.get("content", [])
    parts = []
    for block in blocks:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts).strip()


def _generate_with_anthropic(prompt: str, model: str, temperature: float = 0.2) -> str:
    anthropic_key = (os.getenv("ANTHROPIC_KEY") or "").strip()
    if not anthropic_key:
        raise RuntimeError("ANTHROPIC_KEY is not configured")

    response = requests.post(
        ANTHROPIC_API_URL,
        headers={
            "x-api-key": anthropic_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 1024,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=45,
    )
    if not response.ok:
        detail = _response_preview(response)
        raise RuntimeError(
            "Anthropic request failed "
            f"(status={response.status_code}, model={model}, url={ANTHROPIC_API_URL}, response={detail})"
        )
    return _extract_anthropic_text(response.json())


def generate_text_with_fallback(
    prompt: str,
    gemini_model: str = "gemini-2.0-flash",
    anthropic_model: Optional[str] = None,
    temperature: float = 0.2,
) -> str:
    """
    Generate text with Gemini first, then fallback to Anthropic on failure.
    """
    chosen_anthropic_model = anthropic_model or os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
    gemini_key = (os.getenv("GEMINI_API_KEY") or "").strip()

    try:
        if not gemini_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        client = genai.Client(api_key=gemini_key)
        response = client.models.generate_content(
            model=gemini_model,
            contents=prompt,
        )
        return (response.text or "").strip()
    except Exception as gemini_error:
        fallback_reason = "429/rate-limit" if _is_rate_limit_error(gemini_error) else "Gemini failure"
        print(f"    Gemini {fallback_reason}; trying Anthropic fallback...")
        try:
            return _generate_with_anthropic(
                prompt=prompt,
                model=chosen_anthropic_model,
                temperature=temperature,
            )
        except Exception as anthropic_error:
            raise RuntimeError(
                f"Gemini failed ({gemini_error}); Anthropic fallback failed ({anthropic_error})"
            ) from anthropic_error
