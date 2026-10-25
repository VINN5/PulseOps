# 0004. Baseline C scores are not comparable across runs

Status: accepted (known limit)

## Context
Baseline C averages four equally weighted features. Magnitude is min-max scaled
across the changes in one run. `EXTERNAL_SCORE` (0.25) is an arbitrary constant.

## Decision
Scores rank hypotheses within one run only. Weights and the external constant
are unfitted.

## Consequences
- A score of 0.99 in one run says nothing about another run.
- With one candidate, min-max scaling degenerates, so magnitude is uninformative.
- Scores must not be shown as probabilities. Calibration is a separate piece of
  work that has not been done.