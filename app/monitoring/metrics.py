from __future__ import annotations

import time
from collections import deque


class FPSMeter:
    def __init__(self, window_size: int = 120) -> None:
        self._timestamps: deque[float] = deque(maxlen=window_size)

    def tick(self) -> None:
        self._timestamps.append(time.monotonic())

    @property
    def fps(self) -> float:
        if len(self._timestamps) < 2:
            return 0.0
        elapsed = self._timestamps[-1] - self._timestamps[0]
        if elapsed <= 0:
            return 0.0
        return round((len(self._timestamps) - 1) / elapsed, 2)


class LatencyMeter:
    def __init__(self, window_size: int = 120) -> None:
        self._values: deque[float] = deque(maxlen=window_size)

    def add(self, latency_ms: float) -> None:
        self._values.append(round(latency_ms, 2))

    @property
    def avg_ms(self) -> float | None:
        if not self._values:
            return None
        return round(sum(self._values) / len(self._values), 2)
