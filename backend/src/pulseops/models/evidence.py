from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pulseops.models.ids import sha256_hex


class EvidenceType(StrEnum):
    METRIC_CHANGE = "metric_change"
    LOG_TEMPLATE = "log_template"
    TRACE_PATH = "trace_path"
    CHANGE_EVENT = "change_event"
    TOPOLOGY = "topology"
    ALERT = "alert"


_PREFIX = {
    EvidenceType.METRIC_CHANGE: "met",
    EvidenceType.LOG_TEMPLATE: "log",
    EvidenceType.TRACE_PATH: "trc",
    EvidenceType.CHANGE_EVENT: "chg",
    EvidenceType.TOPOLOGY: "top",
    EvidenceType.ALERT: "alt",
}


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _content(
    type_: EvidenceType, subtype: str | None, service: str | None,
    window_start: datetime, window_end: datetime, event_time: datetime,
    summary: str, data: dict[str, Any], untrusted_paths: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "type": type_.value, "subtype": subtype, "service": service,
        "window": [_utc(window_start), _utc(window_end)], "event_time": _utc(event_time),
        "summary": summary, "data": data, "untrusted": list(untrusted_paths),
    }


class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    type: EvidenceType
    subtype: str | None = None
    service: str | None = None
    window_start: datetime
    window_end: datetime
    event_time: datetime
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)
    untrusted_paths: tuple[str, ...] = ()
    source: dict[str, str] = Field(default_factory=dict)
    hash: str

    @model_validator(mode="after")
    def _check(self) -> Evidence:
        for dt in (self.window_start, self.window_end, self.event_time):
            if dt.tzinfo is None:
                raise ValueError("timestamps must be timezone-aware")
        if self.window_end < self.window_start:
            raise ValueError("window_end before window_start")
        digest = sha256_hex(_content(
            self.type, self.subtype, self.service, self.window_start, self.window_end,
            self.event_time, self.summary, self.data, self.untrusted_paths))
        if self.hash != f"sha256:{digest}" or self.id != f"E-{_PREFIX[self.type]}-{digest[:8]}":
            raise ValueError("id/hash do not match content")
        return self

    @classmethod
    def build(
        cls, *, type: EvidenceType, event_time: datetime, window_start: datetime,
        window_end: datetime, summary: str, subtype: str | None = None,
        service: str | None = None, data: dict[str, Any] | None = None,
        untrusted_paths: tuple[str, ...] = (), source: dict[str, str] | None = None,
    ) -> Evidence:
        data = data or {}
        digest = sha256_hex(_content(
            type, subtype, service, window_start, window_end, event_time,
            summary, data, untrusted_paths))
        return cls(
            id=f"E-{_PREFIX[type]}-{digest[:8]}", hash=f"sha256:{digest}", type=type,
            subtype=subtype, service=service, window_start=window_start,
            window_end=window_end, event_time=event_time, summary=summary, data=data,
            untrusted_paths=untrusted_paths, source=source or {},
        )
