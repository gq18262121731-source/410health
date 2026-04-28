from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "realtime_fall_monitor.py"


def main() -> int:
    cmd = [
        sys.executable,
        str(SCRIPT),
        "--pose-model",
        str(ROOT / "weights" / "yolo11n-pose.pt"),
        "--gru-weights",
        str(ROOT / "weights" / "gru_pose_fall_v1.pt"),
        "--hybrid-weights",
        str(ROOT / "weights" / "hybrid_tcn_transformer_v2_matchgru.pt"),
        "--semantic-weights",
        str(ROOT / "weights" / "semantic_mix_falldb_v1.pt"),
        "--posture-model",
        str(ROOT / "weights" / "posture_person_binary_best.pt"),
        *sys.argv[1:],
    ]
    completed = subprocess.run(cmd)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
