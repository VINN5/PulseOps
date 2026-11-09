from __future__ import annotations

import pytest

from pulseops.ai.llm_client.chain import FallbackModel
from pulseops.ai.llm_client.client import LLMError


class Down:
    def __init__(self, error: LLMError) -> None:
        self.provider_name = "p"
        self.model_name = "down"
        self._error = error

    def complete(self, prompt: str) -> str:
        raise self._error


class Up:
    def __init__(self, name: str, answered_by: str | None = None) -> None:
        self.provider_name = "p"
        self.model_name = name
        self.answered_by = answered_by

    def complete(self, prompt: str) -> str:
        return "[]"


class Once:
    """Succeeds on the first call, then fails."""

    def __init__(self, answered_by: str | None = None) -> None:
        self.provider_name = "p"
        self.model_name = "once"
        self.answered_by = answered_by
        self._calls = 0

    def complete(self, prompt: str) -> str:
        self._calls += 1
        if self._calls > 1:
            raise LLMError("later failure", status=500)
        return "[]"


def test_all_failed_error_carries_the_last_status_and_code():
    chain = FallbackModel([
        Down(LLMError("a", status=403)),
        Down(LLMError("b", status=429, code="rate_limited")),
    ])
    with pytest.raises(LLMError) as exc:
        chain.complete("hi")
    assert exc.value.status == 429
    assert exc.value.code == "rate_limited"
    assert "429" in str(exc.value)


def test_chain_error_does_not_include_inner_message_text():
    chain = FallbackModel([Down(LLMError("SECRET-TEXT-1", status=500))])
    with pytest.raises(LLMError) as exc:
        chain.complete("hi")
    assert "SECRET-TEXT-1" not in str(exc.value)


def test_success_records_the_answering_link():
    chain = FallbackModel([
        Down(LLMError("a", status=500)),
        Up("second", answered_by="vendor/real:free"),
    ])
    assert chain.complete("hi") == "[]"
    assert chain.answered_label == "p/second"
    assert chain.answered_by == "vendor/real:free"


def test_answer_state_is_reset_by_a_later_failure():
    chain = FallbackModel([Once(answered_by="vendor/real:free")])
    chain.complete("hi")
    assert chain.answered_by == "vendor/real:free"
    with pytest.raises(LLMError):
        chain.complete("hi")
    assert chain.answered_by is None
    assert chain.answered_label is None