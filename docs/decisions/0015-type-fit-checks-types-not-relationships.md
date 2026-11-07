# 0015. Type-fit rules check evidence types, not relationships

Status: open (gap recorded, fix not yet chosen)

## Context
A live evaluation on decoy_deploy (one model, openai/gpt-oss-120b via Groq, 18 runs
over three batches) produced accepted hypotheses citing the unrelated payments deploy
in 3 runs. In two of them, seen in detail, the claim was bad_deploy at confidence
0.6 and 0.65. The top hypothesis never cited the decoy.

rules.py requires a bad_deploy to cite a deploy event and a metric change, that every
cited item is an allowed type, and that nothing postdates the symptom. It does not check
that the metric belongs to the deploy's service, that the two are close in time, or that
the services are connected in the dependency graph. In these scenarios the bundle holds
no payments metric, so a payments deploy cited with an orders metric passes. Hypotheses
citing only the deploy were rejected, because a metric is required.
slow_dependency is looser still: a single metric change satisfies it.

## Decision
Record the gap and pin current behaviour with characterization tests
(test_checker_known_gaps.py). The fix is not chosen yet.

## Options
- A. Require a cited change and at least one cited metric to share a service.
  Simple, but rejects genuine cross-service causes, which is the case the graph exists for.
- B. Same service, or the metric's service is downstream of the change's service in the graph.
  Needs graph data in the checker.
- C. Reuse the bundle's own record of which metrics are aligned to each change event.
  Needs a read of how alignment decides that, including cross-service cases.
- D. Accept the limit: treat model hypotheses as advisory and show baseline C beside them.

## Consequences
- The checker guarantees citations exist, fit the claim's type and predate the symptom.
  It does not guarantee they are relevant to each other.
- Baseline C scores the decoy deploy at 0.00, so the deterministic pipeline already
  disagrees with these hypotheses. A model hypothesis should not outrank baseline C
  on the checker's word alone.
- One model on one scenario family is a small sample. The true rate is unknown.