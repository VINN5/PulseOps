# 0014. The prompt must state the output schema

Status: decided

## Context
The first live run (pool_exhaustion, openai/gpt-oss-120b via Groq) failed both
attempts with bad_schema. The model's diagnosis was correct and every ID it cited
was real, but prompt v1 said only "Return a JSON array of hypotheses", so the model
invented field names (hypothesis, evidence). 189 tests passed because FakeModel
always returns correctly shaped output.

## Decision
Prompt v2 states the exact fields, the allowed claim types, the allowed verification
templates with their params, and one example object. All of it is generated from
ClaimType, Hypothesis.model_fields and TEMPLATES, so it cannot drift from what the
parser and checker accept. The retry prompt includes the full original prompt, so
it carries the schema too. Parsing stays strict.

## Consequences
- The prompt is about 1.2K characters longer.
- Tests check that the prompt names every field, claim type and template, and that
  its example parses as a Hypothesis.
- Placeholders in the example may be copied verbatim by a model. They are rejected
  as fabricated IDs, which is the correct outcome.
- Unit tests with a fake model cannot catch a mismatch between prompt and schema.
  Only a live run can. One model on one scenario is a small sample.