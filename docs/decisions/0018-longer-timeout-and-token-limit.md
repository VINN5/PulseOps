# 0018. Longer timeout and token limit after a 10-run live evaluation

Status: decided (values are judgment calls, to be re-measured)

## Context
Ten runs of decoy_deploy on nvidia/nemotron-3.5-lightning:free (via OpenRouter) with
max_tokens=4000 and a 30s timeout: 9 accepted, 4 needed a retry, 1 fell back to baseline C.
Of 14 completed calls, 2 returned HTTP 200 with empty content and finish_reason length (the
model spent all 4000 tokens reasoning). One call hit the 30s read timeout and the client's own
retry recovered it. Three of 12 text replies were not valid JSON (wrong closing brackets at the
end); the retry fixed two, and the third retry call was itself a length failure, which caused the
one fallback.

## Decision
Factory default max_tokens 8000 (was 4000) and timeout 120s (was 30s), overridable with
PULSEOPS_MAX_TOKENS and PULSEOPS_TIMEOUT. The numbers are guesses informed by one model, not
measurements of a limit.

## Consequences
- A worst-case call can now take much longer, up to the timeout times the retries.
- 8000 may still be too small for another model or prompt. live_eval shows 200/length on the
  failures line when it happens.
- The summary's "finish reasons" line counts only successful replies. Truncations show on the
  failures line.
- Parsing stays strict. The bracket slips are model errors; repairing them would weaken the
  guarantee that accepted output was valid as sent. Retrying recovers most of them.
- The model proposed exactly one hypothesis per run and never cited the decoy, so the
  unlinked_change rule was not exercised on this model. Claim type matched the answer key in 2
  of 10 runs; the model prefers bad_config. Neither is resolved here.
- Re-measure with the 8000-token, 120s defaults (nemotron-3.5-lightning, decoy_deploy, 10 runs): accepted 9/10, 2 needed a retry, all 12 completed calls ended with stop, no 200/length failure and no ReadTimeout in the call log. 12 calls cannot show the old 2-in-14 length rate is gone (it would be absent about one time in six by chance at that rate). The one fallback was two unparseable replies in a row. All 6 unparseable replies whose endings were seen across both batches mis-close the verification list (}}}] or }}}]]). The checker rejected 2 hypotheses with type_fit; one of them cited only the change event and also got unlinked_change, and the retry fixed it.
