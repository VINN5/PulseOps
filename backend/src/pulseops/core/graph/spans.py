from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Span:
    trace_id: str
    caller: str
    callee: str
    timestamp: datetime
    duration_ms: float


def load_spans(path: Path) -> list[Span]:
    items = json.loads(path.read_text(encoding="utf-8-sig"))
    return [
        Span(
            trace_id=i["trace_id"],
            caller=i["caller"],
            callee=i["callee"],
            timestamp=datetime.fromisoformat(i["timestamp"]),
            duration_ms=float(i["duration_ms"]),
        )
        for i in items
    ]
