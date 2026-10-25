# 0005. Evidence bundle cap counts items, not tokens

Status: accepted (known limit)

## Context
`build_bundle` keeps at most `DEFAULT_MAX_ITEMS` (12) items by priority tier and
records the rest in `omitted` with a reason.

## Decision
Cap by item count. Do not measure size.

## Consequences
- Item size is unbounded: one item with a huge `summary` or `data` can dominate a
  prompt. Size limits must be added where the prompt is rendered.
- The checker rejects citations of omitted IDs as fabricated, so the model cannot
  cite evidence it was never shown.