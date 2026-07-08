<!-- GSD:project-start source:PROJECT.md -->

## Project

**MTBank Call Analytics — AI Engineer Test Task**

Прототип системы речевой аналитики контакт-центра МТБанка: загруженная запись звонка
автоматически транскрибируется (ASR), диаризуется на Оператор/Клиент и анализируется четырьмя
LLM-агентами. Результат отдаётся и через чат OpenWebUI, и через REST `POST /analyze`. Это
тестовое задание на вакансию AI Engineer (речевая аналитика), оцениваемое по рубрике на 100
баллов (проходной 65), срок 5 рабочих дней.

**Core Value:** Загрузил звонок → получил корректный структурированный анализ (transcript + classification +
quality_score + compliance + summary + action_items) через **настоящий OpenWebUI Pipeline**,
и это работает на живом HTTPS-демо. Если что-то одно должно работать безупречно — это сквозной
путь «аудио → JSON-анализ» в чате и по API.

### Constraints

- **AI-платформа**: OpenWebUI Pipelines (внешний сервер :9099) — обязательно, иначе дисквалификация
- **ASR**: faster-whisper `small`/`base` int8 (medium как opt-in valve) — CPU-бюджет + <60с
- **LLM**: Groq (OpenAI-совместимый, llama-3.3-70b) — через Valves/`.env`, ключ не хардкодить
- **Хост**: CPU, ≥2 vCPU, HTTPS без VPN (HF Spaces Docker / Render); free-микроинстансы слишком медленные
- **Performance**: отклик < 60с на файл до 5 мин
- **Timeline**: 5 рабочих дней; проходной балл 65/100
- **Язык**: README обязателен на русском

<!-- GSD:project-end -->

<!-- GSD:stack-start source:STACK.md -->

## Technology Stack

Technology stack not yet documented. Will populate after codebase mapping or first phase.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
