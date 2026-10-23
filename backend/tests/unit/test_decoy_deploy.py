from datetime import datetime
from pathlib import Path

from pulseops.core.pipeline import run_pipeline
from pulseops.core.scoring.baseline_b import latest_change_before

CAP = Path(__file__).resolve().parents[3] / "scenarios" / "decoy_deploy" / "capture"


def _key(h):
    return h.change.data["external_id"] if h.change else "external"


def test_baseline_b_is_fooled_by_the_later_decoy():
    r = run_pipeline(CAP)
    picked = latest_change_before(r.changes, r.window_end)
    assert picked.data["external_id"] == "chg-2288"


def test_baseline_c_still_ranks_the_real_cause_first():
    r = run_pipeline(CAP)
    assert _key(r.hypotheses[0]) == "chg-2291"


def test_decoy_is_unmatched():
    r = run_pipeline(CAP)
    assert {e.data["external_id"] for e in r.unmatched_changes} == {"chg-2288"}
