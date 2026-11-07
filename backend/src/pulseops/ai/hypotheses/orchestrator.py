from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from pulseops.ai.citation_checker.checker import check_all
from pulseops.ai.prompts.prompt import build_prompt
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


_HINTS = {
    "fabricated_id": "you cited evidence IDs that are not in the bundle",
    "uncited": "a claim had no supporting evidence",
    "type_fit": "the cited evidence does not fit the claim type or confidence",
    "time_sanity": "cited evidence postdates the symptom",
    "template_not_allowed": "a verification template is not on the allow-list",
    "bad_params": "a verification request had the wrong parameters",
    "unlinked_change": "a cited change event has no cited metric change that followed it on the same service",
}


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
    # Feedback is built from our own fixed text keyed by violation code.
    # Violation.detail echoes model-supplied strings, so it must not go back in.
    feedback = [f"{c}: {_HINTS.get(c, 'rule violated')}" for c in sorted(set(reasons))]
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