from __future__ import annotations

import hashlib
import os
import re
import time
from collections.abc import Callable

import httpx
import structlog

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5-5"
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504, 529})

# Provider-supplied tokens (error codes, model names) are kept only if they look like this.
SAFE_TOKEN = re.compile(r"[A-Za-z0-9_.:/-]{1,60}")

log = structlog.get_logger(__name__)


class LLMError(Exception):
    """Any failure to get text from the model.

    The message holds a short reason, a status code and a sanitised provider code: never the
    prompt, the response body, the provider's message text or the API key.
    """

    def __init__(
        self, message: str, *, status: int | None = None, code: str | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


def error_code(resp: httpx.Response | None) -> str | None:
    """A short machine code from an error body, or None. Never returns message text."""
    if resp is None:
        return None
    try:
        err = resp.json()["error"]
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    candidates: list[object] = []
    if isinstance(err, dict):
        candidates = [err.get("type"), err.get("code")]
        meta = err.get("metadata")
        if isinstance(meta, dict):
            candidates.append(meta.get("provider_error_code"))
    for c in candidates:
        if isinstance(c, (str, int)) and not isinstance(c, bool):
            s = str(c)
            if SAFE_TOKEN.fullmatch(s):
                return s
    return None


def retry_delay(attempt: int, resp: httpx.Response | None) -> float:
    """Seconds to wait before the next try. Honours Retry-After, capped at 30s."""
    if resp is not None:
        raw = resp.headers.get("retry-after")
        if raw:
            try:
                return min(max(float(raw), 0.0), 30.0)
            except ValueError:
                pass
        if resp.status_code == 429:
            return min(5.0 * 2.0 ** attempt, 30.0)
    return min(2.0 ** attempt, 8.0)


def describe(prefix: str, status: int | str, code: str | None) -> str:
    return f"{prefix} (status {status}" + (f", {code}" if code else "") + ")"


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
            ok = resp is not None and resp.status_code == 200
            code = None if ok else error_code(resp)
            log.info(
                "llm_call", model=self._model, attempt=attempt + 1,
                prompt_chars=len(prompt), prompt_sha=digest, status=status, code=code,
            )
            if resp is not None and resp.status_code == 200:
                return self._text(resp)
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
    def _text(resp: httpx.Response) -> str:
        try:
            blocks = resp.json()["content"]
            text = "".join(b["text"] for b in blocks if b.get("type") == "text")
        except (ValueError, KeyError, TypeError, AttributeError):
            raise LLMError("malformed response body") from None
        if not text:
            raise LLMError("response contained no text")
        return text