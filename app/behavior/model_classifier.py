from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


BEHAVIOR_LABELS = [
    "standing",
    "walking",
    "sitting",
    "bending",
    "lying",
    "squatting",
    "unknown",
]

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

FEATURE_NAMES = [
    "shoulder_y",
    "hip_y",
    "knee_y",
    "ankle_y",
    "torso_angle",
    "bbox_aspect_ratio",
    "torso_height_body_ratio",
    "lower_body_height_body_ratio",
    "hip_to_knee",
    "knee_to_ankle",
    "shoulder_width_body_ratio",
    "hip_width_body_ratio",
    "knee_width_body_ratio",
    "ankle_width_body_ratio",
    "shoulder_hip_dx_body_ratio",
    "hip_knee_dx_body_ratio",
    "knee_ankle_dx_body_ratio",
    "hip_ankle_dx_body_ratio",
    "left_knee_angle",
    "right_knee_angle",
    "left_lower_leg_angle",
    "right_lower_leg_angle",
    "body_center_x",
    "body_center_y",
    "motion_dx_body_ratio",
    "motion_dy_body_ratio",
    "motion_speed_body_ratio",
    "motion_vertical_speed_body_ratio",
    "motion_window_span_sec",
]


@dataclass(frozen=True)
class ModelBehaviorDecision:
    state: str
    confidence: float
    probabilities: dict[str, float]
    reason: str = "model_classifier"


class PoseFeatureBuilder:
    def __init__(
        self,
        *,
        min_keypoint_confidence: float = 0.2,
        motion_window_size: int = 8,
    ) -> None:
        self.min_keypoint_confidence = min_keypoint_confidence
        self.motion_window_size = max(2, motion_window_size)
        self._history: dict[str, list[tuple[float, tuple[float, float], float]]] = {}

    def reset(self) -> None:
        self._history.clear()

    def extract(self, record: dict[str, Any]) -> dict[str, float]:
        bbox = _extract_bbox(record)
        keypoints = _keypoints_by_name(record.get("keypoints"), self.min_keypoint_confidence)
        frame_width = _safe_float(record.get("frame_width"))
        frame_height = _safe_float(record.get("frame_height"))

        x1, y1, x2, y2 = bbox
        bbox_width = max(0.0, x2 - x1)
        bbox_height = max(0.0, y2 - y1)
        body_height = max(1.0, bbox_height)
        center = ((x1 + x2) / 2, (y1 + y2) / 2)

        head = _mean_point(keypoints, ["nose", "left_eye", "right_eye", "left_ear", "right_ear"])
        shoulder = _mean_point(keypoints, ["left_shoulder", "right_shoulder"])
        hip = _mean_point(keypoints, ["left_hip", "right_hip"])
        knee = _mean_point(keypoints, ["left_knee", "right_knee"])
        ankle = _mean_point(keypoints, ["left_ankle", "right_ankle"])

        top_reference = head or shoulder or (center[0], y1)
        bottom_reference = ankle or knee or hip or (center[0], y2)
        keypoint_body_height = max(1.0, abs(bottom_reference[1] - top_reference[1]))

        timestamp_sec = _timestamp_seconds(record)
        track_key = _track_key(record)
        motion = self._motion_features(track_key, timestamp_sec, center, keypoint_body_height)

        features = {
            "shoulder_y": _relative_y(shoulder, y1, body_height),
            "hip_y": _relative_y(hip, y1, body_height),
            "knee_y": _relative_y(knee, y1, body_height),
            "ankle_y": _relative_y(ankle, y1, body_height),
            "torso_angle": _torso_angle(shoulder, hip),
            "bbox_aspect_ratio": bbox_width / bbox_height if bbox_height > 0 else math.nan,
            "torso_height_body_ratio": _vertical_distance(shoulder, hip) / keypoint_body_height,
            "lower_body_height_body_ratio": _vertical_distance(hip, ankle) / keypoint_body_height,
            "hip_to_knee": _distance(hip, knee) / keypoint_body_height,
            "knee_to_ankle": _distance(knee, ankle) / keypoint_body_height,
            "shoulder_width_body_ratio": _pair_width(keypoints, "left_shoulder", "right_shoulder") / keypoint_body_height,
            "hip_width_body_ratio": _pair_width(keypoints, "left_hip", "right_hip") / keypoint_body_height,
            "knee_width_body_ratio": _pair_width(keypoints, "left_knee", "right_knee") / keypoint_body_height,
            "ankle_width_body_ratio": _pair_width(keypoints, "left_ankle", "right_ankle") / keypoint_body_height,
            "shoulder_hip_dx_body_ratio": _dx(shoulder, hip) / keypoint_body_height,
            "hip_knee_dx_body_ratio": _dx(hip, knee) / keypoint_body_height,
            "knee_ankle_dx_body_ratio": _dx(knee, ankle) / keypoint_body_height,
            "hip_ankle_dx_body_ratio": _dx(hip, ankle) / keypoint_body_height,
            "left_knee_angle": _joint_angle(
                keypoints.get("left_hip"),
                keypoints.get("left_knee"),
                keypoints.get("left_ankle"),
            ),
            "right_knee_angle": _joint_angle(
                keypoints.get("right_hip"),
                keypoints.get("right_knee"),
                keypoints.get("right_ankle"),
            ),
            "left_lower_leg_angle": _limb_angle(keypoints.get("left_knee"), keypoints.get("left_ankle")),
            "right_lower_leg_angle": _limb_angle(keypoints.get("right_knee"), keypoints.get("right_ankle")),
            "body_center_x": center[0] / frame_width if frame_width and frame_width > 0 else math.nan,
            "body_center_y": center[1] / frame_height if frame_height and frame_height > 0 else math.nan,
            **motion,
        }
        return {name: _finite_or_nan(features.get(name)) for name in FEATURE_NAMES}

    def _motion_features(
        self,
        track_key: str,
        timestamp_sec: float,
        center: tuple[float, float],
        body_height: float,
    ) -> dict[str, float]:
        history = self._history.setdefault(track_key, [])
        history.append((timestamp_sec, center, body_height))
        if len(history) > self.motion_window_size:
            del history[: len(history) - self.motion_window_size]
        if len(history) < 2:
            return _empty_motion_features()

        start_time, start_center, start_height = history[0]
        elapsed = max(timestamp_sec - start_time, 1e-6)
        reference_height = max(1.0, (body_height + start_height) / 2)
        dx = center[0] - start_center[0]
        dy = center[1] - start_center[1]
        return {
            "motion_dx_body_ratio": dx / reference_height,
            "motion_dy_body_ratio": dy / reference_height,
            "motion_speed_body_ratio": math.hypot(dx, dy) / elapsed / reference_height,
            "motion_vertical_speed_body_ratio": dy / elapsed / reference_height,
            "motion_window_span_sec": elapsed,
        }


class BehaviorModelClassifier:
    def __init__(
        self,
        model_path: str | Path,
        *,
        min_keypoint_confidence: float = 0.2,
        motion_window_size: int = 8,
    ) -> None:
        self.model_path = Path(model_path)
        self.feature_builder = PoseFeatureBuilder(
            min_keypoint_confidence=min_keypoint_confidence,
            motion_window_size=motion_window_size,
        )
        self._artifact: dict[str, Any] | None = None
        self._model: Any | None = None
        self.feature_names = FEATURE_NAMES
        self.labels = BEHAVIOR_LABELS

    def load(self) -> None:
        try:
            import joblib
        except ImportError as exc:
            raise RuntimeError("joblib is required to load a behavior classifier artifact") from exc

        artifact = joblib.load(self.model_path)
        if not isinstance(artifact, dict) or "model" not in artifact:
            raise RuntimeError(f"invalid behavior classifier artifact: {self.model_path}")
        self._artifact = artifact
        self._model = artifact["model"]
        self.feature_names = list(artifact.get("feature_names") or FEATURE_NAMES)
        self.labels = list(artifact.get("labels") or BEHAVIOR_LABELS)

    def classify_record(self, record: dict[str, Any]) -> ModelBehaviorDecision:
        if self._model is None:
            self.load()
        assert self._model is not None

        features = self.feature_builder.extract(record)
        vector = np.array([[features.get(name, math.nan) for name in self.feature_names]], dtype=float)
        state = str(self._model.predict(vector)[0])
        probabilities = self._probabilities(vector)
        confidence = probabilities.get(state, 0.0)
        return ModelBehaviorDecision(
            state=state,
            confidence=round(float(confidence), 4),
            probabilities={key: round(float(value), 4) for key, value in probabilities.items()},
        )

    def classify_object(
        self,
        obj: Any,
        *,
        frame_width: int | None = None,
        frame_height: int | None = None,
        timestamp_sec: float | None = None,
        camera_id: str = "default",
    ) -> ModelBehaviorDecision:
        record = object_to_record(
            obj,
            frame_width=frame_width,
            frame_height=frame_height,
            timestamp_sec=timestamp_sec,
            camera_id=camera_id,
        )
        return self.classify_record(record)

    def _probabilities(self, vector: np.ndarray) -> dict[str, float]:
        assert self._model is not None
        if hasattr(self._model, "predict_proba"):
            raw = self._model.predict_proba(vector)[0]
            classes = [str(item) for item in getattr(self._model, "classes_", self.labels)]
            return dict(zip(classes, raw))
        state = str(self._model.predict(vector)[0])
        return {label: 1.0 if label == state else 0.0 for label in self.labels}


def object_to_record(
    obj: Any,
    *,
    frame_width: int | None = None,
    frame_height: int | None = None,
    timestamp_sec: float | None = None,
    camera_id: str = "default",
) -> dict[str, Any]:
    if hasattr(obj, "model_dump"):
        data = obj.model_dump()
    elif isinstance(obj, dict):
        data = dict(obj)
    else:
        data = {
            "bbox": getattr(obj, "bbox", None),
            "track_id": getattr(obj, "track_id", None),
            "pose": getattr(obj, "pose", None),
        }
    pose = data.get("pose") or {}
    return {
        "camera_id": camera_id,
        "track_id": data.get("track_id"),
        "bbox": data.get("bbox"),
        "keypoints": pose.get("keypoints") if isinstance(pose, dict) else None,
        "frame_width": frame_width,
        "frame_height": frame_height,
        "timestamp_sec": timestamp_sec if timestamp_sec is not None else time.monotonic(),
    }


def feature_vector_from_record(
    record: dict[str, Any],
    builder: PoseFeatureBuilder | None = None,
) -> dict[str, float]:
    return (builder or PoseFeatureBuilder()).extract(record)


def _extract_bbox(record: dict[str, Any]) -> tuple[float, float, float, float]:
    bbox = record.get("bbox") or [math.nan, math.nan, math.nan, math.nan]
    if len(bbox) < 4:
        return math.nan, math.nan, math.nan, math.nan
    return tuple(float(value) for value in bbox[:4])  # type: ignore[return-value]


def _keypoints_by_name(raw_keypoints: Any, min_confidence: float) -> dict[str, tuple[float, float]]:
    keypoints: dict[str, tuple[float, float]] = {}
    if not isinstance(raw_keypoints, list):
        return keypoints
    for item in raw_keypoints:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        confidence = _safe_float(item.get("confidence"), default=0.0)
        x = _safe_float(item.get("x"))
        y = _safe_float(item.get("y"))
        if name and confidence >= min_confidence and x is not None and y is not None:
            keypoints[str(name)] = (x, y)
    return keypoints


def _track_key(record: dict[str, Any]) -> str:
    source = record.get("source") or record.get("camera_id") or record.get("video_path") or "default"
    track = record.get("track_id")
    if track is None:
        track = record.get("person_index", 0)
    return f"{source}:{track}"


def _timestamp_seconds(record: dict[str, Any]) -> float:
    value = _safe_float(record.get("timestamp_sec"))
    if value is not None:
        return value
    value = _safe_float(record.get("timestamp_ms"))
    if value is not None:
        return value / 1000
    frame_index = _safe_float(record.get("frame_index"))
    fps = _safe_float(record.get("fps"))
    if frame_index is not None and fps and fps > 0:
        return frame_index / fps
    return time.monotonic()


def _empty_motion_features() -> dict[str, float]:
    return {
        "motion_dx_body_ratio": math.nan,
        "motion_dy_body_ratio": math.nan,
        "motion_speed_body_ratio": math.nan,
        "motion_vertical_speed_body_ratio": math.nan,
        "motion_window_span_sec": 0.0,
    }


def _mean_point(
    keypoints: dict[str, tuple[float, float]],
    names: list[str],
) -> tuple[float, float] | None:
    points = [keypoints[name] for name in names if name in keypoints]
    if not points:
        return None
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )


def _relative_y(point: tuple[float, float] | None, bbox_y: float, bbox_height: float) -> float:
    if point is None or not math.isfinite(bbox_y) or bbox_height <= 0:
        return math.nan
    return (point[1] - bbox_y) / bbox_height


def _torso_angle(
    shoulder: tuple[float, float] | None,
    hip: tuple[float, float] | None,
) -> float:
    if shoulder is None or hip is None:
        return math.nan
    dx = hip[0] - shoulder[0]
    dy = hip[1] - shoulder[1]
    if abs(dy) < 1e-6:
        return 90.0
    return math.degrees(math.atan2(dx, dy))


def _vertical_distance(
    a: tuple[float, float] | None,
    b: tuple[float, float] | None,
) -> float:
    if a is None or b is None:
        return math.nan
    return abs(b[1] - a[1])


def _distance(
    a: tuple[float, float] | None,
    b: tuple[float, float] | None,
) -> float:
    if a is None or b is None:
        return math.nan
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _pair_width(keypoints: dict[str, tuple[float, float]], left: str, right: str) -> float:
    if left not in keypoints or right not in keypoints:
        return math.nan
    return abs(keypoints[right][0] - keypoints[left][0])


def _dx(a: tuple[float, float] | None, b: tuple[float, float] | None) -> float:
    if a is None or b is None:
        return math.nan
    return b[0] - a[0]


def _joint_angle(
    a: tuple[float, float] | None,
    b: tuple[float, float] | None,
    c: tuple[float, float] | None,
) -> float:
    if a is None or b is None or c is None:
        return math.nan
    ba = (a[0] - b[0], a[1] - b[1])
    bc = (c[0] - b[0], c[1] - b[1])
    norm_ba = math.hypot(*ba)
    norm_bc = math.hypot(*bc)
    if norm_ba <= 1e-6 or norm_bc <= 1e-6:
        return math.nan
    cosine = max(-1.0, min(1.0, (ba[0] * bc[0] + ba[1] * bc[1]) / (norm_ba * norm_bc)))
    return math.degrees(math.acos(cosine))


def _limb_angle(a: tuple[float, float] | None, b: tuple[float, float] | None) -> float:
    if a is None or b is None:
        return math.nan
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    if abs(dy) < 1e-6:
        return 90.0
    return math.degrees(math.atan2(dx, dy))


def _safe_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _finite_or_nan(value: Any) -> float:
    if value is None:
        return math.nan
    try:
        result = float(value)
    except (TypeError, ValueError):
        return math.nan
    return result if math.isfinite(result) else math.nan
