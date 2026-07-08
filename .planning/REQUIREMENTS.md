# Requirements — MTBank Call Analytics (v1)

Derived from the task rubric (100 pts, pass 65) and spike-verified architecture
(`.planning/spikes/MANIFEST.md`). Every requirement is specific and testable.

## v1 Requirements

### Infrastructure & Platform
- [ ] **INFRA-01**: `docker compose up` поднимает весь стек (openwebui + pipelines + api) одной командой
- [ ] **INFRA-02**: OpenWebUI подключён к внешнему pipelines-серверу (:9099, ключ через env), чат отвечает
- [ ] **INFRA-03**: `.env` и `.env.example` присутствуют; секреты (GROQ_API_KEY, PIPELINES_API_KEY) не захардкожены
- [ ] **INFRA-04**: Структурированные JSON-логи фиксируют input/output каждого агента

### ASR & Diarization
- [ ] **ASR-01**: Пайплайн принимает аудио по URL (в сообщении чата) и через REST, транскрибирует faster-whisper (small int8, VAD)
- [ ] **ASR-02**: Поддержаны минимум два формата из WAV/MP3/OGG
- [ ] **ASR-03**: Транскрипт возвращается сегментами с полями speaker/start/end/text
- [ ] **ASR-04**: Диаризация делит реплики на Оператор/Клиент без pyannote
- [ ] **ASR-05**: Ошибки ASR (битый файл, недоступный URL, пустое аудио) обрабатываются с внятным сообщением

### Multi-Agent Analytics
- [ ] **AGENT-01**: Классификатор возвращает тему (кредиты/карты/переводы/жалобы) + приоритет
- [ ] **AGENT-02**: Агент качества считает чеклист (приветствие, выявление потребности, решение, прощание) + total score
- [ ] **AGENT-03**: Compliance проверяет запрещённые фразы/обязательные disclaimers, возвращает passed + issues
- [ ] **AGENT-04**: Суммаризатор даёт резюме 3–5 предложений + список action_items
- [ ] **ORCH-01**: 4 агента оркестрованы через OpenWebUI Pipeline (LangGraph или Supervisor); выбор обоснован в README

### Interfaces
- [ ] **UI-01**: В чате OpenWebUI пользователь шлёт аудио (URL) → получает полный анализ markdown-ом
- [ ] **API-01**: `POST /analyze` принимает multipart-файл или `{url}` и возвращает JSON по схеме ТЗ (transcript, classification, quality_score, compliance, summary, action_items)
- [ ] **CORE-01**: Общий framework-agnostic `run_analysis(audio)->dict` переиспользуется и Pipeline, и API (без дублирования логики)

### Tests
- [ ] **TEST-01**: pytest unit-тест на каждого из 4 агентов (на фиксированном транскрипте)
- [ ] **TEST-02**: Интеграционный pytest-тест сквозного пайплайна (аудио → JSON)

### Test Data & Evaluation
- [ ] **DATA-01**: 5+ ru-аудио в `test_data/` (вкл. 8kHz телефон и 2-голосый диалог 1мин+, суммарно 5мин+) с эталонными транскриптами
- [ ] **DATA-02**: WER-таблица (jiwer) по всем файлам против эталонов приложена к README

### Documentation & Demo
- [ ] **DOCS-01**: README на русском: архитектурная схема, инструкции запуска, обоснования (Pipeline, LLM, ASR-модель, оркестрация)
- [ ] **DEMO-01**: Живое HTTPS-демо на CPU-хосте ≥2 vCPU, отклик <60с на файл до 5 мин

## v2 / Deferred (Бонусы, +15 сверх 100)
- [ ] **BONUS-01**: Real-time WebSocket транскрипция, задержка <3с
- [ ] **BONUS-02**: Grafana-дашборд (кол-во звонков, quality_score, топ тематик)
- [ ] **BONUS-03**: Агент трендов по нескольким звонкам

## Out of Scope
- **pyannote-диаризация** — GPU/HF-токен, вне CPU-бюджета; эвристика достаточна для 2 говорящих
- **Локальная LLM** — выбран Groq (скорость + <60с); обосновано в README
- **Обучение/файнтюн ASR-моделей** — используем готовую faster-whisper
- **Аутентификация/мультипользовательность** — прототип, вне рамок ТЗ

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Pending |
| INFRA-02 | Phase 1 | Pending |
| INFRA-03 | Phase 1 | Pending |
| INFRA-04 | Phase 1 | Pending |
| CORE-01 | Phase 1 | Pending |
| API-01 | Phase 1 | Pending |
| UI-01 | Phase 1 | Pending |
| ASR-01 | Phase 2 | Pending |
| ASR-02 | Phase 2 | Pending |
| ASR-03 | Phase 2 | Pending |
| ASR-04 | Phase 2 | Pending |
| ASR-05 | Phase 2 | Pending |
| AGENT-01 | Phase 3 | Pending |
| AGENT-02 | Phase 3 | Pending |
| AGENT-03 | Phase 3 | Pending |
| AGENT-04 | Phase 3 | Pending |
| ORCH-01 | Phase 3 | Pending |
| TEST-01 | Phase 4 | Pending |
| TEST-02 | Phase 4 | Pending |
| DATA-01 | Phase 5 | Pending |
| DATA-02 | Phase 5 | Pending |
| DOCS-01 | Phase 5 | Pending |
| DEMO-01 | Phase 5 | Pending |

**Coverage:** 23/23 v1 requirements mapped. No orphans, no duplicates.
