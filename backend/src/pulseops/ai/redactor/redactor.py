from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RedactionResult:
    text: str
    counts: dict[str, int]  # rule name -> number of replacements


_OCTET = r"(?:25[0-5]|2[0-4]\d|1?\d?\d)"

# Order matters: specific token shapes first, generic key=value after them,
# so "token: Bearer abc" cannot leave "abc" behind.
_RULES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "jwt",
        re.compile(r"\beyJ[\w-]+\.[\w-]+\.[\w-]+"),
        "[REDACTED:jwt]",
    ),
    (
        "bearer",
        re.compile(r"(?i)\bBearer\s+[\w.~+/=-]+"),
        "Bearer [REDACTED:bearer]",
    ),
    (
        "aws_key",
        re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        "[REDACTED:aws_key]",
    ),
    (
        "api_key",
        re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{36,})"),
        "[REDACTED:api_key]",
    ),
    (
        "secret",
        re.compile(
            r"(?i)(\b(?:api[_-]?key|secret|token|password|passwd)[\"']?\s*[=:]\s*[\"']?)\S+"
        ),
        r"\1[REDACTED:secret]",
    ),
    (
        "email",
        re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        "[REDACTED:email]",
    ),
    (
        "ipv4",
        re.compile(rf"\b(?:{_OCTET}\.){{3}}{_OCTET}\b"),
        "[REDACTED:ipv4]",
    ),
]


def redact(text: str) -> RedactionResult:
    """Replace secrets and PII with fixed placeholders. Deterministic and idempotent."""
    counts: dict[str, int] = {}
    for name, pattern, replacement in _RULES:
        text, n = pattern.subn(replacement, text)
        if n:
            counts[name] = n
    return RedactionResult(text, counts)