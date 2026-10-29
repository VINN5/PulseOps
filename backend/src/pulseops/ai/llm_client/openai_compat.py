from __future__ import annotations

import hashlib
import os
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx
import structlog

from pulseops.ai.llm_client.client import (
    DEFAULT_MODEL,
    RETRYABLE_STATUS,
    AnthropicModel,
    LLMError,
)

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class Provider:
    name: str
    url: str
    key_env: str
    default_model: str


PROVIDERS: dict[str, Provider] = {
    "groq": Provider(
        "groq",
        "https://api.groq.com/openai/v1/chat/completions",
        "GROQ_API_KEY",
        "openai/gpt-oss-120b",
    ),
    "gemini": Provider(
        "gemini",
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "GEMINI_API_KEY",
        "gemini-2.5-flash",
    ),
    "openrouter": Provider(
        "openrouter",
        "https://openrouter.ai/api/v1/chat/completions",
        "OPENROUTER_API_KEY",
        "openrouter/free",
    ),
}


class OpenAICompatModel:
    """Implements the orchestrator's Model protocol for any /chat/completions provider.

    The key is sent only in the Authorization header, never in the URL.
    """

    def __init__(
        self,
        provider: Provider,
        api_key: str | None = None,
        *,
        model: str | None = None,
        max_tokens: int = 1500,
        timeout: float = 30.0,
        max_retries: int = 2,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        key = api_key or os.environ.get(provider.key_env)
        if not key:
            raise LLMError(f"{provider.key_env} is not set")
        self._provider = provider
        self._key = key
        self.provider_name = provider.name
        self.model_name = model or provider.default_model
        self._max_tokens = max_tokens
        self._timeout = timeout
        self._max_retries = max_retries
        self._sleep = sleep

    def complete(self, prompt: str) -> str:
        body = {
            "model": self.model_name,
            "max_tokens": self._max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
        for attempt in range(self._max_retries + 1):
            try:
                resp = httpx.post(
                    self._provider.url, headers=headers, json=body, timeout=self._timeout
                )
                status: int | str = resp.status_code
            except httpx.TransportError as e:
                resp = None
                status = type(e).__name__
            log.info(
                "llm_call", provider=self.provider_name, model=self.model_name,
                attempt=attempt + 1, prompt_chars=len(prompt), prompt_sha=digest,
                status=status,
            )
            if resp is not None and resp.status_code == 200:
                return self._text(resp)
            retryable = resp is None or resp.status_code in RETRYABLE_STATUS
            if not retryable:
                raise LLMError(f"request rejected with status {status}") from None
            if attempt == self._max_retries:
                raise LLMError(f"gave up after {attempt + 1} attempts (last: {status})") from None
            self._sleep(min(2.0 ** attempt, 8.0))
        raise LLMError("unreachable")  # pragma: no cover

    @staticmethod
    def _text(resp: httpx.Response) -> str:
        try:
            content = resp.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise LLMError("malformed response body") from None
        if not isinstance(content, str) or not content.strip():
            raise LLMError("response contained no text")
        return content


def make_model(
    provider: str | None = None,
    model: str | None = None,
    **kwargs,
) -> OpenAICompatModel | AnthropicModel:
    """Pick a provider by argument, else PULSEOPS_PROVIDER, else groq.

    The model name comes from the argument, else PULSEOPS_MODEL, else the provider default.
    """
    name = provider or os.environ.get("PULSEOPS_PROVIDER") or "groq"
    chosen = model or os.environ.get("PULSEOPS_MODEL") or None
    if name == "anthropic":
        return AnthropicModel(model=chosen or DEFAULT_MODEL, **kwargs)
    spec = PROVIDERS.get(name)
    if spec is None:
        known = ", ".join(["anthropic", *sorted(PROVIDERS)])
        raise LLMError(f"unknown provider (choose one of: {known})")
    return OpenAICompatModel(spec, model=chosen, **kwargs)