from __future__ import annotations

from datetime import datetime

from pulseops.core.graph.spans import Span

Graph = dict[str, frozenset[str]]  # service -> services it calls


def build_graph(spans: list[Span], start: datetime, end: datetime) -> Graph:
    """Spans with start <= timestamp < end. Every service seen as caller or
    callee is a key; leaf services map to an empty frozenset."""
    edges: dict[str, set[str]] = {}
    for s in spans:
        if not (start <= s.timestamp < end):
            continue
        edges.setdefault(s.caller, set()).add(s.callee)
        edges.setdefault(s.callee, set())
    return {k: frozenset(v) for k, v in edges.items()}


def upstream_candidates(graph: Graph, degraded: set[str]) -> list[str]:
    """Degraded services with no degraded callee (self-edges ignored).
    A degraded service absent from the graph is treated as having no callees."""
    out = [
        svc for svc in degraded
        if not any(c in degraded for c in graph.get(svc, frozenset()) if c != svc)
    ]
    return sorted(out)
