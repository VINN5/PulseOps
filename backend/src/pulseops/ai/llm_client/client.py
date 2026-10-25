from __future__ import annotations

import hashlib
import os
import time
from collections.abc import Callable

import httpx
import structlog

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5-5"
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504, 529})

log = structlog.get_logger(__name__)


class LLMError(Exception):
    """Any failure to get text from the model.

    Messages contain a short reason and a status code only: never the prompt,
    the response body or the API key.
    """


class AnthropicModel:
    """Implements the orchestrator's Model protocol over the Messages API."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 1500,
        timeout: float = 30.0,
        max_retries: int = 2,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise LLMError("ANTHROPIC_API_KEY is not set")
        self._key = key
        self._model = model
        self._max_tokens = max_tokens
        self._timeout = timeout
        self._max_retries = max_retries
        self._sleep = sleep

    def complete(self, prompt: str) -> str:
        body = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "x-api-key": self._key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        }
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
        for attempt in range(self._max_retries + 1):
            try:
                resp = httpx.post(API_URL, headers=headers, json=body, timeout=self._timeout)
                status: int | str = resp.status_code
            except httpx.TransportError as e:
                resp = None
                status = type(e).__name__
            log.info(
                "llm_call", model=self._model, attempt=attempt + 1,
                prompt_chars=len(prompt), prompt_sha=digest, status=status,
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
            blocks = resp.json()["content"]
            text = "".join(b["text"] for b in blocks if b.get("type") == "text")
        except (ValueError, KeyError, TypeError, AttributeError):
            raise LLMError("malformed response body") from None
        if not text:
            raise LLMError("response contained no text")
        return text