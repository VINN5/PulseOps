# 0009. Property-test coverage caveats

Status: accepted (known limits)

## Context
`backend/tests/property` runs Hypothesis tests against the real bundle built from
`pool_exhaustion`. Mutation checks were run by hand: removing the checker's
fabricated-ID loop, and removing the redactor's `aws_key` rule.

## Decision
Rely on property tests plus example tests, and re-run mutation checks by hand when
rules change.

## Consequences
- Only one checker property guards the fabricated-ID rule. The other three
  properties still pass with that rule removed.
- Acceptance of valid bad_deploy and bad_config claims needed a targeted generator;
  with plain random generation it was near zero. Other claim types are not covered
  by an acceptance property.
- In the redactor, only the `aws_key` rule has a property test. Email, IPv4,
  bearer, JWT and key-value rules have one example case each.
- Mutation checks are manual. Nothing in CI runs them.