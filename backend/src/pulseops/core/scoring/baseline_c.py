from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta

from pulseops.core.events.align import align
from pulseops.core.graph.graph import Graph, upstream_candidates
from pulseops.models.evidence import Evidence

EXTERNAL_SCORE = 0.25  # arbitrary; documented as such
WEIGHTS = {"same_service": 1.0, "proximity": 1.0, "topology": 1.0, "magnitude": 1.0}
# Equal because there is one scenario and nothing to tune on.
EPS = 1e-6


@dataclass(frozen=True)
class ScoredHypothesis:
    change: Evidence | None  # None means external_or_unknown
    same_service: float
    proximity: float
    topology: float
    magnitude: float
    score: float
    fallback: bool  # True if topology came from the earliest-change fallback


def _raw_magnitude(metric: Evidence) -> float:
    before = float(metric.data["before"])
    after = float(metric.data["after"])
    return abs(math.log10((after + EPS) / (before + EPS)))


def _weighted_mean(f: dict[str, float]) -> float:
    total = sum(WEIGHTS.values())
    return sum(WEIGHTS[k] * f[k] for k in WEIGHTS) / total


def score_changes(
    changes: list[Evidence],
    metrics: list[Evidence],
    graph: Graph,
    lookback: timedelta = timedelta(minutes=60),
) -> list[ScoredHypothesis]:
    lookback_s = lookback.total_seconds()
    degraded = {m.service for m in metrics}
    upstream = set(upstream_candidates(graph, degraded))

    fallback = False
    if not upstream and metrics:
        earliest = min(metrics, key=lambda m: (m.event_time, m.id))
        upstream = {earliest.service}
        fallback = True

    # Min-max scale log-magnitudes across ALL metrics in the run, so scores
    # are comparable across metrics. If max == min every value scales to 0.0
    # (arbitrary degenerate case).
    raw = {m.id: _raw_magnitude(m) for m in metrics}
    lo = min(raw.values(), default=0.0)
    hi = max(raw.values(), default=0.0)

    def scale(v: float) -> float:
        return 0.0 if hi == lo else (v - lo) / (hi - lo)

    cands = [c for c in align(changes, metrics, lookback) if c.relation == "same_service"]

    out: list[ScoredHypothesis] = []
    for ch in changes:
        mine = [c for c in cands if c.change.id == ch.id]
        same = 1.0 if mine else 0.0
        prox = 1.0 - min(c.delta_seconds for c in mine) / lookback_s if mine else 0.0
        topo = 1.0 if ch.service in upstream else 0.0
        mag = scale(max(raw[c.metric.id] for c in mine)) if mine else 0.0
        feats = {"same_service": same, "proximity": prox, "topology": topo, "magnitude": mag}
        out.append(ScoredHypothesis(ch, same, prox, topo, mag, _weighted_mean(feats), fallback))

    out.append(ScoredHypothesis(None, 0.0, 0.0, 0.0, 0.0, EXTERNAL_SCORE, fallback))
    out.sort(key=lambda h: (-h.score, h.change.id if h.change else ""))
    return out