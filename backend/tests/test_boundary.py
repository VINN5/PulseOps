from pathlib import Path

CORE = Path(__file__).resolve().parents[1] / "src" / "pulseops" / "core"


def test_core_never_imports_ai():
    offenders = [
        str(p) for p in CORE.rglob("*.py")
        if "pulseops.ai" in p.read_text(encoding="utf-8-sig")
        or "from pulseops import ai" in p.read_text(encoding="utf-8-sig")
    ]
    assert offenders == []
