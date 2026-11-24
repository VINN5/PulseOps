# 0019. Prompt v3 asks for empty verification

Status: decided (small sample, one model)

## Context
Under prompt v2, 6 of 28 model replies from nvidia/nemotron-3.5-lightning:free were not valid
JSON. In all six, the closing brackets of the verification list were in the wrong order. Nothing
in the repo executes verification requests, so the nested structure costs output and risk without
being used.

## Decision
Prompt v3 tells the model that nothing runs verification requests and to use [] unless a specific
check is essential. The example object has verification []. The schema, parser and checker are
unchanged, so a model may still include requests.

## Evidence
Ten runs of decoy_deploy on the same model, with the same token limit and timeout as the previous
batch. 10 of 10 accepted, 1 needed a retry (a reply that cited only the config change, rejected
with type_fit and unlinked_change; the retry was accepted). 0 of 11 replies were unparseable. If
the true rate were still about 21%, none in 11 would happen about 7% of the time. Against the
previous batch alone (2 of 12) the difference is weaker, about 13%. Two connection drops in one
run were retried by the client and are visible only in the log.

## Consequences
- This is suggestive, not proven: one model, one scenario, a different day and free-tier load.
- Whether the model actually left verification empty was not checked; live_eval does not print it.
- When verification execution is built, the prompt must change again and the version bump.
- The model still gave one hypothesis per run, so the unlinked_change rule against a decoy was
  not exercised on this model. Claim type matched the answer key in 1 of 10 runs.
