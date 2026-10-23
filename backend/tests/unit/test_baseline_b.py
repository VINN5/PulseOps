import json
from datetime import datetime, timezone
from pathlib import Path

from pulseops.core.events.align import load_events
from pulseops.core.scoring.baseline_b import latest_change_before
from pulseops.models.evidence import Evidence, EvidenceType

CAP = Path(__file__).resolve().parents[3] / "scenarios" / "pool_exhaustion" / "capture"


def _at(hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(2026, 3, 14, hour, minute, second, tzinfo=timezone.utc)


def _chg(ext_id: str, service: str, t: datetime) -> Evidence:
    return Evidence.build(
        type=EvidenceType.CHANGE_EVENT,
        subtype="deploy",
        service=service,
        event_time=t, window_start=t, window_end=t,
        summary=f"{ext_id} on {service}",
        data={"external_id": ext_id, "summary": f"{ext_id} on {service}", "actor": "ci", "ref": "x"},
    )


def test_b_picks_real_cause_on_pool_exhaustion():
    changes = load_events(CAP / "events.json")
    trigger = json.loads((CAP / "trigger.json").read_text(encoding="utf-8-sig"))
    alert = datetime.fromisoformat(trigger["alert_time"])
    assert latest_change_before(changes, alert).data["external_id"] == "chg-2291"


def test_b_is_fooled_when_decoy_is_later_than_cause():
    cause = _chg("chg-cause", "orders", _at(2, 3))
    decoy = _chg("chg-decoy", "payments", _at(2, 10))
    picked = latest_change_before([cause, decoy], _at(2, 14))
    assert picked.data["external_id"] == "chg-decoy"  # B fails by design


def test_b_ignores_changes_at_or_after_the_alert():
    cause = _chg("chg-cause", "orders", _at(2, 3))
    at_alert = _chg("chg-at", "orders", _at(2, 14))
    after = _chg("chg-after", "orders", _at(2, 20))
    picked = latest_change_before([after, at_alert, cause], _at(2, 14))
    assert picked.data["external_id"] == "chg-cause"


def test_b_returns_none_when_nothing_precedes_the_alert():
    assert latest_change_before([], _at(2, 14)) is None
    assert latest_change_before([_chg("chg-after", "orders", _at(2, 20))], _at(2, 14)) is None
