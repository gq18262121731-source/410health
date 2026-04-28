from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import torch
from ultralytics import YOLO

from temporal_semantic_utils import semantic_features_from_pose_sequence
from train_temporal_gru import GRUFallNet, normalize_pose
from train_temporal_semantic_mix import SemanticTemporalNet
from train_temporal_tcn_transformer import HybridTCNTransformer


@dataclass
class Track:
    track_id: int
    box_history: deque = field(default_factory=lambda: deque(maxlen=24))
    kp_history: deque = field(default_factory=lambda: deque(maxlen=24))
    posture_history: deque = field(default_factory=lambda: deque(maxlen=24))
    last_box: np.ndarray | None = None
    missed: int = 0
    alert_frames: int = 0
    score: float = 0.0
    gru_score: float = 0.0
    hybrid_score: float = 0.0
    semantic_score: float = 0.0
    posture_score: float = 0.0
    posture_label: str = "unknown"


def iou_xyxy(a: np.ndarray, b: np.ndarray) -> float:
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def extract_people(result) -> list[tuple[np.ndarray, np.ndarray]]:
    people = []
    if result.boxes is None or result.keypoints is None or len(result.boxes) == 0:
        return people
    boxes = result.boxes.xyxy.detach().cpu().numpy()
    conf = result.boxes.conf.detach().cpu().numpy()
    kps = result.keypoints.data.detach().cpu().numpy()
    for box, score, kp in zip(boxes, conf, kps):
        if score < 0.2:
            continue
        people.append((box.astype(np.float32), kp.astype(np.float32)))
    return people


def update_tracks(tracks: dict[int, Track], detections: list[tuple[np.ndarray, np.ndarray]], next_id: int) -> int:
    unmatched = set(range(len(detections)))
    for track in tracks.values():
        best_idx = None
        best_iou = 0.0
        for idx in list(unmatched):
            box, _ = detections[idx]
            if track.last_box is None:
                continue
            score = iou_xyxy(track.last_box, box)
            if score > best_iou:
                best_iou = score
                best_idx = idx
        if best_idx is not None and best_iou >= 0.2:
            box, kp = detections[best_idx]
            track.last_box = box
            track.box_history.append(box)
            track.kp_history.append(kp)
            track.missed = 0
            unmatched.remove(best_idx)
        else:
            track.missed += 1

    stale = [tid for tid, track in tracks.items() if track.missed > 15]
    for tid in stale:
        tracks.pop(tid, None)

    for idx in unmatched:
        box, kp = detections[idx]
        track = Track(track_id=next_id)
        track.last_box = box
        track.box_history.append(box)
        track.kp_history.append(kp)
        track.posture_history.append(0.0)
        tracks[next_id] = track
        next_id += 1
    return next_id


def build_model(weights_path: Path, device: torch.device) -> tuple[torch.nn.Module, dict]:
    checkpoint = torch.load(weights_path, map_location=device)
    model_type = checkpoint.get("model_type", "gru")
    if model_type == "hybrid_tcn_transformer":
        model = HybridTCNTransformer(input_dim=checkpoint["input_dim"]).to(device)
    elif model_type == "semantic_temporal_mix":
        model = SemanticTemporalNet(input_dim=checkpoint["input_dim"]).to(device)
    else:
        model = GRUFallNet(input_dim=checkpoint["input_dim"]).to(device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    return model, checkpoint


def score_track_gru(track: Track, model: torch.nn.Module, device: torch.device) -> float:
    if len(track.kp_history) < track.kp_history.maxlen:
        return 0.0
    kps = np.asarray(track.kp_history, dtype=np.float32)
    boxes = np.asarray(track.box_history, dtype=np.float32)
    features = normalize_pose(kps, boxes)
    x = torch.from_numpy(features).unsqueeze(0).to(device)
    with torch.no_grad():
        prob = torch.sigmoid(model(x)).item()
    return float(prob)


def score_track_hybrid(track: Track, model: torch.nn.Module, device: torch.device) -> float:
    if len(track.kp_history) < track.kp_history.maxlen or len(track.posture_history) < track.posture_history.maxlen:
        return 0.0
    kps = np.asarray(track.kp_history, dtype=np.float32)
    boxes = np.asarray(track.box_history, dtype=np.float32)
    base = normalize_pose(kps, boxes)
    posture = np.asarray(track.posture_history, dtype=np.float32)
    delta = np.concatenate([[0.0], np.diff(posture)]).astype(np.float32)
    smooth = np.asarray([posture[max(0, i - 2) : i + 1].mean() for i in range(len(posture))], dtype=np.float32)
    extra = np.stack([posture, delta, smooth], axis=1)
    features = np.concatenate([base, extra], axis=1)
    x = torch.from_numpy(features).unsqueeze(0).to(device)
    with torch.no_grad():
        prob = torch.sigmoid(model(x)).item()
    return float(prob)


def score_track_semantic(track: Track, model: torch.nn.Module, device: torch.device) -> float:
    if len(track.kp_history) < track.kp_history.maxlen:
        return 0.0
    kps = np.asarray(track.kp_history, dtype=np.float32)
    boxes = np.asarray(track.box_history, dtype=np.float32)
    features = semantic_features_from_pose_sequence(kps, boxes)
    x = torch.from_numpy(features).unsqueeze(0).to(device)
    with torch.no_grad():
        prob = torch.sigmoid(model(x)).item()
    return float(prob)


def classify_posture(crop: np.ndarray, posture_model: YOLO | None) -> tuple[str, float]:
    if posture_model is None or crop.size == 0:
        return "unknown", 0.0
    result = posture_model.predict(crop, verbose=False, imgsz=320)[0]
    probs = result.probs
    if probs is None:
        return "unknown", 0.0
    names = posture_model.names
    top1 = int(probs.top1)
    prob_values = probs.data.detach().cpu().numpy()
    label = names[top1]
    label_set = set(names.values())
    if label_set == {"risk", "safe"}:
        risk_idx = next(idx for idx, name in names.items() if name == "risk")
        return label, float(prob_values[risk_idx])

    mapping = {name: idx for idx, name in names.items()}
    # Auxiliary fall-risk score from static posture
    score = 0.0
    if "lying" in mapping:
        score += float(prob_values[mapping["lying"]]) * 0.9
    if "crawling" in mapping:
        score += float(prob_values[mapping["crawling"]]) * 0.6
    if "bending" in mapping:
        score += float(prob_values[mapping["bending"]]) * 0.25
    if "standing" in mapping:
        score -= float(prob_values[mapping["standing"]]) * 0.35
    if "sitting" in mapping:
        score -= float(prob_values[mapping["sitting"]]) * 0.15
    return label, float(max(0.0, min(1.0, score)))


def names_inv(target: str, names: dict[int, str]) -> int:
    for idx, name in names.items():
        if name == target:
            return idx
    return -1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real-time fall monitoring from webcam or video.")
    parser.add_argument("--source", default="0", help="Webcam index or a video path.")
    parser.add_argument("--pose-model", default="yolo11n-pose.pt")
    parser.add_argument("--gru-weights", default=str(Path(__file__).resolve().parents[1] / "weights" / "gru_pose_fall_v1.pt"))
    parser.add_argument("--hybrid-weights", default=str(Path(__file__).resolve().parents[1] / "weights" / "hybrid_tcn_transformer_v2_matchgru.pt"))
    parser.add_argument("--semantic-weights", default=str(Path(__file__).resolve().parents[1] / "weights" / "semantic_mix_falldb_v1.pt"))
    parser.add_argument("--posture-model", default=str(Path(__file__).resolve().parents[1] / "runs" / "yolo_posture_person_binary_cls_v1" / "weights" / "best.pt"))
    parser.add_argument("--window-size", type=int, default=24)
    parser.add_argument("--threshold", type=float, default=0.45)
    parser.add_argument("--alert-hold", type=int, default=3)
    parser.add_argument("--gru-weight", type=float, default=0.3)
    parser.add_argument("--hybrid-weight", type=float, default=0.45)
    parser.add_argument("--semantic-weight", type=float, default=0.0)
    parser.add_argument("--posture-weight", type=float, default=0.25)
    parser.add_argument("--save-path", default=None)
    parser.add_argument("--no-display", action="store_true")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pose_model = YOLO(args.pose_model)
    gru_model, _ = build_model(Path(args.gru_weights), device)
    hybrid_model = None
    if args.hybrid_weights and Path(args.hybrid_weights).exists():
        hybrid_model, _ = build_model(Path(args.hybrid_weights), device)
    semantic_model = None
    if args.semantic_weights and Path(args.semantic_weights).exists():
        semantic_model, _ = build_model(Path(args.semantic_weights), device)
    posture_model = YOLO(args.posture_model) if args.posture_model and Path(args.posture_model).exists() else None

    source = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open source: {args.source}")

    writer = None
    if args.save_path:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 20.0
        writer = cv2.VideoWriter(args.save_path, fourcc, fps, (width, height))

    tracks: dict[int, Track] = {}
    next_id = 1

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        result = pose_model.predict(frame, verbose=False, imgsz=640, conf=0.2, max_det=8)[0]
        detections = extract_people(result)
        next_id = update_tracks(tracks, detections, next_id)

        for track in tracks.values():
            if track.last_box is None:
                continue
            x1, y1, x2, y2 = track.last_box.astype(int)
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(frame.shape[1], x2)
            y2 = min(frame.shape[0], y2)
            crop = frame[y1:y2, x1:x2]
            posture_label, posture_score = classify_posture(crop, posture_model)
            track.posture_label = posture_label
            track.posture_score = posture_score
            track.posture_history.append(posture_score)
            track.gru_score = score_track_gru(track, gru_model, device)
            if hybrid_model is not None:
                track.hybrid_score = score_track_hybrid(track, hybrid_model, device)
            if semantic_model is not None:
                track.semantic_score = score_track_semantic(track, semantic_model, device)
            combined = (
                track.gru_score * args.gru_weight
                + track.hybrid_score * args.hybrid_weight
                + track.semantic_score * args.semantic_weight
                + posture_score * args.posture_weight
            )
            track.score = float(max(0.0, min(1.0, combined)))

            if track.score >= args.threshold:
                track.alert_frames += 1
            else:
                track.alert_frames = max(0, track.alert_frames - 1)

            box = track.last_box.astype(int)
            is_alert = track.alert_frames >= args.alert_hold
            color = (0, 0, 255) if is_alert else (0, 255, 0)
            label = f"id={track.track_id} fall={track.score:.2f} g={track.gru_score:.2f} h={track.hybrid_score:.2f} s={track.semantic_score:.2f} pose={track.posture_label}"
            if is_alert:
                label += " ALERT"
            cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), color, 2)
            cv2.putText(frame, label, (box[0], max(20, box[1] - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        if writer is not None:
            writer.write(frame)

        if not args.no_display:
            cv2.imshow("Fall Monitor", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == 27 or key == ord("q"):
                break

    cap.release()
    if writer is not None:
        writer.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
