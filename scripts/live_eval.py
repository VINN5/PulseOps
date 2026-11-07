"""Run a live model over a scenario several times and score it against the expected answer.

Usage:
    python scripts/live_eval.py [scenario] [--runs N] [--pause SECONDS] [--show]

--show prints every hypothesis the model proposed, whether the checker accepted it,
which rules rejected it, and what each cited ID refers to.
Output goes to the terminal only.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from pulseops.ai.citation_checker.checker import check_all
from pulseops.ai.hypotheses.orchestrator import parse_output, run_model_step
from pulseops.ai.llm_client.chain import model_from_env
from pulseops.ai.llm_client.client import LLMError
from pulseops.core.evidence_bundle.bundle import build_bundle
from pulseops.core.pipeline import run_pipeline
from pulseops.evaluation.live_scoring import score_run

ROOT = Path(__file__).resolve().parents[1]


class Recorder:
    """Wraps a model and keeps each raw reply so --show can re-check it afterwards."""

    def __init__(self, inner) -> None:
        self._inner = inner
        self.replies: list[str] = []

    def complete(self, prompt: str) -> str:
        reply = self._inner.complete(prompt)
        self.replies.append(reply)
        return reply


def label(model) -> str:
    parts = getattr(model, "models", None) or [model]
    return ", ".join(
        f"{getattr(m, 'provider_name', 'anthropic')}/"
        f"{getattr(m, 'model_name', None) or getattr(m, '_model', '?')}"
        for m in parts
    )


def evidence_id(pipeline_result, external_id: str) -> str | None:
    for c in pipeline_result.changes:
        if c.data.get("external_id") == external_id:
            return c.id
    return None


def show_replies(replies: list[str], bundle, symptom: datetime, names: dict[str, str]) -> None:
    for n, raw in enumerate(replies, 1):
        print(f"  reply {n}:")
        try:
            hypotheses = parse_output(raw)
        except ValueError as e:
            head = raw[:300].replace("\n", "\\n")
            tail = raw[-120:].replace("\n", "\\n")
            print(f"    unparseable ({e}), {len(raw)} chars")
            print(f"      starts: {head}")
            print(f"      ends:   {tail}")
            continue
        checked = check_all(hypotheses, bundle, symptom)
        for h in checked.accepted:
            print(f"    ACCEPT {h.id} {h.claim_type.value} conf={h.confidence}")
            for i in h.supporting:
                print(f"        cites {i} ({names.get(i, '?')})")
        for h, violations in checked.rejected:
            codes = sorted({v.code for v in violations})
            print(f"    REJECT {h.id} {h.claim_type.value} conf={h.confidence} codes={codes}")
            for i in h.supporting:
                print(f"        cites {i} ({names.get(i, '?')})")


def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario", nargs="?", default="pool_exhaustion")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--pause", type=float, default=3.0)
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()

    base = ROOT / "scenarios" / args.scenario
    if not base.is_dir():
        print(f"no such scenario: {args.scenario}")
        return 1
    expected = json.loads((base / "expected_root_cause.json").read_text(encoding="utf-8"))
    trigger = json.loads((base / "capture" / "trigger.json").read_text(encoding="utf-8"))
    symptom = datetime.fromisoformat(trigger["alert_time"])

    pipeline_result = run_pipeline(base / "capture")
    bundle = build_bundle(pipeline_result)
    names = {e.id: f"{e.type.value}: {e.summary[:50]}" for e in bundle.items}
    trigger_id = evidence_id(pipeline_result, expected["trigger"])
    decoy_ids = [d for d in (evidence_id(pipeline_result, x) for x in expected["decoys"]) if d]
    if trigger_id is None:
        print(f"could not find evidence for trigger {expected['trigger']}")
        return 1

    try:
        inner = model_from_env()
    except LLMError as e:
        print(f"FAILED to build model: {e}")
        return 1
    model = Recorder(inner)

    print(f"scenario={args.scenario} model={label(inner)} runs={args.runs}")
    print(f"trigger={trigger_id} decoys={decoy_ids} expected_type={expected['claim_type']}")

    scores = []
    reasons: Counter[str] = Counter()
    for i in range(1, args.runs + 1):
        start = len(model.replies)
        result = run_model_step(model, bundle, symptom)
        s = score_run(result, trigger_id, decoy_ids, expected["claim_type"])
        scores.append(s)
        reasons.update(result.reasons)
        print(
            f"run {i}: {s.outcome:8} attempts={result.attempts} top={s.top_type} "
            f"trigger_in_top={s.trigger_in_top} decoy_in_top={s.decoy_in_top} "
            f"decoy_anywhere={s.decoy_anywhere} type_match={s.type_match}"
        )
        if args.show:
            show_replies(model.replies[start:], bundle, symptom, names)
        if i < args.runs:
            time.sleep(args.pause)

    n = len(scores)
    print(f"\n=== summary over {n} runs ===")
    print(f"accepted (no fallback):  {sum(s.outcome == 'accepted' for s in scores)}/{n}")
    print(f"needed a retry:          {sum(s.retried for s in scores)}/{n}")
    print(f"trigger cited in top:    {sum(s.trigger_in_top for s in scores)}/{n}")
    print(f"decoy cited in top:      {sum(s.decoy_in_top for s in scores)}/{n}")
    print(f"decoy cited anywhere:    {sum(s.decoy_anywhere for s in scores)}/{n}")
    print(f"claim_type matched:      {sum(s.type_match for s in scores)}/{n}")
    print(f"rejection reasons:       {dict(reasons) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())