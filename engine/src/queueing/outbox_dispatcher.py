"""Despachador de eventos outbox hacia la cola de dominio."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from ..persistence import PersistenceProvider


class OutboxDispatcher:
    """Publica eventos outbox persistidos hacia una cola externa."""

    def __init__(
        self,
        persistence: PersistenceProvider,
        queue_client: Any,
        stream_name: str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._persistence = persistence
        self._queue = queue_client
        self._stream_name = (stream_name or os.getenv("AGORA_DOMAIN_EVENTS_STREAM", "agora.domain_events")).strip()
        self._logger = logger or logging.getLogger(__name__)

    def dispatch_once(self, limit: int = 25) -> int:
        dispatched = 0
        for event in self._persistence.claim_outbox_events(limit=limit):
            try:
                self._queue.publish_event(self._stream_name, event)
                self._persistence.mark_outbox_event_dispatched(event["id"])
                dispatched += 1
            except Exception as exc:
                self._persistence.mark_outbox_event_retry(event["id"], str(exc))
                self._logger.exception("outbox dispatch failed event_id=%s", event["id"])
        return dispatched

    def run_forever(self, poll_interval_seconds: float = 1.0, batch_size: int = 25) -> None:
        while True:
            dispatched = self.dispatch_once(limit=batch_size)
            if dispatched == 0:
                time.sleep(max(0.1, float(poll_interval_seconds)))
