import json
from datetime import datetime, timezone
from pathlib import Path

from pulseops.core.change_points.evidence import detect_all
from pulseops.core.graph.graph import build_graph, upstream_candidates
from pulseops.core.graph.spans import load_spans
from pulseops.core.ingest.snapshot import SnapshotBackend

CAP = Path(__file__).resolve().parents[3] / "scenarios" / "pool_exhaustion" / "capture"
T0 = datetime(2026, 3, 14, 1, 50, tzinfo=timezone.utc)
BASE_END = datetime(2026, 3, 14, 2, 0, tzinfo=timezone.utc)


def _spans():
    return load_spans(CAP / "traces.json")


def test_baseline_graph_edges():
    g = build_graph(_spans(), T0, BASE_END)
    assert g == {
        "checkout": frozenset({"orders", "payments"}),
        "orders": frozenset(),
        "payments": frozenset(),
    }


def test_empty_window_gives_empty_graph():
    assert build_graph(_spans(), T0, T0) == {}


def test_deepest_degraded_callee_is_orders():
    trig = json.loads((CAP / "trigger.json").read_text(encoding="utf-8"))
    metrics = detect_all(SnapshotBackend.from_dir(CAP),
                         datetime.fromisoformat(trig["window_start"]),
                         datetime.fromisoformat(trig["alert_time"]))
    degraded = {m.service for m in metrics}
    assert degraded == {"orders", "checkout"}
    g = build_graph(_spans(), T0, BASE_END)
    assert upstream_candidates(g, degraded) == ["orders"]


def test_missing_instrumentation_misblames_the_caller():
    # Drop checkout->orders spans: the edge is invisible, so checkout looks like a leaf cause.
    spans = [s for s in _spans() if s.callee != "orders"]
    g = build_graph(spans, T0, BASE_END)
    assert upstream_candidates(g, {"orders", "checkout"}) == ["checkout", "orders"]


def test_cycle_yields_no_candidate():
    g = {"a": frozenset({"b"}), "b": frozenset({"a"})}
    assert upstream_candidates(g, {"a", "b"}) == []


def test_shared_dependency_is_the_only_candidate():
    g = {"a": frozenset({"c"}), "b": frozenset({"c"}), "c": frozenset()}
    assert upstream_candidates(g, {"a", "b", "c"}) == ["c"]


def test_self_edge_is_ignored():
    g = {"a": frozenset({"a"})}
    assert upstream_candidates(g, {"a"}) == ["a"]