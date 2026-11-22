from __future__ import annotations

import pytest

from pulseops.ai.llm_client.chain import make_chain
from pulseops.ai.llm_client.client import LLMError
from pulseops.ai.llm_client.openai_compat import (
    DEFAULT_TIMEOUT,
    make_model,
    resolve_timeout,
)

KEY = "test-key-0123456789abcdef"


def test_default_timeout_comes_from_the_factory(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", KEY)
    monkeypatch.delenv("PULSEOPS_TIMEOUT", raising=False)
    monkeypatch.delenv("PULSEOPS_MODEL", raising=False)
    assert make_model("groq")._timeout == DEFAULT_TIMEOUT == 120.0


def test_env_overrides_the_timeout(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", KEY)
    monkeypatch.setenv("PULSEOPS_TIMEOUT", "45")
    monkeypatch.delenv("PULSEOPS_MODEL", raising=False)
    assert make_model("groq")._timeout == 45.0


@pytest.mark.parametrize("bad", ["abc", "0", "-3", "nan", "inf"])
def test_bad_timeout_value_is_rejected(monkeypatch, bad):
    monkeypatch.setenv("PULSEOPS_TIMEOUT", bad)
    with pytest.raises(LLMError):
        resolve_timeout()


def test_chain_uses_the_env_timeout(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", KEY)
    monkeypatch.setenv("PULSEOPS_TIMEOUT", "75")
    assert make_chain("groq").models[0]._timeout == 75.0