# 0007. time_sanity violations are detected by matching message text

Status: accepted (known weakness)

## Context
`check_type_fit` in `rules.py` returns violation strings. The checker assigns the
code `time_sanity` when a message contains "postdates the symptom", and
`type_fit` otherwise.

## Decision
Keep the string match for now.

## Consequences
- Rewording the message in `rules.py` silently turns time_sanity violations into
  type_fit violations. Nothing fails; the code is simply wrong.
- Retry hints and reason codes then lose their meaning.
- The fix is for `check_type_fit` to return structured violations (code plus
  message), not strings.