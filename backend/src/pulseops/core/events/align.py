from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from pulseops.models.evidence import Evidence, EvidenceType


@dataclass(frozen=True)
class Candidate:
    change: Evidence        # type change_event
    metric: Evidence        # the metric change it may explain
    delta_seconds: float    # metric.event_time - change.event_time, always > 0
    relation: str           # "same_service" | "unrelated" for now


def load_events(path: Path) -> list[Evidence]:
    items = json.loads(path.read_text(encoding="utf-8-sig"))
    out: list[Evidence] = []
    for item in items:
        t = datetime.fromisoformat(item["time"])
        out.append(Evidence.build(
            type=EvidenceType.CHANGE_EVENT,
            subtype=item["kind"],
            service=item["service"],
            event_time=t, window_start=t, window_end=t,
            summary=item["summary"],
            data={
                "external_id": item["id"],
                "summary": item["summary"],
                "actor": item["actor"],
                "ref": item["ref"],
            },
        ))
    return out


def align(
    changes: list[Evidence],
    metrics: list[Evidence],
    lookback: timedelta = timedelta(minutes=60),
) -> list[Candidate]:
    out: list[Candidate] = []
    for c in changes:
        for m in metrics:
            delta = (m.event_time - c.event_time).total_seconds()
            if delta <= 0 or delta > lookback.total_seconds():
                continue
            relation = "same_service" if c.service == m.service else "unrelated"
            out.append(Candidate(c, m, delta, relation))
    out.sort(key=lambda x: (
        x.relation != "same_service",  # same-service candidates first
        x.delta_seconds,               # then the smaller gap
        x.change.id,                   # then IDs, so input order never matters
        x.metric.id,
    ))
    return out

def unmatched(
    changes: list[Evidence],
    metrics: list[Evidence],
    lookback: timedelta = timedelta(minutes=60),
) -> list[Evidence]:
    """Changes with no same-service metric change following within lookback."""
    matched = {
        c.change.id
        for c in align(changes, metrics, lookback)
        if c.relation == "same_service"
    }
    return [c for c in changes if c.id not in matched]