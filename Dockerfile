# Akili API — Python 3.11, poppler for pdf2image, gunicorn for production
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml requirements.txt README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir -e ".[postgres,auth]" gunicorn

EXPOSE 8080

# Cloud Run sets PORT dynamically; default to 8080
ENV PORT=8080

# GOOGLE_API_KEY and DATABASE_URL must be set at runtime
# 2 uvicorn workers for 1 vCPU Cloud Run instances
# 300s timeout for long PDF ingestion jobs
CMD exec gunicorn akili.api.app:app \
    --bind "0.0.0.0:${PORT}" \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 2 \
    --timeout 300 \
    --access-logfile - \
    --error-logfile -
