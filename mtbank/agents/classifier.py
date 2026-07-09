"""🏷️ Классификатор — тематика обращения + приоритет (AGENT-01)."""

from __future__ import annotations

from .llm import LLMClient, format_transcript

NAME = "classifier"

TOPICS = ("кредиты", "карты", "переводы", "жалобы", "другое")
PRIORITIES = ("low", "medium", "high")

SYSTEM = """Ты — классификатор обращений контакт-центра банка.
Определи тематику звонка и приоритет.

Тематика (topic) — строго одно из: кредиты, карты, переводы, жалобы, другое.
Приоритет (priority) — строго одно из: low, medium, high.
  high   — жалоба, конфликт, блокировка средств, мошенничество, угроза ухода клиента
  medium — клиент выбирает продукт, нужен ответ, но без срочности
  low    — общий информационный вопрос

Верни JSON строго вида:
{"topic": "<тема>", "priority": "<приоритет>", "reason": "<краткое обоснование>"}"""


def run(transcript: list[dict], llm: LLMClient, request_id: str = "-") -> dict:
    data = llm.complete_json(
        SYSTEM,
        f"Транскрипт звонка:\n\n{format_transcript(transcript)}",
        agent=NAME,
        request_id=request_id,
    )

    topic = str(data.get("topic", "")).strip().lower()
    priority = str(data.get("priority", "")).strip().lower()

    return {
        "topic": topic if topic in TOPICS else "другое",
        "priority": priority if priority in PRIORITIES else "medium",
    }


def fallback() -> dict:
    return {"topic": "другое", "priority": "medium"}
