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
    SAFE_TOKEN,
    AnthropicModel,
    LLMError,
    describe,
    error_code,
    retry_delay,
)

log = structlog.get_logger(__name__)

# Reasoning models spend output tokens on thinking before they write the answer. At 1500 one
# did not finish thinking and returned no text (decision 0017).
DEFAULT_MAX_TOKENS = 4000


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


def safe_token(value: object) -> str | None:
    """A provider-supplied short token (model name, finish reason), or None if it looks odd."""
    return value if isinstance(value, str) and SAFE_TOKEN.fullmatch(value) else None


def answered_model(resp: httpx.Response) -> str | None:
    """The model name the provider says answered, if it looks safe to record."""
    try:
        m = resp.json().get("model")
    except (ValueError, AttributeError):
        return None
    return safe_token(m)


def resolve_max_tokens() -> int:
    """PULSEOPS_MAX_TOKENS if set, else DEFAULT_MAX_TOKENS."""
    raw = os.environ.get("PULSEOPS_MAX_TOKENS", "").strip()
    if not raw:
        return DEFAULT_MAX_TOKENS
    try:
        value = int(raw)
    except ValueError:
        raise LLMError("PULSEOPS_MAX_TOKENS must be a positive integer") from None
    if value < 1:
        raise LLMError("PULSEOPS_MAX_TOKENS must be a positive integer")
    return value


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
        self.answered_by: str | None = None
        self.finish_reason: str | None = None
        self.max_tokens = max_tokens
        self._timeout = timeout
        self._max_retries = max_retries
        self._sleep = sleep

    def complete(self, prompt: str) -> str:
        self.answered_by = None
        self.finish_reason = None
        body = {
            "model": self.model_name,
            "max_tokens": self.max_tokens,
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
            ok = resp is not None and resp.status_code == 200
            code = None if ok else error_code(resp)
            log.info(
                "llm_call", provider=self.provider_name, model=self.model_name,
                attempt=attempt + 1, prompt_chars=len(prompt), prompt_sha=digest,
                status=status, code=code,
            )
            if resp is not None and resp.status_code == 200:
                text, finish = self._parse(resp)
                self.answered_by = answered_model(resp)
                self.finish_reason = finish
                log.info(
                    "llm_answer", provider=self.provider_name,
                    requested=self.model_name, answered=self.answered_by,
                    finish_reason=finish,
                )
                return text
            http_status = resp.status_code if resp is not None else None
            retryable = resp is None or resp.status_code in RETRYABLE_STATUS
            if not retryable:
                raise LLMError(
                    describe("request rejected", status, code), status=http_status, code=code
                ) from None
            if attempt == self._max_retries:
                raise LLMError(
                    describe(f"gave up after {attempt + 1} attempts", status, code),
                    status=http_status, code=code,
                ) from None
            self._sleep(retry_delay(attempt, resp))
        raise LLMError("unreachable")  # pragma: no cover

    @staticmethod
    def _parse(resp: httpx.Response) -> tuple[str, str | None]:
        try:
            choice = resp.json()["choices"][0]
            content = choice["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise LLMError("malformed response body") from None
        finish = safe_token(choice.get("finish_reason"))
        if not isinstance(content, str) or not content.strip():
            raise LLMError(
                describe("response contained no text", 200, finish), status=200, code=finish
            )
        return content, finish


def make_model(
    provider: str | None = None,
    model: str | None = None,
    **kwargs,
) -> OpenAICompatModel | AnthropicModel:
    """Pick a provider by argument, else PULSEOPS_PROVIDER, else groq.

    The model name comes from the argument, else PULSEOPS_MODEL, else the provider default.
    max_tokens comes from the caller, else PULSEOPS_MAX_TOKENS, else DEFAULT_MAX_TOKENS.
    """
    name = provider or os.environ.get("PULSEOPS_PROVIDER") or "groq"
    chosen = model or os.environ.get("PULSEOPS_MODEL") or None
    kwargs.setdefault("max_tokens", resolve_max_tokens())
    if name == "anthropic":
        return AnthropicModel(model=chosen or DEFAULT_MODEL, **kwargs)
    spec = PROVIDERS.get(name)
    if spec is None:
        known = ", ".join(["anthropic", *sorted(PROVIDERS)])
        raise LLMError(f"unknown provider (choose one of: {known})")
    return OpenAICompatModel(spec, model=chosen, **kwargs)