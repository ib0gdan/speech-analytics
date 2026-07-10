"""📊 Агент трендов — паттерны по НЕСКОЛЬКИМ звонкам (BONUS-A-TRENDS).

The fifth agent, but a different shape from the other four: it does not join the per-call
supervisor fan-out (AGENT-01..04 all consume one transcript). It runs AFTER `run_batch_analysis`
has produced N `run_analysis()` result dicts, and looks for patterns ACROSS them.

Same split as `quality.compute_total`: numbers are computed HERE, in code —
`compute_aggregates()` never calls the LLM and is reproducible/testable on its own. The LLM is
used ONLY for judgement it is actually good at: naming likely causes, recommending fixes, and
semantically grouping action items / compliance issues that are worded differently call to call
(exact string matching cannot group "отправлю условия" with "вышлю условия по кредиту").
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from ..logging_config import get_logger, log_event
from .compliance import check_forbidden
from .llm import LLMClient

logger = get_logger("mtbank.agents.trends")

NAME = "trends"

# Coercion caps: a runaway LLM must not blow up the chat rendering with a wall of bullets.
_MAX_JUDGEMENT_ITEMS = 10

SYSTEM = """Ты — аналитик контакт-центра банка. Тебе дана СВОДКА по НЕСКОЛЬКИМ звонкам:
агрегаты уже посчитаны кодом (количество звонков, распределение тем, качество, доля нарушений
комплаенса, частота запрещённых фраз) — НЕ считай числа сам, они уже даны.

Твоя задача — судить о смысле, а не о цифрах:
- patterns: повторяющиеся паттерны в поведении клиентов и операторов;
- causes: вероятные причины этих паттернов;
- recommendations: конкретные рекомендации для контакт-центра;
- grouped_action_items: задачи из разных звонков, сгруппированные по смыслу
  (одна и та же задача формулируется по-разному в каждом звонке — объедини её в одну);
- grouped_compliance_issues: нарушения комплаенса, сгруппированные по смыслу.

Верни JSON строго вида:
{"patterns": ["..."], "causes": ["..."], "recommendations": ["..."],
 "grouped_action_items": ["..."], "grouped_compliance_issues": ["..."]}"""

_JUDGEMENT_KEYS = (
    "patterns", "causes", "recommendations", "grouped_action_items", "grouped_compliance_issues",
)


def _empty_aggregates() -> dict[str, Any]:
    return {
        "num_calls": 0,
        "topics": {},
        "quality": {"avg": None, "min": None, "max": None},
        "checklist_pass_rate": {},
        "compliance_failure_rate": 0.0,
        "forbidden_phrase_hits": {},
    }


def _empty_judgement() -> dict[str, list]:
    return {key: [] for key in _JUDGEMENT_KEYS}


def _coerce_str_list(value: Any, max_len: int = _MAX_JUDGEMENT_ITEMS) -> list[str]:
    """Keep only genuine, non-blank strings — drop ints/None/whitespace, reject a non-list."""
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if isinstance(item, str):
            s = item.strip()
            if s:
                out.append(s)
    return out[:max_len]


def compute_aggregates(calls: list[dict]) -> dict[str, Any]:
    """Deterministic layer — pure code, no LLM. Every field read with `.get` so a degraded or
    malformed call dict (one carrying `agent_errors`) is aggregated without raising."""
    num_calls = len(calls)
    if num_calls == 0:
        return _empty_aggregates()

    topics: Counter[str] = Counter()
    totals: list[int] = []
    checklist_pass: Counter[str] = Counter()
    checklist_seen: Counter[str] = Counter()
    compliance_failures = 0
    forbidden_hits: Counter[str] = Counter()

    for call in calls:
        topic = call.get("classification", {}).get("topic", "другое")
        topics[topic] += 1

        totals.append(call.get("quality_score", {}).get("total", 0))

        checklist = call.get("quality_score", {}).get("checklist", {})
        for key, value in checklist.items():
            checklist_seen[key] += 1
            if value:
                checklist_pass[key] += 1

        if not call.get("compliance", {}).get("passed", True):
            compliance_failures += 1

        for issue in check_forbidden(call.get("transcript", [])):
            forbidden_hits[issue] += 1

    checklist_pass_rate = {
        key: round(checklist_pass[key] / num_calls, 4) for key in checklist_seen
    }

    return {
        "num_calls": num_calls,
        "topics": dict(topics),
        "quality": {
            "avg": round(sum(totals) / len(totals), 2),
            "min": min(totals),
            "max": max(totals),
        },
        "checklist_pass_rate": checklist_pass_rate,
        "compliance_failure_rate": round(compliance_failures / num_calls, 4),
        "forbidden_phrase_hits": dict(forbidden_hits),
    }


def _build_digest(calls: list[dict], aggregates: dict[str, Any]) -> str:
    """Compact Russian digest of the batch — enough for judgement, without dumping every
    transcript (that would blow the token budget for a 20-call batch)."""
    lines = [
        f"Агрегаты (уже посчитаны кодом): {aggregates}",
        "",
        "Звонки:",
    ]
    for i, call in enumerate(calls, 1):
        topic = call.get("classification", {}).get("topic", "другое")
        quality_total = call.get("quality_score", {}).get("total", 0)
        comp = call.get("compliance", {})
        verdict = "без нарушений" if comp.get("passed", True) else "есть нарушения"
        issues = comp.get("issues", [])
        action_items = call.get("action_items", [])
        lines.append(
            f"{i}. тема={topic}, качество={quality_total}, комплаенс={verdict}, "
            f"нарушения={issues}, задачи={action_items}"
        )
    return "\n".join(lines)


def run(calls: list[dict], llm: LLMClient, request_id: str = "-") -> dict[str, Any]:
    aggregates = compute_aggregates(calls)
    if not calls:
        return {**aggregates, **_empty_judgement()}

    digest = _build_digest(calls, aggregates)
    try:
        data = llm.complete_json(SYSTEM, digest, agent=NAME, request_id=request_id)
        judgement = {key: _coerce_str_list(data.get(key)) for key in _JUDGEMENT_KEYS}
    except Exception as e:  # noqa: BLE001 — the deterministic aggregates must survive
        log_event(logger, "agent_failed", request_id=request_id, agent=NAME, error=str(e)[:300])
        judgement = _empty_judgement()

    return {**aggregates, **judgement}


def fallback() -> dict[str, Any]:
    return {**_empty_aggregates(), **_empty_judgement()}
