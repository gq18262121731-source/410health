from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

import numpy as np

from app.schemas.vision_result import DetectedObject, VisionResult


@dataclass(frozen=True)
class DetectionSnapshot:
    camera_id: str
    frame_seq: int
    frame_width: int
    frame_height: int
    timestamp: str
    monotonic_at: float
    frame: np.ndarray
    objects: list[DetectedObject]
    detector: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ObjectSnapshot:
    camera_id: str
    frame_seq: int
    frame_width: int
    frame_height: int
    timestamp: str
    monotonic_at: float
    objects: list[DetectedObject]


@dataclass(frozen=True)
class PipelineSnapshot:
    camera_id: str
    latest_detection: DetectionSnapshot | None
    latest_tracking: ObjectSnapshot | None
    latest_pose: ObjectSnapshot | None
    latest_behavior: ObjectSnapshot | None
    latest_published_result: VisionResult | None


class RealtimeResultStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._detections: dict[str, DetectionSnapshot] = {}
        self._tracking: dict[str, ObjectSnapshot] = {}
        self._pose: dict[str, ObjectSnapshot] = {}
        self._behavior: dict[str, ObjectSnapshot] = {}
        self._published: dict[str, VisionResult] = {}

    def update_detection(self, snapshot: DetectionSnapshot) -> None:
        with self._lock:
            self._detections[snapshot.camera_id] = snapshot

    def latest_detection(self, camera_id: str) -> DetectionSnapshot | None:
        with self._lock:
            return self._detections.get(camera_id)

    def update_tracking(self, snapshot: ObjectSnapshot) -> None:
        with self._lock:
            self._tracking[snapshot.camera_id] = snapshot

    def latest_tracking(self, camera_id: str) -> ObjectSnapshot | None:
        with self._lock:
            return self._tracking.get(camera_id)

    def update_pose(self, snapshot: ObjectSnapshot) -> None:
        with self._lock:
            self._pose[snapshot.camera_id] = snapshot

    def latest_pose(self, camera_id: str) -> ObjectSnapshot | None:
        with self._lock:
            return self._pose.get(camera_id)

    def update_behavior(self, snapshot: ObjectSnapshot) -> None:
        with self._lock:
            self._behavior[snapshot.camera_id] = snapshot

    def latest_behavior(self, camera_id: str) -> ObjectSnapshot | None:
        with self._lock:
            return self._behavior.get(camera_id)

    def update_published(self, result: VisionResult) -> None:
        with self._lock:
            self._published[result.camera_id] = result

    def latest_published(self, camera_id: str) -> VisionResult | None:
        with self._lock:
            return self._published.get(camera_id)

    def clear_camera(self, camera_id: str) -> None:
        with self._lock:
            self._detections.pop(camera_id, None)
            self._tracking.pop(camera_id, None)
            self._pose.pop(camera_id, None)
            self._behavior.pop(camera_id, None)
            self._published.pop(camera_id, None)

    def snapshot(self, camera_id: str) -> PipelineSnapshot:
        with self._lock:
            return PipelineSnapshot(
                camera_id=camera_id,
                latest_detection=self._detections.get(camera_id),
                latest_tracking=self._tracking.get(camera_id),
                latest_pose=self._pose.get(camera_id),
                latest_behavior=self._behavior.get(camera_id),
                latest_published_result=self._published.get(camera_id),
            )

    @staticmethod
    def age_ms(monotonic_at: float | None) -> float | None:
        if monotonic_at is None:
            return None
        return round((time.monotonic() - monotonic_at) * 1000, 2)
