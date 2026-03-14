"""Adaptador de Redis Streams para publicación/consumo de eventos."""

from __future__ import annotations

import importlib
import json
import os
from typing import Any


class RedisStreamQueue:
    """Wrapper mínimo sobre Redis Streams con import lazy."""

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = (redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")).strip()
        try:
            redis_module = importlib.import_module("redis")
        except ModuleNotFoundError as exc:
            raise RuntimeError("Falta dependencia 'redis' para usar Redis Streams") from exc
        self._client = redis_module.Redis.from_url(self._redis_url, decode_responses=True)

    def publish_event(self, stream_name: str, event: dict[str, Any]) -> str:
        payload = {
            "event_id": str(event.get("id") or ""),
            "event_type": str(event.get("event_type") or ""),
            "aggregate_type": str(event.get("aggregate_type") or ""),
            "aggregate_id": str(event.get("aggregate_id") or ""),
            "payload_json": json.dumps(event.get("payload_json") or {}, ensure_ascii=False),
        }
        return str(self._client.xadd(stream_name, payload))

    def ensure_group(self, stream_name: str, group_name: str) -> None:
        try:
            self._client.xgroup_create(stream_name, group_name, id="$", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def read_group(
        self,
        stream_name: str,
        group_name: str,
        consumer_name: str,
        count: int = 10,
        block_ms: int = 5000,
    ) -> list[dict[str, Any]]:
        response = self._client.xreadgroup(
            group_name,
            consumer_name,
            {stream_name: ">"},
            count=count,
            block=block_ms,
        )
        items: list[dict[str, Any]] = []
        for _stream, messages in response:
            for message_id, fields in messages:
                items.append(
                    {
                        "message_id": message_id,
                        "event_id": str(fields.get("event_id") or ""),
                        "event_type": str(fields.get("event_type") or ""),
                        "aggregate_type": str(fields.get("aggregate_type") or ""),
                        "aggregate_id": str(fields.get("aggregate_id") or ""),
                        "payload_json": json.loads(fields.get("payload_json") or "{}"),
                    }
                )
        return items

    def ack(self, stream_name: str, group_name: str, message_id: str) -> None:
        self._client.xack(stream_name, group_name, message_id)
