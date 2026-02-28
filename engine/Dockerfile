FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app/engine

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry==1.8.3 poetry-plugin-export==1.8.0

COPY engine/pyproject.toml engine/poetry.lock ./
RUN poetry export -f requirements.txt --without-hashes -o /tmp/requirements.txt

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /tmp/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

COPY engine /app/engine
COPY frontend /app/frontend

WORKDIR /app/engine

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=30s --retries=6 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["python", "main.py"]
