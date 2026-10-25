from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from pulseops.ai.redactor.redactor import redact

SETTINGS = settings(max_examples=300, deadline=None)
PLANTED = "AKIAIOSFODNN7EXAMPLE"


@SETTINGS
@given(st.text())
def test_redacting_twice_equals_redacting_once(s):
    once = redact(s).text
    assert redact(once).text == once


@SETTINGS
@given(st.text(), st.text())
def test_a_planted_key_never_survives_any_surrounding_text(a, b):
    out = redact(f"{a} {PLANTED} {b}").text
    assert PLANTED not in out