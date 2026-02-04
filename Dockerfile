# Akili API — Python 3.11, poppler for pdf2image, pip install
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml requirements.txt ./
COPY src/ ./src/

RUN pip install --no-cache-dir -e .

EXPOSE 8000

# GOOGLE_API_KEY must be set at runtime (e.g. via .env or docker-compose)
# Optional: AKILI_DB_PATH for DB location (default: akili.db in cwd)
CMD ["akili-serve"]
