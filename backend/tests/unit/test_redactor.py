from __future__ import annotations

from pathlib import Path

import pytest

from pulseops.ai.redactor.redactor import redact
from pulseops.core.evidence_bundle.bundle import build_bundle
from pulseops.core.pipeline import run_pipeline

POOL = Path(__file__).resolve().parents[3] / "scenarios" / "pool_exhaustion" / "capture"
BUNDLE = build_bundle(run_pipeline(POOL))

# (text containing a secret, the secret part that must not survive)
SECRETS = {
    "email": ("contact alice@example.com now", "alice@example.com"),
    "ipv4": ("from 10.20.30.40 port 5432", "10.20.30.40"),
    "bearer": ("Authorization: Bearer abc.DEF-123_xyz", "abc.DEF-123_xyz"),
    "aws_key": ("key AKIAIOSFODNN7EXAMPLE used", "AKIAIOSFODNN7EXAMPLE"),
    "sk_key": ("sk-abcdefghijklmnopqrstuvwxyz123456", "abcdefghijklmnopqrstuvwxyz123456"),
    "github_token": ("ghp_" + "a" * 36, "a" * 36),
    "jwt": (
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.c2lnbmF0dXJl",
        "eyJzdWIiOiIxMjMifQ",
    ),
    "kv_equals": ("password=hunter2", "hunter2"),
    "kv_colon": ("api_key: s3cr3tvalue", "s3cr3tvalue"),
    "kv_json": ('{"token": "abcd1234"}', "abcd1234"),
}


@pytest.mark.parametrize("name", sorted(SECRETS))
def test_secret_is_removed(name):
    text, secret = SECRETS[name]
    out = redact(text)
    assert secret not in out.text
    assert "[REDACTED" in out.text
    assert sum(out.counts.values()) >= 1


def test_counts_are_reported_per_rule():
    assert redact("a@b.co and c@d.io").counts == {"email": 2}


def test_placeholder_prefix_cannot_smuggle_a_secret():
    out = redact("password=[REDACTED:secret]realsecret")
    assert "realsecret" not in out.text


NOT_SECRETS = [
    "E-met-9ba030d9",
    "checkout",
    "latency_p99",
    "02:03:11",
    "token bucket exhausted",
    "python 3.12.9",
    "999.1.1.1",
]


@pytest.mark.parametrize("text", NOT_SECRETS)
def test_ordinary_text_survives_untouched(text):
    out = redact(text)
    assert out.text == text
    assert out.counts == {}


def test_real_bundle_ids_and_summaries_survive():
    for e in BUNDLE.items:
        assert redact(e.id).text == e.id
        assert redact(e.summary).text == e.summary, e.summary