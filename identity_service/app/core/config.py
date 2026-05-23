from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw)


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    return float(raw)


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "identity-service")
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = _get_int("PORT", 8100)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    identity_store_dir: str = os.getenv("IDENTITY_STORE_DIR", "data/identities")
    identity_max_images: int = _get_int("IDENTITY_MAX_IMAGES", 5)
    match_threshold: float = _get_float("MATCH_THRESHOLD", 0.45)

    insightface_model_name: str = os.getenv("INSIGHTFACE_MODEL_NAME", "buffalo_l")
    insightface_ctx_id: int = _get_int("INSIGHTFACE_CTX_ID", 0)
    insightface_det_size: int = _get_int("INSIGHTFACE_DET_SIZE", 640)
    insightface_providers: str | None = os.getenv("INSIGHTFACE_PROVIDERS") or None


@lru_cache
def get_settings() -> Settings:
    return Settings()
