from __future__ import annotations

import time
from pathlib import Path
from threading import RLock
from typing import Any

import cv2
import numpy as np
from ultralytics.trackers.byte_tracker import BYTETracker
from ultralytics.utils import IterableSimpleNamespace

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
        self._session_match_cache: dict[str, dict[str, Any]] = {}
        self._session_trackers: dict[str, BYTETracker] = {}
        self._match_cache_ttl_ms = 1800
        self._full_refresh_interval_ms = 900
        self._tracker_args = IterableSimpleNamespace(
            tracker_type="bytetrack",
            track_high_thresh=0.25,
            track_low_thresh=0.1,
            new_track_thresh=0.25,
            track_buffer=30,
            match_thresh=0.8,
            fuse_score=True,
        )
        self._roi_padding_ratio = 0.18
        self._init_fall_frame_service()

    def _init_fall_frame_service(self) -> None:
        try:
            from backend.services.fall_frame_test_service import FallFrameTestService
            from backend.config import get_settings

            self._fall_frame_service = FallFrameTestService(get_settings())
        except Exception:
            self._fall_frame_service = None

    def detect(
        self,
        image_bytes: bytes,
        *,
        include_annotated_image: bool = True,
        target_only: bool = True,
        session_id: str = "default",
    ) -> dict[str, Any]:
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

        now_ms = int(time.perf_counter() * 1000)
        cache_entry = self._get_cache_entry(session_id)
        force_full_match = True
        if cache_entry is not None and "last_full_match_ms" not in cache_entry:
            cache_entry["last_full_match_ms"] = int(cache_entry.get("ts_ms", now_ms))
        if cache_entry and (now_ms - int(cache_entry["last_full_match_ms"])) <= self._full_refresh_interval_ms:
            force_full_match = False

        tracked_persons = self._resolve_tracked_persons(frame=frame, session_id=session_id)
        tracked_person = None
        target_features = None
        target_match = None
        tracking_payload = {
            "session_id": session_id,
            "track_id": None,
            "used_track": False,
            "full_match_refreshed": force_full_match,
            "candidate_count": len(tracked_persons),
        }

        if tracked_persons:
            tracked_person, target_match, target_features = self._pick_target_candidate(
                tracked_persons=tracked_persons,
                session_id=session_id,
                now_ms=now_ms,
                force_full_match=force_full_match,
            )
            if tracked_person is not None:
                tracking_payload["track_id"] = tracked_person["track_id"]
                tracking_payload["used_track"] = True

        if target_match is None or target_features is None:
            target_features = self._target_user_service.extract_features_from_frame(
                frame,
                include_face=force_full_match,
                include_body=True,
            )
            target_match = self._resolve_target_match(
                face_embedding=target_features["face_embedding"],
                body_profile=target_features["body_profile"],
                session_id=session_id,
                now_ms=now_ms,
                track_id=tracked_person["track_id"] if tracked_person is not None else None,
            )

        assert target_match is not None
        assert target_features is not None

        if target_only and not target_match.matched:
            return {
                "ok": True,
                "status": "filtered_non_target",
                "target_match": target_match.model_dump(mode="json"),
                "fall_result": None,
                "warnings": target_features["warnings"],
                "tracking": tracking_payload,
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }

        if self._fall_frame_service is None:
            return {
                "ok": False,
                "status": "model_unavailable",
                "error": "FALL_MODEL_UNAVAILABLE",
                "target_match": target_match.model_dump(mode="json"),
                "fall_result": None,
                "tracking": tracking_payload,
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }

        roi_info = None
        if tracked_person is not None and target_match.matched:
            roi_frame, roi_bbox = self._crop_target_roi(frame, tracked_person["bbox"])
            if roi_frame is not None:
                fall_result = self._fall_frame_service.detect_frame(roi_frame, include_annotated_image=include_annotated_image)
                self._offset_detections(fall_result, roi_bbox)
                roi_info = {
                    "bbox": roi_bbox,
                    "used_roi": True,
                }
            else:
                fall_result = self._fall_frame_service.detect_frame(frame, include_annotated_image=include_annotated_image)
        else:
            fall_result = self._fall_frame_service.detect_frame(frame, include_annotated_image=include_annotated_image)

        if fall_result.get("frame"):
            fall_result["frame"] = {"width": frame.shape[1], "height": frame.shape[0]}
        return {
            "ok": bool(fall_result.get("ok", False)),
            "status": fall_result.get("status"),
            "target_match": target_match.model_dump(mode="json"),
            "fall_result": fall_result,
            "warnings": target_features["warnings"],
            "tracking": {
                **tracking_payload,
                "roi": roi_info,
            },
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }

    def _resolve_target_match(
        self,
        *,
        face_embedding: list[float] | None,
        body_profile: dict[str, float] | None,
        session_id: str,
        now_ms: int,
        track_id: int | None,
    ):
        cached = self._get_cache_entry(session_id)

        if cached and (now_ms - int(cached["ts_ms"])) <= self._match_cache_ttl_ms:
            if track_id is not None and cached.get("track_id") is not None and int(cached["track_id"]) != int(track_id):
                cached = None
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
            last_full_match_ms = now_ms
            if face_embedding is None and cached is not None:
                last_full_match_ms = int(cached.get("last_full_match_ms", now_ms))
            self._set_cache_entry(
                session_id,
                {
                    "ts_ms": now_ms,
                    "last_full_match_ms": last_full_match_ms,
                    "match": target_match,
                    "body_profile": body_profile,
                    "track_id": track_id,
                },
            )
        else:
            if cached and (now_ms - int(cached["ts_ms"])) > self._match_cache_ttl_ms:
                self._clear_cache_entry(session_id)
        return target_match

    def _resolve_tracked_persons(self, *, frame: np.ndarray, session_id: str) -> list[dict[str, Any]]:
        tracker = self._get_or_create_tracker(session_id)
        person_boxes = self._target_user_service._collect_person_boxes(  # type: ignore[attr-defined]
            frame,
            self._target_user_service._person_model,  # type: ignore[attr-defined]
            allowed_labels={"person"},
            conf=0.2,
        )
        if not person_boxes:
            person_boxes = self._target_user_service._collect_person_boxes(  # type: ignore[attr-defined]
                frame,
                self._target_user_service._fallback_person_model,  # type: ignore[attr-defined]
                allowed_labels={"person", "fall", "fallen", "sitting", "lying", "bending"},
                conf=0.2,
            )
        if not person_boxes:
            return []

        class _TrackResults:
            def __init__(self, boxes):
                xywh = []
                conf = []
                cls = []
                for box, score, label in boxes:
                    x1, y1, x2, y2 = [float(v) for v in box]
                    xywh.append([(x1 + x2) * 0.5, (y1 + y2) * 0.5, max(1.0, x2 - x1), max(1.0, y2 - y1)])
                    conf.append(float(score))
                    cls.append(0.0 if label == "person" else 1.0)
                self.xywh = np.asarray(xywh, dtype=np.float32)
                self.conf = np.asarray(conf, dtype=np.float32)
                self.cls = np.asarray(cls, dtype=np.float32)

        tracks = tracker.update(_TrackResults(person_boxes), frame)
        if tracks is None or len(tracks) == 0:
            return []

        cache_entry = self._get_cache_entry(session_id)
        preferred_track_id = cache_entry.get("track_id") if cache_entry else None
        ordered_tracks = list(tracks)
        if preferred_track_id is not None:
            ordered_tracks.sort(key=lambda item: 0 if int(item[4]) == int(preferred_track_id) else 1)

        people: list[dict[str, Any]] = []
        h, w = frame.shape[:2]
        for selected in ordered_tracks:
            x1, y1, x2, y2, track_id, *_rest = [float(v) for v in selected]
            x1i = max(0, min(w - 1, int(round(x1))))
            y1i = max(0, min(h - 1, int(round(y1))))
            x2i = max(0, min(w, int(round(x2))))
            y2i = max(0, min(h, int(round(y2))))
            if x2i <= x1i or y2i <= y1i:
                continue
            crop = frame[y1i:y2i, x1i:x2i]
            if crop.size == 0:
                continue
            people.append(
                {
                    "track_id": int(track_id),
                    "bbox": [x1i, y1i, x2i, y2i],
                    "crop": crop,
                }
            )
        return people

    def _pick_target_candidate(
        self,
        *,
        tracked_persons: list[dict[str, Any]],
        session_id: str,
        now_ms: int,
        force_full_match: bool,
    ) -> tuple[dict[str, Any] | None, Any | None, dict[str, Any] | None]:
        cached = self._get_cache_entry(session_id)
        if cached and cached.get("track_id") is not None:
            preferred = next((item for item in tracked_persons if int(item["track_id"]) == int(cached["track_id"])), None)
            if preferred is not None:
                preferred_features = self._target_user_service.extract_features_from_frame(
                    preferred["crop"],
                    include_face=force_full_match,
                    include_body=True,
                )
                preferred_match = self._resolve_target_match(
                    face_embedding=preferred_features["face_embedding"],
                    body_profile=preferred_features["body_profile"],
                    session_id=session_id,
                    now_ms=now_ms,
                    track_id=preferred["track_id"],
                )
                if preferred_match.matched:
                    return preferred, preferred_match, preferred_features

        best_person = None
        best_features = None
        best_match = None
        best_score = -1.0
        for person in tracked_persons:
            features = self._target_user_service.extract_features_from_frame(
                person["crop"],
                include_face=force_full_match,
                include_body=True,
            )
            candidate = self._target_user_service.match_target(
                face_embedding=features["face_embedding"],
                body_profile=features["body_profile"],
            )
            score = float(candidate.fused_score)
            if score > best_score:
                best_score = score
                best_person = person
                best_features = features
                best_match = candidate

        if best_person is None or best_features is None:
            return None, None, None

        final_match = self._resolve_target_match(
            face_embedding=best_features["face_embedding"],
            body_profile=best_features["body_profile"],
            session_id=session_id,
            now_ms=now_ms,
            track_id=best_person["track_id"],
        )
        return best_person, final_match, best_features

    def _get_or_create_tracker(self, session_id: str) -> BYTETracker:
        with self._lock:
            tracker = self._session_trackers.get(session_id)
            if tracker is None:
                tracker = BYTETracker(self._tracker_args, frame_rate=30)
                self._session_trackers[session_id] = tracker
            return tracker

    def _get_cache_entry(self, session_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._session_match_cache.get(session_id)

    def _set_cache_entry(self, session_id: str, payload: dict[str, Any]) -> None:
        with self._lock:
            self._session_match_cache[session_id] = payload

    def _clear_cache_entry(self, session_id: str) -> None:
        with self._lock:
            self._session_match_cache.pop(session_id, None)

    def _crop_target_roi(self, frame: np.ndarray, bbox: list[int]) -> tuple[np.ndarray | None, list[int] | None]:
        if frame is None or frame.size == 0:
            return None, None
        x1, y1, x2, y2 = [int(v) for v in bbox]
        h, w = frame.shape[:2]
        box_w = max(1, x2 - x1)
        box_h = max(1, y2 - y1)
        pad_x = int(round(box_w * self._roi_padding_ratio))
        pad_y = int(round(box_h * self._roi_padding_ratio))
        rx1 = max(0, x1 - pad_x)
        ry1 = max(0, y1 - pad_y)
        rx2 = min(w, x2 + pad_x)
        ry2 = min(h, y2 + pad_y)
        if rx2 <= rx1 or ry2 <= ry1:
            return None, None
        crop = frame[ry1:ry2, rx1:rx2]
        if crop.size == 0:
            return None, None
        return crop, [rx1, ry1, rx2, ry2]

    @staticmethod
    def _offset_detections(fall_result: dict[str, Any], roi_bbox: list[int] | None) -> None:
        if roi_bbox is None:
            return
        detections = fall_result.get("detections") or []
        ox, oy = roi_bbox[0], roi_bbox[1]
        for item in detections:
            box = item.get("bbox")
            if not box or len(box) < 4:
                continue
            item["bbox"] = [
                round(float(box[0]) + ox, 1),
                round(float(box[1]) + oy, 1),
                round(float(box[2]) + ox, 1),
                round(float(box[3]) + oy, 1),
            ]
