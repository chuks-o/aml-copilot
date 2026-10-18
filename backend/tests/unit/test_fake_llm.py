import pytest

from tests.fixtures.fake_llm import FakeLLM, FakeLLMExhaustedError


def test_returns_scripted_replies_in_order_and_records_prompts(fake_llm: FakeLLM) -> None:
    fake_llm.script("first", "second")

    assert [fake_llm.complete("a"), fake_llm.complete("b")] == ["first", "second"]
    assert fake_llm.prompts == ["a", "b"]


def test_an_unscripted_call_fails_the_test() -> None:
    with pytest.raises(FakeLLMExhaustedError, match="unscripted call #1"):
        FakeLLM().complete("anything")
