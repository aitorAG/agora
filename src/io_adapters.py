"""Abstracciones de I/O para desacoplar el motor de terminal/HTTP.

El motor no conoce input() ni print(); recibe InputProvider y OutputHandler
por inyección.
"""

from dataclasses import dataclass
from typing import Protocol
from .state import Message


@dataclass
class UserInputResult:
    """Resultado de obtener input del jugador."""
    text: str | None  # Texto escrito; None o "" = no añadir mensaje
    user_exit: bool   # True si el jugador pidió salir (exit/quit/salir/q)


class InputProvider(Protocol):
    """Provee la siguiente entrada del jugador. El motor llama a get_user_input()."""

    def get_user_input(self) -> UserInputResult:
        """Obtiene input del jugador. Bloquea hasta que haya entrada (en terminal)."""
        ...


class OutputHandler(Protocol):
    """Recibe eventos del motor (mensajes, errores, setup). El motor/cliente llama a estos métodos."""

    def on_message(self, message: Message) -> None:
        """Se emitió un mensaje de un personaje (o del sistema) para mostrar al jugador."""
        ...

    def on_setup_ready(self, setup: dict) -> None:
        """Setup de partida listo (narrativa_inicial, player_mission, etc.) para mostrar al jugador."""
        ...

    def on_game_ended(self, reason: str, mission_evaluation: dict) -> None:
        """Partida terminada por misión cumplida + evidencia narrativa. reason indica quién cumplió objetivo."""
        ...

    def on_error(self, msg: str) -> None:
        """Se produjo un error que el cliente puede mostrar."""
        ...


# --- Implementaciones para terminal (cliente actual) ---


class TerminalInputProvider:
    """InputProvider que usa input() y detecta comandos de salida."""

    EXIT_COMMANDS = {"exit", "quit", "salir", "q"}

    def get_user_input(self) -> UserInputResult:
        raw = input("Tú: ").strip()
        if raw.lower() in self.EXIT_COMMANDS:
            return UserInputResult(text=None, user_exit=True)
        return UserInputResult(text=raw if raw else None, user_exit=False)


class TerminalOutputHandler:
    """OutputHandler que imprime en stdout (narrativa, mensajes, errores)."""

    def on_message(self, message: Message) -> None:
        if message.get("displayed"):
            return
        print(f"[{message['author']}] {message['content']}")

    def on_setup_ready(self, setup: dict) -> None:
        narrativa = setup.get("narrativa_inicial", "").strip()
        if narrativa:
            print(narrativa)
        else:
            print("Ambientación:", setup.get("ambientacion", ""))
            print()
            print("Situación:", setup.get("contexto_problema", ""))
            print()
            print("Por qué te importa:", setup.get("relevancia_jugador", ""))
            print()
            print("Personajes en la escena:")
            for a in setup.get("actors", []):
                print(f"  **{a['name']}**: {a.get('presencia_escena', 'Presente en la escena.')}")
        print()
        print("Tu misión (privada):", setup.get("player_mission", ""))
        print()

    def on_game_ended(self, reason: str, mission_evaluation: dict) -> None:
        print()
        print("=== Partida terminada ===")
        print(reason)
        ev = mission_evaluation or {}
        if ev.get("player_mission_achieved"):
            print("- El jugador ha cumplido su misión.")
        for name, achieved in ev.get("actor_missions_achieved", {}).items():
            if achieved:
                print(f"- {name} ha cumplido su misión.")
        if ev.get("reasoning"):
            print("Motivo:", ev["reasoning"])
        print()

    def on_error(self, msg: str) -> None:
        print(msg)
