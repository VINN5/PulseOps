from datetime import datetime
from pathlib import Path

from pulseops.core.pipeline import run_pipeline

CAP = Path(__file__).resolve().parents[3] / "scenarios" / "pool_exhaustion" / "capture"


def _key(h):
    return h.change.data["external_id"] if h.change else "external"


def test_baseline_end_is_forty_samples_in():
    r = run_pipeline(CAP)
    assert r.baseline_end == datetime.fromisoformat("2026-03-14T02:00:00+00:00")


def test_pipeline_ranking_matches_scoring_tests():
    r = run_pipeline(CAP)
    assert [_key(h) for h in r.hypotheses] == ["chg-2291", "external", "chg-2288"]


def test_pipeline_finds_orders_upstream_and_decoy_unmatched():
    r = run_pipeline(CAP)
    assert r.upstream == ["orders"]
    assert {e.data["external_id"] for e in r.unmatched_changes} == {"chg-2288"}


def test_pipeline_records_what_was_examined():
    r = run_pipeline(CAP)
    assert "latency_p99" in r.metrics_examined["payments"]


def test_pipeline_uses_detector_baseline_constant():
    from pulseops.core import pipeline
    from pulseops.core.change_points.detector import DEFAULT_BASELINE_POINTS

    assert pipeline.DEFAULT_BASELINE_POINTS is DEFAULT_BASELINE_POINTS
    assert not hasattr(pipeline, "BASELINE_SAMPLES")