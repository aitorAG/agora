"""Construcción del grafo LangGraph."""

from typing import Literal
from langgraph.graph import StateGraph, END
from .state import ConversationState
from .manager import ConversationManager
from .agents.character import CharacterAgent
from .agents.observer import ObserverAgent
from .io_adapters import InputProvider, OutputHandler


def route_continuation(
    continuation_decision: dict,
    character_agent_names: list[str],
) -> Literal["character", "user_input", "continue"]:
    """Decide el siguiente nodo tras el observer: character, user_input o continue.
    
    Args:
        continuation_decision: Dict con needs_response y who_should_respond.
        character_agent_names: Lista de nombres de agentes (claves del dict de character_agents).
    
    Returns:
        "character", "user_input" o "continue".
    """
    if not continuation_decision.get("needs_response", False):
        return "continue"
    who_should_respond = continuation_decision.get("who_should_respond", "none")
    if who_should_respond == "user":
        return "user_input"
    if who_should_respond == "character" or who_should_respond in character_agent_names:
        return "character"
    return "continue"


def route_should_continue(state: ConversationState, max_turns: int) -> Literal["continue", "end"]:
    """Decide si continuar al siguiente turno o terminar.
    
    Args:
        state: Estado actual de la conversación.
        max_turns: Número máximo de turnos (intervenciones del jugador).
    
    Returns:
        "continue" o "end".
    """
    if state.get("metadata", {}).get("user_exit", False):
        return "end"
    if state["turn"] >= max_turns:
        return "end"
    return "continue"


def create_conversation_graph(
    character_agents: dict[str, CharacterAgent],
    observer_agent: ObserverAgent,
    manager: ConversationManager,
    max_turns: int = 10,
    *,
    input_provider: InputProvider,
    output_handler: OutputHandler,
) -> StateGraph:
    """Crea el grafo de conversación con LangGraph.
    
    Args:
        character_agents: Diccionario nombre del personaje -> CharacterAgent (uno o varios)
        observer_agent: Agente observador que analiza
        manager: ConversationManager para gestionar estado
        max_turns: Número máximo de turnos
        input_provider: Abstracción para obtener input del jugador (inyección de I/O)
        output_handler: Abstracción para emitir mensajes y errores (inyección de I/O)
        
    Returns:
        Grafo LangGraph configurado
    """
    # Orden fijo de nombres (primer personaje abre cada turno cuando no hay decisión de continuación)
    agent_names_ordered = list(character_agents.keys())

    def character_agent_node(state: ConversationState) -> ConversationState:
        """Nodo que ejecuta el CharacterAgent correspondiente (por nombre o el primero del turno)."""
        continuation_decision = state.get("metadata", {}).get("continuation_decision", {})
        who_should_respond = continuation_decision.get("who_should_respond", "")
        # Si hay un nombre concreto en character_agents, usar ese agente; si no, usar el primero (nuevo turno)
        if who_should_respond and who_should_respond in character_agents:
            agent = character_agents[who_should_respond]
        else:
            agent = character_agents[agent_names_ordered[0]]
        result = agent.process(state)
        
        if "error" in result:
            output_handler.on_error(f"Error en {agent.name}: {result['error']}")
            return state
        
        # Añadir mensaje al estado
        manager.add_message(result["author"], result["message"])
        
        # Emitir mensaje vía handler (motor no conoce print)
        last_message = manager.state["messages"][-1]
        output_handler.on_message(last_message)
        
        return manager.state
    
    def user_input_node(state: ConversationState) -> ConversationState:
        """Nodo que solicita entrada del usuario vía InputProvider."""
        user_result = input_provider.get_user_input()
        
        if user_result.user_exit:
            manager.update_metadata("user_exit", True)
            return manager.state
        
        if not user_result.text or not user_result.text.strip():
            return manager.state
        
        manager.add_message("Usuario", user_result.text.strip())
        manager.increment_turn()
        
        return manager.state
    
    def observer_agent_node(state: ConversationState) -> ConversationState:
        """Nodo que ejecuta el ObserverAgent."""
        result = observer_agent.process(state)
        
        if "update_metadata" in result and result["update_metadata"]:
            # Actualizar metadata con el análisis
            analysis = result.get("analysis", {})
            manager.update_metadata(f"turn_{state['turn']}_analysis", analysis)
        
        # Guardar decisión de continuación en metadata
        if "continuation_decision" in result:
            manager.update_metadata("continuation_decision", result["continuation_decision"])
        # Guardar evaluación de misiones (jugador y actores) al final del turno
        if "mission_evaluation" in result:
            manager.update_metadata("last_mission_evaluation", result["mission_evaluation"])
            manager.update_metadata(f"turn_{state['turn']}_mission_evaluation", result["mission_evaluation"])
        # Guardar decisión de cierre (partida terminada por misión + evidencia)
        if "game_ended" in result:
            manager.update_metadata("game_ended", result["game_ended"])
        if "game_ended_reason" in result:
            manager.update_metadata("game_ended_reason", result["game_ended_reason"])
        
        return manager.state
    
    def increment_turn_node(state: ConversationState) -> ConversationState:
        """Passthrough: el turno ya se incrementó en user_input_node al hablar el jugador."""
        return manager.state

    def finalize_node(state: ConversationState) -> ConversationState:
        """Cierre por misión cumplida: notifica al cliente y termina."""
        reason = state.get("metadata", {}).get("game_ended_reason", "")
        evaluation = state.get("metadata", {}).get("last_mission_evaluation", {})
        output_handler.on_game_ended(reason, evaluation)
        return manager.state
    
    def observer_route(state: ConversationState) -> Literal["finalize", "character", "user_input", "continue"]:
        """Primero game_ended → finalize; si no, decisión de continuación (character / user_input / continue)."""
        if state.get("metadata", {}).get("game_ended", False):
            return "finalize"
        continuation_decision = state.get("metadata", {}).get("continuation_decision", {})
        return route_continuation(continuation_decision, agent_names_ordered)
    
    def should_continue(state: ConversationState) -> Literal["continue", "end"]:
        return route_should_continue(state, max_turns)
    
    # Construir grafo
    workflow = StateGraph(ConversationState)
    
    # Añadir nodos
    workflow.add_node("character", character_agent_node)
    workflow.add_node("user_input", user_input_node)
    workflow.add_node("observer", observer_agent_node)
    workflow.add_node("increment_turn", increment_turn_node)
    workflow.add_node("finalize", finalize_node)
    
    # Definir punto de entrada
    workflow.set_entry_point("character")
    
    # Arcos: tras cada intervención (character o user_input) se pasa por observer
    workflow.add_edge("character", "observer")
    workflow.add_edge("user_input", "observer")
    
    # Edge condicional desde observer: game_ended → finalize; si no → character | user_input | increment_turn
    workflow.add_conditional_edges(
        "observer",
        observer_route,
        {
            "finalize": "finalize",
            "character": "character",
            "user_input": "user_input",
            "continue": "increment_turn"
        }
    )
    workflow.add_edge("finalize", END)
    
    # Edge condicional desde increment_turn
    workflow.add_conditional_edges(
        "increment_turn",
        should_continue,
        {
            "continue": "character",
            "end": END
        }
    )
    
    return workflow.compile()
