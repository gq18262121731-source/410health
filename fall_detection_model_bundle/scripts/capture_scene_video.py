from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import cv2


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "data_private" / "camera_scene" / "raw_videos"


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture a local camera or stream into the private scene dataset folder.")
    parser.add_argument("--source", default="0", help="Camera index or stream/video source.")
    parser.add_argument("--output-dir", default=str(DEFAULT_DIR))
    parser.add_argument("--name", default=None, help="Optional output filename stem.")
    parser.add_argument("--fps", type=float, default=20.0)
    args = parser.parse_args()

    source = int(args.source) if args.source.isdigit() else args.source
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.name or datetime.now().strftime("scene_%Y%m%d_%H%M%S")
    out_path = out_dir / f"{stem}.mp4"

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open source: {args.source}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
    fps = cap.get(cv2.CAP_PROP_FPS) or args.fps
    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))

    print(f"[recording] {out_path}")
    print("Press 'q' or ESC to stop.")
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        writer.write(frame)
        cv2.imshow("Capture Scene Video", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == 27 or key == ord("q"):
            break

    cap.release()
    writer.release()
    cv2.destroyAllWindows()
    print(f"[saved] {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
