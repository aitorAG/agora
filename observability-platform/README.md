# Observability Platform

Esta carpeta contiene el stack de Langfuse desacoplado del servicio principal.

## Arranque

```bash
./deploy/up.sh
```

## Exposición pública recomendada

- `langfuse-web` se publica solo en `127.0.0.1:3000`.
- El acceso externo debe hacerse a través del Nginx del stack principal, con autorización admin.
- Ruta pública recomendada: `https://<tu-dominio>/admin/observability/`.
- La URL pública se resuelve automáticamente según `AGORA_DEPLOY_TARGET` y `AGORA_BASE_URL_*`.
- Para despliegue single-node, usa `CLICKHOUSE_CLUSTER_ENABLED=false`.
