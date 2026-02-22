# Product Management

## Product brief

`Agora` es un juego narrativo conversacional donde el usuario interactúa con personajes con personalidad y objetivos propios, en una historia orquestada por agentes.

Propuesta de valor:
- Experiencias narrativas únicas por partida.
- Interacción natural en chat con contexto dinámico.
- Misión clara del jugador con resolución verificable.

## Problema que resolvemos

- Los juegos narrativos tradicionales son lineales y poco reactivos.
- Los usuarios quieren agency real: influir en la historia con sus decisiones.
- Existe oportunidad en experiencias de rol accesibles desde chat/UI ligera.

## Usuarios objetivo (v1)

- Jugadores que disfrutan narrativa e improvisación.
- Creadores/testers narrativos que quieren prototipar historias rápido.
- Usuarios casuales que prefieren interacción conversacional frente a menús complejos.

## Jobs-to-be-done

- “Quiero vivir una historia interactiva distinta cada vez.”
- “Quiero decidir cómo actuar y ver consecuencias narrativas coherentes.”
- “Quiero sesiones cortas con objetivo claro y cierre satisfactorio.”

## User journey principal

1. Usuario abre UI.
2. Crea nueva partida (con seed opcional o por defecto).
3. Recibe contexto inicial + misión privada.
4. Interactúa por turnos con personajes.
5. El sistema evalúa progreso de misión del jugador.
6. Partida termina por:
   - misión del jugador cumplida, o
   - `max_turns`, o
   - salida del usuario.

## North Star y métricas

### North Star

- **Partidas completadas con satisfacción** (proxy inicial: partidas finalizadas por misión / partidas iniciadas).

### Métricas de activación

- Tiempo a primera interacción (TTFI).
- % usuarios que crean primera partida.
- % usuarios que envían al menos 1 turno.

### Métricas de engagement

- Turnos medios por partida.
- Duración media de sesión.
- % partidas con más de N turnos (ej. 5).

### Métricas de resultado narrativo

- % partidas finalizadas por misión del jugador.
- % partidas terminadas por límite de turnos.
- % partidas abandonadas.

### Guardrails

- Tasa de errores en creación de partida.
- Tiempo de respuesta por turno.
- Errores de persistencia (JSON/DB).

## Roadmap de producto (Now / Next / Later)

## Now (0-4 semanas)

- Estabilizar UX de creación de partida con seed.
- Mejorar variedad narrativa (seed y calidad de setup).
- Observabilidad de métricas básicas de sesión y finalización.

## Next (1-2 meses)

- Selector de historias predefinidas (sin regenerar setup).
- Mejoras de onboarding y claridad de misión.
- Persistencia robusta con modo DB en local/equipos.

## Later (2-4 meses)

- Modo de juego por opciones + libre (coexistencia).
- Memoria extendida de personajes y estrategia interna.
- Inventario y estado de mundo.
- Fondos/activos visuales generados asíncronamente.

## Backlog priorizado

- **P0**
  - Reducir repetición de historias con seeds similares.
  - Mejorar feedback de progreso de misión en UI.
  - Endpoints de listado/recuperación de partidas para continuidad.
- **P1**
  - Catálogo de historias preconfiguradas curadas.
  - Panel de “historial de decisiones” del jugador.
- **P2**
  - Telemetría de calidad narrativa y ajuste automático de prompts.

## Riesgos de producto

- Repetición narrativa percibida.
- Dificultad excesiva para cumplir misión.
- Sesiones largas sin sensación de progreso.
- Dependencia de calidad LLM y latencia externa.

## Mitigaciones

- Seed explícito y controles de estilo/tema.
- Reglas de cierre claras y feedback continuo.
- Métricas y experimentación por cohorts.
- Fallbacks robustos para setup y persistencia.

## Criterios de aceptación de hitos

- **Hito creación partida**
  - Formulario funcional, validaciones correctas, fallback por defecto cuando aplica.
- **Hito narrativa**
  - Contexto inicial coherente + misión accionable en >95% de partidas testeadas.
- **Hito persistencia**
  - Guardado y recuperación consistentes en modo JSON y DB.

## Dependencias inter-áreas

- Producto + Ingeniería: definición de métricas y eventos.
- Producto + Narrativa: calidad de prompts y tono de historias.
- Producto + Infra: estabilidad de entorno DB para iteración rápida.

## Decisiones de alcance

- v1 no contempla autenticación real (usuario fijo `usuario`).
- Prioridad en calidad de loop narrativo antes de features cosméticas avanzadas.

## Referencias

- `README.md`
- `.cursor/features.txt`
- `documents/infra.md`
