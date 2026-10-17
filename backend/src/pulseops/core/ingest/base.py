from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

import numpy as np


class MissingTelemetry(Exception):
    """Requested metric is not available (feeds the partial_telemetry failure mode)."""


@dataclass(frozen=True, eq=False)
class Series:
    service: str
    metric: str
    timestamps: np.ndarray  # epoch seconds, float, ascending
    values: np.ndarray

    def time_at(self, i: int) -> datetime:
        return datetime.fromtimestamp(float(self.timestamps[i]), tz=timezone.utc)


class MetricBackend(Protocol):
    """The pipeline only ever sees this interface: live backends and snapshots both fit."""

    def list_services(self) -> list[str]: ...

    def list_metrics(self, service: str) -> list[str]: ...

    def query_range(self, service: str, metric: str, start: datetime, end: datetime) -> Series: ...
