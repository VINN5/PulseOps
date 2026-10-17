from datetime import datetime, timedelta, timezone

import pytest

from pulseops.models.claims import ClaimType
from pulseops.models.evidence import Evidence, EvidenceType
from pulseops.models.rules import check_type_fit

T0 = datetime(2026, 3, 14, 2, 0, tzinfo=timezone.utc)


def ev(type_, subtype, minutes, summary="x"):
    t = T0 + timedelta(minutes=minutes)
    return Evidence.build(type=type_, subtype=subtype, event_time=t, window_start=t,
                          window_end=t + timedelta(minutes=5), summary=summary, service="orders")


def test_ids_are_deterministic():
    assert ev(EvidenceType.METRIC_CHANGE, "saturation", 6).id == \
           ev(EvidenceType.METRIC_CHANGE, "saturation", 6).id


def test_tampered_content_is_rejected():
    e = ev(EvidenceType.METRIC_CHANGE, "saturation", 6)
    with pytest.raises(ValueError):
        Evidence(**{**e.model_dump(), "summary": "tampered"})


def test_bad_deploy_without_deploy_event_is_rejected():
    cited = [ev(EvidenceType.METRIC_CHANGE, "latency", 6)]
    errs = check_type_fit(ClaimType.BAD_DEPLOY, 0.7, cited, T0 + timedelta(minutes=10))
    assert any("deploy event" in e for e in errs)


def test_valid_resource_exhaustion_passes():
    cited = [ev(EvidenceType.METRIC_CHANGE, "saturation", 6),
             ev(EvidenceType.CHANGE_EVENT, "config_change", 3)]
    assert check_type_fit(ClaimType.RESOURCE_EXHAUSTION, 0.7, cited, T0 + timedelta(minutes=10)) == []


def test_evidence_after_symptom_is_rejected():
    cited = [ev(EvidenceType.METRIC_CHANGE, "saturation", 12)]
    errs = check_type_fit(ClaimType.RESOURCE_EXHAUSTION, 0.7, cited, T0 + timedelta(minutes=10))
    assert any("postdates" in e for e in errs)


def test_unknown_confidence_is_capped():
    errs = check_type_fit(ClaimType.EXTERNAL_OR_UNKNOWN, 0.9, [], T0)
    assert any("exceeds cap" in e for e in errs)
