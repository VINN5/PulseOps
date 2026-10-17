from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from pulseops.core.ingest.base import MissingTelemetry, Series


def _epoch(s: str) -> float:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        raise ValueError(f"snapshot timestamp must be timezone-aware: {s}")
    return dt.timestamp()


class SnapshotBackend:
    """Serves metrics from a captured snapshot.

    Format of metrics.json: {"service/metric": {"timestamps": [iso...], "values": [...]}}
    """

    def __init__(self, data: dict[str, dict[str, Any]]) -> None:
        self._series: dict[tuple[str, str], tuple[np.ndarray, np.ndarray]] = {}
        for key, body in data.items():
            service, _, metric = key.partition("/")
            ts = np.array([_epoch(t) for t in body["timestamps"]], dtype=float)
            vals = np.array(body["values"], dtype=float)
            if ts.shape != vals.shape:
                raise ValueError(f"{key}: timestamps and values differ in length")
            order = np.argsort(ts, kind="stable")
            self._series[(service, metric)] = (ts[order], vals[order])

    @classmethod
    def from_dir(cls, path: str | Path) -> SnapshotBackend:
        text = (Path(path) / "metrics.json").read_text(encoding="utf-8-sig")
        return cls(json.loads(text))

    def list_services(self) -> list[str]:
        return sorted({s for (s, _) in self._series})

    def list_metrics(self, service: str) -> list[str]:
        return sorted(m for (s, m) in self._series if s == service)

    def query_range(self, service: str, metric: str, start: datetime, end: datetime) -> Series:
        try:
            ts, vals = self._series[(service, metric)]
        except KeyError:
            raise MissingTelemetry(f"{service}/{metric} not in snapshot") from None
        mask = (ts >= start.timestamp()) & (ts <= end.timestamp())
        return Series(service, metric, ts[mask], vals[mask])
