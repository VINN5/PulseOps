from __future__ import annotations

# metric name -> evidence subtype. The claim rules match on these subtypes,
# so a metric missing here produces evidence the rules cannot use. Keep it explicit.
METRIC_SUBTYPES: dict[str, str] = {
    "db_pool_wait_p95": "saturation",
    "db_pool_in_use": "saturation",
    "queue_depth": "saturation",
    "memory_bytes": "saturation",
    "cpu_utilization": "saturation",
    "disk_used_ratio": "saturation",
    "request_rate": "request_rate",
    "retry_rate": "retries",
    "latency_p95": "latency",
    "latency_p99": "latency",
    "error_rate": "error_rate",
}


def subtype_for(metric: str) -> str | None:
    return METRIC_SUBTYPES.get(metric)
