from __future__ import annotations

import base64
import json
import sys
import traceback
from typing import Any

import cv2
import numpy as np

from backend.config import get_settings
from backend.dependencies import get_fall_multimodal_review_status, get_target_pose_service, get_target_user_fall_service

_SESSION_BBOX: dict[str, list[int]] = {}
_SETTINGS = get_settings()


def _pose_points_to_latest(pose_result: dict[str, Any], *, width: int, height: int) -> dict[str, Any]:
    pose = pose_result.get("pose") if isinstance(pose_result, dict) else None
    if not isinstance(pose, dict):
        return {"status": "empty", "frame_width": width, "frame_height": height, "tracks": []}
    raw_points = pose.get("points")
    if not isinstance(raw_points, list):
        return {"status": "empty", "frame_width": width, "frame_height": height, "tracks": []}

    keypoints: list[list[float]] = []
    for point in raw_points:
        if not isinstance(point, dict):
            continue
        keypoints.append(
            [
                float(point.get("x") or 0),
                float(point.get("y") or 0),
                float(point.get("score") or 0),
            ]
        )
    if not keypoints:
        return {"status": "empty", "frame_width": width, "frame_height": height, "tracks": []}

    posture = pose.get("posture") if isinstance(pose.get("posture"), dict) else {}
    quality = pose.get("quality") if isinstance(pose.get("quality"), dict) else {}
    label = str(posture.get("label") or "unknown") if isinstance(posture, dict) else "unknown"
    score = float(posture.get("score") or posture.get("confidence") or 0) if isinstance(posture, dict) else 0.0
    pose_score = float(quality.get("mean_score") or 0) if isinstance(quality, dict) else 0.0
    return {
        "backend": "single_frame_worker",
        "profile": "browser_preview",
        "frame_width": width,
        "frame_height": height,
        "tracks": [
            {
                "track_id": 1,
                "bbox": [],
                "pose_score": pose_score,
                "state_label": label,
                "state_score": score,
                "keypoints": keypoints,
                "features": {"quality": quality},
            }
        ],
    }


def _bbox_from_pose_latest(pose_latest: dict[str, Any]) -> list[int] | None:
    tracks = pose_latest.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        return None
    track = tracks[0]
    if not isinstance(track, dict):
        return None
    keypoints = track.get("keypoints")
    if not isinstance(keypoints, list):
        return None
    xs: list[float] = []
    ys: list[float] = []
    for point in keypoints:
        if not isinstance(point, list) or len(point) < 3:
            continue
        score = float(point[2] or 0)
        if score < 0.25:
            continue
        xs.append(float(point[0] or 0))
        ys.append(float(point[1] or 0))
    if len(xs) < 5 or len(ys) < 5:
        return None
    x1, x2 = min(xs), max(xs)
    y1, y2 = min(ys), max(ys)
    pad_x = max(24.0, (x2 - x1) * 0.25)
    pad_y = max(32.0, (y2 - y1) * 0.28)
    return [int(x1 - pad_x), int(y1 - pad_y), int(x2 + pad_x), int(y2 + pad_y)]


def _clamp_bbox(bbox: list[int], *, width: int, height: int) -> list[int] | None:
    if len(bbox) < 4:
        return None
    x1 = max(0, min(width - 2, int(bbox[0])))
    y1 = max(0, min(height - 2, int(bbox[1])))
    x2 = max(x1 + 1, min(width, int(bbox[2])))
    y2 = max(y1 + 1, min(height, int(bbox[3])))
    if (x2 - x1) < 48 or (y2 - y1) < 80:
        return None
    return [x1, y1, x2, y2]


def _analyze(payload: dict[str, Any]) -> dict[str, Any]:
    image_b64 = str(payload.get("image_b64") or "")
    session_id = str(payload.get("session_id") or "browser-preview")
    run_pose = bool(payload.get("run_pose", True))
    run_fall = bool(payload.get("run_fall", True))
    image_bytes = base64.b64decode(image_b64, validate=True)
    frame = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        return {"ok": False, "error": "INVALID_IMAGE"}

    if run_pose:
        pose_result = get_target_pose_service().estimate_pose(
            frame,
            imgsz=int(payload.get("pose_imgsz") or _SETTINGS.pose_detection_single_frame_imgsz),
            conf=float(payload.get("pose_conf") or 0.2),
            session_id=session_id,
        )
    else:
        pose_result = {
            "ok": False,
            "status": "skipped",
            "pose": {
                "points": [],
                "connections": [],
                "posture": {"label": "disabled", "severity": "normal", "confidence": 0.0},
                "quality": {"visible_points": 0, "mean_score": 0.0, "estimated_points": 0},
            },
        }
    if run_fall:
        fall_result = get_target_user_fall_service().detect(
            image_bytes,
            include_annotated_image=False,
            target_only=False,
            session_id=session_id,
        )
    else:
        fall_result = {"ok": False, "status": "skipped", "fall_result": None}

    pose_latest = _pose_points_to_latest(
        pose_result,
        width=int(frame.shape[1]),
        height=int(frame.shape[0]),
    )
    return {
        "ok": bool(pose_result.get("ok") or fall_result.get("ok")),
        "pose": pose_result,
        "pose_latest": pose_latest,
        "fall": fall_result,
        "multimodal_review": get_fall_multimodal_review_status(),
    }


def _analyze_pose(payload: dict[str, Any]) -> dict[str, Any]:
    image_b64 = str(payload.get("image_b64") or "")
    session_id = str(payload.get("session_id") or "browser-preview")
    image_bytes = base64.b64decode(image_b64, validate=True)
    frame = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        return {"ok": False, "error": "INVALID_IMAGE", "pose_latest": {"status": "empty", "tracks": []}}

    pose_result = get_target_pose_service().estimate_pose(
        frame,
        bbox=_clamp_bbox(_SESSION_BBOX.get(session_id, []), width=int(frame.shape[1]), height=int(frame.shape[0])),
        imgsz=int(payload.get("pose_imgsz") or _SETTINGS.pose_detection_single_frame_imgsz),
        conf=float(payload.get("pose_conf") or 0.2),
        session_id=session_id,
    )
    pose_latest = _pose_points_to_latest(
        pose_result,
        width=int(frame.shape[1]),
        height=int(frame.shape[0]),
    )
    next_bbox = _bbox_from_pose_latest(pose_latest)
    if next_bbox is not None:
        _SESSION_BBOX[session_id] = next_bbox
    elif not pose_result.get("ok"):
        _SESSION_BBOX.pop(session_id, None)
    return {
        "ok": bool(pose_result.get("ok")),
        "pose": pose_result,
        "pose_latest": pose_latest,
    }


def _analyze_fall(payload: dict[str, Any]) -> dict[str, Any]:
    image_b64 = str(payload.get("image_b64") or "")
    session_id = str(payload.get("session_id") or "browser-preview")
    image_bytes = base64.b64decode(image_b64, validate=True)
    fall_result = get_target_user_fall_service().detect(
        image_bytes,
        include_annotated_image=False,
        target_only=False,
        session_id=session_id,
    )
    return {
        "ok": bool(fall_result.get("ok")),
        "fall": fall_result,
        "multimodal_review": get_fall_multimodal_review_status(),
    }


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            request_id = request.get("id")
            payload = request.get("payload") if isinstance(request.get("payload"), dict) else {}
            task = str(request.get("task") or payload.get("task") or "full")
            if task == "pose":
                result = _analyze_pose(payload)
            elif task == "fall":
                result = _analyze_fall(payload)
            else:
                result = _analyze(payload)
            response = {"id": request_id, "ok": True, "result": result}
        except Exception as exc:
            response = {
                "id": locals().get("request", {}).get("id") if isinstance(locals().get("request"), dict) else None,
                "ok": False,
                "error": f"{exc.__class__.__name__}: {exc}",
                "traceback": traceback.format_exc(limit=6),
            }
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
