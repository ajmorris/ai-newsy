import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests
from google import genai
from openai import OpenAI


ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_PROVIDER_CHAIN = "anthropic,gemini,openai"
DEFAULT_MODELS = {
    "anthropic": "claude-opus-4-6",
    "gemini": "gemini-2.0-flash",
    "openai": "gpt-4o-mini",
}
PROVIDER_MODEL_ENV_KEYS = {
    "anthropic": "ANTHROPIC_MODEL",
    "gemini": "GEMINI_MODEL",
    "openai": "OPENAI_MODEL",
}


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


def _model_looks_compatible(provider: str, model: str) -> bool:
    normalized = (model or "").strip().lower()
    if not normalized:
        return False
    if provider == "anthropic":
        return normalized.startswith("claude")
    if provider == "gemini":
        return normalized.startswith("gemini")
    if provider == "openai":
        return normalized.startswith(("gpt", "o1", "o3", "o4"))
    return False


def _error_category(error: Exception) -> str:
    message = str(error).lower()
    if any(token in message for token in ["401", "403", "unauthorized", "forbidden", "invalid api key"]):
        return "auth"
    if any(token in message for token in ["429", "rate limit", "too many requests", "resource_exhausted"]):
        return "rate-limit"
    if any(token in message for token in ["timeout", "timed out", "connection reset", "service unavailable", "503", "502", "500"]):
        return "transient"
    return "provider-error"


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def generate(self, prompt: str, model: str, temperature: float) -> str:
        """Generate text for the given prompt."""


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def generate(self, prompt: str, model: str, temperature: float) -> str:
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


class GeminiProvider(LLMProvider):
    name = "gemini"

    def generate(self, prompt: str, model: str, temperature: float) -> str:
        gemini_key = (os.getenv("GEMINI_API_KEY") or "").strip()
        if not gemini_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        client = genai.Client(api_key=gemini_key)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config={"temperature": temperature},
        )
        return (response.text or "").strip()


class OpenAIProvider(LLMProvider):
    name = "openai"

    def generate(self, prompt: str, model: str, temperature: float) -> str:
        openai_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        if not openai_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        client = OpenAI(api_key=openai_key)
        response = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return (response.choices[0].message.content or "").strip()


@dataclass
class AttemptFailure:
    provider: str
    model: str
    category: str
    error: str


def _provider_chain_from_env() -> List[str]:
    raw_chain = os.getenv("LLM_PROVIDER_CHAIN", DEFAULT_PROVIDER_CHAIN)
    providers = [entry.strip().lower() for entry in raw_chain.split(",") if entry.strip()]
    if not providers:
        return [entry.strip() for entry in DEFAULT_PROVIDER_CHAIN.split(",")]
    return providers


def _provider_default_model(provider: str) -> str:
    env_key = PROVIDER_MODEL_ENV_KEYS.get(provider, "")
    model_from_env = (os.getenv(env_key) or "").strip() if env_key else ""
    if model_from_env:
        return model_from_env
    return DEFAULT_MODELS[provider]


def _resolve_model_for_provider(
    provider: str,
    logical_model: str,
    anthropic_model_override: Optional[str],
    openai_model_override: Optional[str],
) -> str:
    if provider == "anthropic" and anthropic_model_override:
        return anthropic_model_override
    if provider == "openai" and openai_model_override:
        return openai_model_override
    if _model_looks_compatible(provider=provider, model=logical_model):
        return logical_model
    return _provider_default_model(provider)


def generate_text_with_fallback(
    prompt: str,
    gemini_model: str = "gemini-2.0-flash",
    anthropic_model: Optional[str] = None,
    temperature: float = 0.2,
    openai_model: Optional[str] = None,
) -> str:
    """
    Generate text with provider chain fallback.
    Default chain: Anthropic -> Gemini -> OpenAI.
    """
    provider_registry: Dict[str, LLMProvider] = {
        "anthropic": AnthropicProvider(),
        "gemini": GeminiProvider(),
        "openai": OpenAIProvider(),
    }
    failures: List[AttemptFailure] = []

    for provider_name in _provider_chain_from_env():
        provider = provider_registry.get(provider_name)
        if provider is None:
            failures.append(
                AttemptFailure(
                    provider=provider_name,
                    model="n/a",
                    category="config",
                    error="Unknown provider in LLM_PROVIDER_CHAIN",
                )
            )
            continue

        chosen_model = _resolve_model_for_provider(
            provider=provider_name,
            logical_model=gemini_model,
            anthropic_model_override=anthropic_model,
            openai_model_override=openai_model,
        )
        try:
            text = provider.generate(prompt=prompt, model=chosen_model, temperature=temperature).strip()
            print(f"    LLM provider selected: {provider_name} (model={chosen_model})")
            return text
        except Exception as error:
            category = _error_category(error)
            print(
                f"    LLM provider failed: {provider_name} "
                f"(model={chosen_model}, category={category}); trying next provider..."
            )
            failures.append(
                AttemptFailure(
                    provider=provider_name,
                    model=chosen_model,
                    category=category,
                    error=str(error),
                )
            )

    details = "; ".join(
        [
            f"{item.provider}[model={item.model}, category={item.category}] failed ({item.error})"
            for item in failures
        ]
    )
    raise RuntimeError(f"All configured LLM providers failed: {details}")
