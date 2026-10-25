# 0012. Redaction is pattern-based and best-effort

Status: accepted (known limits)

## Context
`redact` replaces JWTs, bearer tokens, AWS and API keys, key=value secrets, emails
and IPv4 addresses with fixed placeholders. It is deterministic and idempotent on
the text it returns.

## Decision
Use ordered regular expressions with no dictionary, entropy test or model.

## Consequences
- A secret with no recognisable shape passes through, such as a free-form
  password or a customer name.
- `password: two words` redacts only the first word.
- IPv6 addresses and other identifiers are not covered.
- `counts` overcounts on a second pass: idempotence is promised for `text` only.
- The key=value rule has no skip for already-redacted values. That is deliberate,
  because skipping would let `password=[REDACTED:secret]realsecret` leak.