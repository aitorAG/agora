# Conversation Engine

Motor narrativo conversacional para videojuego basado en agentes, construido con LangGraph.

## Descripción

Este proyecto implementa un sistema de conversación donde múltiples agentes interactúan en un chat grupal. El sistema separa agentes "actores" (que participan en la conversación) de agentes "observadores" (que analizan sin escribir).

## Características

- **Estado conversacional persistente**: Mantiene historial completo de mensajes
- **Múltiples agentes**: Soporte para agentes con distintos roles
- **Separación actores/observadores**: Agentes que hablan vs. agentes que solo analizan
- **Arquitectura extensible**: Base para futuras funcionalidades narrativas complejas

## Requisitos

- Python 3.8+
- Poetry (para gestión de dependencias)
- API Key de DeepSeek

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

5. Edita `.env` y añade tu API key de DeepSeek:
```
DEEPSEEK_API_KEY=tu_api_key_aqui
```

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

El sistema iniciará una conversación con un CharacterAgent y un ObserverAgent, mostrando los mensajes en terminal.

## Estructura del Proyecto

```
agora/
├── src/
│   ├── state.py              # ConversationState (TypedDict)
│   ├── manager.py            # ConversationManager
│   ├── agents/
│   │   ├── base.py           # Clase base Agent
│   │   ├── character.py      # CharacterAgent
│   │   └── observer.py       # ObserverAgent
│   ├── graph.py              # Construcción del grafo LangGraph
│   └── renderer.py           # Renderizado en terminal
├── main.py                   # Punto de entrada
├── pyproject.toml            # Configuración de Poetry
├── poetry.lock               # Lock file de dependencias (generado)
├── requirements.txt          # Dependencias (opcional, para compatibilidad)
├── .env.example
└── README.md
```

## Componentes Principales

### ConversationState
Estado global que contiene:
- `messages`: Lista de mensajes con autor, contenido, timestamp y turno
- `turn`: Contador de turnos
- `metadata`: Espacio para análisis y flags narrativos

### ConversationManager
Orquestador que:
- Gestiona el estado de conversación
- Valida quién puede escribir
- Proporciona historial a los agentes

### CharacterAgent
Agente actor que:
- Participa activamente en la conversación
- Genera respuestas usando DeepSeek
- Tiene personalidad configurable

### ObserverAgent
Agente observador que:
- Analiza la conversación sin escribir
- Calcula métricas (participación, longitud, repeticiones, tono)
- Actualiza metadata del estado

### Grafo LangGraph
Flujo de ejecución:
1. `character_agent_node`: Genera mensaje
2. `observer_agent_node`: Analiza estado
3. `increment_turn_node`: Incrementa contador
4. Ciclo hasta máximo de turnos

## Extensibilidad

El diseño permite fácilmente:
- Añadir más CharacterAgents
- Implementar agentes narrativos (ritmo, giros, tensión)
- Integrar decisiones del jugador
- Migrar a interfaz gráfica

## Licencia

Este proyecto es parte de un videojuego en desarrollo.
