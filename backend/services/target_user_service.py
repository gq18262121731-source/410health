from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

import cv2
import numpy as np
from pydantic import ValidationError
from ultralytics import YOLO

from backend.models.target_user_model import TargetUserCreateResponse, TargetUserDeleteResponse, TargetUserMatchResult, TargetUserRecord


class TargetUserService:
    """Local target-user registry with lightweight face/body feature extraction.

    Phase-1 MVP goals:
    - register a target user from a few uploaded photos
    - derive simple face/body signatures
    - provide target-only matching for online filtering
    """

    def __init__(self, *, data_root: Path, model_root: Path) -> None:
        self._root = data_root / "target_users"
        self._root.mkdir(parents=True, exist_ok=True)
        self._assets = data_root / "target_user_assets"
        self._assets.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._records: dict[str, TargetUserRecord] = {}
        self._feature_cache: dict[str, dict[str, Any]] = {}
        self._haar_face_detector = cv2.CascadeClassifier(
            str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
        )
        self._yunet_path = self._assets / "face_detection_yunet.onnx"
        self._sface_path = self._assets / "face_recognition_sface.onnx"
        self._face_detector_yn = None
        self._face_recognizer_sf = None
        self._init_face_models()
        self._person_model = YOLO(str(model_root / "yolo11n.pt"))
        self._fallback_person_model = YOLO(str(model_root / "weights" / "yolo_fall_detector_v1.pt"))
        self._load_records()

    def list_users(self) -> list[TargetUserRecord]:
        with self._lock:
            return sorted(self._records.values(), key=lambda item: item.created_at)

    def get_user(self, user_id: str) -> TargetUserRecord | None:
        with self._lock:
            return self._records.get(user_id)

    def create_user(
        self,
        *,
        display_name: str,
        group: str,
        note: str,
        image_blobs: list[bytes],
    ) -> TargetUserCreateResponse:
        if not image_blobs:
            raise ValueError("TARGET_USER_IMAGES_REQUIRED")

        normalized_name = display_name.strip() or ""
        normalized_group = group.strip() or "default"
        if not normalized_name:
            raise ValueError("TARGET_USER_DISPLAY_NAME_REQUIRED")
        with self._lock:
            duplicate = next(
                (
                    item for item in self._records.values()
                    if item.display_name.strip().lower() == normalized_name.lower()
                    and item.group.strip().lower() == normalized_group.lower()
                    and item.enabled
                ),
                None,
            )
        if duplicate is not None:
            raise ValueError("TARGET_USER_ALREADY_EXISTS")

        user_id = uuid4().hex[:12]
        user_dir = self._root / user_id
        photos_dir = user_dir / "photos"
        photos_dir.mkdir(parents=True, exist_ok=True)

        warnings: list[str] = []
        face_embeddings: list[list[float]] = []
        body_profiles: list[dict[str, float]] = []

        for index, blob in enumerate(image_blobs, start=1):
            photo_path = photos_dir / f"photo_{index:02d}.jpg"
            photo_path.write_bytes(blob)
            features = self._extract_features(blob)
            if features["warnings"]:
                warnings.extend(features["warnings"])
            if features["face_embedding"] is not None:
                face_embeddings.append(features["face_embedding"])
            if features["body_profile"] is not None:
                body_profiles.append(features["body_profile"])

        if not face_embeddings:
            warnings.append("NO_RELIABLE_FACE_FOUND")
        if not body_profiles:
            warnings.append("NO_RELIABLE_BODY_FOUND")
        if not face_embeddings and not body_profiles:
            self._purge_directory(user_dir)
            raise ValueError("TARGET_USER_NO_VALID_FEATURES")

        now = datetime.now(timezone.utc)
        record = TargetUserRecord(
            id=user_id,
            display_name=normalized_name or user_id,
            group=normalized_group,
            note=note.strip(),
            enabled=True,
            created_at=now,
            updated_at=now,
            photo_count=len(image_blobs),
            face_embedding_count=len(face_embeddings),
            body_profile_count=len(body_profiles),
        )

        payload = {
            "record": record.model_dump(mode="json"),
            "face_embeddings": face_embeddings,
            "body_profiles": body_profiles,
        }
        (user_dir / "embeddings.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._feature_cache[record.id] = payload

        with self._lock:
            self._records[record.id] = record
            self._save_record(record)

        return TargetUserCreateResponse(user=record, warnings=sorted(set(warnings)))

    def face_model_status(self) -> dict[str, Any]:
        return {
            "yunet_path": str(self._yunet_path),
            "sface_path": str(self._sface_path),
            "yunet_available": self._face_detector_yn is not None,
            "sface_available": self._face_recognizer_sf is not None,
            "fallback_haar_available": not self._haar_face_detector.empty(),
        }

    def debug_extract_features(self, image_bytes: bytes) -> dict[str, Any]:
        np_buffer = np.frombuffer(image_bytes, dtype=np.uint8)
        frame = cv2.imdecode(np_buffer, cv2.IMREAD_COLOR)
        if frame is None:
            return {"ok": False, "error": "INVALID_IMAGE"}
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        haar_faces = self._haar_face_detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
        yunet_face = self._detect_with_yunet(frame)
        body_profile = self._extract_body_profile(frame)
        return {
            "ok": True,
            "shape": list(frame.shape),
            "haar_face_count": len(haar_faces),
            "yunet_face_found": yunet_face is not None,
            "body_profile_found": body_profile is not None,
            "face_embedding_found": self._extract_face_embedding(frame) is not None,
        }

    def delete_user(self, user_id: str) -> TargetUserDeleteResponse:
        user_dir = self._root / user_id
        with self._lock:
            if user_id not in self._records:
                raise ValueError("TARGET_USER_NOT_FOUND")
            self._records.pop(user_id, None)
            self._feature_cache.pop(user_id, None)
        self._purge_directory(user_dir)
        return TargetUserDeleteResponse(id=user_id)

    def match_target(
        self,
        *,
        face_embedding: list[float] | None,
        body_profile: dict[str, float] | None,
    ) -> TargetUserMatchResult:
        best = TargetUserMatchResult()
        if not self._records:
            return best

        for record in self.list_users():
            payload = self._feature_cache.get(record.id)
            if payload is None:
                features_path = self._root / record.id / "embeddings.json"
                if not features_path.exists():
                    continue
                payload = json.loads(features_path.read_text(encoding="utf-8"))
                self._feature_cache[record.id] = payload
            face_gallery = payload.get("face_embeddings") or []
            body_gallery = payload.get("body_profiles") or []

            face_score = self._best_face_similarity(face_embedding, face_gallery)
            body_score = self._best_body_similarity(body_profile, body_gallery)
            if face_embedding is not None and body_profile is not None:
                fused = 0.75 * face_score + 0.25 * body_score
            elif face_embedding is not None:
                fused = face_score
            else:
                fused = body_score
            decision = "target" if fused >= 0.62 and (face_score >= 0.62 or body_score >= 0.72) else "non_target"
            if fused > best.fused_score:
                best = TargetUserMatchResult(
                    matched=decision == "target",
                    user_id=record.id if decision == "target" else None,
                    display_name=record.display_name if decision == "target" else None,
                    face_score=round(face_score, 4),
                    body_score=round(body_score, 4),
                    fused_score=round(fused, 4),
                    decision=decision,
                )
        if best.fused_score <= 0:
            best.decision = "unknown"
        return best

    def match_target_from_image(self, image_bytes: bytes) -> TargetUserMatchResult:
        features = self._extract_features(image_bytes)
        return self.match_target(
            face_embedding=features["face_embedding"],
            body_profile=features["body_profile"],
        )

    def extract_features_from_frame(
        self,
        frame: np.ndarray,
        *,
        include_face: bool = True,
        include_body: bool = True,
    ) -> dict[str, Any]:
        if frame is None or frame.size == 0:
            return {"warnings": ["INVALID_IMAGE"], "face_embedding": None, "body_profile": None}

        warnings: list[str] = []
        face_embedding = self._extract_face_embedding(frame) if include_face else None
        if include_face and face_embedding is None:
            warnings.append("FACE_NOT_FOUND")

        body_profile = self._extract_body_profile(frame) if include_body else None
        if include_body and body_profile is None:
            warnings.append("BODY_NOT_FOUND")

        return {
            "warnings": warnings,
            "face_embedding": face_embedding,
            "body_profile": body_profile,
        }

    def _extract_features(
        self,
        image_bytes: bytes,
        *,
        include_face: bool = True,
        include_body: bool = True,
    ) -> dict[str, Any]:
        np_buffer = np.frombuffer(image_bytes, dtype=np.uint8)
        frame = cv2.imdecode(np_buffer, cv2.IMREAD_COLOR)
        return self.extract_features_from_frame(frame, include_face=include_face, include_body=include_body)

    def _extract_face_embedding(self, frame: np.ndarray) -> list[float] | None:
        if self._face_detector_yn is not None and self._face_recognizer_sf is not None:
            face = self._detect_with_yunet(frame)
            if face is not None:
                return self._embed_with_sface(frame, face)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._haar_face_detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
        if len(faces) == 0:
            return None
        x, y, w, h = max(faces, key=lambda item: item[2] * item[3])
        crop = gray[max(0, y):max(0, y + h), max(0, x):max(0, x + w)]
        if crop.size == 0:
            return None
        resized = cv2.resize(crop, (32, 32), interpolation=cv2.INTER_AREA)
        vector = resized.astype(np.float32).reshape(-1)
        norm = float(np.linalg.norm(vector))
        if norm <= 1e-6:
            return None
        return (vector / norm).tolist()

    def _init_face_models(self) -> None:
        if self._yunet_path.is_file():
            try:
                self._face_detector_yn = cv2.FaceDetectorYN.create(
                    str(self._yunet_path),
                    "",
                    (320, 320),
                )
            except Exception:
                self._face_detector_yn = None
        if self._sface_path.is_file():
            try:
                self._face_recognizer_sf = cv2.FaceRecognizerSF.create(
                    str(self._sface_path),
                    "",
                )
            except Exception:
                self._face_recognizer_sf = None

    def _detect_with_yunet(self, frame: np.ndarray) -> np.ndarray | None:
        if self._face_detector_yn is None:
            return None
        height, width = frame.shape[:2]
        self._face_detector_yn.setInputSize((width, height))
        _retval, faces = self._face_detector_yn.detect(frame)
        if faces is None or len(faces) == 0:
            return None
        faces = np.asarray(faces, dtype=np.float32)
        return max(faces, key=lambda item: float(item[2] * item[3]))

    def _embed_with_sface(self, frame: np.ndarray, face: np.ndarray) -> list[float] | None:
        if self._face_recognizer_sf is None:
            return None
        try:
            aligned = self._face_recognizer_sf.alignCrop(frame, face)
            embedding = self._face_recognizer_sf.feature(aligned)
        except Exception:
            return None
        if embedding is None:
            return None
        vector = np.asarray(embedding, dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(vector))
        if norm <= 1e-6:
            return None
        return (vector / norm).tolist()

    def _extract_body_profile(self, frame: np.ndarray) -> dict[str, float] | None:
        person_boxes = self._collect_person_boxes(frame, self._person_model, allowed_labels={"person"}, conf=0.2)
        if not person_boxes:
            person_boxes = self._collect_person_boxes(
                frame,
                self._fallback_person_model,
                allowed_labels={"person", "fall", "fallen", "sitting", "lying", "bending"},
                conf=0.2,
            )
        if not person_boxes:
            return None
        box, conf, label = max(person_boxes, key=lambda item: (item[1], (item[0][2] - item[0][0]) * (item[0][3] - item[0][1])))
        x1, y1, x2, y2 = [float(value) for value in box]
        width = max(1.0, x2 - x1)
        height = max(1.0, y2 - y1)
        frame_h, frame_w = frame.shape[:2]
        area_ratio = float((width * height) / max(1.0, frame_h * frame_w))
        aspect = float(width / height)
        center_x = float(((x1 + x2) * 0.5) / max(1.0, frame_w))
        center_y = float(((y1 + y2) * 0.5) / max(1.0, frame_h))
        return {
            "aspect": round(aspect, 6),
            "area_ratio": round(area_ratio, 6),
            "center_x": round(center_x, 6),
            "center_y": round(center_y, 6),
            "confidence": round(conf, 6),
            "label_code": float({
                "person": 0,
                "fall": 1,
                "fallen": 2,
                "sitting": 3,
                "lying": 4,
                "bending": 5,
            }.get(label, 0)),
        }

    @staticmethod
    def _purge_directory(path: Path) -> None:
        if not path.exists():
            return
        for item in sorted(path.rglob("*"), reverse=True):
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                item.rmdir()
        if path.exists():
            path.rmdir()

    @staticmethod
    def _collect_person_boxes(
        frame: np.ndarray,
        model: YOLO,
        *,
        allowed_labels: set[str],
        conf: float,
    ) -> list[tuple[np.ndarray, float, str]]:
        result = model.predict(frame, verbose=False, imgsz=640, conf=conf, iou=0.45)[0]
        if result.boxes is None or len(result.boxes) == 0:
            return []
        names = result.names if hasattr(result, "names") else model.names
        boxes = result.boxes.xyxy.detach().cpu().numpy()
        confs = result.boxes.conf.detach().cpu().numpy()
        classes = result.boxes.cls.detach().cpu().numpy().astype(int)
        person_boxes: list[tuple[np.ndarray, float, str]] = []
        for box, score, cls_idx in zip(boxes, confs, classes):
            label = str(names.get(int(cls_idx), cls_idx)).lower()
            if label not in allowed_labels:
                continue
            person_boxes.append((box, float(score), label))
        return person_boxes

    @staticmethod
    def _best_face_similarity(face_embedding: list[float] | None, gallery: list[list[float]]) -> float:
        if face_embedding is None or not gallery:
            return 0.0
        query = np.asarray(face_embedding, dtype=np.float32)
        best = 0.0
        for item in gallery:
            target = np.asarray(item, dtype=np.float32)
            if query.shape != target.shape:
                continue
            score = float(np.dot(query, target) / max(1e-6, float(np.linalg.norm(query) * np.linalg.norm(target))))
            best = max(best, score)
        return max(0.0, min(1.0, (best + 1.0) * 0.5))

    @staticmethod
    def _best_body_similarity(body_profile: dict[str, float] | None, gallery: list[dict[str, float]]) -> float:
        if body_profile is None or not gallery:
            return 0.0
        best = 0.0
        keys = ("aspect", "area_ratio", "center_x", "center_y", "label_code")
        for item in gallery:
            diffs = []
            for key in keys:
                diffs.append(abs(float(body_profile.get(key, 0.0)) - float(item.get(key, 0.0))))
            avg_diff = sum(diffs) / len(diffs)
            score = max(0.0, 1.0 - avg_diff)
            best = max(best, score)
        return best

    def _load_records(self) -> None:
        for meta_path in self._root.glob("*/meta.json"):
            try:
                payload = json.loads(meta_path.read_text(encoding="utf-8"))
                record = TargetUserRecord.model_validate(payload)
            except (json.JSONDecodeError, ValidationError):
                continue
            if record.face_embedding_count <= 0 and record.body_profile_count <= 0:
                self._purge_directory(meta_path.parent)
                continue
            self._records[record.id] = record
            features_path = meta_path.parent / "embeddings.json"
            if features_path.exists():
                try:
                    self._feature_cache[record.id] = json.loads(features_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    self._feature_cache.pop(record.id, None)

    def _save_record(self, record: TargetUserRecord) -> None:
        user_dir = self._root / record.id
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "meta.json").write_text(
            json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
