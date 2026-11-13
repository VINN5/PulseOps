# 0016. LLM errors carry a status and a sanitised code, never provider text

Status: decided

## Context
During an outage, a 403 (Groq blocking the network), a 400 (an OpenAI key sent to
OpenRouter) and two 429s (a shared upstream pool) all ended up as "model_error" in the
evaluation summary. The client kept only a short reason, because the provider's message
text can echo request content. Finding the cause took many rounds of one-off commands.

## Decision
LLMError carries status and code. code comes from error.type, error.code or
error.metadata.provider_error_code, and is kept only if it matches [A-Za-z0-9_.:/-]{1,60}.
Message text is never kept. 429 retries wait 5s doubling to a 30s cap, and a Retry-After
header is honoured up to 30s. The OpenAI-compatible client records the model that answered
(the response's model field, same sanitising), because routers such as openrouter/free
can swap models between calls.

## Consequences
- A provider can still return a short misleading code. It is displayed, never trusted.
- The message text is still not available in the app. A one-off command shows the body.
- Three 429s now cost about 15s of waiting per call, up from about 3s, so evaluations
  that hit rate limits run slower.
- The orchestrator still reports model_error. The per-status counts need the chain and
  the evaluation script to pass the status through; see the next change.
- Update: FallbackModel now raises with the last link's status and code and records which link answered. live_eval.py prints failure counts by status/code and the answering models, via evaluation/recorder.py.
- Update: FallbackModel now raises with the last link's status and code and records which link answered. live_eval.py prints failure counts by status/code and the answering models, via evaluation/recorder.py.
- Update: FallbackModel now raises with the last link's status and code and records which link answered. live_eval.py prints failure counts by status/code and the answering models, via evaluation/recorder.py.
