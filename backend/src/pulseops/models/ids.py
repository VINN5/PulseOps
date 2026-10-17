from __future__ import annotations

import hashlib
import json
from typing import Any


def _normalize(obj: Any) -> Any:
    if isinstance(obj, float):
        return round(obj, 6)  # avoid float noise changing IDs
    if isinstance(obj, dict):
        return {k: _normalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_normalize(v) for v in obj]
    return obj


def canonical_json(obj: Any) -> str:
    return json.dumps(_normalize(obj), sort_keys=True, separators=(",", ":"), default=str)


def sha256_hex(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()
