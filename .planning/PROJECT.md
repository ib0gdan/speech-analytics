# MTBank Call Analytics — AI Engineer Test Task

## What This Is

Прототип системы речевой аналитики контакт-центра МТБанка: загруженная запись звонка
автоматически транскрибируется (ASR), диаризуется на Оператор/Клиент и анализируется четырьмя
LLM-агентами. Результат отдаётся и через чат OpenWebUI, и через REST `POST /analyze`. Это
тестовое задание на вакансию AI Engineer (речевая аналитика), оцениваемое по рубрике на 100
баллов (проходной 65), срок 5 рабочих дней.

## Core Value

Загрузил звонок → получил корректный структурированный анализ (transcript + classification +
quality_score + compliance + summary + action_items) через **настоящий OpenWebUI Pipeline**,
и это работает на живом HTTPS-демо. Если что-то одно должно работать безупречно — это сквозной
путь «аудио → JSON-анализ» в чате и по API.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] **ASR Pipeline**: faster-whisper (small int8, VAD), форматы WAV/MP3/OGG, timestamps
- [ ] **Диаризация** Оператор/Клиент без pyannote (VAD + эвристика поворотов + LLM-разметка)
- [ ] **4 агента**: классификатор (тема+приоритет), качество (чеклист), compliance, суммаризатор
- [ ] **Оркестрация** агентов через OpenWebUI Pipeline (LangGraph или Supervisor — обосновать)
- [ ] **OpenWebUI Pipeline** (внешний сервер :9099) — обязателен; аудио через URL в сообщении
- [ ] **REST `POST /analyze`** (multipart-файл или `{url}`) с JSON-ответом по схеме ТЗ
- [ ] **Общий core** `run_analysis(audio)->dict`, переиспользуемый Pipeline и API
- [ ] **Docker Compose** — `docker compose up` поднимает openwebui + pipelines + api
- [ ] **Тесты** pytest: unit на каждого агента + интеграционный тест пайплайна
- [ ] **`.env` / `.env.example`** + JSON-логи с input/output каждого агента
- [ ] **Тестовые данные**: 5+ ru-аудио (вкл. 8kHz телефон и 2-голосый диалог 1мин+, суммарно 5мин+) + эталоны + WER-таблица (jiwer)
- [ ] **README на русском**: архитектурная схема, инструкции, обоснования решений
- [ ] **Живое HTTPS-демо** на CPU-хосте ≥2 vCPU, отклик <60с на 5-мин файл

### Out of Scope

- **pyannote-диаризация** — тяжёлая, GPU/HF-токен, не влезает в CPU-бюджет; лёгкая эвристика достаточна для 2 говорящих
- **Локальная LLM** — выбран внешний Groq API (скорость + бесплатно + <60с); обосновано
- **Бонусы (real-time WebSocket / Grafana / агент трендов)** — только после сдачи основного (+15 сверх 100), не блокируют проходной балл

## Context

- **Стек и архитектура проверены спайком** — см. `.planning/spikes/MANIFEST.md` и `CONVENTIONS.md`. Ключевые факты:
  - `pipe(self, user_message, model_id, messages, body) -> Union[str, Generator, Iterator]`
  - Аудио НЕ доходит до `pipe()` сырыми байтами → основной путь = URL в сообщении; прямой файл — через REST `/analyze`
  - README pipelines гласит «DO NOT USE PIPELINES!» кроме тяжёлых вычислений вне основного инстанса → наш whisper+агенты = легитимный кейс (аргумент для README)
  - `small int8` ≈ 50с/5мин (впритык <60с), `medium` — за пределом → дефолт small, medium как valve
- **Оценка по рубрике**: Pipeline-архитектура 25, Multi-Agent 25, ASR 20, Код/тесты 15, Docs 10, Демо 5.
- **Дисквалификация**: приватный репо, недоступное демо, отсутствие Pipeline, чужой код без источника, README без русской версии.
- Сдача: письмо на azubik@mtbank.by (ссылка на репо + демо + описание + затраченное время).

## Constraints

- **AI-платформа**: OpenWebUI Pipelines (внешний сервер :9099) — обязательно, иначе дисквалификация
- **ASR**: faster-whisper `small`/`base` int8 (medium как opt-in valve) — CPU-бюджет + <60с
- **LLM**: Groq (OpenAI-совместимый, llama-3.3-70b) — через Valves/`.env`, ключ не хардкодить
- **Хост**: CPU, ≥2 vCPU, HTTPS без VPN (HF Spaces Docker / Render); free-микроинстансы слишком медленные
- **Performance**: отклик < 60с на файл до 5 мин
- **Timeline**: 5 рабочих дней; проходной балл 65/100
- **Язык**: README обязателен на русском

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| OpenWebUI Pipelines (внешний сервер), не Functions | Требование ТЗ; наш кейс — «тяжёлые вычисления вне основного инстанса», единственный оправданный по офиц. README | — Pending |
| Аудио через URL в сообщении + REST `/analyze` для файла | Спайк 001: сырые байты не доходят до `pipe()` | — Pending |
| Общий `run_analysis()` core для Pipeline и API | Спайк 003: нет дублирования логики, Pipeline остаётся оркестратором | — Pending |
| Groq как LLM-бэкенд | Скорость (<60с при 4 агентах), бесплатный tier, OpenAI-совместимость | — Pending |
| faster-whisper small int8 дефолт | Спайк 004: medium не укладывается в <60с на CPU | — Pending |
| Диаризация без pyannote (VAD+эвристика+LLM) | CPU-бюджет; 2 говорящих — простой случай | — Pending (валидировать в ASR-фазе) |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-08 after initialization*
