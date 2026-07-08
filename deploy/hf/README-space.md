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

OpenWebUI chat + REST `POST /analyze` for contact-center call analytics
(ASR + Оператор/Клиент diarization + 4 LLM agents). Source:
https://github.com/ib0gdan/speech-analytics

- Chat UI: open this Space's root URL, pick the **MTBank Call Analytics** model,
  paste an audio URL.
- REST: `POST /analyze` (multipart `file` or JSON `{"url": "..."}`), `GET /health`.

**Secret required:** set `GROQ_API_KEY` in the Space **Settings → Variables and secrets**.
