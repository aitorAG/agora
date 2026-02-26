# Conversation Engine

Motor narrativo conversacional para videojuego basado en agentes, orquestado con **CrewAI** (Director central, roles para Guionista, Character y Observer).

## Descripción

Este proyecto implementa un sistema de conversación donde múltiples agentes interactúan en un chat grupal. El **Director** orquesta el flujo: solicita setup al Guionista, y en cada turno consulta al Observer (quién habla, evaluación de misiones) e invoca Character agents o input del jugador.

## Características

- **Director como orquestador central**: Bucle de partida en código (sin grafo); delega en roles CrewAI (Guionista, Character, Observer).
- **Estado conversacional persistente**: Historial completo de mensajes con turno por intervención del jugador (ConversationManager).
- **Tres personajes por partida**: El Guionista genera ambientación, situación, relevancia y tres actores con presencia en escena.
- **Narrativa inicial en prosa**: Presentación orgánica (sin apartados) al jugador; misión privada al final.
- **Turno = intervención del jugador**: Cada vez que el jugador escribe se cuenta un turno; `max_turns` limita esas intervenciones.
- **Evaluación de misiones**: El Observer evalúa quién debe hablar y si se cumplieron misiones (game_ended); el Director aplica el cierre.
- **Routing por nombre**: El Observer indica qué personaje debe hablar; el Director invoca al Character correcto.
- **Terminal jugable**: Cliente ligero con InputProvider/OutputHandler; arquitectura lista para cliente Android o UI futura.
- **DeepSeek vía cliente OpenAI**: Todas las llamadas al LLM pasan por `src/agents/deepseek_adapter.py` (función `send_message`); se usa el paquete `openai` con `base_url` de DeepSeek. No se usa LangChain ni LiteLLM.

## Requisitos

- Python 3.10+
- Poetry (para gestión de dependencias)
- API Key de DeepSeek (para ejecutar el juego; los tests no la necesitan)

## Instalación

### Instalar Poetry

Si no tienes Poetry instalado, puedes instalarlo con:

```bash
# Windows (PowerShell)
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -

# Linux/macOS
curl -sSL https://install.python-poetry.org | python3 -
```

O usando pip:
```bash
pip install poetry
```

### Configurar el proyecto

1. Clona el repositorio o navega al directorio del proyecto

2. **Configurar Poetry para usar el intérprete de Python del PATH:**

   Para que Poetry use el intérprete de Python que está en tu PATH, ejecuta:

   ```bash
   # Windows
   poetry env use python

   # Linux/macOS
   poetry env use python3
   ```

   O si quieres que Poetry siempre use el intérprete activo del sistema:

   ```bash
   poetry config virtualenvs.prefer-active-python true
   ```

   Esto hará que Poetry use el intérprete de Python que está actualmente activo en tu PATH.

3. Instala las dependencias con Poetry:
```bash
poetry install
```

   **Nota:** Puedes verificar qué intérprete de Python está usando Poetry con:
   ```bash
   poetry env info
   ```

4. Crea un archivo `.env` basado en `.env.example`:
```bash
cp .env.example .env
```

5. Edita `.env` y configura variables mínimas:
```
DEEPSEEK_API_KEY=tu_api_key_aqui
DATABASE_URL=postgresql://agora_user:agora_pass@localhost:5432/agora
```
   Las llamadas al modelo se realizan con el **cliente OpenAI** apuntando al endpoint de DeepSeek (`https://api.deepseek.com`); el adaptador central está en `src/agents/deepseek_adapter.py` y usa esta variable de entorno. La persistencia de partidas y usuarios es DB-only y requiere `DATABASE_URL`.

## Docker y Observabilidad (Langfuse)

El proyecto incluye un `docker-compose.yml` que levanta la infraestructura necesaria:

```bash
docker compose up -d
```

Se inician:

- **Postgres** (Agora): `localhost:5432` — base de datos para partidas y usuarios
- **Langfuse** (observabilidad): UI en http://localhost:3000 — trazas, tokens y tiempos de ejecución
- **Postgres Langfuse**, ClickHouse, Redis, MinIO — servicios internos de Langfuse

Esperar 2-3 minutos hasta que `langfuse-web` muestre "Ready" en los logs.

### Configurar Langfuse (opcional)

Para habilitar la observabilidad en Agora:

1. Crear cuenta en la UI de Langfuse (http://localhost:3000)
2. Crear un proyecto
3. Copiar las credenciales (Public Key, Secret Key) del proyecto
4. Añadir a `.env`:

```
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000
# Opcional: si no usas LANGFUSE_HOST
# LANGFUSE_BASE_URL=http://localhost:3000
# Opcional: pricing DeepSeek para calcular gasto en Langfuse
DEEPSEEK_INPUT_COST_PER_1M_TOKENS=0.27
DEEPSEEK_OUTPUT_COST_PER_1M_TOKENS=1.10
```

O usar `LANGFUSE_BASE_URL` en lugar de `LANGFUSE_HOST`. Si no se configuran, Agora funciona sin observabilidad.
Para visualizar gasto aunque Langfuse no tenga pricing nativo del modelo, Agora envía `cost_details` por llamada usando las tarifas anteriores.

### Producción

Para producción, actualizar los secrets en `.env` o variables de entorno:

- `ENCRYPTION_KEY`: generar con `openssl rand -hex 32`
- `NEXTAUTH_SECRET`: valor aleatorio seguro
- `POSTGRES_PASSWORD`, `CLICKHOUSE_PASSWORD`, `REDIS_AUTH`, `MINIO_ROOT_PASSWORD`: contraseñas fuertes

Referencias: [Langfuse Self-Hosting](https://langfuse.com/self-hosting/deployment/docker-compose), [PRD Observabilidad](.cursor/PRD-observabilidad-langfuse-despliegue.md).

## Uso

### Opción 1: Usando Poetry run

Ejecuta el programa con:

```bash
poetry run agora
```

### Opción 2: Activando el entorno virtual

Activa el shell de Poetry y ejecuta directamente:

```bash
poetry shell
agora
```

### Opción 3: Ejecutar directamente (si el entorno está activo)

```bash
python main.py
```

El sistema generará un setup con el Guionista (ambientación, situación, tres personajes), mostrará la narrativa inicial y tu misión, y comenzará una conversación por turnos. Los mensajes se muestran en terminal.

## Tests

El proyecto incluye tests unitarios para reducir riesgo en cambios de estado, reglas de turno, routing del Director y parsing de respuestas (Observer, Guionista). Son deterministas y rápidos; no usan LLM ni entorno gráfico.

### Instalar dependencias de desarrollo

Para ejecutar los tests necesitas las dependencias de desarrollo (p. ej. pytest):

```bash
poetry install
```

Con `poetry install` se instalan también las dependencias del grupo `dev` (pytest). Si ya tenías el proyecto instalado y no tienes pytest:

```bash
poetry install --with dev
```

### Ejecutar los tests

Desde la raíz del proyecto:

```bash
# Todos los tests
poetry run pytest

# Con salida verbose (nombre de cada test)
poetry run pytest -v

# Solo tests unitarios
poetry run pytest tests/unit/

# Un archivo concreto
poetry run pytest tests/unit/test_manager.py -v
```

Los tests no requieren API key ni red; se ejecutan en local y en CI sin entorno gráfico.

### Estructura de tests

```
tests/
├── conftest.py                   # Fixtures compartidos (manager, sample state)
└── unit/
    ├── test_manager.py           # ConversationManager (estado, turno, metadata)
    ├── test_director.py          # route_continuation, route_should_continue
    ├── test_observer_normalization.py   # normalize_who_should_respond
    ├── test_observer_missions_parsing.py # parse_mission_evaluation_response
    ├── test_observer_game_ended.py      # game_ended / game_ended_reason
    └── test_guionista.py         # _default_setup (claves, actores, narrativa_inicial)
```

## Estructura del Proyecto

```
agora/
├── src/
│   ├── state.py              # ConversationState (TypedDict)
│   ├── manager.py            # ConversationManager
│   ├── crew_roles/           # Roles CrewAI (Director orquesta; Guionista, Character, Observer)
│   │   ├── director.py       # run_game_loop, route_continuation, route_should_continue
│   │   ├── guionista.py      # create_guionista_agent, run_setup_task
│   │   ├── character.py      # create_character_agent, run_character_response
│   │   └── observer.py       # create_observer_agent, run_observer_tasks
│   ├── agents/               # Implementación de agentes (usados por crew_roles)
│   │   ├── base.py           # Clase base Agent
│   │   ├── deepseek_adapter.py  # send_message: llamadas a DeepSeek vía cliente OpenAI
│   │   ├── character.py      # CharacterAgent
│   │   ├── observer.py       # ObserverAgent
│   │   └── guionista.py      # GuionistaAgent (_default_setup)
│   ├── session.py            # create_session (runner, initial_state, setup)
│   ├── io_adapters.py        # InputProvider, OutputHandler (terminal)
│   └── renderer.py           # Renderizado en terminal
├── tests/
│   ├── conftest.py
│   └── unit/
├── main.py                   # Cliente terminal (invoca session + runner)
├── game_setup.json           # Setup generado por el Guionista al iniciar
├── pyproject.toml
├── poetry.lock
├── requirements.txt
├── .env.example
└── README.md
```

### game_setup.json

Lo genera el **Guionista** al iniciar la partida. Contiene:

- **ambientacion**: Escenario, época, lugar, tono.
- **contexto_problema**: Situación o conflicto en juego.
- **relevancia_jugador**: Por qué le importa al jugador.
- **player_mission**: Misión privada del jugador (se muestra al inicio).
- **narrativa_inicial**: Prosa continua que integra todo lo anterior y presenta a los tres personajes en escena (sin apartados).
- **actors**: Lista de tres actores, cada uno con `name`, `personality`, `mission`, `background` y `presencia_escena` (frase breve para la narrativa inicial).

Formato resumido:

```json
{
  "ambientacion": "...",
  "contexto_problema": "...",
  "relevancia_jugador": "...",
  "player_mission": "...",
  "narrativa_inicial": "Prosa continua con escenario, situación y los tres personajes...",
  "actors": [
    { "name": "...", "personality": "...", "mission": "...", "background": "...", "presencia_escena": "..." }
  ]
}
```

## Componentes Principales

### ConversationState
Estado global que contiene:
- `messages`: Lista de mensajes con autor, contenido, timestamp y turno
- `turn`: Contador de turnos
- `metadata`: Espacio para análisis y flags narrativos

### ConversationManager
Orquestador que:
- Gestiona el estado (messages, turn, metadata)
- Añade mensajes con el turn actual; el turno se incrementa en el nodo de input del usuario (cada intervención del jugador = 1 turno)
- Proporciona historial y metadata a los agentes

### GuionistaAgent
Agente que al inicio genera el setup (no es actor):
- Genera ambientación, contexto_problema, relevancia_jugador, player_mission, narrativa_inicial y tres actores (name, personality, mission, background, presencia_escena)
- Se invoca una vez al arranque; el resultado se guarda en game_setup.json
- Si el LLM falla, se usa `_default_setup(num_actors)` con valores por defecto

### CharacterAgent
Agente actor que:
- Participa en la conversación; con varios actores el grafo elige cuál invocar por nombre
- Genera respuestas con DeepSeek según personalidad, misión privada y background

### Observer (rol CrewAI)
Agente observador que:
- Analiza la conversación sin escribir (métricas, participación).
- Decide quién debe hablar (who_should_respond: user, nombre de personaje o none); normalización en `normalize_who_should_respond`.
- Evalúa misiones (player_mission_achieved, actor_missions_achieved); parsing en `parse_mission_evaluation_response`. Deriva `game_ended` y `game_ended_reason` para cierre narrativo.

### Director (orquestador)
- **run_game_loop**: Ejecuta el bucle de partida: tras cada intervención (character o user) llama al Observer; según decisión invoca Character, pide user_input o pasa a increment_turn; si game_ended llama a output_handler.on_game_ended y termina.
- **route_continuation** y **route_should_continue**: Funciones puras que deciden el siguiente paso o el fin (testeables en test_director.py).

### Flujo (diagrama)

```mermaid
flowchart TB
  subgraph init [Inicialización]
    A[Director crea agentes]
    B[Guionista: generar setup]
    C[Manager estado inicial]
    A --> B --> C
  end
  subgraph loop [Bucle de turno]
    D[Director pide Observer: quién habla y misiones]
    E{game_ended?}
    F[finalize: on_game_ended]
    G{who_should_respond?}
    H[Character: generar respuesta]
    I[user_input]
    J[Director: add_message, increment_turn si user]
    K{max_turns o user_exit?}
    D --> E
    E -->|sí| F
    E -->|no| G
    G -->|character| H
    G -->|user| I
    G -->|continue| K
    H --> J
    I --> J
    J --> K
    K -->|no| D
    K -->|sí| endNode[END]
    F --> endNode
  end
  C --> D
```

### Tabla de roles

| Rol        | Entradas                    | Salidas                                                                 | Responsabilidades                          |
|-----------|-----------------------------|--------------------------------------------------------------------------|-------------------------------------------|
| Guionista | theme, num_actors            | ambientacion, contexto_problema, player_mission, narrativa_inicial, actors | Generar setup inicial (game_setup.json)  |
| Character | historial, personality, mission, background, name | message, author (o error)                                              | Generar réplica del personaje             |
| Observer  | historial, turno, actor_names, player_mission, actor_missions | continuation_decision, mission_evaluation, game_ended, game_ended_reason | Quién habla; evaluación misiones; cierre  |
| Director  | Manager, agentes, I/O, max_turns | —                                                                       | Orquestar bucle; llamar a Guionista/Character/Observer; finalize        |

## Lista de cambios (migración LangGraph → CrewAI)

- **Reescrito**: Grafo LangGraph eliminado; lógica de bucle y routing en `crew_roles/director.py`; `session.py` devuelve `(runner, initial_state, setup)` y usa crew_roles; `main.py` invoca `runner()` en lugar de `graph.invoke()`.
- **Adaptado**: `state.py` y `manager.py` sin cambio de contrato; `io_adapters.py` sin cambio; tests: `test_graph_routing` sustituido por `test_director` (imports desde `crew_roles.director`); tests de observer game_ended con mock de LLM para determinismo; `pyproject.toml` y `requirements.txt` con `crewai`, sin `langgraph`.
- **Eliminado**: Dependencia LangGraph; `src/graph.py`.

## Extensibilidad

El diseño permite fácilmente:
- Añadir más CharacterAgents
- Implementar agentes narrativos (ritmo, giros, tensión)
- Integrar decisiones del jugador
- Migrar a interfaz gráfica

## Licencia

Este proyecto es parte de un videojuego en desarrollo.
