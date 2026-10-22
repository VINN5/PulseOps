from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from pulseops.core.change_points.detector import DEFAULT_BASELINE_POINTS
from pulseops.core.change_points.evidence import detect_all
from pulseops.core.events.align import Candidate, align, load_events, unmatched
from pulseops.core.graph.graph import Graph, build_graph, upstream_candidates
from pulseops.core.graph.spans import load_spans
from pulseops.core.ingest.snapshot import SnapshotBackend
from pulseops.core.scoring.baseline_c import ScoredHypothesis, score_changes
from pulseops.models.evidence import Evidence

LOOKBACK = timedelta(minutes=60)


@dataclass(frozen=True)
class PipelineResult:
    trigger: dict
    window_start: datetime
    window_end: datetime
    baseline_end: datetime
    metrics: list[Evidence]
    changes: list[Evidence]
    candidates: list[Candidate]
    unmatched_changes: list[Evidence]
    graph: Graph
    upstream: list[str]
    hypotheses: list[ScoredHypothesis]
    metrics_examined: dict[str, list[str]]  # what was checked, for "against:" lines


def _dt(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        raise ValueError(f"timestamp must be timezone-aware: {s}")
    return dt


def run_pipeline(capture_dir: Path) -> PipelineResult:
    """capture_dir is the folder holding trigger.json, metrics.json, events.json, traces.json."""
    capture_dir = Path(capture_dir)
    trigger = json.loads((capture_dir / "trigger.json").read_text(encoding="utf-8-sig"))
    start = _dt(trigger["window_start"])
    end = _dt(trigger["alert_time"])  # never look past the alert

    backend = SnapshotBackend.from_dir(capture_dir)
    metrics = detect_all(backend, start, end)
    examined = {s: backend.list_metrics(s) for s in backend.list_services()}

    # Baseline end = timestamp of the first post-baseline sample.
    first_service = backend.list_services()[0]
    first_metric = backend.list_metrics(first_service)[0]
    series = backend.query_range(first_service, first_metric, start, end)
    baseline_end = series.time_at(min(DEFAULT_BASELINE_POINTS, len(series.values) - 1))

    changes = load_events(capture_dir / "events.json")
    graph = build_graph(load_spans(capture_dir / "traces.json"), start, baseline_end)
    upstream = upstream_candidates(graph, {m.service for m in metrics})

    return PipelineResult(
        trigger=trigger,
        window_start=start,
        window_end=end,
        baseline_end=baseline_end,
        metrics=metrics,
        changes=changes,
        candidates=align(changes, metrics, LOOKBACK),
        unmatched_changes=unmatched(changes, metrics, LOOKBACK),
        graph=graph,
        upstream=upstream,
        hypotheses=score_changes(changes, metrics, graph, LOOKBACK),
        metrics_examined=examined,
    )