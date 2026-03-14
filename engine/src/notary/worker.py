"""Worker del notario sobre la cola de eventos de dominio."""

from __future__ import annotations

import logging
import os
from typing import Any

from ..observability import span_agent
from ..persistence import PersistenceProvider
from .processor import NotaryProcessor


class NotaryWorker:
    """Consume checkpoints de turno y persiste snapshots del notario."""

    def __init__(
        self,
        persistence: PersistenceProvider,
        queue_client: Any,
        processor: NotaryProcessor,
        stream_name: str | None = None,
        group_name: str | None = None,
        consumer_name: str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._persistence = persistence
        self._queue = queue_client
        self._processor = processor
        self._stream_name = (stream_name or os.getenv("AGORA_DOMAIN_EVENTS_STREAM", "agora.domain_events")).strip()
        self._group_name = (group_name or os.getenv("AGORA_NOTARY_GROUP", "notary-workers")).strip()
        self._consumer_name = (consumer_name or os.getenv("AGORA_NOTARY_CONSUMER", "notary-1")).strip()
        self._logger = logger or logging.getLogger(__name__)

    def run_once(self, count: int = 10, block_ms: int = 5000) -> int:
        self._queue.ensure_group(self._stream_name, self._group_name)
        processed = 0
        for event in self._queue.read_group(
            self._stream_name,
            self._group_name,
            self._consumer_name,
            count=count,
            block_ms=block_ms,
        ):
            if event.get("event_type") != "turn_reached_user_input":
                self._queue.ack(self._stream_name, self._group_name, event["message_id"])
                continue
            payload = event.get("payload_json") or {}
            game_id = str(payload.get("game_id") or event.get("aggregate_id") or "").strip()
            if not game_id:
                self._queue.ack(self._stream_name, self._group_name, event["message_id"])
                continue
            turn = int(payload.get("turn") or 0)
            window_size = max(1, int(payload.get("window_size") or 1))
            message_count = max(0, int(payload.get("message_count") or 0))
            game = self._persistence.get_game(game_id)
            player_mission = str((game.get("config_json") or {}).get("player_mission") or "")
            recent_messages = self._persistence.get_recent_game_messages(game_id, window_size)
            with span_agent(
                "notary_scene_snapshot",
                metadata={
                    "agent_name": "Notario",
                    "agent_type": "notary",
                    "agent_step": "scene_snapshot",
                    "game_id": game_id,
                    "turn": str(turn),
                    "user_id": str(game.get("user_id") or game.get("user") or ""),
                    "username": str(game.get("user") or ""),
                },
            ):
                result = self._processor.process(
                    game_id=game_id,
                    turn=turn,
                    recent_messages=[
                        {
                            "author": str(msg.get("author") or (msg.get("metadata_json") or {}).get("author") or ""),
                            "content": str(msg.get("content") or ""),
                            "turn": int(msg.get("turn_number") or 0),
                        }
                        for msg in recent_messages
                    ],
                    player_mission=player_mission,
                )
            entry_id = self._persistence.create_notary_entry(
                game_id=game_id,
                turn=turn,
                based_on_message_count=message_count,
                window_size=window_size,
                summary_text=str(result.get("summary_text") or ""),
                facts_json=list(result.get("facts_json") or []),
                mission_progress_json=dict(result.get("mission_progress_json") or {}),
                open_threads_json=list(result.get("open_threads_json") or []),
            )
            self._persistence.upsert_scene_snapshot(
                game_id=game_id,
                source_notary_entry_id=entry_id,
                version_turn=turn,
                facts_json=list(result.get("facts_json") or []),
                mission_progress_json=dict(result.get("mission_progress_json") or {}),
                open_threads_json=list(result.get("open_threads_json") or []),
                summary_text=str(result.get("summary_text") or ""),
            )
            self._queue.ack(self._stream_name, self._group_name, event["message_id"])
            processed += 1
        return processed
