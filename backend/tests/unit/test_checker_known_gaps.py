"""Pins the checker's CURRENT behaviour where live runs showed it is looser than it looks.

These are characterization tests, not endorsements. rules.py checks evidence TYPES, not whether
the evidence is related (same service, close in time, connected in the graph). See decision 0015.
When a relevance rule is added, tests 1 and 3 should be inverted on purpose, not deleted.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pulseops.ai.citation_checker.checker import check_hypothesis
from pulseops.core.evidence_bundle.bundle import build_bundle
from pulseops.core.pipeline import run_pipeline
from pulseops.models.claims import ClaimType, Hypothesis

POOL = Path(__file__).resolve().parents[3] / "scenarios" / "pool_exhaustion" / "capture"
R = run_pipeline(POOL)
BUNDLE = build_bundle(R)
SYMPTOM = datetime(2026, 3, 14, 2, 14, tzinfo=timezone.utc)
DECOY = next(c for c in R.changes if c.data["external_id"] == "chg-2288")  # payments deploy
ORDERS_METRIC = next(m for m in R.metrics if m.service == "orders")
CHECKOUT_METRIC = next(m for m in R.metrics if m.service == "checkout")


def hyp(claim: ClaimType, confidence: float, *cited) -> Hypothesis:
    return Hypothesis(
        id="H1", title="t", claim_type=claim, confidence=confidence,
        supporting=[e.id for e in cited],
    )


def codes(violations) -> set[str]:
    return {v.code for v in violations}


def test_known_gap_deploy_on_another_service_passes_with_any_metric():
    assert DECOY.id in {e.id for e in BUNDLE.items}
    assert DECOY.service == "payments"
    assert ORDERS_METRIC.service == "orders"
    h = hyp(ClaimType.BAD_DEPLOY, 0.6, DECOY, ORDERS_METRIC)
    assert check_hypothesis(h, BUNDLE, SYMPTOM) == []


def test_deploy_with_no_metric_is_rejected():
    h = hyp(ClaimType.BAD_DEPLOY, 0.4, DECOY)
    assert "type_fit" in codes(check_hypothesis(h, BUNDLE, SYMPTOM))


def test_known_gap_slow_dependency_passes_on_a_single_metric():
    h = hyp(ClaimType.SLOW_DEPENDENCY, 0.6, CHECKOUT_METRIC)
    assert check_hypothesis(h, BUNDLE, SYMPTOM) == []