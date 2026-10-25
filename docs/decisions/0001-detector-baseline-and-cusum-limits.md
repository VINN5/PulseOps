# 0001. Change-point detector: baseline window and CUSUM limits

Status: accepted (known limits)

## Context
`detect_change_point` scores a series with a robust z-score against a baseline
of the first `DEFAULT_BASELINE_POINTS` (40) samples, then runs a two-sided CUSUM
(k=0.5, h=8.0) and applies thresholds on post-change z and relative change.

## Decision
Keep a fixed-length leading baseline and fixed thresholds. They are tuned on
synthetic scenarios only.

## Consequences
- A series with fewer than the baseline length, or with a shift inside the
  baseline window, is under-detected or mis-detected.
- A slow drift can stay under the CUSUM threshold and produce no change point.
- Thresholds are not calibrated against real incident data. Detection rates on
  real services are unknown.