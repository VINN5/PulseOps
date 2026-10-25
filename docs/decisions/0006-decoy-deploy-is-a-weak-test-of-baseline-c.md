# 0006. The decoy_deploy scenario is a weak test of baseline C

Status: accepted (known limit)

## Context
`scenarios/decoy_deploy` moves the decoy deploy (chg-2288) to 02:09, after the
real cause (chg-2291, 02:03) and before the alert. Baseline B picks the decoy;
baseline C ranks the real cause first.

## Decision
Keep the scenario as a regression test that B fails and C passes.

## Consequences
- The decoy sits on `payments`, which shows no metric change, so the
  same-service feature alone defeats it. The scenario does not test the
  proximity or topology features.
- Passing it is weak evidence that C is good. A harder variant is needed, such as
  a decoy on a degraded service near its own latency shift.
- Both scenarios come from one generator and one seed, so they are not
  independent samples.