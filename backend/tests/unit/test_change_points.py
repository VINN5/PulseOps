from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from pulseops.core.change_points.detector import detect_change_point
from pulseops.core.ingest.base import MissingTelemetry, Series
from pulseops.core.ingest.snapshot import SnapshotBackend

T0 = datetime(2026, 3, 14, 2, 0, tzinfo=timezone.utc)
STEP = 15  # seconds between samples


def make_series(n=120, step_at=None, before=100.0, after=150.0, noise=5.0, seed=0, spike_at=None):
    rng = np.random.default_rng(seed)
    y = before + rng.normal(0, noise, n)
    if step_at is not None:
        y[step_at:] += after - before
    if spike_at is not None:
        y[spike_at] += 500
    ts = T0.timestamp() + STEP * np.arange(n)
    return Series("orders", "db_pool_wait_p95", ts, y)


def test_upward_step_is_found_near_true_time():
    cp = detect_change_point(make_series(step_at=70))
    assert cp is not None and cp.direction == "up"
    assert abs(cp.index - 70) <= 3
    assert cp.after > cp.before


def test_downward_step_is_found():
    cp = detect_change_point(make_series(step_at=70, after=50.0))
    assert cp is not None and cp.direction == "down"
    assert abs(cp.index - 70) <= 3


def test_flat_noise_gives_no_change_point():
    for seed in range(20):
        assert detect_change_point(make_series(seed=seed)) is None


def test_single_spike_is_not_a_change_point():
    assert detect_change_point(make_series(spike_at=60)) is None


def test_snapshot_roundtrip_and_detection(tmp_path):
    import json

    s = make_series(step_at=70)
    data = {"orders/db_pool_wait_p95": {
        "timestamps": [(T0 + timedelta(seconds=STEP * i)).isoformat() for i in range(len(s.values))],
        "values": [float(v) for v in s.values],
    }}
    (tmp_path / "metrics.json").write_text(json.dumps(data), encoding="utf-8")

    backend = SnapshotBackend.from_dir(tmp_path)
    assert backend.list_metrics("orders") == ["db_pool_wait_p95"]
    got = backend.query_range("orders", "db_pool_wait_p95", T0, T0 + timedelta(hours=1))
    cp = detect_change_point(got)
    assert cp is not None
    injected = T0 + timedelta(seconds=STEP * 70)
    assert abs((cp.time - injected).total_seconds()) <= 3 * STEP


def test_missing_metric_raises_missing_telemetry():
    backend = SnapshotBackend({})
    with pytest.raises(MissingTelemetry):
        backend.query_range("orders", "nope", T0, T0 + timedelta(hours=1))
