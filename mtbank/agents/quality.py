"""⭐ Агент качества — чеклист оператора + балл (AGENT-02).

The LLM only judges the four boolean checks (an observation task it does well). The numeric
`total` is computed HERE from fixed weights: the score stays reproducible, auditable, and
unit-testable, and it can never drift because the model felt generous today.
"""

from __future__ import annotations

from .llm import LLMClient, format_transcript

NAME = "quality"

# Weights sum to 100. Solving the client's problem is worth more than saying goodbye.
WEIGHTS = {
    "greeting": 20,           # приветствие + представился
    "need_detection": 30,     # выявил потребность, задал уточняющие вопросы
    "solution_provided": 30,  # предложил решение / дал ответ по существу
    "farewell": 20,           # корректно завершил разговор
}

SYSTEM = """Ты — супервайзер контакт-центра банка. Оцени работу ОПЕРАТОРА по чеклисту.
Оценивай только реплики оператора. Отвечай честно: если пункт не выполнен — false.

Пункты:
- greeting: оператор поздоровался и представился (назвал банк и/или своё имя)
- need_detection: оператор выявил потребность клиента, задал уточняющие вопросы
- solution_provided: оператор дал ответ по существу или предложил решение
- farewell: оператор корректно завершил разговор (попрощался)

Верни JSON строго вида:
{"greeting": true/false, "need_detection": true/false,
 "solution_provided": true/false, "farewell": true/false,
 "comment": "<краткое пояснение>"}"""


def compute_total(checklist: dict[str, bool]) -> int:
    """Deterministic weighted score — not delegated to the LLM."""
    return sum(WEIGHTS[k] for k, v in checklist.items() if v)


def run(transcript: list[dict], llm: LLMClient, request_id: str = "-") -> dict:
    data = llm.complete_json(
        SYSTEM,
        f"Транскрипт звонка:\n\n{format_transcript(transcript)}",
        agent=NAME,
        request_id=request_id,
    )

    checklist = {k: bool(data.get(k, False)) for k in WEIGHTS}
    return {"total": compute_total(checklist), "checklist": checklist}


def fallback() -> dict:
    checklist = dict.fromkeys(WEIGHTS, False)
    return {"total": 0, "checklist": checklist}
