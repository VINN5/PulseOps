from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pulseops.core.evidence_bundle.bundle import EvidenceBundle
from pulseops.core.verification.templates import TEMPLATES
from pulseops.models.claims import ClaimType, Hypothesis
from pulseops.models.rules import check_type_fit


@dataclass(frozen=True)
class Violation:
    code: str  # fabricated_id | uncited | type_fit | time_sanity | template_not_allowed | bad_params
    hypothesis_id: str
    detail: str


@dataclass(frozen=True)
class CheckResult:
    accepted: list[Hypothesis]
    rejected: list[tuple[Hypothesis, list[Violation]]]


def check_hypothesis(h: Hypothesis, bundle: EvidenceBundle, symptom_time: datetime) -> list[Violation]:
    """Return every violation found (an empty list means the hypothesis passes)."""
    violations: list[Violation] = []
    by_id = {e.id: e for e in bundle.items}  # only what the model was shown
    services = {e.service for e in bundle.items}

    # 1. fabricated_id: an ID absent from the bundle (including ones the cap dropped).
    for eid in [*h.supporting, *h.contradicting]:
        if eid not in by_id:
            violations.append(Violation("fabricated_id", h.id, f"{eid} is not in the bundle"))

    # 2. uncited: every claim except external_or_unknown must cite something.
    if not h.supporting and h.claim_type != ClaimType.EXTERNAL_OR_UNKNOWN:
        violations.append(Violation("uncited", h.id, "no supporting evidence cited"))

    # 3. type_fit / time_sanity: only supporting IDs that exist.
    # Brittle: the code is chosen by matching text in rules.py's message.
    cited = [by_id[i] for i in h.supporting if i in by_id]
    for msg in check_type_fit(h.claim_type, h.confidence, cited, symptom_time):
        code = "time_sanity" if "postdates the symptom" in msg else "type_fit"
        violations.append(Violation(code, h.id, msg))

    # 4. verification requests: allow-listed template, exact params, known service.
    for v in h.verification:
        if v.template not in TEMPLATES:
            violations.append(Violation(
                "template_not_allowed", h.id, f"template {v.template!r} is not on the allow-list"))
            continue
        if set(v.params) != TEMPLATES[v.template]:
            violations.append(Violation(
                "bad_params", h.id,
                f"{v.template}: params {sorted(v.params)} != required {sorted(TEMPLATES[v.template])}"))
        service = v.params.get("service")
        if service is not None and service not in services:
            violations.append(Violation(
                "bad_params", h.id, f"{v.template}: service {service!r} not in the bundle"))
    return violations


def check_all(hs: list[Hypothesis], bundle: EvidenceBundle, symptom_time: datetime) -> CheckResult:
    """Split hypotheses into accepted and rejected. Never modifies a hypothesis."""
    accepted: list[Hypothesis] = []
    rejected: list[tuple[Hypothesis, list[Violation]]] = []
    for h in hs:
        found = check_hypothesis(h, bundle, symptom_time)
        if found:
            rejected.append((h, found))
        else:
            accepted.append(h)
    return CheckResult(accepted, rejected)