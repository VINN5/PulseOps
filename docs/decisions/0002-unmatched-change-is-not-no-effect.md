# 0002. An unmatched change event is not evidence of no effect

Status: accepted (known limit)

## Context
`align` links a change event to metric shifts on the same service within the
lookback window. Changes with no match are kept in the bundle as contradicting
evidence.

## Decision
Treat "no matching metric shift found" as weak contradiction only.

## Consequences
- A change can still be the cause when its effect shows on a different service
  (a dependency) or in a metric we do not collect.
- Reports must not state that an unmatched change "had no effect".