r"""Generates a deterministic synthetic capture for the pool_exhaustion scenario.

Run: python scenarios\pool_exhaustion\make_synthetic_capture.py
Ground truth is written here, at generation time, never afterwards.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
OUT = HERE / "capture"
T0 = datetime(2026, 3, 14, 1, 50, tzinfo=timezone.utc)
STEP = 15  # seconds between samples
N = 120    # 30 minutes
SEED = 20260314

TOPOLOGY = [("checkout", "orders"), ("checkout", "payments")]


def idx(h: int, m: int, s: int = 0) -> int:
    t = datetime(2026, 3, 14, h, m, s, tzinfo=timezone.utc)
    return int((t - T0).total_seconds() // STEP)


def make(rng, base, noise, step_at=None, after=None, after_noise=None):
    y = rng.normal(base, noise, N)
    if step_at is not None:
        y[step_at:] = rng.normal(after, after_noise or noise, N - step_at)
    return np.clip(y, 0, None)


def make_traces(rng) -> list[dict]:
    """Two spans per edge per 15 s step. Durations follow the callee's latency metric."""
    orders_degraded_at = idx(2, 7)
    spans: list[dict] = []
    for i in range(N):
        for caller, callee in TOPOLOGY:
            for _ in range(2):
                t = T0 + timedelta(seconds=STEP * i + float(rng.uniform(0, STEP)))
                if callee == "orders":
                    mean, sd = (2800, 150) if i >= orders_degraded_at else (120, 6)
                else:
                    mean, sd = 90, 5
                dur = max(1.0, float(rng.normal(mean + 3, sd)))  # +3 ms call overhead
                spans.append({"caller": caller, "callee": callee,
                              "timestamp": t.isoformat(), "duration_ms": round(dur, 3)})
    spans.sort(key=lambda s: s["timestamp"])
    for n, s in enumerate(spans):
        s["trace_id"] = f"t{n:05d}"
    return spans


def main() -> None:
    rng = np.random.default_rng(SEED)
    ts = [(T0 + timedelta(seconds=STEP * i)).isoformat() for i in range(N)]
    series = {
        "orders/db_pool_wait_p95": make(rng, 4, 0.4, idx(2, 6), 910, 40),
        "orders/latency_p99": make(rng, 120, 6, idx(2, 7), 2800, 150),
        "orders/request_rate": make(rng, 200, 8),
        "checkout/latency_p99": make(rng, 420, 20, idx(2, 9), 3100, 150),
        "checkout/request_rate": make(rng, 350, 12),
        "payments/latency_p99": make(rng, 90, 5),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    metrics = {k: {"timestamps": ts, "values": [round(float(v), 3) for v in y]}
               for k, y in series.items()}
    (OUT / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")

    # Not consumed by the pipeline yet; the events stage will read this.
    events = [
        {"id": "chg-2291", "kind": "config_change", "service": "orders",
         "time": "2026-03-14T02:03:11+00:00", "summary": "db_pool_size 50 -> 10",
         "actor": "ci", "ref": "commit abc123"},
        {"id": "chg-2288", "kind": "deploy", "service": "payments",
         "time": "2026-03-14T01:11:40+00:00", "summary": "payments v2.14.0",
         "actor": "ci", "ref": "commit 9f3e1a"},
    ]
    (OUT / "events.json").write_text(json.dumps(events, indent=2), encoding="utf-8")

    trigger = {
        "service": "checkout", "symptom_metric": "latency_p99",
        "alert_time": "2026-03-14T02:14:00+00:00",
        "window_start": T0.isoformat(),
    }
    (OUT / "trigger.json").write_text(json.dumps(trigger, indent=2), encoding="utf-8")

    # Separate RNG so adding spans never shifts the metric draws above.
    spans = make_traces(np.random.default_rng(SEED + 1))
    (OUT / "traces.json").write_text(json.dumps(spans), encoding="utf-8")

    truth = {
        "service": "orders", "claim_type": "resource_exhaustion",
        "trigger": "chg-2291", "decoys": ["chg-2288"], "allowed_alternates": [],
        "injected_changes": {
            "orders/db_pool_wait_p95": "2026-03-14T02:06:00+00:00",
            "orders/latency_p99": "2026-03-14T02:07:00+00:00",
            "checkout/latency_p99": "2026-03-14T02:09:00+00:00",
        },
        "synthetic": True,
    }
    (HERE / "expected_root_cause.json").write_text(json.dumps(truth, indent=2), encoding="utf-8")
    print(f"wrote capture to {OUT}")


if __name__ == "__main__":
    main()