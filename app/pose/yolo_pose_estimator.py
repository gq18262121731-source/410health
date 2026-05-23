from __future__ import annotations

import cv2
import numpy as np

from app.core.config import Settings
from app.core.logger import get_logger
from app.pose.schemas import PoseKeypoint, PoseResult
from app.schemas.vision_result import DetectedObject

logger = get_logger(__name__)

COCO_KEYPOINT_NAMES = [
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
]


class YoloPoseEstimator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model = None
        self._last_error: str | None = None
        self._load()

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def _load(self) -> None:
        try:
            from ultralytics import YOLO

            self._model = YOLO(self.settings.yolo_pose_model_path)
            self._last_error = None
            logger.info("yolo_pose_loaded model=%s", self.settings.yolo_pose_model_path)
        except Exception as exc:
            self._model = None
            self._last_error = str(exc)
            logger.error("yolo_pose_load_failed error=%s", exc)

    def estimate(self, frame: np.ndarray, objects: list[DetectedObject]) -> dict[int, PoseResult]:
        if self._model is None:
            self._load()
        if self._model is None:
            raise RuntimeError(f"yolo pose model unavailable: {self._last_error}")

        results: dict[int, PoseResult] = {}
        for item in objects:
            if item.track_id is None:
                continue
            crop_info = self._crop(frame, item.bbox)
            if crop_info is None:
                continue
            crop, left, top = crop_info
            pose = self._estimate_crop(crop, left, top, item.track_id)
            if pose is not None:
                results[item.track_id] = pose
        return results

    def _estimate_crop(self, crop: np.ndarray, left: int, top: int, track_id: int) -> PoseResult | None:
        kwargs = {
            "conf": self.settings.yolo_pose_confidence,
            "imgsz": self.settings.yolo_pose_imgsz,
            "verbose": False,
        }
        if self.settings.yolo_pose_device:
            kwargs["device"] = self.settings.yolo_pose_device

        predictions = self._model.predict(crop, **kwargs)
        if not predictions:
            return None
        result = predictions[0]
        keypoints = getattr(result, "keypoints", None)
        if keypoints is None or keypoints.xy is None or len(keypoints.xy) == 0:
            return None

        candidate_index = 0
        if getattr(result, "boxes", None) is not None and result.boxes.conf is not None and len(result.boxes.conf) > 0:
            candidate_index = int(np.argmax(result.boxes.conf.cpu().numpy()))

        xy = keypoints.xy[candidate_index].cpu().numpy()
        conf = keypoints.conf[candidate_index].cpu().numpy() if keypoints.conf is not None else np.ones(len(xy))
        points: list[PoseKeypoint] = []
        confidences: list[float] = []
        for index, (point, score) in enumerate(zip(xy, conf)):
            name = COCO_KEYPOINT_NAMES[index] if index < len(COCO_KEYPOINT_NAMES) else f"kp_{index}"
            x, y = float(point[0]) + left, float(point[1]) + top
            confidence = round(float(score), 4)
            points.append(PoseKeypoint(name=name, x=round(x, 2), y=round(y, 2), confidence=confidence))
            confidences.append(float(score))
        skeleton_confidence = round(float(np.mean(confidences)), 4) if confidences else 0.0
        return PoseResult(track_id=track_id, keypoints=points, skeleton_confidence=skeleton_confidence)

    def _crop(self, frame: np.ndarray, bbox: list[float]) -> tuple[np.ndarray, int, int] | None:
        height, width = frame.shape[:2]
        x1, y1, x2, y2 = bbox
        pad_x = (x2 - x1) * self.settings.pose_crop_padding_ratio
        pad_y = (y2 - y1) * self.settings.pose_crop_padding_ratio
        left = max(0, int(x1 - pad_x))
        top = max(0, int(y1 - pad_y))
        right = min(width, int(x2 + pad_x))
        bottom = min(height, int(y2 + pad_y))
        if right <= left or bottom <= top:
            return None
        crop = frame[top:bottom, left:right]
        if crop.size == 0:
            return None
        # Ensure contiguous BGR input for Ultralytics.
        return cv2.copyMakeBorder(crop, 0, 0, 0, 0, cv2.BORDER_CONSTANT), left, top
