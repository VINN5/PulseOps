# 0008. must_state_absence is defined but not enforced

Status: accepted (known gap)

## Context
`ClaimRule` for `external_or_unknown` has a `must_state_absence` flag: such a
claim should say what was checked and not found. The `Hypothesis` model has no
field for that, and the checker does not look for it.

## Decision
Accept `external_or_unknown` claims with no supporting evidence, as the checker
does today.

## Consequences
- A model can emit "external or unknown" with no checked-and-absent statement, as
  a way to avoid being wrong. The checker accepts it.
- The fix is an optional field on `Hypothesis` (what was checked) plus a checker
  rule that requires it for this claim type.