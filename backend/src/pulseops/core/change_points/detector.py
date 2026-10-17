from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np

from pulseops.core.ingest.base import Series


@dataclass(frozen=True)
class ChangePoint:
    index: int
    time: datetime
    before: float      # baseline median
    after: float       # median of the points just after the change
    direction: str     # "up" | "down"
    score: float       # |robust z| of the post-change median


def detect_change_point(
    series: Series,
    *,
    baseline_points: int = 40,
    k: float = 0.5,          # CUSUM allowance, in robust-sigma units
    h: float = 8.0,          # CUSUM alarm threshold, in robust-sigma units
    after_window: int = 10,
    min_after_points: int = 3,
    min_z_after: float = 3.0,
    min_rel_change: float = 0.05,
) -> ChangePoint | None:
    """Robust z-score against a baseline, with two-sided CUSUM to time the shift.

    The baseline is the first `baseline_points` samples. Median and MAD give a robust
    location and scale. CUSUM raises an alarm; the change time is where the cumulative
    sum last left zero. A candidate is confirmed only if the median of the points after it
    is itself far from the baseline, so single spikes are rejected.
    Returns the first confirmed change point, or None.
    """
    y = series.values
    n = len(y)
    if n < baseline_points + min_after_points:
        return None

    base = y[:baseline_points]
    med = float(np.median(base))
    mad = float(np.median(np.abs(base - med)))
    sigma = max(1.4826 * mad, 0.02 * abs(med), 1e-9)
    z = (y - med) / sigma

    def confirm(start: int, direction: str) -> ChangePoint | None:
        after_vals = y[start : start + after_window]
        if len(after_vals) < min_after_points:
            return None
        after = float(np.median(after_vals))
        z_after = (after - med) / sigma
        if (direction == "up") != (z_after > 0):
            return None
        if abs(z_after) < min_z_after:
            return None
        if abs(after - med) < min_rel_change * abs(med):
            return None
        return ChangePoint(start, series.time_at(start), med, after, direction, abs(z_after))

    pos = neg = 0.0
    pos_start = neg_start = baseline_points
    for i in range(baseline_points, n):
        pos = max(0.0, pos + z[i] - k)
        if pos == 0.0:
            pos_start = i + 1
        neg = max(0.0, neg - z[i] - k)
        if neg == 0.0:
            neg_start = i + 1

        candidate: ChangePoint | None = None
        alarmed = False
        if pos > h:
            alarmed = True
            candidate = confirm(pos_start, "up")
        elif neg > h:
            alarmed = True
            candidate = confirm(neg_start, "down")
        if candidate:
            return candidate
        if alarmed:  # rejected (for example a spike): reset and keep scanning
            pos = neg = 0.0
            pos_start = neg_start = i + 1
    return None
