"""Punto de entrada del Conversation Engine."""

import os
import logging
from dotenv import load_dotenv
from src.state import ConversationState
from src.manager import ConversationManager
from src.agents.character import CharacterAgent
from src.agents.observer import ObserverAgent
from src.graph import create_conversation_graph

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Silenciar logs HTTP de librerías externas
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.WARNING)
logging.getLogger("langgraph").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def main():
    """Función principal."""
    # Verificar API key
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("Error: DEEPSEEK_API_KEY no encontrada en variables de entorno")
        print("Por favor, crea un archivo .env con tu API key de DeepSeek")
        return
    
    print("=== Conversation Engine ===")
    print("Inicializando sistema conversacional...\n")
    
    # Inicializar estado
    manager = ConversationManager()
    initial_state: ConversationState = manager.state
    
    # Crear agentes
    character = CharacterAgent(
        name="Alice",
        personality="Eres curiosa, amigable y entusiasta. Te gusta hacer preguntas y mantener conversaciones interesantes."
    )
    
    observer = ObserverAgent()
    
    print(f"Agente creado: {character.name}")
    print(f"Observador creado: {observer.name}\n")
    
    # Obtener número máximo de turnos desde variable de entorno
    max_turns_str = os.getenv("MAX_TURNS", "10")
    try:
        max_turns = int(max_turns_str)
        if max_turns <= 0:
            raise ValueError("MAX_TURNS debe ser un número positivo")
    except ValueError as e:
        logger.warning(f"Valor inválido para MAX_TURNS: {max_turns_str}. Usando valor por defecto: 10")
        max_turns = 10
    
    print(f"Máximo de turnos: {max_turns}")
    print("Iniciando conversación...\n")
    print("-" * 50)
    
    # Crear grafo
    graph = create_conversation_graph(
        character_agent=character,
        observer_agent=observer,
        manager=manager,
        max_turns=max_turns
    )
    
    # Ejecutar grafo
    try:
        final_state = graph.invoke(initial_state)
        print("-" * 50)
        print(f"\nConversación finalizada después de {final_state['turn']} turnos.")
        print(f"Total de mensajes: {len(final_state['messages'])}")
                    
    except Exception as e:
        logger.error(f"Error durante la ejecución: {e}", exc_info=True)
        print(f"\nError: {e}")


if __name__ == "__main__":
    main()
