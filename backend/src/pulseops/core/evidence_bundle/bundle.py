from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from pulseops.core.pipeline import PipelineResult
from pulseops.models.evidence import Evidence

DEFAULT_MAX_ITEMS = 12


@dataclass(frozen=True)
class Omission:
    id: str
    reason: str


@dataclass(frozen=True)
class EvidenceBundle:
    items: list[Evidence]             # kept, in time order
    omitted: list[Omission]           # dropped, with the reason
    supporting: dict[str, list[str]]  # change evidence ID -> same-service metric evidence IDs
    bundle_hash: str


def build_bundle(result: PipelineResult, max_items: int = DEFAULT_MAX_ITEMS) -> EvidenceBundle:
    if max_items < 1:
        raise ValueError("max_items must be at least 1")

    by_time = sorted(result.candidates, key=lambda c: (c.metric.event_time, c.metric.id))
    supporting: dict[str, list[str]] = {}
    for ch in result.changes:
        ids = [c.metric.id for c in by_time
               if c.change.id == ch.id and c.relation == "same_service"]
        supporting[ch.id] = list(dict.fromkeys(ids))

    supporting_metric_ids = {i for ids in supporting.values() for i in ids}
    symptom = [m for m in result.metrics
               if m.service == result.trigger["service"]
               and m.data["metric"] == result.trigger["symptom_metric"]]
    tiers = [
        (0, symptom),
        (1, [c for c in result.changes if supporting[c.id]]),
        (2, [m for m in result.metrics if m.id in supporting_metric_ids]),
        (3, [c for c in result.changes if not supporting[c.id]]),
        (4, list(result.metrics)),
    ]

    ranked: list[tuple[int, Evidence]] = []
    seen: set[str] = set()
    for tier, group in tiers:
        for ev in sorted(group, key=lambda e: (e.event_time, e.id)):
            if ev.id not in seen:
                seen.add(ev.id)
                ranked.append((tier, ev))

    kept, dropped = ranked[:max_items], ranked[max_items:]
    items = sorted((e for _, e in kept), key=lambda e: (e.event_time, e.id))
    omitted = [Omission(e.id, f"over cap of {max_items} items (priority tier {t})")
               for t, e in dropped]

    payload = {
        "items": [e.id for e in items],
        "omitted": [[o.id, o.reason] for o in omitted],
        "supporting": supporting,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return EvidenceBundle(items, omitted, supporting, f"sha256:{digest}")
