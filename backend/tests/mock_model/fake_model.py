class FakeModel:
    def __init__(self, *outputs: str | Exception):
        self._outputs = list(outputs)
        self.prompts: list[str] = []   # what we sent, for assertions

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        out = self._outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return out