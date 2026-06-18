# Akili API — Python 3.11, poppler for pdf2image, gunicorn for production
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml requirements.txt README.md ./
COPY src/ ./src/

# psycopg2-binary and slowapi are core deps in pyproject; [auth] adds firebase-admin.
RUN pip install --no-cache-dir -e ".[auth]" gunicorn

# Run as a non-root user; pre-create the writable docs dir it owns.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data/docs \
    && chown -R appuser:appuser /app
USER appuser

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
