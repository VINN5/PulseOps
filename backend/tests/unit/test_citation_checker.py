from pathlib import Path

from pulseops.ai.citation_checker.checker import check_all, check_hypothesis
from pulseops.core.evidence_bundle.bundle import build_bundle
from pulseops.core.pipeline import run_pipeline
from pulseops.models.claims import ClaimType, Hypothesis, VerificationRequest

POOL = Path(__file__).resolve().parents[3] / "scenarios" / "pool_exhaustion" / "capture"


def _setup():
    r = run_pipeline(POOL)
    b = build_bundle(r)
    chg = next(c for c in r.changes if c.data["external_id"] == "chg-2291")
    decoy = next(c for c in r.changes if c.data["external_id"] == "chg-2288")
    symptom = next(m for m in r.metrics if m.service == "checkout").event_time
    return r, b, chg, decoy, symptom


def _hyp(**kw) -> Hypothesis:
    base = dict(id="H1", title="t", claim_type=ClaimType.BAD_CONFIG, service="orders",
                confidence=0.7, supporting=[], contradicting=[], verification=[])
    base.update(kw)
    return Hypothesis(**base)


def _codes(violations) -> set[str]:
    return {v.code for v in violations}


def test_valid_hypothesis_passes():
    r, b, chg, _, symptom = _setup()
    h = _hyp(supporting=[chg.id, *b.supporting[chg.id]],
             verification=[VerificationRequest(
                 template="metric_series",
                 params={"service": "orders", "metric": "db_pool_wait_p95"})])
    assert check_hypothesis(h, b, symptom) == []


def test_fabricated_supporting_id_is_flagged():
    r, b, chg, _, symptom = _setup()
    h = _hyp(supporting=[chg.id, "E-met-deadbeef"])
    assert "fabricated_id" in _codes(check_hypothesis(h, b, symptom))


def test_fabricated_contradicting_id_is_flagged():
    r, b, chg, _, symptom = _setup()
    h = _hyp(supporting=[chg.id, *b.supporting[chg.id]], contradicting=["E-chg-00000000"])
    assert "fabricated_id" in _codes(check_hypothesis(h, b, symptom))


def test_id_dropped_by_the_cap_counts_as_fabricated():
    r, _, _, decoy, symptom = _setup()
    small = build_bundle(r, max_items=3)
    assert decoy.id in {o.id for o in small.omitted}
    h = _hyp(claim_type=ClaimType.BAD_DEPLOY, supporting=[decoy.id])
    assert "fabricated_id" in _codes(check_hypothesis(h, small, symptom))


def test_wrong_evidence_type_for_claim_is_flagged():
    r, b, chg, _, symptom = _setup()
    h = _hyp(claim_type=ClaimType.BAD_DEPLOY, supporting=[chg.id, *b.supporting[chg.id]])
    assert "type_fit" in _codes(check_hypothesis(h, b, symptom))


def test_evidence_after_the_symptom_is_flagged():
    r, b, chg, _, symptom = _setup()
    early = chg.event_time.replace(minute=0, second=0)
    h = _hyp(supporting=[chg.id, *b.supporting[chg.id]])
    assert "time_sanity" in _codes(check_hypothesis(h, b, early))


def test_uncited_claim_is_flagged():
    _, b, _, _, symptom = _setup()
    assert "uncited" in _codes(check_hypothesis(_hyp(supporting=[]), b, symptom))


def test_external_or_unknown_needs_low_confidence_but_not_citations():
    _, b, _, _, symptom = _setup()
    loud = _hyp(claim_type=ClaimType.EXTERNAL_OR_UNKNOWN, confidence=0.8)
    quiet = _hyp(claim_type=ClaimType.EXTERNAL_OR_UNKNOWN, confidence=0.2)
    assert "type_fit" in _codes(check_hypothesis(loud, b, symptom))
    assert "uncited" not in _codes(check_hypothesis(loud, b, symptom))
    assert check_hypothesis(quiet, b, symptom) == []


def test_template_outside_the_allow_list_is_flagged():
    r, b, chg, _, symptom = _setup()
    h = _hyp(supporting=[chg.id, *b.supporting[chg.id]],
             verification=[VerificationRequest(template="run_sql", params={"query": "x"})])
    assert "template_not_allowed" in _codes(check_hypothesis(h, b, symptom))


def test_bad_verification_params_are_flagged():
    r, b, chg, _, symptom = _setup()
    support = [chg.id, *b.supporting[chg.id]]
    unknown_service = _hyp(supporting=support, verification=[VerificationRequest(
        template="metric_series", params={"service": "nope", "metric": "latency_p99"})])
    missing_key = _hyp(supporting=support, verification=[VerificationRequest(
        template="metric_series", params={"service": "orders"})])
    assert "bad_params" in _codes(check_hypothesis(unknown_service, b, symptom))
    assert "bad_params" in _codes(check_hypothesis(missing_key, b, symptom))


def test_check_all_splits_and_never_modifies():
    r, b, chg, _, symptom = _setup()
    good = _hyp(id="H1", supporting=[chg.id, *b.supporting[chg.id]])
    bad = _hyp(id="H2", supporting=["E-met-deadbeef"])
    result = check_all([good, bad], b, symptom)
    assert result.accepted == [good]
    assert result.rejected[0][0] is bad
    assert result.rejected[0][1]
    assert bad.supporting == ["E-met-deadbeef"]