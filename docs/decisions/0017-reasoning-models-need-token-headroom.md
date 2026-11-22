# 0017. Reasoning models need token headroom; empty replies carry the finish reason

Status: decided

## Context
Six live calls to nvidia/nemotron-3.5-lightning:free (via OpenRouter) all returned HTTP 200
but were counted as model_error with no status. A probe showed why. With max_tokens=1500 the
model spent all 1500 tokens on reasoning (finish_reason=length) and returned content=None. With
max_tokens=4000 it used 2651 reasoning tokens, finished (stop) and returned valid-looking JSON
that cited the true cause. This was one probe per setting; reasoning length varies per call.
openai/gpt-oss-120b is also a reasoning model, and some of its bad_json replies may have been
replies cut off at 1500. That was not checked, because Groq was unreachable.

## Decision
Models built by make_model and make_chain default to max_tokens=4000, overridable with
PULSEOPS_MAX_TOKENS (a positive integer, otherwise an error). An empty reply raises LLMError with
status 200 and the sanitised finish reason as its code. The OpenAI-compatible client records
finish_reason, and Recorder counts it, so the evaluation summary shows how generation stopped.

## Consequences
- 4000 is not proven sufficient. It left about 1350 tokens spare in one sample.
- More output tokens means slower calls; calls already took 15-26 seconds at 1500.
- A non-empty reply that was cut off at the limit still fails later as bad_json. It is
  visible only through the finish-reason counts.
- FallbackModel does not forward finish_reason, so chain runs do not report it yet.
- Constructor defaults stay at 1500; only the factories apply the new default.
