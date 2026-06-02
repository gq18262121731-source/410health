from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import Iterator


_ULTRALYTICS_LOCK = threading.Lock()


@contextmanager
def ultralytics_inference_lock(blocking: bool = True) -> Iterator[tuple[bool, float]]:
    started = time.perf_counter()
    acquired = _ULTRALYTICS_LOCK.acquire(blocking=blocking)
    wait_ms = (time.perf_counter() - started) * 1000
    try:
        yield acquired, wait_ms
    finally:
        if acquired:
            _ULTRALYTICS_LOCK.release()
