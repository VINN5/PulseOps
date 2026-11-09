from __future__ import annotations

import pytest

from pulseops.ai.llm_client.client import LLMError
from pulseops.evaluation.recorder import Recorder


class Ok:
    def __init__(self, **attrs) -> None:
        self.__dict__.update(attrs)

    def complete(self, prompt: str) -> str:
        return "[]"


class Boom:
    def __init__(self, status: int | None, code: str | None = None) -> None:
        self.status = status
        self.code = code

    def complete(self, prompt: str) -> str:
        raise LLMError("x", status=self.status, code=self.code)


def test_replies_are_kept():
    r = Recorder(Ok())
    assert r.complete("hi") == "[]"
    assert r.replies == ["[]"]


def test_failures_are_recorded_and_reraised():
    r = Recorder(Boom(429, "rate_limited"))
    with pytest.raises(LLMError):
        r.complete("hi")
    assert r.failures == [(429, "rate_limited")]
    assert r.replies == []


def test_failure_counts_are_keyed_by_status_and_code():
    r = Recorder(Ok())
    r.failures = [(429, "rate_limited"), (429, "rate_limited"), (403, None), (None, None)]
    assert r.failure_counts() == {"429/rate_limited": 2, "403": 1, "none": 1}


def test_answering_model_is_recorded():
    r = Recorder(Ok(answered_by="vendor/real:free"))
    r.complete("hi")
    assert r.answered_counts() == {"vendor/real:free": 1}


def test_answered_label_is_used_when_the_provider_reports_nothing():
    r = Recorder(Ok(answered_by=None, answered_label="p/second"))
    r.complete("hi")
    assert r.answered_counts() == {"p/second": 1}