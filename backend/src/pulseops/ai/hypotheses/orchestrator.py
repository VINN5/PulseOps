from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from pulseops.ai.citation_checker.checker import check_all
from pulseops.core.evidence_bundle.bundle import EvidenceBundle
from pulseops.models.claims import Hypothesis


class Model(Protocol):
    def complete(self, prompt: str) -> str: ...


@dataclass(frozen=True)
class OrchestratorResult:
    accepted: list[Hypothesis]
    used_fallback: bool  # True => caller should render baseline C instead
    attempts: int  # 1 or 2
    reasons: list[str]  # why we retried / fell back


def parse_output(raw: str) -> list[Hypothesis]:
    """Strict: a JSON array of objects that validate as Hypothesis, else ValueError."""
    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as e:
        raise ValueError("bad_json") from e
    if not isinstance(data, list):
        raise ValueError("not_a_list")
    try:
        return [Hypothesis.model_validate(item) for item in data]
    except Exception as e:
        raise ValueError("bad_schema") from e


def build_prompt(bundle: EvidenceBundle) -> str:
    # Stub: the versioned prompt files come later.
    ids = ", ".join(e.id for e in bundle.items)
    return f"Return a JSON array of hypotheses. Cite only these evidence IDs: {ids}"


def _attempt(
    model: Model, prompt: str, bundle: EvidenceBundle, symptom_time: datetime
) -> tuple[list[Hypothesis], list[str], list[str]]:
    """One model call. Returns (accepted, reason codes, feedback lines for a retry)."""
    try:
        raw = model.complete(prompt)
    except Exception:
        return [], ["model_error"], ["model_error: the model call failed"]
    try:
        hs = parse_output(raw)
    except ValueError as e:
        code = str(e)
        return [], [code], [f"{code}: output must be a JSON array of hypothesis objects"]
    except Exception:
        return [], ["bad_schema"], ["bad_schema: output could not be parsed"]
    if not hs:
        return [], ["no_hypotheses"], ["no_hypotheses: the array was empty"]
    try:
        result = check_all(hs, bundle, symptom_time)
    except Exception:
        return [], ["checker_error"], ["checker_error: the output could not be checked"]
    reasons = [v.code for _, vs in result.rejected for v in vs]
    # Only codes and details we generated; nothing from the model's own text.
    feedback = [f"{v.code}: {v.detail}" for _, vs in result.rejected for v in vs]
    return result.accepted, reasons, feedback


def run_model_step(
    model: Model, bundle: EvidenceBundle, symptom_time: datetime
) -> OrchestratorResult:
    prompt = build_prompt(bundle)
    accepted, reasons, feedback = _attempt(model, prompt, bundle, symptom_time)
    if accepted:
        return OrchestratorResult(accepted, False, 1, reasons)

    retry_prompt = prompt + "\n\nYour previous answer was rejected:\n" + "\n".join(feedback)
    accepted2, reasons2, _ = _attempt(model, retry_prompt, bundle, symptom_time)
    all_reasons = reasons + reasons2
    if accepted2:
        return OrchestratorResult(accepted2, False, 2, all_reasons)
    return OrchestratorResult([], True, 2, all_reasons)