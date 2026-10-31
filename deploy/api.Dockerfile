FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    AI4BRAIN_DB=/var/lib/ai4brain/ai4brain.sqlite3 \
    AI4BRAIN_TTS_CACHE=/var/cache/ai4brain/tts \
    HF_HOME=/var/cache/ai4brain/huggingface

RUN apt-get update \
    && apt-get install -y --no-install-recommends libsndfile1 libgomp1 espeak-ng ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app \
    && mkdir -p /var/lib/ai4brain /var/cache/ai4brain \
    && chown -R app:app /var/lib/ai4brain /var/cache/ai4brain

WORKDIR /app
COPY backend/requirements-lock.txt backend/requirements-lock.txt
COPY deploy/requirements-tts.txt deploy/requirements-tts.txt
RUN python -m pip install --no-cache-dir -r backend/requirements-lock.txt -r deploy/requirements-tts.txt \
    && python -m pip install --no-cache-dir --no-deps kittenml==0.9.4

COPY backend/ backend/
COPY deploy/sqlite_transfer.py deploy/sqlite_transfer.py
USER app
EXPOSE 8000
# One worker preserves the application's process-owned coaching/speech lifecycle.
CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
