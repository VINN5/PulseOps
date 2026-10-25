from __future__ import annotations

import json

import httpx
import pytest
import respx
from structlog.testing import capture_logs

from pulseops.ai.llm_client.client import API_URL, AnthropicModel, LLMError

KEY = "sk-ant-TESTKEY-0123456789abcdef"
OK = {"content": [{"type": "text", "text": "[]"}]}


def model(**kw) -> AnthropicModel:
    return AnthropicModel(KEY, sleep=lambda s: None, **kw)


@respx.mock
def test_success_returns_text_and_sends_expected_request():
    route = respx.post(API_URL).mock(return_value=httpx.Response(200, json=OK))
    assert model().complete("hi") == "[]"
    req = route.calls.last.request
    assert req.headers["x-api-key"] == KEY
    assert req.headers["anthropic-version"] == "2023-06-01"
    body = json.loads(req.content)
    assert body["model"] == "claude-sonnet-5-5"
    assert body["max_tokens"] == 1500
    assert body["messages"] == [{"role": "user", "content": "hi"}]


@respx.mock
def test_429_then_success_retries():
    route = respx.post(API_URL).mock(
        side_effect=[httpx.Response(429), httpx.Response(200, json=OK)]
    )
    assert model().complete("hi") == "[]"
    assert route.call_count == 2


@respx.mock
def test_persistent_500_gives_up_after_bounded_retries():
    route = respx.post(API_URL).mock(return_value=httpx.Response(500))
    with pytest.raises(LLMError):
        model(max_retries=2).complete("hi")
    assert route.call_count == 3


@respx.mock
def test_timeout_is_retried_then_raises_llm_error():
    route = respx.post(API_URL).mock(side_effect=httpx.ConnectTimeout("slow"))
    with pytest.raises(LLMError):
        model(max_retries=1).complete("hi")
    assert route.call_count == 2


@respx.mock
def test_client_error_is_not_retried():
    route = respx.post(API_URL).mock(return_value=httpx.Response(400))
    with pytest.raises(LLMError):
        model().complete("hi")
    assert route.call_count == 1


@respx.mock
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"nope": 1}),
        httpx.Response(200, json={"content": []}),
    ],
)
def test_malformed_body_raises_llm_error(response):
    respx.post(API_URL).mock(return_value=response)
    with pytest.raises(LLMError):
        model().complete("hi")


@respx.mock
def test_neither_key_nor_prompt_leaks_into_errors_or_logs():
    secret_prompt = "SECRET-PROMPT-TEXT-9921"
    respx.post(API_URL).mock(return_value=httpx.Response(500, text=secret_prompt))
    with capture_logs() as logs:
        with pytest.raises(LLMError) as exc:
            model(max_retries=1).complete(secret_prompt)
    blob = str(exc.value) + repr(logs)
    assert KEY not in blob
    assert secret_prompt not in blob
    assert logs, "expected at least one log record"


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(LLMError):
        AnthropicModel()


def test_key_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    assert AnthropicModel() is not None