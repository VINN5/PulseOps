# 0015. Type-fit checks types, not relationships

Status: decided (partial)

## Context
A live evaluation on decoy_deploy (one model, openai/gpt-oss-120b via Groq, 18 runs
over three batches) produced accepted hypotheses citing the unrelated payments deploy
in 3 runs, two of them seen in detail: bad_deploy at confidence 0.6 and 0.65. The top
hypothesis never cited the decoy.

rules.py requires a bad_deploy to cite a deploy event and a metric change, that every
cited item is an allowed type, and that nothing postdates the symptom. It does not check
that the evidence is related. In these scenarios no payments metric follows the payments
deploy, so citing it beside any orders metric passed.

## Decision
checker.py now enforces: every cited change event must be linked to at least one cited
metric, where "linked" is the bundle's own same-service alignment (bundle.supporting).
Violation code: unlinked_change. A fixed retry hint exists for it in the orchestrator.

## Consequences
- A deploy on service A that really causes a metric change on service B can no longer be
  cited as bad_deploy, because the pipeline links changes only to same-service metrics.
  Such cases must go through slow_dependency. This follows from how alignment works and
  is a known cost, not a fix for it.
- slow_dependency is still loose: a single metric change satisfies it (pinned by a test).
- The rule applies to every cited change, so a hypothesis citing the true cause plus a
  decoy is rejected as a whole.
- Partial acceptance skips the retry, so the model rarely sees the hint when other
  hypotheses in the same reply passed.
- Live re-run after the rule (decoy_deploy, 10 runs, same model): decoy cited anywhere 0/10, trigger cited in top 8/10. The two misses were fallbacks; their reasons were not inspected, and both rate-limit errors and unparseable replies occurred. 10 runs is a small sample.
- Three older test files built their "valid" claim from the first deploy in the bundle, which is the decoy. They were changed to the real cause (the orders config change, bad_config). The old checker could not tell the difference.
- test_accepted_deploy_and_config_claims_cite_the_right_event_kind can no longer accept a bad_deploy on the pool_exhaustion bundle, because its only deploy has no linked metric. That branch is vacuous until a scenario has a deploy with linked metrics.