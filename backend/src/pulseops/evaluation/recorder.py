from __future__ import annotations

from collections import Counter
from typing import Protocol

from pulseops.ai.llm_client.client import LLMError


class _Completer(Protocol):
    def complete(self, prompt: str) -> str: ...


class Recorder:
    """Wraps a model. Keeps raw replies, failures by status/code, and which model answered."""

    def __init__(self, inner: _Completer) -> None:
        self._inner = inner
        self.replies: list[str] = []
        self.failures: list[tuple[int | None, str | None]] = []
        self.answered: list[str] = []

    def complete(self, prompt: str) -> str:
        try:
            reply = self._inner.complete(prompt)
        except LLMError as e:
            self.failures.append((e.status, e.code))
            raise
        self.replies.append(reply)
        name = getattr(self._inner, "answered_by", None) or getattr(
            self._inner, "answered_label", None
        )
        if isinstance(name, str):
            self.answered.append(name)
        return reply

    def failure_counts(self) -> dict[str, int]:
        keys = [
            f"{status if status is not None else 'none'}" + (f"/{code}" if code else "")
            for status, code in self.failures
        ]
        return dict(Counter(keys))

    def answered_counts(self) -> dict[str, int]:
        return dict(Counter(self.answered))