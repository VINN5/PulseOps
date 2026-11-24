from __future__ import annotations

from pathlib import Path

from pulseops.ai.hypotheses.orchestrator import parse_output
from pulseops.ai.prompts.prompt import PROMPT_VERSION, build_prompt
from pulseops.core.evidence_bundle.bundle import build_bundle
from pulseops.core.pipeline import run_pipeline

POOL = Path(__file__).resolve().parents[3] / "scenarios" / "pool_exhaustion" / "capture"
BUNDLE = build_bundle(run_pipeline(POOL))


def example_hypotheses():
    p = build_prompt(BUNDLE)
    line = next(ln for ln in p.splitlines() if ln.startswith("Example"))
    return parse_output(line[line.index("[") :])


def test_version_is_v3():
    assert PROMPT_VERSION == "v3"
    assert "prompt v3" in build_prompt(BUNDLE)


def test_example_shows_an_empty_verification_list():
    assert example_hypotheses()[0].verification == []


def test_prompt_tells_the_model_verification_is_not_run_and_defaults_to_empty():
    p = build_prompt(BUNDLE)
    assert "Nothing in this version runs verification requests" in p
    assert "use []" in p