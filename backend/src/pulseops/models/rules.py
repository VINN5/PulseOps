from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from pulseops.models.claims import ClaimType
from pulseops.models.evidence import Evidence, EvidenceType

Match = tuple[EvidenceType, str | None]  # subtype None = any subtype

MET, LOG, TRC = EvidenceType.METRIC_CHANGE, EvidenceType.LOG_TEMPLATE, EvidenceType.TRACE_PATH
CHG, TOP = EvidenceType.CHANGE_EVENT, EvidenceType.TOPOLOGY


@dataclass(frozen=True)
class Need:
    """One starred requirement: at least one cited item must match any of these."""
    description: str
    any_of: tuple[Match, ...]


@dataclass(frozen=True)
class ClaimRule:
    required: tuple[Need, ...]
    optional_types: frozenset[EvidenceType] = frozenset()
    max_confidence: float = 1.0
    must_state_absence: bool = False


RULES: dict[ClaimType, ClaimRule] = {
    ClaimType.BAD_DEPLOY: ClaimRule(
        required=(Need("a deploy event", ((CHG, "deploy"),)),
                  Need("a metric change", ((MET, None),))),
        optional_types=frozenset({LOG})),
    ClaimType.BAD_CONFIG: ClaimRule(
        required=(Need("a config change or flag flip", ((CHG, "config_change"), (CHG, "flag_flip"))),
                  Need("a metric change", ((MET, None),)))),
    ClaimType.RESOURCE_EXHAUSTION: ClaimRule(
        required=(Need("a saturation metric change", ((MET, "saturation"),)),),
        optional_types=frozenset({LOG, CHG})),
    ClaimType.SLOW_DEPENDENCY: ClaimRule(
        required=(Need("a trace path or downstream metric change", ((TRC, None), (MET, None))),),
        optional_types=frozenset({TOP})),
    ClaimType.RETRY_STORM: ClaimRule(
        required=(Need("a request-rate metric change", ((MET, "request_rate"),)),
                  Need("a retry metric change", ((MET, "retries"),))),
        optional_types=frozenset({LOG})),
    ClaimType.CAPACITY_OR_TRAFFIC: ClaimRule(
        required=(Need("a request-rate metric change", ((MET, "request_rate"),)),),
        optional_types=frozenset({MET})),
    ClaimType.EXTERNAL_OR_UNKNOWN: ClaimRule(
        required=(), max_confidence=0.3, must_state_absence=True),
}


def _matches(e: Evidence, m: Match) -> bool:
    return e.type == m[0] and (m[1] is None or e.subtype == m[1])


def check_type_fit(
    claim_type: ClaimType, confidence: float,
    cited: Sequence[Evidence], symptom_time: datetime,
) -> list[str]:
    """Return a list of rule violations; an empty list means the claim passes."""
    rule = RULES[claim_type]
    errors: list[str] = []

    for need in rule.required:
        if not any(_matches(e, m) for e in cited for m in need.any_of):
            errors.append(f"{claim_type}: missing required evidence: {need.description}")

    allowed = {m[0] for n in rule.required for m in n.any_of} | rule.optional_types
    for e in cited:
        if e.type not in allowed:
            errors.append(f"{e.id}: evidence type {e.type} not allowed for {claim_type}")
        if e.event_time > symptom_time:
            errors.append(f"{e.id}: postdates the symptom, cannot be its cause")

    if confidence > rule.max_confidence:
        errors.append(f"{claim_type}: confidence {confidence} exceeds cap {rule.max_confidence}")
    return errors
