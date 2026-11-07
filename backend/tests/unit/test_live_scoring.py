from __future__ import annotations

from types import SimpleNamespace

from pulseops.evaluation.live_scoring import score_run
from pulseops.models.claims import ClaimType, Hypothesis

TRIGGER = "E-chg-d9c1c237"
DECOY = "E-chg-224e230c"


def hyp(hid: str, claim: ClaimType, conf: float, supporting: list[str]) -> Hypothesis:
    return Hypothesis(
        id=hid, title="t", claim_type=claim, confidence=conf, supporting=supporting
    )


def result(*hyps: Hypothesis, fallback: bool = False, attempts: int = 1):
    return SimpleNamespace(accepted=list(hyps), used_fallback=fallback, attempts=attempts)


def run(r):
    return score_run(r, TRIGGER, [DECOY], "resource_exhaustion")


def test_fallback_is_reported_as_fallback():
    s = run(result(fallback=True, attempts=2))
    assert s.outcome == "fallback"
    assert s.retried is True
    assert s.trigger_in_top is False


def test_top_hypothesis_is_the_most_confident_not_the_first():
    low = hyp("H1", ClaimType.BAD_DEPLOY, 0.3, [DECOY])
    high = hyp("H2", ClaimType.BAD_CONFIG, 0.9, [TRIGGER])
    s = run(result(low, high))
    assert s.trigger_in_top is True
    assert s.decoy_in_top is False


def test_decoy_cited_only_by_a_lower_hypothesis_is_flagged_as_anywhere():
    top = hyp("H1", ClaimType.BAD_CONFIG, 0.9, [TRIGGER])
    other = hyp("H2", ClaimType.BAD_DEPLOY, 0.2, [DECOY])
    s = run(result(top, other))
    assert s.decoy_in_top is False
    assert s.decoy_anywhere is True


def test_claim_type_mismatch_does_not_hide_a_correct_trigger():
    s = run(result(hyp("H1", ClaimType.BAD_CONFIG, 0.9, [TRIGGER])))
    assert s.trigger_in_top is True
    assert s.type_match is False
    assert s.top_type == "bad_config"


def test_matching_claim_type_is_recognised():
    s = run(result(hyp("H1", ClaimType.RESOURCE_EXHAUSTION, 0.9, [TRIGGER])))
    assert s.type_match is True