# Observability Platform

Esta carpeta contiene el stack de Langfuse desacoplado del servicio principal.

## Arranque

```bash
docker network create agora_edge || true
docker compose -f observability-platform/docker-compose.langfuse.yml up -d
```

## Exposición pública recomendada

- `langfuse-web` se publica solo en `127.0.0.1:3000`.
- El acceso externo debe hacerse a través del Nginx del stack principal, con Basic Auth.
- El vhost público esperado es `obs.<tu-dominio>`.
