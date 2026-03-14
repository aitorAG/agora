"""Contrato de persistencia para partidas y conversaciones."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PersistenceProvider(ABC):
    """Interfaz de almacenamiento desacoplada del engine."""

    @abstractmethod
    def create_game(
        self,
        title: str,
        config_json: dict[str, Any],
        username: str | None = None,
        game_mode: str = "custom",
        standard_template_id: str | None = None,
        template_version: str | None = None,
    ) -> str:
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

    @abstractmethod
    def create_feedback(self, game_id: str, user_id: str, feedback_text: str) -> str:
        """Guarda feedback libre asociado a partida y usuario. Devuelve feedback_id."""

    @abstractmethod
    def list_feedback(self, limit: int = 500) -> list[dict[str, Any]]:
        """Lista feedback global para panel admin (ordenado por fecha desc)."""

    def persist_game_progress(
        self,
        game_id: str,
        new_messages: list[dict[str, Any]],
        state_json: dict[str, Any],
        domain_events: list[dict[str, Any]] | None = None,
    ) -> None:
        """Persiste mensajes nuevos + snapshot de estado.

        Implementación por defecto compatible con providers simples o tests.
        Los providers productivos pueden sobreescribirlo para hacerlo atómico.
        """
        for msg in new_messages:
            author = str(msg.get("author", ""))
            timestamp = msg.get("timestamp")
            self.append_message(
                game_id=game_id,
                turn_number=int(msg.get("turn", 0)),
                role=str(msg.get("role") or "actor"),
                content=str(msg.get("content", "")),
                metadata_json={
                    "author": author,
                    "timestamp": timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp) if timestamp is not None else None,
                    "displayed": bool(msg.get("displayed", False)),
                },
            )
        self.save_game_state(game_id, state_json)
        for event in domain_events or []:
            self.enqueue_domain_event(
                event_type=str(event.get("event_type") or ""),
                aggregate_type=str(event.get("aggregate_type") or "game"),
                aggregate_id=str(event.get("aggregate_id") or game_id),
                payload_json=dict(event.get("payload_json") or {}),
            )

    def get_recent_game_messages(self, game_id: str, limit: int) -> list[dict[str, Any]]:
        """Recupera una ventana reciente de mensajes ordenada por antigüedad."""
        safe_limit = max(1, int(limit))
        messages = self.get_game_messages(game_id)
        if safe_limit >= len(messages):
            return messages
        return messages[-safe_limit:]

    def enqueue_domain_event(
        self,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload_json: dict[str, Any],
    ) -> str:
        """Inserta un evento de dominio en outbox."""
        raise NotImplementedError("This persistence provider does not support outbox events")

    def claim_outbox_events(self, limit: int = 50) -> list[dict[str, Any]]:
        """Reserva eventos pendientes para su publicación en la cola."""
        raise NotImplementedError("This persistence provider does not support outbox events")

    def mark_outbox_event_dispatched(self, event_id: str) -> None:
        """Marca un evento outbox como publicado en la cola."""
        raise NotImplementedError("This persistence provider does not support outbox events")

    def mark_outbox_event_retry(self, event_id: str, error_message: str | None = None) -> None:
        """Incrementa contador de reintentos tras un fallo de publicación."""
        raise NotImplementedError("This persistence provider does not support outbox events")

    def create_notary_entry(
        self,
        game_id: str,
        turn: int,
        based_on_message_count: int,
        window_size: int,
        summary_text: str,
        facts_json: list[dict[str, Any]],
        mission_progress_json: dict[str, Any],
        open_threads_json: list[str],
    ) -> str:
        """Persiste una entrada append-only del notario."""
        raise NotImplementedError("This persistence provider does not support notary entries")

    def upsert_scene_snapshot(
        self,
        game_id: str,
        source_notary_entry_id: str,
        version_turn: int,
        facts_json: list[dict[str, Any]],
        mission_progress_json: dict[str, Any],
        open_threads_json: list[str],
        summary_text: str,
    ) -> None:
        """Actualiza el snapshot materializado más reciente de la escena."""
        raise NotImplementedError("This persistence provider does not support scene snapshots")
