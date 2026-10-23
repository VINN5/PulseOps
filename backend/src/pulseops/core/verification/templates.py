from __future__ import annotations

# Allow-list of verification query templates: name -> exact set of required params.
# The model picks a template and params; code validates them and builds the query.
TEMPLATES: dict[str, frozenset[str]] = {
    "metric_series": frozenset({"service", "metric"}),
    "log_template_count": frozenset({"service", "template_id"}),
    "trace_latency_by_service": frozenset({"service"}),
}