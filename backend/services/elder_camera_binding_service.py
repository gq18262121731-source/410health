from __future__ import annotations

import json
from pathlib import Path


class ElderCameraBindingService:
    """Persist elder-to-camera bindings in a small local JSON file."""

    def __init__(self, data_root: Path) -> None:
        self._path = data_root / "elder_camera_bindings.json"

    def get_camera_id(self, elder_id: str) -> str | None:
        normalized = elder_id.strip()
        if not normalized:
            return None
        payload = self._load()
        value = payload.get(normalized)
        if not isinstance(value, str):
            return None
        camera_id = value.strip().lower()
        return camera_id or None

    def set_camera_id(self, elder_id: str, camera_id: str) -> dict[str, str]:
        normalized_elder_id = elder_id.strip()
        normalized_camera_id = camera_id.strip().lower()
        if not normalized_elder_id:
            raise ValueError("ELDER_ID_REQUIRED")
        if not normalized_camera_id:
            raise ValueError("CAMERA_ID_REQUIRED")
        payload = self._load()
        payload[normalized_elder_id] = normalized_camera_id
        self._save(payload)
        return {"elder_id": normalized_elder_id, "camera_id": normalized_camera_id}

    def clear_camera_id(self, elder_id: str) -> dict[str, str | bool]:
        normalized = elder_id.strip()
        if not normalized:
            raise ValueError("ELDER_ID_REQUIRED")
        payload = self._load()
        removed = payload.pop(normalized, None) is not None
        self._save(payload)
        return {"elder_id": normalized, "removed": removed}

    def _load(self) -> dict[str, str]:
        if not self._path.is_file():
            return {}
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        normalized: dict[str, str] = {}
        for key, value in payload.items():
            if not isinstance(key, str) or not isinstance(value, str):
                continue
            elder_id = key.strip()
            camera_id = value.strip().lower()
            if elder_id and camera_id:
                normalized[elder_id] = camera_id
        return normalized

    def _save(self, payload: dict[str, str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
