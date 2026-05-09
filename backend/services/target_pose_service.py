from __future__ import annotations

import time
from pathlib import Path
from threading import RLock
from typing import Any

import numpy as np
import torch
from ultralytics import YOLO


COCO_SKELETON = [
    (0, 1), (0, 2), (1, 3), (2, 4),
    (5, 6),
    (5, 7), (7, 9),
    (6, 8), (8, 10),
    (5, 11), (6, 12),
    (11, 12),
    (11, 13), (13, 15),
    (12, 14), (14, 16),
]


class TargetPoseService:
    """Pose estimation on a target-only ROI."""

    def __init__(self, *, model_root: Path) -> None:
        self._lock = RLock()
        self._loaded = False
        self._load_error: str | None = None
        self._model: YOLO | None = None
        self._device: str | int = "cpu"
        self._half = False
        self._pose_path = model_root / "yolo11n-pose.pt"

    def status(self) -> dict[str, Any]:
        return {
            "loaded": self._loaded,
            "load_error": self._load_error,
            "pose_path": str(self._pose_path),
            "device": self._device,
            "half": self._half,
        }

    def warmup(self, *, imgsz: int = 384, conf: float = 0.25) -> dict[str, Any]:
        dummy = np.zeros((420, 240, 3), dtype=np.uint8)
        return self.estimate_pose(dummy, imgsz=imgsz, conf=conf)

    def estimate_pose(
        self,
        frame: np.ndarray,
        *,
        bbox: list[int] | None = None,
        imgsz: int = 640,
        conf: float = 0.2,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            self._ensure_loaded()
            if frame is None or frame.size == 0:
                return self._empty_payload("INVALID_IMAGE", started)

            roi = frame
            offset_x = 0
            offset_y = 0
            if bbox is not None:
                x1, y1, x2, y2 = [int(v) for v in bbox]
                h, w = frame.shape[:2]
                x1 = max(0, min(w - 1, x1))
                y1 = max(0, min(h - 1, y1))
                x2 = max(0, min(w, x2))
                y2 = max(0, min(h, y2))
                if x2 > x1 and y2 > y1:
                    roi = frame[y1:y2, x1:x2]
                    offset_x = x1
                    offset_y = y1

            with torch.inference_mode():
                result = self._model.predict(  # type: ignore[union-attr]
                    roi,
                    verbose=False,
                    imgsz=imgsz,
                    conf=conf,
                    device=self._device,
                    half=self._half,
                )[0]
            keypoints = result.keypoints
            if keypoints is None or keypoints.xy is None or len(keypoints.xy) == 0:
                return self._empty_payload("POSE_NOT_FOUND", started)

            xy = keypoints.xy.detach().cpu().numpy()[0]
            conf = keypoints.conf.detach().cpu().numpy()[0] if keypoints.conf is not None else np.zeros((xy.shape[0],), dtype=np.float32)

            points = []
            for idx, ((x, y), score) in enumerate(zip(xy, conf)):
                points.append(
                    {
                        "index": idx,
                        "x": round(float(x) + offset_x, 1),
                        "y": round(float(y) + offset_y, 1),
                        "score": round(float(score), 4),
                    }
                )

            connections = []
            for a, b in COCO_SKELETON:
                if a < len(points) and b < len(points):
                    connections.append({"from": a, "to": b})

            posture = self._classify_posture(points)
            return {
                "ok": True,
                "pose": {
                    "points": points,
                    "connections": connections,
                    "posture": posture,
                },
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "model": self.status(),
            }
        except Exception as exc:
            self._load_error = f"{exc.__class__.__name__}: {exc}"
            return self._empty_payload(self._load_error, started)

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            if not self._pose_path.exists():
                raise FileNotFoundError(self._pose_path)
            use_cuda = torch.cuda.is_available()
            self._device = 0 if use_cuda else "cpu"
            self._half = use_cuda
            self._model = YOLO(str(self._pose_path))
            self._loaded = True
            self._load_error = None

    @staticmethod
    def _classify_posture(points: list[dict[str, Any]]) -> dict[str, Any]:
        def pt(idx: int):
            if idx >= len(points):
                return None
            p = points[idx]
            if float(p["score"]) < 0.2:
                return None
            return np.array([float(p["x"]), float(p["y"])], dtype=np.float32)

        left_shoulder = pt(5)
        right_shoulder = pt(6)
        left_hip = pt(11)
        right_hip = pt(12)
        nose = pt(0)
        left_wrist = pt(9)
        right_wrist = pt(10)

        if left_shoulder is None or right_shoulder is None:
            return {
                "label": "unknown",
                "severity": "normal",
                "confidence": 0.0,
                "torso_angle_deg": None,
                "features": {},
            }

        shoulder_mid = (left_shoulder + right_shoulder) * 0.5
        hip_mid = (left_hip + right_hip) * 0.5 if left_hip is not None and right_hip is not None else None
        anchor = hip_mid if hip_mid is not None else shoulder_mid

        angle = None
        if hip_mid is not None:
            torso = shoulder_mid - hip_mid
            torso_norm = max(float(np.linalg.norm(torso)), 1e-6)
            vertical = np.array([0.0, -1.0], dtype=np.float32)
            cosine = float(np.dot(torso / torso_norm, vertical))
            angle = float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))

        label = "upright"
        severity = "normal"
        confidence = 0.0

        hand_to_chest = False
        hand_to_abdomen = False
        shoulder_span = float(np.linalg.norm(left_shoulder - right_shoulder))
        if shoulder_span > 1e-6:
            chest_threshold = shoulder_span * 0.75
            abdomen_threshold = shoulder_span * 0.9
            if left_wrist is not None:
                if float(np.linalg.norm(left_wrist - shoulder_mid)) <= chest_threshold:
                    hand_to_chest = True
                if hip_mid is not None and float(np.linalg.norm(left_wrist - hip_mid)) <= abdomen_threshold:
                    hand_to_abdomen = True
            if right_wrist is not None:
                if float(np.linalg.norm(right_wrist - shoulder_mid)) <= chest_threshold:
                    hand_to_chest = True
                if hip_mid is not None and float(np.linalg.norm(right_wrist - hip_mid)) <= abdomen_threshold:
                    hand_to_abdomen = True

        if hand_to_chest or hand_to_abdomen:
            label = "hand_to_chest_or_abdomen"
            severity = "warning"
            confidence = 0.7
        elif angle is not None:
            confidence = max(0.0, min(1.0, angle / 90.0))
            if angle >= 68:
                label = "fall_like"
                severity = "danger"
            elif angle >= 42:
                label = "leaning"
                severity = "warning"
            elif nose is not None and hip_mid is not None and nose[1] > hip_mid[1]:
                label = "slumped"
                severity = "warning"
                confidence = max(confidence, 0.65)
        elif nose is not None and nose[1] > shoulder_mid[1] + max(shoulder_span * 0.15, 10.0):
            label = "slumped"
            severity = "warning"
            confidence = 0.6
        else:
            label = "upright"
            severity = "normal"
            confidence = 0.45

        return {
            "label": label,
            "severity": severity,
            "confidence": round(confidence, 4),
            "torso_angle_deg": round(angle, 2) if angle is not None else None,
            "features": {
                "hand_to_chest": hand_to_chest,
                "hand_to_abdomen": hand_to_abdomen,
                "hips_visible": hip_mid is not None,
                "anchor_x": round(float(anchor[0]), 2),
                "anchor_y": round(float(anchor[1]), 2),
                "shoulder_span": round(float(shoulder_span), 2),
            },
        }

    def _empty_payload(self, error: str, started: float) -> dict[str, Any]:
        return {
            "ok": False,
            "error": error,
            "pose": {
                "points": [],
                "connections": [],
                "posture": {
                    "label": "unknown",
                    "severity": "normal",
                    "confidence": 0.0,
                },
            },
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "model": self.status(),
        }
