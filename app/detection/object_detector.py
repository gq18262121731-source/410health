from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from app.ai.inference_guard import ultralytics_inference_lock
from app.core.config import Settings
from app.core.logger import get_logger
from app.schemas.vision_result import DetectedObject

logger = get_logger(__name__)


@dataclass
class DetectorStatus:
    enabled: bool
    loaded: bool = False
    model_name: str | None = None
    last_error: str | None = None
    lock_wait_avg_ms: float | None = None
    lock_wait_p95_ms: float | None = None
    last_lock_wait_ms: float | None = None


class PersonDetector:
    def detect(self, frame: np.ndarray) -> list[DetectedObject]:
        raise NotImplementedError

    def status(self) -> DetectorStatus:
        raise NotImplementedError


class YoloPersonDetector(PersonDetector):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model = None
        self._status = DetectorStatus(
            enabled=settings.detection_enabled,
            loaded=False,
            model_name=settings.yolo_model_path,
        )
        self._lock_wait_ms: list[float] = []
        if settings.detection_enabled:
            self._load()

    def _load(self) -> None:
        try:
            from ultralytics import YOLO

            self._model = YOLO(self.settings.yolo_model_path)
            self._status.loaded = True
            self._status.last_error = None
            logger.info("yolo_loaded model=%s", self.settings.yolo_model_path)
        except Exception as exc:
            self._model = None
            self._status.loaded = False
            self._status.last_error = str(exc)
            logger.error("yolo_load_failed error=%s", exc)

    def detect(self, frame: np.ndarray) -> list[DetectedObject]:
        if not self._status.enabled or not self._model:
            return []

        kwargs = {
            "conf": self.settings.yolo_confidence,
            "imgsz": self.settings.yolo_imgsz,
            "verbose": False,
            "classes": [0],
        }
        if self.settings.yolo_device:
            kwargs["device"] = self.settings.yolo_device

        with ultralytics_inference_lock(blocking=True) as lock_state:
            acquired, wait_ms = lock_state
            if not acquired:
                return []
            self._record_lock_wait(wait_ms)
            results = self._model.predict(frame, **kwargs)
        if not results:
            return []

        detections: list[DetectedObject] = []
        result = results[0]
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return detections

        for box in boxes:
            xyxy = box.xyxy[0].tolist()
            confidence = float(box.conf[0].item())
            detections.append(
                DetectedObject(
                    label="person",
                    confidence=round(confidence, 4),
                    bbox=[round(float(v), 2) for v in xyxy],
                )
            )
        return detections

    def status(self) -> DetectorStatus:
        status = DetectorStatus(**self._status.__dict__)
        wait_values = list(self._lock_wait_ms)
        if wait_values:
            ordered = sorted(wait_values)
            status.lock_wait_avg_ms = round(sum(ordered) / len(ordered), 2)
            p95_index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * 0.95))))
            status.lock_wait_p95_ms = round(ordered[p95_index], 2)
            status.last_lock_wait_ms = round(ordered[-1], 2)
        return status

    def _record_lock_wait(self, wait_ms: float) -> None:
        rounded = round(wait_ms, 2)
        self._lock_wait_ms.append(rounded)
        if len(self._lock_wait_ms) > 120:
            self._lock_wait_ms = self._lock_wait_ms[-120:]


class NoopPersonDetector(PersonDetector):
    def __init__(self, message: str = "detection disabled") -> None:
        self._status = DetectorStatus(
            enabled=False,
            loaded=False,
            model_name=None,
            last_error=message,
        )

    def detect(self, frame: np.ndarray) -> list[DetectedObject]:
        return []

    def status(self) -> DetectorStatus:
        return DetectorStatus(**self._status.__dict__)


@dataclass
class DetectionRunStats:
    inference_latency_ms: float | None = None
    last_error: str | None = None
    last_detected_at: float | None = None
    loop_latency_ms: float | None = None
    lock_wait_ms: float | None = None
