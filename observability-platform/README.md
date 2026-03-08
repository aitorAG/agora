# Observability Platform

Esta carpeta contiene el servicio de telemetría desacoplado del engine.

## Arranque

```bash
bash ./deploy/up.sh
```

## Exposición pública recomendada

- `telemetry` se publica solo en `127.0.0.1:8081`.
- La UI de observabilidad se sirve desde Agora y usa la misma sesión admin.
- Ruta pública recomendada: `https://<tu-dominio>/admin/observability/`.
- La API admin integrada cuelga de `/admin/observability/api/*`.

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
