# 0011. Retry feedback must not repeat model-supplied text

Status: fixed

## Context
The first orchestrator built retry feedback from `Violation.detail`. Those strings
echo values the model supplied: cited IDs, template names, service names. The
hostile-output tests showed a marker planted in those fields appearing in the
second prompt. A mutation check confirmed four leaking cases.

## Decision
Build retry feedback from fixed hint text keyed by violation code (`_HINTS` in
`orchestrator.py`).

## Consequences
- The retry prompt says which rule failed and nothing the model wrote.
- Any new violation code needs an entry in `_HINTS`. Without one it falls back to
  "rule violated".
- `Violation.detail` is still shown to developers, so logs and reports must treat
  it as untrusted.