# 0013. untrusted_paths is unused and redaction scope is undecided

Status: open

## Context
`Evidence.untrusted_paths` is defined and included in the content hash, but no
other code reads it. The redactor works on plain strings and is not yet called by
anything. `build_prompt` currently sends only evidence IDs.

## Decision
Defer. When evidence summaries are rendered into a prompt, decide which fields are
redacted and whether `untrusted_paths` marks free-text values from outside.

## Consequences
- Until then, no evidence text reaches a model, so redaction has no effect.
- The planned key test is a secret planted in an evidence summary that must not
  appear in the prompt.
- Size limits on rendered fields belong in the same change (see 0005).