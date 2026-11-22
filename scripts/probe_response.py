"""Shows the SHAPE of a model's reply to the real prompt. Prints no prompt and no key."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

from pulseops.ai.llm_client.openai_compat import PROVIDERS
from pulseops.ai.prompts.prompt import build_prompt
from pulseops.core.evidence_bundle.bundle import build_bundle
from pulseops.core.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    load_dotenv()
    scenario = sys.argv[1] if len(sys.argv) > 1 else "decoy_deploy"
    provider = PROVIDERS[os.environ.get("PULSEOPS_PROVIDER") or "groq"]
    model = os.environ.get("PULSEOPS_MODEL") or provider.default_model
    max_tokens = int(os.environ.get("PROBE_MAX_TOKENS", "1500"))
    bundle = build_bundle(run_pipeline(ROOT / "scenarios" / scenario / "capture"))
    r = httpx.post(
        provider.url,
        headers={"Authorization": f"Bearer {os.environ[provider.key_env]}"},
        json={
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": build_prompt(bundle)}],
        },
        timeout=120,
    )
    print(f"status={r.status_code} model={model} max_tokens={max_tokens}")
    try:
        data = r.json()
    except ValueError:
        print("reply is not JSON")
        return 1
    try:
        choice = data["choices"][0]
        msg = choice["message"]
    except (KeyError, IndexError, TypeError):
        print("no choices; top-level keys:",
              sorted(data) if isinstance(data, dict) else type(data).__name__)
        return 1
    content = msg.get("content")
    print("finish_reason:", choice.get("finish_reason"))
    print("usage:", data.get("usage"))
    print("message keys:", sorted(msg))
    print("content:", type(content).__name__, len(content or ""))
    for k in ("reasoning", "reasoning_content"):
        v = msg.get(k)
        if isinstance(v, str):
            print(f"{k}: {len(v)} chars")
    if content:
        print("content starts:", content[:300].replace("\n", "\\n"))
    return 0


if __name__ == "__main__":
    sys.exit(main())