from __future__ import annotations

import httpx
import pytest
import respx
from structlog.testing import capture_logs

from pulseops.ai.llm_client.client import LLMError
from pulseops.ai.llm_client.chain import FallbackModel, make_chain, model_from_env
from pulseops.ai.llm_client.openai_compat import PROVIDERS, OpenAICompatModel

KEY = "test-key-0123456789abcdef"
OK = {"choices": [{"message": {"content": "[]"}}]}
G = PROVIDERS["groq"]
O = PROVIDERS["openrouter"]


def m(p) -> OpenAICompatModel:
    return OpenAICompatModel(p, KEY, max_retries=0, sleep=lambda s: None)


@respx.mock
def test_first_success_skips_the_rest():
    a = respx.post(G.url).mock(return_value=httpx.Response(200, json=OK))
    b = respx.post(O.url).mock(return_value=httpx.Response(200, json=OK))
    assert FallbackModel([m(G), m(O)]).complete("hi") == "[]"
    assert a.call_count == 1
    assert b.call_count == 0


@respx.mock
def test_falls_through_on_failure():
    a = respx.post(G.url).mock(return_value=httpx.Response(404))
    b = respx.post(O.url).mock(return_value=httpx.Response(200, json=OK))
    assert FallbackModel([m(G), m(O)]).complete("hi") == "[]"
    assert a.call_count == 1
    assert b.call_count == 1


@respx.mock
def test_all_failing_raises_without_leaking():
    secret = "SECRET-PROMPT-TEXT-9921"
    respx.post(G.url).mock(return_value=httpx.Response(500, text=secret))
    respx.post(O.url).mock(return_value=httpx.Response(500, text=secret))
    with capture_logs() as logs:
        with pytest.raises(LLMError) as exc:
            FallbackModel([m(G), m(O)]).complete(secret)
    blob = str(exc.value) + repr(logs)
    assert secret not in blob
    assert KEY not in blob


def test_empty_chain_is_rejected():
    with pytest.raises(ValueError):
        FallbackModel([])


def test_make_chain_parses_provider_and_model(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", KEY)
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    monkeypatch.setenv("PULSEOPS_MODEL", "must-be-ignored")
    chain = make_chain("groq:openai/gpt-oss-120b, openrouter:vendor/x:free, groq")
    assert [(x.provider_name, x.model_name) for x in chain.models] == [
        ("groq", "openai/gpt-oss-120b"),
        ("openrouter", "vendor/x:free"),
        ("groq", G.default_model),
    ]


def test_make_chain_skips_unconfigured_providers(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", KEY)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    chain = make_chain("openrouter,groq")
    assert [x.provider_name for x in chain.models] == ["groq"]


def test_make_chain_with_nothing_configured_raises(monkeypatch):
    for env in ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    with pytest.raises(LLMError):
        make_chain("groq,openrouter")


def test_model_from_env_prefers_the_chain(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", KEY)
    monkeypatch.setenv("PULSEOPS_CHAIN", "groq")
    assert isinstance(model_from_env(), FallbackModel)


def test_model_from_env_defaults_to_a_single_model(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", KEY)
    monkeypatch.delenv("PULSEOPS_CHAIN", raising=False)
    monkeypatch.setenv("PULSEOPS_PROVIDER", "groq")
    assert isinstance(model_from_env(), OpenAICompatModel)