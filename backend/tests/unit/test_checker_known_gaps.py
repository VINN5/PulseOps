"""Checker relevance behaviour (decision 0015).

A cited change event must be linked to at least one cited metric (the bundle's same-service
alignment). Still open, and pinned below: slow_dependency accepts a single metric on its own.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pulseops.ai.citation_checker.checker import check_hypothesis
from pulseops.ai.hypotheses.orchestrator import _HINTS
from pulseops.core.evidence_bundle.bundle import build_bundle
from pulseops.core.pipeline import run_pipeline
from pulseops.models.claims import ClaimType, Hypothesis

SCENARIOS = Path(__file__).resolve().parents[3] / "scenarios"
R = run_pipeline(SCENARIOS / "pool_exhaustion" / "capture")
BUNDLE = build_bundle(R)
RD = run_pipeline(SCENARIOS / "decoy_deploy" / "capture")
BUNDLE_D = build_bundle(RD)
SYMPTOM = datetime(2026, 3, 14, 2, 14, tzinfo=timezone.utc)


def change(result, external_id):
    return next(c for c in result.changes if c.data["external_id"] == external_id)


def metric(result, service):
    return next(m for m in result.metrics if m.service == service)


DECOY = change(R, "chg-2288")  # payments deploy, no payments metric follows it
CONFIG = change(R, "chg-2291")  # orders config change, the true cause
LINKED = [e for e in BUNDLE.items if e.id in BUNDLE.supporting[CONFIG.id]]
ORDERS_METRIC = metric(R, "orders")
CHECKOUT_METRIC = metric(R, "checkout")


def hyp(claim: ClaimType, confidence: float, *cited) -> Hypothesis:
    return Hypothesis(
        id="H1", title="t", claim_type=claim, confidence=confidence,
        supporting=[e.id for e in cited],
    )


def codes(violations) -> set[str]:
    return {v.code for v in violations}


def test_deploy_on_another_service_with_any_metric_is_rejected():
    assert DECOY.id in {e.id for e in BUNDLE.items}
    assert DECOY.service == "payments"
    h = hyp(ClaimType.BAD_DEPLOY, 0.6, DECOY, ORDERS_METRIC)
    assert "unlinked_change" in codes(check_hypothesis(h, BUNDLE, SYMPTOM))


def test_deploy_with_no_metric_is_rejected():
    h = hyp(ClaimType.BAD_DEPLOY, 0.4, DECOY)
    assert "type_fit" in codes(check_hypothesis(h, BUNDLE, SYMPTOM))


def test_decoy_deploy_scenario_is_rejected_too():
    decoy = change(RD, "chg-2288")
    assert decoy.id in {e.id for e in BUNDLE_D.items}
    h = hyp(ClaimType.BAD_DEPLOY, 0.6, decoy, metric(RD, "orders"))
    assert "unlinked_change" in codes(check_hypothesis(h, BUNDLE_D, SYMPTOM))


def test_true_cause_with_its_linked_metrics_passes():
    assert LINKED, "expected the config change to have linked metrics"
    h = hyp(ClaimType.BAD_CONFIG, 0.85, CONFIG, *LINKED)
    assert check_hypothesis(h, BUNDLE, SYMPTOM) == []


def test_true_cause_plus_a_downstream_metric_still_passes():
    h = hyp(ClaimType.BAD_CONFIG, 0.85, CONFIG, *LINKED, CHECKOUT_METRIC)
    assert check_hypothesis(h, BUNDLE, SYMPTOM) == []


def test_a_decoy_cited_beside_the_true_cause_is_rejected():
    h = hyp(ClaimType.BAD_CONFIG, 0.85, CONFIG, DECOY, *LINKED)
    assert "unlinked_change" in codes(check_hypothesis(h, BUNDLE, SYMPTOM))


def test_known_gap_slow_dependency_passes_on_a_single_metric():
    h = hyp(ClaimType.SLOW_DEPENDENCY, 0.6, CHECKOUT_METRIC)
    assert check_hypothesis(h, BUNDLE, SYMPTOM) == []


def test_unlinked_change_has_a_fixed_retry_hint():
    assert "unlinked_change" in _HINTS