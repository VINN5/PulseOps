import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from pulseops.core.change_points.catalogue import subtype_for
from pulseops.core.change_points.detector import detect_change_point
from pulseops.core.change_points.evidence import change_point_to_evidence, detect_all
from pulseops.core.ingest.base import Series
from pulseops.core.ingest.snapshot import SnapshotBackend
from pulseops.models.evidence import Evidence, EvidenceType

T0 = datetime(2026, 3, 14, 2, 0, tzinfo=timezone.utc)
SCENARIO = Path(__file__).resolve().parents[3] / "scenarios" / "pool_exhaustion"


def make_series(metric="db_pool_wait_p95", service="orders", step_at=70):
    rng = np.random.default_rng(0)
    y = 100.0 + rng.normal(0, 5.0, 120)
    y[step_at:] += 50.0
    ts = T0.timestamp() + 15 * np.arange(120)
    return Series(service, metric, ts, y)


def test_change_point_becomes_typed_evidence():
    s = make_series()
    cp = detect_change_point(s)
    assert cp is not None
    e = change_point_to_evidence(cp, s)
    assert e.type == EvidenceType.METRIC_CHANGE
    assert e.subtype == "saturation"
    assert e.service == "orders"
    assert e.id.startswith("E-met-")
    assert e.event_time == cp.time
    assert e.window_start <= e.event_time <= e.window_end
    assert set(e.data) == {"metric", "before", "after", "score", "direction", "change_time"}
    assert e.data["before"] < e.data["after"] and e.data["direction"] == "up"
    assert Evidence.model_validate(e.model_dump()) == e  # id and hash survive a round trip


def test_conversion_is_deterministic():
    s = make_series()
    cp = detect_change_point(s)
    assert change_point_to_evidence(cp, s).id == change_point_to_evidence(cp, s).id


def test_unknown_metric_has_no_subtype():
    assert subtype_for("db_pool_wait_p95") == "saturation"
    assert subtype_for("something_new") is None


def _run_scenario():
    assert SCENARIO.exists(), "run scenarios/pool_exhaustion/make_synthetic_capture.py first"
    cap = SCENARIO / "capture"
    trig = json.loads((cap / "trigger.json").read_text(encoding="utf-8"))
    backend = SnapshotBackend.from_dir(cap)
    return detect_all(backend, datetime.fromisoformat(trig["window_start"]),
                      datetime.fromisoformat(trig["alert_time"]))


def test_pool_exhaustion_capture_end_to_end():
    evidence = _run_scenario()
    found = {(e.service, e.data["metric"]): e for e in evidence}
    # flat series (request rates, payments) must stay quiet
    assert set(found) == {
        ("orders", "db_pool_wait_p95"),
        ("orders", "latency_p99"),
        ("checkout", "latency_p99"),
    }
    pool = found[("orders", "db_pool_wait_p95")]
    assert pool.subtype == "saturation"
    expected = datetime(2026, 3, 14, 2, 6, tzinfo=timezone.utc)
    assert abs((pool.event_time - expected).total_seconds()) <= 2 * 15
    # upstream-most degradation comes first in time
    assert [(e.service, e.data["metric"]) for e in evidence] == [
        ("orders", "db_pool_wait_p95"), ("orders", "latency_p99"), ("checkout", "latency_p99"),
    ]


def test_scenario_run_is_reproducible():
    assert [e.id for e in _run_scenario()] == [e.id for e in _run_scenario()]
