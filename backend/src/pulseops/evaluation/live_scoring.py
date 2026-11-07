from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RunScore:
    outcome: str  # "accepted" or "fallback"
    retried: bool
    top_type: str | None = None
    trigger_in_top: bool = False  # top hypothesis cites the true trigger's evidence
    decoy_in_top: bool = False  # top hypothesis cites a decoy's evidence
    decoy_anywhere: bool = False  # any accepted hypothesis cites a decoy's evidence
    type_match: bool = False  # reported separately: claim_type is a weaker signal


def score_run(
    result: Any, trigger_id: str, decoy_ids: Sequence[str], expected_type: str
) -> RunScore:
    """Score one OrchestratorResult. The top hypothesis is the most confident accepted one."""
    retried = result.attempts > 1
    if result.used_fallback or not result.accepted:
        return RunScore(outcome="fallback", retried=retried)
    top = max(result.accepted, key=lambda h: h.confidence)
    cited_anywhere = {i for h in result.accepted for i in h.supporting}
    return RunScore(
        outcome="accepted",
        retried=retried,
        top_type=top.claim_type.value,
        trigger_in_top=trigger_id in top.supporting,
        decoy_in_top=any(d in top.supporting for d in decoy_ids),
        decoy_anywhere=any(d in cited_anywhere for d in decoy_ids),
        type_match=top.claim_type.value == expected_type,
    )