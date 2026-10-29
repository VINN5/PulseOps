"""One tiny live call to check provider, model name and key. Costs next to nothing."""
from __future__ import annotations

import sys

from pulseops.ai.llm_client.client import LLMError
from pulseops.ai.llm_client.openai_compat import make_model


def main() -> int:
    try:
        model = make_model()
        name = getattr(model, "provider_name", "anthropic")
        label = getattr(model, "model_name", None) or getattr(model, "_model", "?")
        print(f"provider={name} model={label}")
        reply = model.complete("Reply with exactly one word: pong")
    except LLMError as e:
        print(f"FAILED: {e}")
        return 1
    print(f"reply: {reply.strip()[:200]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())