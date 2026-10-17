from __future__ import annotations

from datetime import datetime

from pulseops.core.change_points.catalogue import subtype_for
from pulseops.core.change_points.detector import ChangePoint, detect_change_point
from pulseops.core.ingest.base import MetricBackend, Series
from pulseops.models.evidence import Evidence, EvidenceType


def change_point_to_evidence(
    cp: ChangePoint, series: Series, *, after_window: int = 10
) -> Evidence:
    """Pure conversion: the same change point always yields the same Evidence id."""
    n = len(series.values)
    start_i = max(cp.index - 4, 0)
    end_i = min(cp.index + after_window - 1, n - 1)
    verb = "rose" if cp.direction == "up" else "fell"
    summary = f"{series.metric} {verb} from {cp.before:.4g} to {cp.after:.4g} at {cp.time:%H:%M:%S}Z"
    return Evidence.build(
        type=EvidenceType.METRIC_CHANGE,
        subtype=subtype_for(series.metric),
        service=series.service,
        event_time=cp.time,
        window_start=series.time_at(start_i),
        window_end=series.time_at(end_i),
        summary=summary,
        data={
            "metric": series.metric,
            "before": round(float(cp.before), 6),
            "after": round(float(cp.after), 6),
            "score": round(float(cp.score), 6),
            "direction": cp.direction,
            "change_time": cp.time.isoformat(),
        },
        source={"series": f"{series.service}/{series.metric}"},
    )


def detect_all(backend: MetricBackend, start: datetime, end: datetime) -> list[Evidence]:
    """Run the detector over every series in the window; return evidence ordered by time."""
    out: list[Evidence] = []
    for service in backend.list_services():
        for metric in backend.list_metrics(service):
            series = backend.query_range(service, metric, start, end)
            cp = detect_change_point(series)
            if cp is not None:
                out.append(change_point_to_evidence(cp, series))
    out.sort(key=lambda e: (e.event_time, e.id))
    return out
