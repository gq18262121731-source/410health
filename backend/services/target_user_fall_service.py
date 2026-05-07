from __future__ import annotations

import time
from pathlib import Path
from threading import RLock
from typing import Any

import cv2
import numpy as np

from backend.services.target_user_service import TargetUserService


class TargetUserFallService:
    """Phase-1 target-only fall detection bridge.

    This service does not yet solve full multi-person tracking. It provides a
    clean target-user gate in front of single-frame fall detection so the rest
    of the system can evolve toward the final multi-person target-only flow.
    """

    def __init__(self, *, data_root: Path, model_root: Path, target_user_service: TargetUserService) -> None:
        self._target_user_service = target_user_service
        self._model_root = model_root
        self._data_root = data_root
        self._fall_frame_service = None
        self._lock = RLock()
        self._last_target_match: dict[str, Any] | None = None
        self._match_cache_ttl_ms = 1800
        self._init_fall_frame_service()

    def _init_fall_frame_service(self) -> None:
        try:
            from backend.services.fall_frame_test_service import FallFrameTestService
            from backend.config import get_settings

            self._fall_frame_service = FallFrameTestService(get_settings())
        except Exception:
            self._fall_frame_service = None

    def detect(self, image_bytes: bytes, *, include_annotated_image: bool = True, target_only: bool = True) -> dict[str, Any]:
        started = time.perf_counter()
        np_buffer = np.frombuffer(image_bytes, dtype=np.uint8)
        frame = cv2.imdecode(np_buffer, cv2.IMREAD_COLOR)
        if frame is None:
            return {
                "ok": False,
                "status": "model_unavailable",
                "error": "INVALID_IMAGE",
                "target_match": None,
                "fall_result": None,
                "latency_ms": 0,
            }

        target_features = self._target_user_service.extract_features_from_frame(frame)
        target_match = self._resolve_target_match(
            face_embedding=target_features["face_embedding"],
            body_profile=target_features["body_profile"],
        )

        if target_only and not target_match.matched:
            return {
                "ok": True,
                "status": "filtered_non_target",
                "target_match": target_match.model_dump(mode="json"),
                "fall_result": None,
                "warnings": target_features["warnings"],
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }

        if self._fall_frame_service is None:
            return {
                "ok": False,
                "status": "model_unavailable",
                "error": "FALL_MODEL_UNAVAILABLE",
                "target_match": target_match.model_dump(mode="json"),
                "fall_result": None,
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }

        fall_result = self._fall_frame_service.detect_frame(frame, include_annotated_image=include_annotated_image)
        return {
            "ok": bool(fall_result.get("ok", False)),
            "status": fall_result.get("status"),
            "target_match": target_match.model_dump(mode="json"),
            "fall_result": fall_result,
            "warnings": target_features["warnings"],
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }

    def _resolve_target_match(
        self,
        *,
        face_embedding: list[float] | None,
        body_profile: dict[str, float] | None,
    ):
        now_ms = int(time.perf_counter() * 1000)
        cached = None
        with self._lock:
            cached = self._last_target_match

        if cached and (now_ms - int(cached["ts_ms"])) <= self._match_cache_ttl_ms:
            if face_embedding is None and body_profile is not None and cached.get("body_profile") is not None:
                body_score = self._target_user_service._best_body_similarity(  # type: ignore[attr-defined]
                    body_profile,
                    [cached["body_profile"]],
                )
                if body_score >= 0.84:
                    match = cached["match"].model_copy(update={
                        "body_score": round(body_score, 4),
                        "fused_score": round(max(float(cached["match"].fused_score), body_score), 4),
                    })
                    return match

        target_match = self._target_user_service.match_target(
            face_embedding=face_embedding,
            body_profile=body_profile,
        )
        if target_match.matched:
            with self._lock:
                self._last_target_match = {
                    "ts_ms": now_ms,
                    "match": target_match,
                    "body_profile": body_profile,
                }
        else:
            with self._lock:
                if cached and (now_ms - int(cached["ts_ms"])) > self._match_cache_ttl_ms:
                    self._last_target_match = None
        return target_match
