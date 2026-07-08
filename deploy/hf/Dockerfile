# All-in-one image for Hugging Face Spaces (Docker SDK, single container, single port 7860).
# Self-contained: clones the public project repo at build time, so the HF Space needs only
# this Dockerfile + README.md. Runs OpenWebUI (8080) + Pipelines (9099) + FastAPI (8000)
# behind nginx (7860). The Pipeline and API share the same mtbank/ core (no duplicated logic).
FROM ghcr.io/open-webui/open-webui:main

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
        nginx supervisor git ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# --- External OpenWebUI Pipelines server ---
RUN git clone --depth 1 https://github.com/open-webui/pipelines /pipelines \
    && pip install --no-cache-dir -r /pipelines/requirements.txt

# --- Project code (public repo). Bump REF / use --no-cache to redeploy latest. ---
ARG REPO=https://github.com/ib0gdan/speech-analytics
ARG REF=main
RUN git clone --depth 1 -b ${REF} ${REPO} /opt/app \
    && cp /opt/app/pipelines/mtbank_pipeline.py /pipelines/pipelines/mtbank_pipeline.py \
    && cp /opt/app/deploy/hf/supervisord.conf /etc/supervisor/conf.d/mtbank.conf \
    && cp /opt/app/deploy/hf/nginx.conf /etc/nginx/sites-available/default \
    && cp /opt/app/deploy/hf/start.sh /start.sh \
    && chmod +x /start.sh \
    && mkdir -p /app/backend/data /pipelines/pipelines /var/log/supervisor \
    && chmod -R 777 /app/backend/data /pipelines /var/lib/nginx /var/log/nginx /var/log/supervisor

ENV PYTHONPATH=/opt/app \
    WEBUI_AUTH=False \
    ENABLE_OPENAI_API=true \
    OPENAI_API_BASE_URL=http://127.0.0.1:9099 \
    OPENAI_API_KEY=0p3n-w3bu! \
    PIPELINES_API_KEY=0p3n-w3bu! \
    LLM_BASE_URL=https://api.groq.com/openai/v1 \
    LLM_MODEL=llama-3.3-70b-versatile \
    PORT=8080

EXPOSE 7860
CMD ["/start.sh"]
