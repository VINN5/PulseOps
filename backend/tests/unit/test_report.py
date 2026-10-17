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