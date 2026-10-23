from __future__ import annotations

from datetime import datetime

from pulseops.models.evidence import Evidence


def latest_change_before(changes: list[Evidence], alert_time: datetime) -> Evidence | None:
    """Baseline B: the most recent change strictly before the alert.

    Deliberately naive: no service filtering, no topology. On equal times the larger
    ID wins, which is arbitrary but deterministic.
    """
    eligible = [c for c in changes if c.event_time < alert_time]
    if not eligible:
        return None
    return max(eligible, key=lambda c: (c.event_time, c.id))
