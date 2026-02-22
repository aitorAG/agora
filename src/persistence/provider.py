"""Contrato de persistencia para partidas y conversaciones."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PersistenceProvider(ABC):
    """Interfaz de almacenamiento desacoplada del engine."""

    @abstractmethod
    def create_game(self, title: str, config_json: dict[str, Any]) -> str:
        """Crea partida + config + estado inicial y devuelve game_id."""

    @abstractmethod
    def save_game_state(self, game_id: str, state_json: dict[str, Any]) -> None:
        """Guarda snapshot del estado actual de la partida."""

    @abstractmethod
    def append_message(
        self,
        game_id: str,
        turn_number: int,
        role: str,
        content: str,
        metadata_json: dict[str, Any] | None = None,
    ) -> None:
        """Añade un mensaje de conversación asociado a un turno."""

    @abstractmethod
    def get_game(self, game_id: str) -> dict[str, Any]:
        """Recupera metadata, config y estado de la partida."""

    @abstractmethod
    def get_game_messages(self, game_id: str) -> list[dict[str, Any]]:
        """Recupera mensajes ordenados por turno/fecha."""

    @abstractmethod
    def list_games_for_user(self, username: str) -> list[dict[str, Any]]:
        """Lista partidas de un usuario."""
