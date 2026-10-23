from datetime import datetime, timezone
from pathlib import Path

from hypothesis import given, settings, event
from hypothesis import strategies as st

from pulseops.ai.citation_checker.checker import Violation, check_hypothesis
from pulseops.core.evidence_bundle.bundle import build_bundle
from pulseops.core.pipeline import run_pipeline
from pulseops.core.verification.templates import TEMPLATES
from pulseops.models.claims import ClaimType, Hypothesis, VerificationRequest
from pulseops.models.evidence import EvidenceType
from pulseops.models.rules import check_type_fit

POOL = Path(__file__).resolve().parents[3] / "scenarios" / "pool_exhaustion" / "capture"
BUNDLE = build_bundle(run_pipeline(POOL))
BY_ID = {e.id: e for e in BUNDLE.items}
REAL_IDS = sorted(BY_ID)

fake_ids = st.from_regex(r"E-(met|chg|log|top)-[0-9a-f]{8}", fullmatch=True)
mixed_ids = st.lists(st.one_of(st.sampled_from(REAL_IDS), fake_ids), max_size=6)
real_only_ids = st.lists(st.sampled_from(REAL_IDS), max_size=5, unique=True)

symptom_times = st.datetimes(
    min_value=datetime(2026, 3, 14, 1, 50),
    max_value=datetime(2026, 3, 14, 2, 14),
    timezones=st.just(timezone.utc),
)

requests = st.builds(
    VerificationRequest,
    template=st.one_of(st.sampled_from(sorted(TEMPLATES)), st.text(max_size=12)),
    params=st.dictionaries(
        st.sampled_from(["service", "metric", "template_id", "query"]),
        st.sampled_from(["orders", "checkout", "payments", "nope", "latency_p99"]),
        max_size=3,
    ),
)


def hypotheses(ids):
    return st.builds(
        Hypothesis,
        id=st.just("H"),
        title=st.just("t"),
        claim_type=st.sampled_from(list(ClaimType)),
        service=st.none(),
        confidence=st.floats(min_value=0.0, max_value=1.0),
        supporting=ids,
        contradicting=ids,
        verification=st.lists(requests, max_size=2),
    )


SETTINGS = settings(max_examples=300, deadline=None)


@SETTINGS
@given(h=hypotheses(mixed_ids), t=symptom_times)
def test_a_nonexistent_id_is_never_accepted(h, t):
    violations = check_hypothesis(h, BUNDLE, t)
    bad = [i for i in [*h.supporting, *h.contradicting] if i not in BY_ID]
    if bad:
        assert any(v.code == "fabricated_id" for v in violations)
        assert violations != []


@SETTINGS
@given(h=hypotheses(real_only_ids), t=symptom_times)
def test_accepted_means_everything_cited_exists_and_fits(h, t):
    if check_hypothesis(h, BUNDLE, t) != []:
        return
    event("accepted")
    assert all(i in BY_ID for i in [*h.supporting, *h.contradicting])
    if h.claim_type != ClaimType.EXTERNAL_OR_UNKNOWN:
        assert h.supporting
    cited = [BY_ID[i] for i in h.supporting]
    assert check_type_fit(h.claim_type, h.confidence, cited, t) == []
    for v in h.verification:
        assert v.template in TEMPLATES
        assert set(v.params) == TEMPLATES[v.template]


@SETTINGS
@given(h=hypotheses(real_only_ids), t=symptom_times)
def test_accepted_deploy_and_config_claims_cite_the_right_event_kind(h, t):
    # Independent of rules.py: re-states the guide's 4.4 requirement directly.
    if check_hypothesis(h, BUNDLE, t) != []:
        return
    cited = [BY_ID[i] for i in h.supporting]
    has_metric = any(e.type == EvidenceType.METRIC_CHANGE for e in cited)
    if h.claim_type == ClaimType.BAD_DEPLOY:
        event("accepted bad_deploy")
        assert has_metric
        assert any(e.type == EvidenceType.CHANGE_EVENT and e.subtype == "deploy" for e in cited)
    if h.claim_type == ClaimType.BAD_CONFIG:
        event("accepted bad_config")
        assert has_metric
        assert any(e.type == EvidenceType.CHANGE_EVENT
                   and e.subtype in ("config_change", "flag_flip") for e in cited)


@SETTINGS
@given(h=hypotheses(mixed_ids), t=symptom_times)
def test_checker_never_crashes_and_is_deterministic(h, t):
    first = check_hypothesis(h, BUNDLE, t)
    assert isinstance(first, list)
    assert all(isinstance(v, Violation) for v in first)
    assert first == check_hypothesis(h, BUNDLE, t)