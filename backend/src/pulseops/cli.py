from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from pulseops.core.change_points.evidence import detect_all
from pulseops.core.ingest.snapshot import SnapshotBackend


def _parse(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        raise ValueError(f"timestamp must be timezone-aware: {s}")
    return dt


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="pulseops")
    p.add_argument("scenario", type=Path, help="scenario folder that contains capture/")
    p.add_argument("--json", action="store_true", help="print evidence as JSON")
    args = p.parse_args(argv)

    capture = args.scenario / "capture"
    trigger = json.loads((capture / "trigger.json").read_text(encoding="utf-8-sig"))
    backend = SnapshotBackend.from_dir(capture)
    start = _parse(trigger["window_start"])
    end = _parse(trigger["alert_time"])  # never look past the alert
    evidence = detect_all(backend, start, end)

    if args.json:
        print(json.dumps([e.model_dump(mode="json") for e in evidence], indent=2))
        return 0

    print(f"TRIGGER   {trigger['service']} {trigger['symptom_metric']} alert at {trigger['alert_time']}")
    print(f"WINDOW    {trigger['window_start']} to {trigger['alert_time']}")
    print(f"EVIDENCE  {len(evidence)} metric change(s)")
    for e in evidence:
        print(f"  {e.event_time:%H:%M:%S} [{e.id}] {e.service}: {e.summary} (subtype={e.subtype})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
