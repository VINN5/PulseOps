# 0003. Dependency graph: hidden edges and cycles

Status: accepted (known limits)

## Context
`build_graph` derives caller to callee edges from spans in the window.
`upstream_candidates` picks the deepest degraded callee. Missing or cyclic
graphs return no candidates, and scoring falls back to the earliest change point.

## Decision
Build the graph from observed spans only, with no inferred or configured edges.

## Consequences
- Dependencies with no spans in the window (queues, caches, sampled-out traces)
  are invisible, so their failures are misattributed.
- Cycles disable the topology feature instead of being resolved.
- The fallback path is flagged (`fallback=True`) and must stay visible in reports.