from __future__ import annotations

from pulseops.core.pipeline import LOOKBACK, PipelineResult


def _ext(ev) -> str:
    return ev.data["external_id"]


def render_report(r: PipelineResult) -> str:
    lines: list[str] = []
    t = r.trigger
    lines.append(f"INCIDENT  {t['service']} {t['symptom_metric']} alert at {t['alert_time']}")
    lines.append(f"WINDOW    {t['window_start']} to {t['alert_time']}")
    lines.append(f"BASELINE  {t['window_start']} to {r.baseline_end.isoformat()}")
    lines.append("")

    lines.append("TIMELINE")
    rows = [(m.event_time, m.id, m.summary, m.service) for m in r.metrics]
    rows += [(c.event_time, c.id, f"{c.subtype}: {c.summary} ({_ext(c)})", c.service)
             for c in r.changes]
    for when, eid, text, svc in sorted(rows, key=lambda x: (x[0], x[1])):
        lines.append(f"  {when:%H:%M:%S} [{eid}] {svc}: {text}")
    lines.append("")

    lines.append(f"UPSTREAM  deepest degraded callee: {', '.join(r.upstream) or 'none'}")
    if any(h.fallback for h in r.hypotheses):
        lines.append("NOTE      graph gave no answer; used earliest change point instead")
    lines.append("")

    lines.append("HYPOTHESES (scores are rankings, not probabilities)")
    minutes = int(LOOKBACK.total_seconds() // 60)
    unmatched_ids = {c.id for c in r.unmatched_changes}
    for n, h in enumerate(r.hypotheses, 1):
        if h.change is None:
            lines.append(f"  {n}. external_or_unknown  score {h.score:.2f}")
            lines.append("     no change event explains the metric changes")
            continue
        c = h.change
        lines.append(f"  {n}. {c.subtype} {_ext(c)} on {c.service}  score {h.score:.2f}")
        lines.append(f"     features: same_service={h.same_service:.0f} "
                     f"proximity={h.proximity:.2f} topology={h.topology:.0f} "
                     f"magnitude={h.magnitude:.2f}")
        if c.id in unmatched_ids:
            examined = ", ".join(r.metrics_examined.get(c.service, [])) or "no metrics"
            lines.append(f"     against: no {c.service} metric change detected within "
                         f"{minutes} min of {_ext(c)} (examined: {examined})")
        else:
            lines.append(f"     for: {c.id}")
    return "\n".join(lines)