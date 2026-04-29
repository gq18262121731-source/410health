from __future__ import annotations

import os
import time
from pathlib import Path

import websocket


ROOT = Path(__file__).resolve().parents[1]


def load_env() -> dict[str, str]:
    values = dict(os.environ)
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            values.setdefault(key.strip(), value.strip())
    return values


def main() -> int:
    env = load_env()
    seconds = float(env.get("CAMERA_WS_PROBE_SECONDS", "10"))
    url = env.get("CAMERA_WS_PROBE_URL", "ws://127.0.0.1:8000/ws/camera")

    print(f"Connecting {url}")
    print(f"Probe duration: {seconds:.1f}s")
    ws = websocket.create_connection(url, timeout=8)
    ws.settimeout(3)
    started = time.perf_counter()
    frames = 0
    bytes_total = 0
    first_frame_at: float | None = None
    errors: list[str] = []

    try:
        while time.perf_counter() - started < seconds:
            try:
                message = ws.recv()
            except Exception as exc:  # noqa: BLE001 - summarize probe behavior.
                errors.append(f"{exc.__class__.__name__}: {exc}")
                break

            if isinstance(message, str):
                print(f"text: {message[:160]}")
                continue

            if first_frame_at is None:
                first_frame_at = time.perf_counter()
            frames += 1
            bytes_total += len(message)
    finally:
        ws.close()

    elapsed = max(time.perf_counter() - started, 0.001)
    active_elapsed = max((time.perf_counter() - first_frame_at) if first_frame_at else elapsed, 0.001)
    fps = frames / active_elapsed
    avg_kb = (bytes_total / frames / 1024) if frames else 0
    mbps = (bytes_total * 8 / elapsed / 1_000_000) if elapsed else 0

    print(f"frames={frames}")
    print(f"fps={fps:.2f}")
    print(f"avg_frame={avg_kb:.1f} KB")
    print(f"throughput={mbps:.2f} Mbps")
    if errors:
        print(f"error={errors[-1]}")

    if frames == 0:
        print("Diagnosis: backend did not deliver frames. Check camera reachability and backend logs.")
    elif fps < 20:
        print("Diagnosis: backend WebSocket delivery is below 24 fps.")
    else:
        print("Diagnosis: backend WebSocket delivery is near 24 fps.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
