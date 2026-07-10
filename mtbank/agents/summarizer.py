"""📝 Суммаризатор — резюме 3–5 предложений + action items (AGENT-04)."""

from __future__ import annotations

from .llm import LLMClient, format_transcript

NAME = "summarizer"

_MAX_ACTION_ITEMS = 6

SYSTEM = """Ты — аналитик контакт-центра банка. Составь краткое резюме звонка.

Требования:
- summary: 3–5 предложений на русском. Кто обратился, с каким вопросом, что решили.
  Без воды и без пересказа реплик дословно.
- action_items: список конкретных задач, которые нужно выполнить ПОСЛЕ звонка.
  Каждое обещание оператора — это задача: «я отправлю», «оформлю заявление», «перевыпустим
  карту», «направим запрос», «передам руководителю», «пришлём смс».
  Формулируй в повелительном наклонении: «Отправить условия кредита на email клиента».
  Пустой список — только если оператор ничего не пообещал и делать после звонка нечего.

Верни JSON строго вида:
{"summary": "<текст>", "action_items": ["<задача 1>", "<задача 2>"]}"""


def run(transcript: list[dict], llm: LLMClient, request_id: str = "-") -> dict:
    data = llm.complete_json(
        SYSTEM,
        f"Транскрипт звонка:\n\n{format_transcript(transcript)}",
        agent=NAME,
        request_id=request_id,
    )

    summary = str(data.get("summary", "")).strip()
    raw_items = data.get("action_items", [])
    action_items = [str(i).strip() for i in raw_items if str(i).strip()][:_MAX_ACTION_ITEMS]

    return {
        "summary": summary or "Резюме недоступно.",
        "action_items": action_items,
    }


def fallback() -> dict:
    return {"summary": "Резюме недоступно.", "action_items": []}
