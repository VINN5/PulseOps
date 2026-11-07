from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from mock_model.fake_model import FakeModel
from pulseops.ai.hypotheses.orchestrator import run_model_step
from pulseops.core.evidence_bundle.bundle import build_bundle
from pulseops.core.pipeline import run_pipeline
from pulseops.models.claims import ClaimType, Hypothesis
from pulseops.models.evidence import EvidenceType

POOL = Path(__file__).resolve().parents[3] / "scenarios" / "pool_exhaustion" / "capture"
BUNDLE = build_bundle(run_pipeline(POOL))

SYMPTOM = datetime(2026, 3, 14, 2, 14, tzinfo=timezone.utc)


def good() -> Hypothesis:
    cause = next(
        e for e in BUNDLE.items
        if e.type == EvidenceType.CHANGE_EVENT and e.subtype == "config_change"
    )
    metric = next(e for e in BUNDLE.items if e.type == EvidenceType.METRIC_CHANGE)
    return Hypothesis(
        id="H-good",
        title="t",
        claim_type=ClaimType.BAD_CONFIG,
        confidence=0.5,
        supporting=[cause.id, metric.id],
    )


def fabricated(title: str = "t") -> Hypothesis:
    return Hypothesis(
        id="H-bad",
        title=title,
        claim_type=ClaimType.BAD_CONFIG,
        confidence=0.5,
        supporting=["E-met-00000000"],
    )


def dump(*hs: Hypothesis) -> str:
    return json.dumps([h.model_dump(mode="json") for h in hs])


def test_happy_path():
    r = run_model_step(FakeModel(dump(good())), BUNDLE, SYMPTOM)
    assert r.accepted and r.attempts == 1 and r.used_fallback is False


def test_malformed_json_then_valid():
    r = run_model_step(FakeModel("not json", dump(good())), BUNDLE, SYMPTOM)
    assert r.attempts == 2 and r.accepted
    assert "bad_json" in r.reasons


def test_fabricated_ids_twice_falls_back():
    m = FakeModel(dump(fabricated()), dump(fabricated()))
    r = run_model_step(m, BUNDLE, SYMPTOM)
    assert r.used_fallback is True and r.accepted == [] and r.attempts == 2


def test_model_errors_never_escape():
    m = FakeModel(RuntimeError("timeout"), RuntimeError("timeout"))
    r = run_model_step(m, BUNDLE, SYMPTOM)
    assert r.used_fallback is True
    assert "model_error" in r.reasons


def test_retry_prompt_has_codes_but_not_model_output():
    marker = "LEAK-MARKER-7731"
    m = FakeModel(dump(fabricated(title=marker)), dump(good()))
    run_model_step(m, BUNDLE, SYMPTOM)
    assert "fabricated_id" in m.prompts[1]
    assert marker not in m.prompts[1]


def test_partial_acceptance_keeps_good_and_skips_retry():
    m = FakeModel(dump(good(), fabricated()))
    r = run_model_step(m, BUNDLE, SYMPTOM)
    assert r.attempts == 1 and len(r.accepted) == 1
    assert r.used_fallback is False
    assert len(m.prompts) == 1