"""Non-blocking telemetry emitter for LLM call metrics."""

from __future__ import annotations

import atexit
import json
import os
import queue
import threading
import time
from typing import Any
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class TelemetryEmitter:
    def __init__(self) -> None:
        self._enabled = _bool_env("TELEMETRY_ENABLED", True)
        self._endpoint = (
            os.getenv("TELEMETRY_ENDPOINT", "http://localhost:8081/v1/events").strip()
        )
        self._ingest_key = os.getenv("TELEMETRY_INGEST_KEY", "").strip()
        self._batch_size = max(1, int((os.getenv("TELEMETRY_BATCH_SIZE") or "32").strip()))
        self._flush_interval = max(
            0.1, float((os.getenv("TELEMETRY_FLUSH_INTERVAL_SECONDS") or "1.5").strip())
        )
        self._timeout_seconds = max(
            0.2, float((os.getenv("TELEMETRY_TIMEOUT_SECONDS") or "1.0").strip())
        )
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(
            maxsize=max(10, int((os.getenv("TELEMETRY_QUEUE_MAX") or "4096").strip()))
        )
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None
        self._started = False
        self._dropped = 0

    def _start_worker(self) -> None:
        if self._started or not self._enabled:
            return
        self._started = True
        self._worker = threading.Thread(target=self._run, name="telemetry-emitter", daemon=True)
        self._worker.start()

    def emit(self, event: dict[str, Any]) -> None:
        if not self._enabled or not self._endpoint:
            return
        self._start_worker()
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            self._dropped += 1

    def flush(self) -> None:
        if not self._started:
            return
        deadline = time.time() + max(1.0, self._timeout_seconds * 8.0)
        while not self._queue.empty() and time.time() < deadline:
            time.sleep(0.05)

    def shutdown(self) -> None:
        if not self._started:
            return
        self.flush()
        self._stop.set()
        if self._worker is not None:
            self._worker.join(timeout=2.0)

    def dropped_events(self) -> int:
        return self._dropped

    def _run(self) -> None:
        batch: list[dict[str, Any]] = []
        next_flush = time.monotonic() + self._flush_interval
        while not self._stop.is_set():
            timeout = max(0.05, next_flush - time.monotonic())
            try:
                item = self._queue.get(timeout=timeout)
                batch.append(item)
                if len(batch) >= self._batch_size:
                    self._post_batch(batch)
                    batch.clear()
                    next_flush = time.monotonic() + self._flush_interval
            except queue.Empty:
                if batch:
                    self._post_batch(batch)
                    batch.clear()
                next_flush = time.monotonic() + self._flush_interval
        if batch:
            self._post_batch(batch)

    def _post_batch(self, items: list[dict[str, Any]]) -> None:
        body = json.dumps({"events": items}, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._ingest_key:
            headers["X-Agora-Ingest-Key"] = self._ingest_key
        request = Request(self._endpoint, method="POST", data=body, headers=headers)
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                if response.status >= 400:
                    return
        except (URLError, HTTPError, TimeoutError):
            return
        except Exception:
            return


_EMITTER = TelemetryEmitter()
atexit.register(_EMITTER.shutdown)


def emit_telemetry_event(event: dict[str, Any]) -> None:
    _EMITTER.emit(event)


def flush_telemetry() -> None:
    _EMITTER.flush()


def dropped_telemetry_events() -> int:
    return _EMITTER.dropped_events()
