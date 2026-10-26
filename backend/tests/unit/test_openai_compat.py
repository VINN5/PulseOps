from __future__ import annotations

import json

import httpx
import pytest
import respx
from structlog.testing import capture_logs

from pulseops.ai.llm_client.client import AnthropicModel, LLMError
from pulseops.ai.llm_client.openai_compat import PROVIDERS, OpenAICompatModel, make_model

KEY = "test-key-0123456789abcdef"
OK = {"choices": [{"message": {"role": "assistant", "content": "[]"}}]}
NAMES = sorted(PROVIDERS)


def model(name: str, **kw) -> OpenAICompatModel:
    return OpenAICompatModel(PROVIDERS[name], KEY, sleep=lambda s: None, **kw)


@respx.mock
@pytest.mark.parametrize("name", NAMES)
def test_success_returns_text_and_sends_expected_request(name):
    p = PROVIDERS[name]
    route = respx.post(p.url).mock(return_value=httpx.Response(200, json=OK))
    assert model(name).complete("hi") == "[]"
    req = route.calls.last.request
    assert req.headers["authorization"] == f"Bearer {KEY}"
    assert KEY not in str(req.url)
    body = json.loads(req.content)
    assert body["model"] == p.default_model
    assert body["max_tokens"] == 1500
    assert body["messages"] == [{"role": "user", "content": "hi"}]


@respx.mock
@pytest.mark.parametrize("name", NAMES)
def test_429_then_success_retries(name):
    route = respx.post(PROVIDERS[name].url).mock(
        side_effect=[httpx.Response(429), httpx.Response(200, json=OK)]
    )
    assert model(name).complete("hi") == "[]"
    assert route.call_count == 2


@respx.mock
@pytest.mark.parametrize("name", NAMES)
def test_persistent_500_gives_up_after_bounded_retries(name):
    route = respx.post(PROVIDERS[name].url).mock(return_value=httpx.Response(500))
    with pytest.raises(LLMError):
        model(name, max_retries=2).complete("hi")
    assert route.call_count == 3


@respx.mock
def test_timeout_is_retried_then_raises_llm_error():
    route = respx.post(PROVIDERS["groq"].url).mock(side_effect=httpx.ConnectTimeout("slow"))
    with pytest.raises(LLMError):
        model("groq", max_retries=1).complete("hi")
    assert route.call_count == 2


@respx.mock
def test_client_error_is_not_retried():
    route = respx.post(PROVIDERS["groq"].url).mock(return_value=httpx.Response(400))
    with pytest.raises(LLMError):
        model("groq").complete("hi")
    assert route.call_count == 1


@respx.mock
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"choices": [{"message": {"content": None}}]}),
        httpx.Response(200, json={"nope": 1}),
    ],
)
def test_malformed_body_raises_llm_error(response):
    respx.post(PROVIDERS["groq"].url).mock(return_value=response)
    with pytest.raises(LLMError):
        model("groq").complete("hi")


@respx.mock
@pytest.mark.parametrize("name", NAMES)
def test_neither_key_nor_prompt_leaks_into_errors_or_logs(name):
    secret_prompt = "SECRET-PROMPT-TEXT-9921"
    respx.post(PROVIDERS[name].url).mock(return_value=httpx.Response(500, text=secret_prompt))
    with capture_logs() as logs:
        with pytest.raises(LLMError) as exc:
            model(name, max_retries=1).complete(secret_prompt)
    blob = str(exc.value) + repr(logs)
    assert KEY not in blob
    assert secret_prompt not in blob
    assert logs, "expected at least one log record"


@pytest.mark.parametrize("name", NAMES)
def test_missing_key_raises(monkeypatch, name):
    monkeypatch.delenv(PROVIDERS[name].key_env, raising=False)
    with pytest.raises(LLMError):
        OpenAICompatModel(PROVIDERS[name])


def test_make_model_rejects_unknown_provider():
    with pytest.raises(LLMError):
        make_model("nope")


@pytest.mark.parametrize("name", ["anthropic", *NAMES])
def test_make_model_selects_provider_from_environment(monkeypatch, name):
    key_env = "ANTHROPIC_API_KEY" if name == "anthropic" else PROVIDERS[name].key_env
    monkeypatch.setenv("PULSEOPS_PROVIDER", name)
    monkeypatch.setenv(key_env, KEY)
    m = make_model()
    if name == "anthropic":
        assert isinstance(m, AnthropicModel)
    else:
        assert isinstance(m, OpenAICompatModel)
        assert m.provider_name == name


def test_make_model_model_override(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", KEY)
    monkeypatch.delenv("PULSEOPS_MODEL", raising=False)
    m = make_model("groq", model="custom-model")
    assert isinstance(m, OpenAICompatModel)
    assert m.model_name == "custom-model"