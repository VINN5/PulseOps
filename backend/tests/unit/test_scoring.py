import json
from datetime import datetime
from pathlib import Path

from pulseops.core.change_points.evidence import detect_all
from pulseops.core.events.align import load_events
from pulseops.core.graph.graph import build_graph
from pulseops.core.graph.spans import load_spans
from pulseops.core.ingest.snapshot import SnapshotBackend
from pulseops.core.scoring.baseline_c import EXTERNAL_SCORE, score_changes

CAP = Path(__file__).resolve().parents[3] / "scenarios" / "pool_exhaustion" / "capture"
T0 = datetime.fromisoformat("2026-03-14T01:50:00+00:00")
BASE_END = datetime.fromisoformat("2026-03-14T02:00:00+00:00")


def _inputs():
    trig = json.loads((CAP / "trigger.json").read_text(encoding="utf-8"))
    metrics = detect_all(SnapshotBackend.from_dir(CAP),
                         datetime.fromisoformat(trig["window_start"]),
                         datetime.fromisoformat(trig["alert_time"]))
    changes = load_events(CAP / "events.json")
    graph = build_graph(load_spans(CAP / "traces.json"), T0, BASE_END)
    return changes, metrics, graph


def _key(h):
    return h.change.data["external_id"] if h.change else "external"


def test_real_cause_first_then_external_then_decoy():
    changes, metrics, graph = _inputs()
    ranked = score_changes(changes, metrics, graph)
    assert [_key(h) for h in ranked] == ["chg-2291", "external", "chg-2288"]


def test_decoy_has_no_same_service_match():
    changes, metrics, graph = _inputs()
    decoy = next(h for h in score_changes(changes, metrics, graph)
                 if h.change and h.change.data["external_id"] == "chg-2288")
    assert decoy.same_service == 0.0
    assert decoy.proximity == 0.0
    assert decoy.topology == 0.0
    assert decoy.score < EXTERNAL_SCORE


def test_no_changes_returns_only_external():
    _, metrics, graph = _inputs()
    ranked = score_changes([], metrics, graph)
    assert [_key(h) for h in ranked] == ["external"]
    assert ranked[0].score == EXTERNAL_SCORE


def test_input_order_does_not_matter():
    changes, metrics, graph = _inputs()
    a = [(_key(h), h.score) for h in score_changes(changes, metrics, graph)]
    b = [(_key(h), h.score) for h in score_changes(list(reversed(changes)),
                                                   list(reversed(metrics)), graph)]
    assert a == b


def test_features_and_score_stay_in_unit_interval():
    changes, metrics, graph = _inputs()
    for h in score_changes(changes, metrics, graph):
        for v in (h.same_service, h.proximity, h.topology, h.magnitude, h.score):
            assert 0.0 <= v <= 1.0


def test_normal_case_does_not_use_fallback():
    changes, metrics, graph = _inputs()
    assert all(not h.fallback for h in score_changes(changes, metrics, graph))


def test_cycle_falls_back_to_earliest_change_point():
    changes, metrics, _ = _inputs()
    cyc = {"orders": frozenset({"checkout"}), "checkout": frozenset({"orders"})}
    ranked = score_changes(changes, metrics, cyc)
    assert all(h.fallback for h in ranked)
    real = next(h for h in ranked if h.change and h.change.data["external_id"] == "chg-2291")
    assert real.topology == 1.0