"""Construcción del grafo LangGraph."""

from typing import Literal
from langgraph.graph import StateGraph, END
from .state import ConversationState
from .manager import ConversationManager
from .agents.character import CharacterAgent
from .agents.observer import ObserverAgent
from .renderer import render_message


def create_conversation_graph(
    character_agents: dict[str, CharacterAgent],
    observer_agent: ObserverAgent,
    manager: ConversationManager,
    max_turns: int = 10
) -> StateGraph:
    """Crea el grafo de conversación con LangGraph.
    
    Args:
        character_agents: Diccionario nombre del personaje -> CharacterAgent (uno o varios)
        observer_agent: Agente observador que analiza
        manager: ConversationManager para gestionar estado
        max_turns: Número máximo de turnos
        
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
            print(f"Error en {agent.name}: {result['error']}")
            return state
        
        # Añadir mensaje al estado
        manager.add_message(result["author"], result["message"])
        
        # Renderizar mensaje
        last_message = manager.state["messages"][-1]
        render_message(last_message)
        
        return manager.state
    
    def user_input_node(state: ConversationState) -> ConversationState:
        """Nodo que solicita entrada del usuario."""
        # Solicitar input del usuario
        user_input = input("Tú: ").strip()
        
        # Comandos de salida (case-insensitive)
        exit_commands = {"exit", "quit", "salir", "q"}
        if user_input.lower() in exit_commands:
            # Marcar en metadata que el usuario quiere salir
            manager.update_metadata("user_exit", True)
            return manager.state
        
        # Si el usuario no escribió nada, no añadir mensaje
        if not user_input:
            return manager.state
        
        # Añadir mensaje del usuario al estado
        manager.add_message("Usuario", user_input)
        
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
        
        return manager.state
    
    def increment_turn_node(state: ConversationState) -> ConversationState:
        """Nodo que incrementa el contador de turnos."""
        manager.increment_turn()
        return manager.state
    
    def should_allow_continuation(state: ConversationState) -> Literal["character", "user_input", "continue"]:
        """Decide si alguien debe continuar antes de incrementar el turno.
        
        Basado en la decisión del ObserverAgent: character (nombre concreto o "character"),
        user, o nadie. Si who_should_respond es un nombre en character_agents o "character", va al nodo character.
        """
        # Obtener decisión del observer desde metadata
        continuation_decision = state.get("metadata", {}).get("continuation_decision", {})
        
        # Si no hay decisión o no se necesita respuesta, continuar normalmente
        if not continuation_decision.get("needs_response", False):
            return "continue"
        
        # Verificar quién debe responder
        who_should_respond = continuation_decision.get("who_should_respond", "none")
        
        if who_should_respond == "user":
            return "user_input"
        if who_should_respond == "character" or who_should_respond in character_agents:
            return "character"
        return "continue"
    
    def should_continue(state: ConversationState) -> Literal["continue", "end"]:
        """Condición para decidir si continuar o terminar."""
        # Verificar si el usuario quiere salir
        if state.get("metadata", {}).get("user_exit", False):
            return "end"
        
        # Verificar si se alcanzó el máximo de turnos
        if state["turn"] >= max_turns:
            return "end"
        
        return "continue"
    
    # Construir grafo
    workflow = StateGraph(ConversationState)
    
    # Añadir nodos
    workflow.add_node("character", character_agent_node)
    workflow.add_node("user_input", user_input_node)
    workflow.add_node("observer", observer_agent_node)
    workflow.add_node("increment_turn", increment_turn_node)
    
    # Definir punto de entrada
    workflow.set_entry_point("character")
    
    # Añadir edges
    workflow.add_edge("character", "user_input")
    workflow.add_edge("user_input", "observer")
    
    # Edge condicional desde observer basado en decisión de continuación
    workflow.add_conditional_edges(
        "observer",
        should_allow_continuation,
        {
            "character": "character",
            "user_input": "user_input",
            "continue": "increment_turn"
        }
    )
    
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
