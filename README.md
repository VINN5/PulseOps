# PulseOps

An evidence-first incident investigator for OpenTelemetry services.

Given a captured window of metrics, change events and traces around a symptom, PulseOps works out
**what changed, where, and what most plausibly caused it**, and it shows its evidence. A
deterministic pipeline does the analysis first. An optional LLM step may then propose explanations,
but every claim it makes is checked against the evidence before anyone sees it.

> **Status: early and incomplete.** The deterministic core and the verification layer are built and
> tested. It has only been exercised on synthetic scenarios. See [Status](#status) and
> [Known limitations](#known-limitations) before relying on any result.

---

## Design principles

1. **Evidence first.** The deterministic pipeline produces evidence and ranked hypotheses before any
   model is involved. The system is useful with no LLM at all.
2. **Every claim cites evidence.** Each piece of evidence has a stable, content-hashed ID
   (for example `E-met-1a2b3c4d`). A hypothesis must cite IDs that exist in the bundle it was shown.
3. **Verify, don't trust.** Model output is untrusted input. A citation checker rejects fabricated
   IDs, uncited claims, claims that don't fit their evidence, and verification requests outside a
   fixed allow-list.
4. **Fail soft.** If the model errors, returns malformed output, or cites nothing real, the
   orchestrator retries once and then falls back to the deterministic hypotheses. It never raises
   out to the caller.
5. **Be honest about limits.** Known weaknesses are written down as decision records in
   [`docs/decisions/`](docs/decisions/), not hidden.

---

## How it works

```
 capture/ (metrics, events, traces, trigger)
        |
        v
  ingest  ──>  change-point detection (CUSUM)  ──>  metric_change evidence
        |                                              |
        |-- change events aligned to the symptom ──────|
        |-- dependency graph built from observed spans |
        v                                              v
                  scoring (baseline C)  ──>  ranked hypotheses + timeline
                                |
                                v
                 evidence bundle (capped, redacted for prompts)
                                |
              (optional)        v
              prompt v1 ──> LLM ──> strict JSON parse ──> citation checker
                                           |                    |
                                           |        accepted ───┴──> report
                                           └── rejected twice ──> fall back to baseline C
```

### Evidence types

`metric_change`, `log_template`, `trace_path`, `change_event`, `topology`, `alert`.
Each item carries a type, optional service, a time window, a one-line summary, structured data,
and a hash that the ID is derived from. Items are immutable.

### The deterministic core

| Stage | Where | What it does |
|---|---|---|
| Ingest | `core/ingest/` | Reads a snapshot capture into typed objects |
| Change points | `core/change_points/` | CUSUM detector over a fixed leading baseline; emits metric-change evidence |
| Event alignment | `core/events/` | Matches change events (deploys, config changes) to metric shifts in time |
| Dependency graph | `core/graph/` | Builds a service graph from observed spans only |
| Scoring | `core/scoring/` | Baseline C ranks hypotheses by feature breakdown; baseline B is kept for comparison |
| Bundle | `core/evidence_bundle/` | Selects a capped set of evidence items for a model to see |
| Report | `core/report.py` | Renders the timeline and ranked hypotheses as text |

### The verification layer

| Piece | Where | What it does |
|---|---|---|
| Citation checker | `ai/citation_checker/` | Rejects fabricated IDs, uncited claims, type/confidence mismatches, evidence that postdates the symptom, cited change events with no linked metric, and disallowed verification templates or parameters |
| Redactor | `ai/redactor/` | Pattern-based removal of tokens, keys, emails and IPs before text reaches a prompt |
| Prompt | `ai/prompts/` | Versioned (`v2`, which states the exact JSON schema). Evidence is fenced in markers, angle brackets are neutralised, fields are truncated, and the model is told the block is untrusted data |
| Orchestrator | `ai/hypotheses/` | One model call, one retry on zero acceptance, then fall back. Retry feedback uses fixed hint text only, never model-supplied strings |
| LLM clients | `ai/llm_client/` | Anthropic, plus any OpenAI-compatible provider (Groq, Gemini, OpenRouter), with bounded retries and no prompt or key in logs. A fallback chain can try several models in order |

---

## Quick start

Requires **Python 3.12+**. Commands below are for Windows PowerShell. On macOS or Linux, activate
the venv with `source .venv/bin/activate` and use forward slashes in paths.

```powershell
# from the repo root
python -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

pytest -q
```

Run the deterministic pipeline on a scenario and print the report:

```powershell
python -m pulseops.cli scenarios\pool_exhaustion
python -m pulseops.cli scenarios\decoy_deploy
```

The report lists a timeline of detected changes and the ranked hypotheses with their feature
breakdowns. Evidence IDs in the report are the same IDs a model would be allowed to cite.

> The CLI runs the **deterministic** path only. The LLM step is available as a library
> (`pulseops.ai.hypotheses.orchestrator.run_model_step`) but is not yet wired into the CLI.

---

## Scenarios

A scenario is a folder under `scenarios/`:

```
scenarios/<name>/
├── capture/
│   ├── trigger.json    # the symptom: what fired and when
│   ├── metrics.json    # time series per service and metric
│   ├── events.json     # change events: deploys, config changes, ...
│   └── traces.json     # spans, used to build the dependency graph
├── expected_root_cause.json   # the answer a correct run should rank first
└── make_synthetic_capture.py  # regenerates the capture deterministically
```

Currently populated:

| Scenario | What it tests |
|---|---|
| `pool_exhaustion` | A connection-pool exhaustion that shows up as latency on an upstream service |
| `decoy_deploy` | The same fault with an unrelated deploy placed nearby, to check the deploy is not blamed |

**These two are not independent.** `decoy_deploy` is a variant of the first with the same seed and
fault (decision 0006). Treat them as one scenario with two layouts when judging accuracy.

To add a scenario: create the folder with the files above, generate the capture with a script so it
is reproducible, write `expected_root_cause.json`, and add a test that runs the pipeline and asserts
the expected cause ranks first.

---

## Using a live model (optional)

Nothing in the test suite touches the network. To try a real model, set a key and a provider.

Keys are read from environment variables. For local development you can put them in a `.env` file
at the repo root. **`.env` is gitignored; never commit a real key.** Start from the template:

```powershell
Copy-Item .env.example .env
# then edit .env and fill in a key
```

| Provider | Key variable | Default model |
|---|---|---|
| `groq` (default) | `GROQ_API_KEY` | `openai/gpt-oss-120b` |
| `gemini` | `GEMINI_API_KEY` | `gemini-2.5-flash` |
| `openrouter` | `OPENROUTER_API_KEY` | `openrouter/free` |
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-sonnet-5-5` |

Free tiers and model names change often. If a call returns 404, list the models your key can use
and set `PULSEOPS_MODEL`.

| Variable | Meaning |
|---|---|
| `PULSEOPS_PROVIDER` | Which provider to use (default `groq`) |
| `PULSEOPS_MODEL` | Override the provider's default model |
| `PULSEOPS_CHAIN` | Try several models in order, e.g. `groq:openai/gpt-oss-120b,openrouter` |

Check that a key and model work with one tiny call:

```powershell
python scripts\smoke_llm.py
```

The library never reads `.env` itself. Only the scripts in `scripts/` do, so importing `pulseops`
has no side effects.

**Privacy note.** Prompts are redacted before sending, and the logs record only a prompt's length
and a short hash. Redaction is pattern-based and best-effort (decision 0012). Free-tier providers
may use prompts for training, so do not send real production data through them.

---

## Project layout

```
backend/
├── src/pulseops/
│   ├── models/          # evidence, claims, ids, rules
│   ├── core/            # ingest, change_points, events, graph, scoring, evidence_bundle,
│   │                    # pipeline, report
│   ├── ai/              # citation_checker, redactor, prompts, hypotheses, llm_client
│   └── cli.py
└── tests/
    ├── unit/            # per-module tests, including orchestrator, prompt, clients
    ├── property/        # hypothesis-based tests for the checker and redactor
    └── mock_model/      # a scripted FakeModel for tests
docs/decisions/          # decision records 0001-0015
scenarios/               # synthetic captures with expected root causes
scripts/                 # smoke_llm.py and other one-off utilities
```

---

## Testing

```powershell
pytest -q
```

- **Unit tests** cover each stage, the report, the orchestrator, the prompt builder and the LLM
  clients (HTTP mocked with `respx`).
- **Property tests** (`hypothesis`) check that the checker never accepts a nonexistent ID, and that
  redaction is idempotent and never lets a planted AWS key through.
- **Hostile-output tests** feed the orchestrator injected instructions, oversized and deeply nested
  JSON, and lookalike Unicode IDs. All must be rejected without crashing. These tests found and
  fixed a real leak: model-supplied text was being echoed into the retry prompt (decision 0011).
- **Mutation checks.** For each new guard, the logic it protects was disabled and the matching
  test was confirmed to fail, then restored. This is a manual practice, not automated yet.

---

## Status

**Built and tested**

- Deterministic pipeline: ingest, change points, event alignment, graph, scoring, bundle, report
- Citation checker, redactor, versioned prompt, orchestrator with retry and fallback
- LLM clients for Anthropic, Groq, Gemini and OpenRouter, plus a fallback chain

**Not done yet**

- Wiring the LLM step into the CLI and report (a live-run script is in progress)
- Scenarios beyond the two synthetic ones; calibration of scores
- The verification-request execution step (templates exist, nothing runs them)
- The `core/slo` package (empty), persistence, live backends such as Prometheus or OTLP
- CI and a `pulseops` console command

---

## Known limitations

These are documented in full in [`docs/decisions/`](docs/decisions/). The important ones:

- **Tuned on synthetic data.** The detector uses a fixed leading baseline and fixed CUSUM
  parameters. Slow drifts and short series are under-detected (0001). Accuracy on real systems is
  unknown.
- **Scores are rankings, not probabilities.** They are not comparable across runs (0004).
- **Unmatched change does not mean no effect** (0002). The graph misses edges that spans do not
  show, such as queues and caches, and handles cycles poorly (0003).
- **The bundle cap counts items, not tokens** (0005).
- **The checker judges citations, not prose.** It does not sanitise titles (0010), so free-text
  fields should be treated as untrusted when displayed.
- **Redaction is best-effort** (0012). Only the AWS-key rule has property-test coverage (0009).
- **Prompt scope.** The prompt shows only ID, type, subtype, service, time and summary. The
  `untrusted_paths` field is defined and hashed but not yet used (0013).

### Decision records

| # | Topic |
|---|---|
| 0001 | Detector baseline and CUSUM limits |
| 0002 | An unmatched change is not "no effect" |
| 0003 | Hidden edges and cycles in the graph |
| 0004 | Scores are not comparable across runs |
| 0005 | Bundle cap counts items, not tokens |
| 0006 | `decoy_deploy` is a weak test of baseline C |
| 0007 | `time_sanity` is detected by string match |
| 0008 | `must_state_absence` is not enforced |
| 0009 | Property-test coverage caveats |
| 0010 | The checker does not sanitise titles |
| 0011 | Retry-feedback leak (fixed) |
| 0012 | Redaction is best-effort |
| 0013 | `untrusted_paths` unused; redaction scope |
| 0014 | The prompt must state the output schema |
| 0015 | Type-fit checks types, not relationships |

---

## License

   Released under the [MIT License](LICENSE).
