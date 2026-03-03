# Observability Platform

Esta carpeta contiene el servicio de telemetría desacoplado del engine.

## Arranque

```bash
bash ./deploy/up.sh
```

## Exposición pública recomendada

- `telemetry` se publica solo en `127.0.0.1:8081`.
- El acceso externo se hace por Nginx del stack principal con autorización admin.
- Ruta pública recomendada: `https://<tu-dominio>/admin/observability/`.
- API agregada: `/admin/observability/api/v1/metrics/*`.

## Qué mide

- Coste, tiempo y tokens por llamada LLM.
- Agregados por usuario.
- Agregados por partida.
- Agregados por turno.
- Agregados por agente.

## Variables relevantes

- `TELEMETRY_ENABLED`: activa o desactiva emisión desde el engine.
- `TELEMETRY_INGEST_KEY`: clave compartida entre engine y servicio de telemetría.
- `TELEMETRY_ENDPOINT`: endpoint interno de ingesta. En Docker: `http://telemetry:8081/v1/events`.
