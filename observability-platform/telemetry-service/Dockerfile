FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gosu \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system agora && useradd --system --gid agora --create-home --home-dir /home/agora agora

COPY observability-platform/telemetry-service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

RUN mkdir -p /data && chown -R agora:agora /data /app

COPY --chown=agora:agora observability-platform/telemetry-service /app
COPY observability-platform/telemetry-service/docker-entrypoint.sh /usr/local/bin/telemetry-entrypoint.sh

RUN chmod +x /usr/local/bin/telemetry-entrypoint.sh

EXPOSE 8081

HEALTHCHECK --interval=20s --timeout=5s --start-period=10s --retries=6 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8081/health', timeout=3)"

ENTRYPOINT ["/usr/local/bin/telemetry-entrypoint.sh"]
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8081"]
