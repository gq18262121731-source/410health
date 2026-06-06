from __future__ import annotations

from typing import Any


class PoseStateService:
    """Thin accessor around the latest pose payload for UI-facing helpers."""

    def __init__(self) -> None:
        self._latest: dict[str, Any] | None = None

    def update(self, payload: dict[str, Any] | None) -> None:
        self._latest = payload

    def latest(self) -> dict[str, Any] | None:
        return self._latest
