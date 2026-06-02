from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WorkerHealthSnapshot:
    worker_alive: bool = False
    heartbeat_at: str | None = None
    last_success_at: str | None = None
    error_count: int = 0
    restart_count: int = 0
    last_error: str | None = None
    avg_latency_ms: float | None = None
    last_latency_ms: float | None = None


class WorkerHealthTracker:
    def __init__(self, latency_window_size: int = 120) -> None:
        self._heartbeat_at: str | None = None
        self._last_success_at: str | None = None
        self._error_count = 0
        self._restart_count = 0
        self._last_error: str | None = None
        self._last_latency_ms: float | None = None
        self._latencies: deque[float] = deque(maxlen=latency_window_size)
        self._lock = threading.Lock()

    def mark_heartbeat(self) -> None:
        with self._lock:
            self._heartbeat_at = utc_now_iso()

    def mark_success(self, latency_ms: float | None = None) -> None:
        now = utc_now_iso()
        with self._lock:
            self._heartbeat_at = now
            self._last_success_at = now
            self._last_error = None
            if latency_ms is not None:
                rounded = round(latency_ms, 2)
                self._last_latency_ms = rounded
                self._latencies.append(rounded)

    def mark_error(self, error: str) -> None:
        with self._lock:
            self._heartbeat_at = utc_now_iso()
            self._error_count += 1
            self._last_error = error

    def mark_restart(self) -> None:
        with self._lock:
            self._restart_count += 1
            self._heartbeat_at = utc_now_iso()

    def snapshot(self, *, worker_alive: bool) -> WorkerHealthSnapshot:
        with self._lock:
            avg_latency_ms = None
            if self._latencies:
                avg_latency_ms = round(sum(self._latencies) / len(self._latencies), 2)
            return WorkerHealthSnapshot(
                worker_alive=worker_alive,
                heartbeat_at=self._heartbeat_at,
                last_success_at=self._last_success_at,
                error_count=self._error_count,
                restart_count=self._restart_count,
                last_error=self._last_error,
                avg_latency_ms=avg_latency_ms,
                last_latency_ms=self._last_latency_ms,
            )


def monotonic_age_ms(monotonic_at: float | None) -> float | None:
    if monotonic_at is None:
        return None
    return round((time.monotonic() - monotonic_at) * 1000, 2)
