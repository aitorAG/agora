# ADR: Standard Templates In DB

## Estado

Aprobado.

## Contexto

Las partidas standard estaban repartidas entre `manifest.json` y `config.json` dentro de `engine/game_templates/*`.
Eso permitia arrancar partidas, pero no permitia gestionarlas desde el panel admin ni editarlas con persistencia compartida.

## Decision

La libreria de partidas standard pasa a persistirse en base de datos mediante la tabla `standard_templates`.

Cada registro contiene:

- `id` como clave estable e inmutable
- `version`
- `active`
- `config_json` con el setup completo de la partida
- `created_at`
- `updated_at`

El runtime usa DB como fuente principal para:

- listar plantillas standard
- cargar una plantilla standard para iniciar partida
- editar plantillas desde admin

## Bootstrap

Durante la transicion, `DatabasePersistenceProvider` importa automaticamente las plantillas desde `engine/game_templates/*/config.json` si la tabla `standard_templates` esta vacia.

Esto permite:

- conservar las historias ya creadas
- desacoplar el runtime de los ficheros
- retirar los JSON del flujo principal sin perder contenido

## Consecuencias

- El panel admin puede listar y editar la libreria de partidas.
- `GET /game/standard/list` y `POST /game/standard/start` pueden operar sobre DB.
- El filesystem queda solo como semilla temporal y respaldo de migracion.
- El `id` no se edita desde UI ni desde API.

## Pendiente

- retirar el fallback/seed desde ficheros cuando la migracion a DB quede cerrada
- decidir si la `version` se incrementa manualmente o automaticamente
