from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pulseops.core.pipeline import run_pipeline
from pulseops.core.report import render_report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="pulseops")
    p.add_argument("scenario", type=Path, help="scenario folder that contains capture/")
    p.add_argument("--json", action="store_true", help="print metric evidence as JSON")
    args = p.parse_args(argv)

    result = run_pipeline(args.scenario / "capture")

    if args.json:
        print(json.dumps([e.model_dump(mode="json") for e in result.metrics], indent=2))
        return 0

    print(render_report(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())