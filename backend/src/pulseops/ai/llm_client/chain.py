from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Protocol

import structlog

from pulseops.ai.llm_client.client import DEFAULT_MODEL, AnthropicModel, LLMError, describe
from pulseops.ai.llm_client.openai_compat import PROVIDERS, OpenAICompatModel, make_model

log = structlog.get_logger(__name__)


class _Completer(Protocol):
    def complete(self, prompt: str) -> str: ...


def _label(m: object) -> str:
    provider = getattr(m, "provider_name", "anthropic")
    model = getattr(m, "model_name", None) or getattr(m, "_model", "?")
    return f"{provider}/{model}"


class FallbackModel:
    """Tries each model in order; moves on when one raises LLMError.

    This covers availability (down, rate-limited, retired). Bad output is the
    orchestrator's job, not this class's. If every model fails, the raised error carries
    the LAST model's status and code. After a success, answered_label names the chain link
    that answered and answered_by is the provider-reported model, when there is one.
    """

    def __init__(self, models: Sequence[_Completer]) -> None:
        if not models:
            raise ValueError("FallbackModel needs at least one model")
        self.models = tuple(models)
        self.answered_label: str | None = None
        self.answered_by: str | None = None

    def complete(self, prompt: str) -> str:
        self.answered_label = None
        self.answered_by = None
        last: LLMError | None = None
        for m in self.models:
            try:
                text = m.complete(prompt)
            except LLMError as e:
                last = e
                log.warning("llm_fallback", model=_label(m), reason=str(e))
                continue
            self.answered_label = _label(m)
            self.answered_by = getattr(m, "answered_by", None)
            return text
        status = last.status if last is not None else None
        code = last.code if last is not None else None
        raise LLMError(
            describe(
                f"all {len(self.models)} models in the chain failed",
                status if status is not None else "n/a",
                code,
            ),
            status=status,
            code=code,
        )


def make_chain(spec: str, **kwargs) -> FallbackModel:
    """Build a chain from 'provider[:model],provider[:model],...'."""
    models: list[OpenAICompatModel | AnthropicModel] = []
    for raw in spec.split(","):
        item = raw.strip()
        if not item:
            continue
        provider, _, model = item.partition(":")
        provider, model = provider.strip(), model.strip()
        if provider != "anthropic" and provider not in PROVIDERS:
            known = ", ".join(["anthropic", *sorted(PROVIDERS)])
            raise LLMError(f"unknown provider in chain (choose from: {known})")
        try:
            if provider == "anthropic":
                models.append(AnthropicModel(model=model or DEFAULT_MODEL, **kwargs))
            else:
                models.append(OpenAICompatModel(PROVIDERS[provider], model=model or None, **kwargs))
        except LLMError as e:
            log.warning("llm_chain_skip", provider=provider, reason=str(e))
    if not models:
        raise LLMError("no usable model in chain (check provider names and API keys)")
    return FallbackModel(models)


def model_from_env(**kwargs) -> _Completer:
    """PULSEOPS_CHAIN if set, else the single model make_model() picks."""
    spec = os.environ.get("PULSEOPS_CHAIN", "").strip()
    if spec:
        return make_chain(spec, **kwargs)
    return make_model(**kwargs)