from pathlib import Path

from pulseops.core.pipeline import run_pipeline
from pulseops.core.report import render_report

CAP = Path(__file__).resolve().parents[3] / "scenarios" / "pool_exhaustion" / "capture"


def test_report_mentions_cause_and_phrases_decoy_as_checked():
    text = render_report(run_pipeline(CAP))
    assert "chg-2291" in text
    assert "no payments metric change detected within 60 min of chg-2288" in text
    assert "examined: latency_p99" in text


def test_report_never_claims_no_effect():
    assert "no effect" not in render_report(run_pipeline(CAP))


def test_report_lists_hypotheses_in_ranked_order():
    text = render_report(run_pipeline(CAP))
    assert text.index("chg-2291 on orders") < text.index("external_or_unknown") \
        < text.index("chg-2288 on payments")

def test_for_line_cites_supporting_metric_ids():
    from pulseops.core.evidence_bundle.bundle import build_bundle

    r = run_pipeline(CAP)
    b = build_bundle(r)
    change = next(c for c in r.changes if c.data["external_id"] == "chg-2291")
    supporting = b.supporting[change.id]
    assert supporting
    for_line = next(ln for ln in render_report(r).splitlines() if ln.strip().startswith("for:"))
    assert change.id in for_line
    assert all(i in for_line for i in supporting)
    checkout = next(m for m in r.metrics if m.service == "checkout")
    assert checkout.id not in for_line  # different service, not a supporting ID


def test_only_the_matched_change_gets_a_for_line():
    text = render_report(run_pipeline(CAP))
    assert sum(1 for ln in text.splitlines() if ln.strip().startswith("for:")) == 1
