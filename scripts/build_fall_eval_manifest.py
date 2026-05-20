from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".m4v"}
LABEL_DIRS = {"fall", "normal", "sitting", "lying", "bending"}
ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a fall evaluation manifest from labeled video folders.")
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT / "data" / "fall_eval",
        help="Evaluation root containing videos/<label> folders.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=ROOT / "data" / "fall_eval" / "fall_eval_manifest.json",
    )
    parser.add_argument(
        "--review-frames",
        type=Path,
        default=ROOT / "data" / "fall_media_demo" / "review_frames",
        help="Optional review-frame root to index as needs_label samples.",
    )
    return parser.parse_args()


def load_sidecar_events(video: Path, label: str) -> list[dict[str, Any]]:
    sidecar = video.with_suffix(video.suffix + ".json")
    if not sidecar.exists():
        return [{"label": "fall", "start_s": 0.0, "end_s": 999999.0}] if label == "fall" else []
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    events = payload.get("events") if isinstance(payload, dict) else payload
    if not isinstance(events, list):
        return []
    normalized: list[dict[str, Any]] = []
    for event in events:
        event_label = str(event.get("label") or event.get("status") or label).lower()
        if event_label != "fall":
            continue
        start = float(event.get("start_s", event.get("start_sec", 0.0)))
        end = float(event.get("end_s", event.get("end_sec", start)))
        if end > start:
            normalized.append({"label": "fall", "start_s": start, "end_s": end})
    return normalized


def main() -> int:
    args = parse_args()
    videos_root = args.root / "videos"
    items: list[dict[str, Any]] = []
    for label in sorted(LABEL_DIRS):
        label_dir = videos_root / label
        if not label_dir.exists():
            continue
        for video in sorted(label_dir.rglob("*")):
            if video.suffix.lower() not in VIDEO_SUFFIXES:
                continue
            items.append(
                {
                    "name": f"{label}-{video.stem}",
                    "label": label,
                    "video": str(video.resolve()),
                    "events": load_sidecar_events(video, label),
                }
            )

    review_samples: list[dict[str, Any]] = []
    if args.review_frames.exists():
        for image in sorted(args.review_frames.rglob("*.jpg")):
            review_samples.append(
                {
                    "path": str(image.resolve()),
                    "label": "needs_label",
                    "source": "review_frames",
                }
            )

    payload = {
        "description": "Fall evaluation manifest. Put videos under videos/fall|normal|sitting|lying|bending.",
        "items": items,
        "review_frames": review_samples,
        "label_notes": {
            "fall": "Use sidecar <video>.mp4.json with events when only part of the video contains a fall.",
            "normal/sitting/lying/bending": "Non-fall classes should normally have an empty events list.",
            "review_frames": "Manually label these hard frames before using them for training.",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[manifest] videos={len(items)} review_frames={len(review_samples)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
