"""Run the real pipeline on pool_exhaustion and let a live model try to explain it.

Prints what the model said, what the citation checker accepted, and why anything was rejected.
Output goes to the terminal only. Nothing is written to disk.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from pulseops.ai.hypotheses.orchestrator import run_model_step
from pulseops.ai.llm_client.chain import model_from_env
from pulseops.ai.llm_client.client import LLMError
from pulseops.core.evidence_bundle.bundle import build_bundle
from pulseops.core.pipeline import run_pipeline

POOL = Path(__file__).resolve().parents[1] / "scenarios" / "pool_exhaustion" / "capture"
SYMPTOM = datetime(2026, 3, 14, 2, 14, tzinfo=timezone.utc)


class Recorder:
    """Wraps a model and keeps each raw reply so we can look at it afterwards."""

    def __init__(self, inner) -> None:
        self._inner = inner
        self.replies: list[str] = []

    def complete(self, prompt: str) -> str:
        reply = self._inner.complete(prompt)
        self.replies.append(reply)
        return reply


def main() -> int:
    load_dotenv()  # reads .env if present; variables already set in the shell win
    try:
        model = Recorder(model_from_env())
    except LLMError as e:
        print(f"FAILED to build model: {e}")
        return 1

    bundle = build_bundle(run_pipeline(POOL))
    print(f"bundle: {len(bundle.items)} evidence items")

    result = run_model_step(model, bundle, SYMPTOM)

    print(f"\nmodel calls that returned text: {len(model.replies)}")
    for i, raw in enumerate(model.replies, 1):
        print(f"--- raw reply {i} ({len(raw)} chars) ---")
        print(raw[:600] + (" ..." if len(raw) > 600 else ""))

    print("\n=== result ===")
    print(f"attempts:      {result.attempts}")
    print(f"used_fallback: {result.used_fallback}")
    print(f"reasons:       {result.reasons}")
    print(f"accepted:      {len(result.accepted)}")
    for h in result.accepted:
        print(f"  {h.id} | {h.claim_type} | conf={h.confidence} | cites={h.supporting}")
        print(f"    {h.title}")
    if result.used_fallback:
        print("\nFallback: the caller would now render the baseline C hypotheses instead.")
    return 0


if __name__ == "__main__":
    sys.exit(main())