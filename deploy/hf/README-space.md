---
title: MTBank Call Analytics
emoji: 📞
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# MTBank Call Analytics — live demo

Речевая аналитика звонков контакт-центра: ASR + диаризация Оператор/Клиент + LLM-агенты.
Один звонок разбирают четыре агента (классификация, качество, compliance, резюме), серию
звонков — пятый агент трендов. Доступно и в чате OpenWebUI, и по REST.

Исходники и подробный README: https://github.com/ib0gdan/speech-analytics

- **Чат:** откройте корневой URL Space, выберите модель **MTBank Call Analytics** и вставьте
  ссылку на аудио. Демо-записи вшиты в образ — например `<этот-URL>/files/call_dialog.mp3`.
  Несколько ссылок в одном сообщении → анализ трендов по серии.
- **REST:** `POST /analyze` (multipart `file` или JSON `{"url": "..."}`),
  `POST /analyze-batch` (`{"urls": [...]}`), `GET /health`.
- **Дашборд метрик (Grafana):** `<этот-URL>/grafana/` — количество звонков, quality_score,
  топ тематик (анонимный просмотр, без входа).

**Нужен секрет:** задайте `GROQ_API_KEY` в **Settings → Variables and secrets** — без него
ASR отработает, а LLM-агенты деградируют до безопасных значений (в ответе будет `agent_errors`).

> Первый запуск прогревает whisper (~500 МБ, ≈70 с) — до появления модели анализ ждёт.
