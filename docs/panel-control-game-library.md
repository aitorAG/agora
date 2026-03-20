# Panel de Control: Libreria de Partidas

## Objetivo

Permitir a un admin gestionar el contenido de las partidas standard desde el panel de control, sin depender de archivos JSON.

## UI

La antigua seccion de observabilidad pasa a llamarse `Panel de control`.

Nueva pestaña:

- `Libreria de partidas`

Comportamiento:

- muestra todas las partidas, activas e inactivas
- selector visual con `id` en verde si esta activa y en rojo si esta inactiva
- muestra el numero de actores entre parentesis
- al seleccionar una partida, se cargan dos columnas

Columna izquierda:

- contenido actual persistido

Columna derecha:

- campos editables para modificar la partida

Cabecera:

- `ID` visible pero no editable
- toggle `Active` a la derecha del ID

## Campos editables

- `version`
- `titulo`
- `descripcion_breve`
- `ambientacion`
- `contexto_problema`
- `relevancia_jugador`
- `player_mission`
- `player_public_mission`
- `narrativa_inicial`
- todos los campos de cada actor

## API admin

- `GET /admin/standard-templates`
- `GET /admin/standard-templates/{id}`
- `PUT /admin/standard-templates/{id}`

## Reglas

- `id` es inmutable
- `config_json.id` debe coincidir con el `id` del path
- el contenido se valida con `validate_game_setup()`
- los cambios solo afectan a partidas standard nuevas

## Validacion sugerida

- guardar con boton explicito
- permitir descartar cambios
- mostrar error de validacion del backend en el panel
