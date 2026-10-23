from pathlib import Path

from pulseops.core.evidence_bundle.bundle import build_bundle
from pulseops.core.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[3] / "scenarios"
POOL = ROOT / "pool_exhaustion" / "capture"
DECOY = ROOT / "decoy_deploy" / "capture"


def _all_ids(r):
    return {e.id for e in r.metrics} | {e.id for e in r.changes}


def _change(r, ext):
    return next(c for c in r.changes if c.data["external_id"] == ext)


def _change_ext_ids(items):
    return {e.data["external_id"] for e in items if "external_id" in e.data}


def test_default_cap_keeps_everything():
    r = run_pipeline(POOL)
    b = build_bundle(r)
    assert {e.id for e in b.items} == _all_ids(r)
    assert b.omitted == []


def test_small_cap_records_every_omission():
    r = run_pipeline(POOL)
    b = build_bundle(r, max_items=3)
    kept = {e.id for e in b.items}
    dropped = {o.id for o in b.omitted}
    assert len(b.items) == 3
    assert kept.isdisjoint(dropped)
    assert kept | dropped == _all_ids(r)
    assert all(o.reason for o in b.omitted)
    assert any(e.service == "checkout" and e.data.get("metric") == "latency_p99" for e in b.items)
    assert "chg-2291" in _change_ext_ids(b.items)
    assert _change(r, "chg-2288").id in dropped


def test_supporting_ids_point_at_same_service_metrics():
    r = run_pipeline(POOL)
    b = build_bundle(r)
    by_id = {m.id: m for m in r.metrics}
    ids = b.supporting[_change(r, "chg-2291").id]
    assert ids
    assert {by_id[i].service for i in ids} == {"orders"}
    assert "db_pool_wait_p95" in {by_id[i].data["metric"] for i in ids}
    assert b.supporting[_change(r, "chg-2288").id] == []


def test_hash_is_deterministic_and_cap_sensitive():
    r = run_pipeline(POOL)
    assert build_bundle(r).bundle_hash == build_bundle(r).bundle_hash
    assert build_bundle(r).bundle_hash != build_bundle(r, max_items=3).bundle_hash


def test_decoy_deploy_keeps_the_decoy_as_contradicting_evidence():
    r = run_pipeline(DECOY)
    b = build_bundle(r)
    assert "chg-2288" in _change_ext_ids(b.items)
    assert b.supporting[_change(r, "chg-2288").id] == []
