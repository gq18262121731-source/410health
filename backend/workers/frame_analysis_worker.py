from __future__ import annotations

import base64
import json
import sys
import traceback
from typing import Any

import cv2
import numpy as np

from backend.dependencies import get_fall_multimodal_review_status, get_target_pose_service, get_target_user_fall_service


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


def _analyze(payload: dict[str, Any]) -> dict[str, Any]:
    image_b64 = str(payload.get("image_b64") or "")
    session_id = str(payload.get("session_id") or "browser-preview")
    run_fall = bool(payload.get("run_fall", True))
    image_bytes = base64.b64decode(image_b64, validate=True)
    frame = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        return {"ok": False, "error": "INVALID_IMAGE"}

    pose_result = get_target_pose_service().estimate_pose(
        frame,
        imgsz=int(payload.get("pose_imgsz") or 640),
        conf=float(payload.get("pose_conf") or 0.2),
        session_id=session_id,
    )
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


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            request_id = request.get("id")
            payload = request.get("payload") if isinstance(request.get("payload"), dict) else {}
            response = {"id": request_id, "ok": True, "result": _analyze(payload)}
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
