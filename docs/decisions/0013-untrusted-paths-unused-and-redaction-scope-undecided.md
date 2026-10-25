# 0013. Prompt rendering: redaction scope and untrusted_paths

Status: decided (partial)

## Context
`Evidence.untrusted_paths` is defined and hashed but read by nothing. Free-text
fields on `Evidence` are `summary`, `service`, `subtype`, `data` and `source`.

## Decision
`ai/prompts/prompt.py` (version v1) renders only ID, type, subtype, service, time
and summary. Each free-text field is redacted, has `<` and `>` replaced, is
flattened to one line, then truncated (200 chars, 40 for subtype and service).
Redaction runs before truncation. `data` and `source` are not rendered.
Evidence sits between fixed markers, with an instruction that it is untrusted data.

## Consequences
- `untrusted_paths` is still unused. The whole summary is treated as untrusted
  and the model gets no `data` values, so the model cannot see before/after
  numbers. Adding `data` keys later needs its own decision and tests.
- Truncation limits are characters, not tokens (see 0005).
- The instruction to ignore embedded commands is a mitigation, not a guarantee.
  The checker (0010) remains the real control.