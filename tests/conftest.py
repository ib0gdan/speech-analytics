"""Shared fixtures.

No test ever calls the real LLM: it is slow, costs tokens, needs a key, and is
non-deterministic — none of which belongs in a test suite. `FakeLLM` returns canned JSON per
agent, so what we assert is OUR logic (validation, coercion, scoring, merging, degradation).

The integration test DOES run the real faster-whisper model (that is the point of an
integration test); it is marked `slow` so you can skip it with `pytest -m "not slow"`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

TEST_DATA = Path(__file__).resolve().parent.parent / "test_data"


class FakeLLM:
    """Stands in for LLMClient. Returns a canned dict per agent; can be told to fail."""

    def __init__(self, responses: dict[str, dict] | None = None, fail: tuple[str, ...] = ()):
        self.responses = responses or DEFAULT_RESPONSES
        self.fail = fail
        self.calls: list[str] = []

    def complete_json(self, system: str, user: str, *, agent: str, request_id: str = "-") -> dict:
        self.calls.append(agent)
        if agent in self.fail:
            raise RuntimeError(f"simulated {agent} failure")
        return self.responses[agent]


DEFAULT_RESPONSES: dict[str, dict] = {
    "classifier": {"topic": "кредиты", "priority": "medium", "reason": "вопрос по кредиту"},
    "quality": {
        "greeting": True, "need_detection": True,
        "solution_provided": True, "farewell": False, "comment": "не попрощался",
    },
    "compliance": {"passed": True, "issues": []},
    "summarizer": {
        "summary": "Клиент спросил про кредит. Оператор назвал ставку.",
        "action_items": ["Отправить условия на email"],
    },
    "trends": {
        "patterns": ["Клиенты часто жалуются на списания"],
        "causes": ["Недостаточно информирования об условиях"],
        "recommendations": ["Обучить операторов disclaimer"],
        "grouped_action_items": ["Отправить условия кредита"],
        "grouped_compliance_issues": ["Отсутствует disclaimer о решении банка"],
    },
}


@pytest.fixture
def good_transcript() -> list[dict]:
    return [
        {"speaker": "Оператор", "start": 0.0, "end": 4.2,
         "text": "Добрый день, МТБанк, меня зовут Анна. Чем могу помочь?"},
        {"speaker": "Клиент", "start": 4.5, "end": 8.1,
         "text": "Здравствуйте, хочу узнать про кредит наличными."},
        {"speaker": "Оператор", "start": 8.3, "end": 13.0,
         "text": "Ставка от 18 процентов. Окончательное решение принимает банк."},
    ]


@pytest.fixture
def bad_transcript() -> list[dict]:
    """Operator makes forbidden promises — the deterministic compliance layer must fire."""
    return [
        {"speaker": "Клиент", "start": 0.0, "end": 4.0,
         "text": "У меня третий раз списали деньги с карты!"},
        {"speaker": "Оператор", "start": 4.0, "end": 9.0,
         "text": "Оформите кредит, я гарантирую одобрение, вам стопроцентно одобрят."},
        {"speaker": "Оператор", "start": 9.0, "end": 12.0,
         "text": "Деньги вернутся в любом случае, никаких рисков."},
    ]


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()
