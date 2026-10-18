"""FakeLLM: a scripted stand-in for the language model. Placeholder until T29.

Tests never call real LLM APIs (CLAUDE.md). Give the fake the replies it should return, run
the code under test, then assert on ``prompts``. Calling it more times than scripted raises,
so an unexpected extra model call fails the test instead of passing silently.
"""

from collections import deque
from collections.abc import Iterable

import pytest


class FakeLLMExhaustedError(AssertionError):
    """The code under test called the model more times than the test scripted."""


class FakeLLM:
    def __init__(self, replies: Iterable[str] = ()) -> None:
        self._replies = deque(replies)
        self.prompts: list[str] = []

    def script(self, *replies: str) -> None:
        self._replies.extend(replies)

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self._replies:
            raise FakeLLMExhaustedError(f"unscripted call #{len(self.prompts)}: {prompt[:80]!r}")
        return self._replies.popleft()


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()
