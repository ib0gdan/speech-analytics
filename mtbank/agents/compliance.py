"""🛡️ Compliance — запрещённые фразы, обязательные disclaimers, корректность предложений (AGENT-03).

Two layers, deliberately:
  1. A deterministic keyword pass — a hard guarantee that known-forbidden wording is always
     caught, even if the LLM is lenient. Cheap and fully testable.
  2. An LLM pass for judgement calls (misleading promises, missing disclaimers in context).
Findings are merged; `passed` is false if either layer objects.
"""

from __future__ import annotations

from .llm import LLMClient, format_transcript

NAME = "compliance"

# Absolute promises a bank operator must never make.
FORBIDDEN_PHRASES = (
    "гарантирую одобрение",
    "гарантированно одобрим",
    "стопроцентно одобрят",
    "100% одобрение",
    "точно одобрят",
    "без всяких рисков",
    "никаких рисков",
    "деньги вернутся в любом случае",
)

# Missing disclaimers are left to the LLM layer: they are paraphrased far too freely
# ("решение за банком", "банк может отказать") for exact matching to be meaningful.

SYSTEM = """Ты — комплаенс-контролёр банка. Проверь реплики ОПЕРАТОРА.

Нарушения (issues):
1. Запрещённые обещания: гарантии одобрения кредита, обещание «100% одобрят»,
   отрицание рисков, обещание вернуть деньги в любом случае.
2. Отсутствие обязательного disclaimer: если оператор называет ставку/условия кредита,
   он обязан предупредить, что окончательное решение принимает банк.
3. Некорректное предложение продукта: навязывание, введение в заблуждение,
   умолчание о существенных условиях.

Верни JSON строго вида:
{"passed": true/false, "issues": ["<нарушение 1>", "<нарушение 2>"]}
Если нарушений нет — passed=true, issues=[]."""


def check_forbidden(transcript: list[dict]) -> list[str]:
    """Deterministic layer: exact forbidden wording in operator turns."""
    found = []
    for seg in transcript:
        if seg.get("speaker") != "Оператор":
            continue
        text = seg["text"].lower()
        for phrase in FORBIDDEN_PHRASES:
            if phrase in text:
                found.append(f"Запрещённая фраза оператора: «{phrase}»")
    return found


def run(transcript: list[dict], llm: LLMClient, request_id: str = "-") -> dict:
    rule_issues = check_forbidden(transcript)

    data = llm.complete_json(
        SYSTEM,
        f"Транскрипт звонка:\n\n{format_transcript(transcript)}",
        agent=NAME,
        request_id=request_id,
    )

    llm_issues = [str(i) for i in data.get("issues", []) if str(i).strip()]
    issues = rule_issues + [i for i in llm_issues if i not in rule_issues]
    passed = bool(data.get("passed", True)) and not rule_issues and not issues

    return {"passed": passed, "issues": issues}


def fallback() -> dict:
    return {"passed": True, "issues": []}
