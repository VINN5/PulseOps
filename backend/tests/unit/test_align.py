import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pulseops.core.change_points.evidence import detect_all
from pulseops.core.events.align import align, load_events, unmatched
from pulseops.core.ingest.snapshot import SnapshotBackend
from pulseops.models.evidence import Evidence, EvidenceType

CAP = Path(__file__).resolve().parents[3] / "scenarios" / "pool_exhaustion" / "capture"


def _inputs():
    trig = json.loads((CAP / "trigger.json").read_text(encoding="utf-8"))
    backend = SnapshotBackend.from_dir(CAP)
    metrics = detect_all(backend, datetime.fromisoformat(trig["window_start"]),
                         datetime.fromisoformat(trig["alert_time"]))
    return load_events(CAP / "events.json"), metrics


def _ext(c):
    return c.change.data["external_id"]


def _ext_ev(e):
    return e.data["external_id"]


def _change(service, t, ext):
    return Evidence.build(
        type=EvidenceType.CHANGE_EVENT, subtype="deploy", service=service,
        event_time=t, window_start=t, window_end=t,
        summary=ext, data={"external_id": ext})


def test_events_load_as_change_evidence():
    changes, _ = _inputs()
    assert all(c.type == EvidenceType.CHANGE_EVENT for c in changes)
    assert {c.subtype for c in changes} == {"config_change", "deploy"}
    assert {c.data["external_id"] for c in changes} == {"chg-2291", "chg-2288"}


def test_config_change_ranks_first_and_links_to_pool_wait():
    changes, metrics = _inputs()
    cands = align(changes, metrics)
    assert _ext(cands[0]) == "chg-2291"
    assert cands[0].metric.data["metric"] == "db_pool_wait_p95"
    assert cands[0].relation == "same_service"
    assert 160 <= cands[0].delta_seconds <= 180


def test_decoy_is_kept_but_ranked_below_and_unrelated():
    changes, metrics = _inputs()
    cands = align(changes, metrics)
    decoys = [c for c in cands if _ext(c) == "chg-2288"]
    assert decoys and all(c.relation == "unrelated" for c in decoys)
    first_decoy = min(i for i, c in enumerate(cands) if _ext(c) == "chg-2288")
    assert first_decoy > 0


def test_lookback_is_respected():
    changes, metrics = _inputs()
    cands = align(changes, metrics, lookback=timedelta(seconds=60))
    assert cands == []


def test_change_after_its_supposed_effect_is_never_a_candidate():
    _, metrics = _inputs()
    late = Evidence.build(
        type=EvidenceType.CHANGE_EVENT, subtype="deploy", service="orders",
        event_time=datetime(2026, 3, 14, 2, 20, tzinfo=timezone.utc),
        window_start=datetime(2026, 3, 14, 2, 20, tzinfo=timezone.utc),
        window_end=datetime(2026, 3, 14, 2, 20, tzinfo=timezone.utc),
        summary="late deploy", data={"external_id": "chg-late"})
    assert align([late], metrics) == []


def test_alignment_is_deterministic():
    changes, metrics = _inputs()
    a = [(c.change.id, c.metric.id) for c in align(changes, metrics)]
    b = [(c.change.id, c.metric.id) for c in align(list(reversed(changes)), metrics)]
    assert a == b


def test_decoy_is_unmatched_and_real_cause_is_not():
    changes, metrics = _inputs()
    ids = {_ext_ev(e) for e in unmatched(changes, metrics)}
    assert "chg-2288" in ids
    assert "chg-2291" not in ids


def test_unmatched_agrees_with_align():
    changes, metrics = _inputs()
    matched = {c.change.id for c in align(changes, metrics)
               if c.relation == "same_service"}
    assert {e.id for e in unmatched(changes, metrics)} == \
        {c.id for c in changes} - matched


def test_unmatched_boundaries():
    _, metrics = _inputs()
    orders = sorted((m for m in metrics if m.service == "orders"),
                    key=lambda m: m.event_time)
    first, last = orders[0], orders[-1]
    hour = timedelta(minutes=60)
    s = timedelta(seconds=1)

    # upper bound inclusive: first metric lands exactly at the lookback edge
    assert unmatched([_change("orders", first.event_time - hour, "a")], metrics) == []
    # one second past the edge: no orders metric is within reach
    assert len(unmatched([_change("orders", first.event_time - hour - s, "b")], metrics)) == 1
    # metric at the same instant is not "following"
    assert len(unmatched([_change("orders", last.event_time, "c")], metrics)) == 1
    # metric before the change
    assert len(unmatched([_change("orders", last.event_time + s, "d")], metrics)) == 1
    # only other-service metrics follow
    assert len(unmatched([_change("inventory", first.event_time - timedelta(minutes=5), "e")], metrics)) == 1


def test_unmatched_preserves_input_order_and_handles_empty():
    changes, metrics = _inputs()
    assert unmatched([], metrics) == []
    assert unmatched(changes, []) == changes