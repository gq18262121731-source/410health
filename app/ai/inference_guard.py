from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator


_ULTRALYTICS_LOCK = threading.Lock()


@contextmanager
def ultralytics_inference_lock(blocking: bool = True) -> Iterator[bool]:
    acquired = _ULTRALYTICS_LOCK.acquire(blocking=blocking)
    try:
        yield acquired
    finally:
        if acquired:
            _ULTRALYTICS_LOCK.release()
