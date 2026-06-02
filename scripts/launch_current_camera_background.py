from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(r"C:\Users\13010\anaconda3\envs\torchgpu\python.exe")
OUT_LOG = ROOT / "logs" / "runtime_debug" / "current_camera.out.log"
ERR_LOG = ROOT / "logs" / "runtime_debug" / "current_camera.err.log"


def main() -> int:
    OUT_LOG.parent.mkdir(parents=True, exist_ok=True)
    out = OUT_LOG.open("w", encoding="utf-8")
    err = ERR_LOG.open("w", encoding="utf-8")
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    if sys.platform == "win32":
        creationflags |= subprocess.DETACHED_PROCESS
    process = subprocess.Popen(
        [str(PYTHON), "scripts/start_current_camera.py"],
        cwd=str(ROOT),
        stdout=out,
        stderr=err,
        stdin=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creationflags,
    )
    print(process.pid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
