from __future__ import annotations

import argparse
import json
import math
import os
import signal
import struct
import time
from pathlib import Path
from typing import Any

import websocket


DEFAULT_WS_URLS = (
    "ws://127.0.0.1:8010/ws/camera/audio/listen",
    "ws://127.0.0.1:8000/ws/camera/audio/listen",
)


def pcm16_stats(chunk: bytes) -> tuple[int, float]:
    limit = len(chunk) - (len(chunk) % 2)
    if limit <= 0:
        return 0, 0.0

    peak = 0
    square_sum = 0
    count = limit // 2
    for (sample,) in struct.iter_unpack("<h", chunk[:limit]):
        abs_sample = abs(sample)
        peak = max(peak, abs_sample)
        square_sum += sample * sample

    peak_percent = round(peak / 32767 * 100)
    rms_percent = math.sqrt(square_sum / count) / 32767 * 100 if count else 0.0
    return min(100, peak_percent), round(rms_percent, 2)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


def connect(urls: list[str], timeout: float) -> tuple[websocket.WebSocket, str]:
    last_error: Exception | None = None
    for url in urls:
        try:
            return websocket.create_connection(url, timeout=timeout), url
        except Exception as exc:  # noqa: BLE001 - try the next configured backend port.
            last_error = exc
    raise RuntimeError(f"Could not connect to audio listen WebSocket: {last_error}")


def monitor(args: argparse.Namespace) -> int:
    stop = False

    def _stop(_: int, __: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    urls = [args.ws_url] if args.ws_url else list(DEFAULT_WS_URLS)
    started_at = time.time()
    last_write_at = 0.0
    last_audio_at: float | None = None
    last_peak = 0
    last_rms = 0.0
    max_peak = 0
    bytes_total = 0
    chunks_total = 0
    window_bytes = 0
    window_started_at = started_at
    bytes_per_second = 0.0
    error: str | None = None

    output = Path(args.output)
    status: dict[str, Any] = {
        "stream_online": False,
        "heard_sound": False,
        "running": True,
        "error": None,
        "ws_url": None,
        "started_at": started_at,
        "updated_at": started_at,
        "last_audio_at": None,
        "seconds_since_audio": None,
        "chunks_total": 0,
        "bytes_total": 0,
        "bytes_per_second": 0,
        "peak_level": 0,
        "rms_level": 0,
        "max_peak_level": 0,
        "threshold": args.threshold,
    }
    write_json_atomic(output, status)

    ws: websocket.WebSocket | None = None
    try:
        ws, connected_url = connect(urls, args.timeout)
        status["ws_url"] = connected_url
        status["stream_online"] = True
        write_json_atomic(output, status)

        while not stop:
            if args.duration and time.time() - started_at >= args.duration:
                break

            try:
                chunk = ws.recv()
            except websocket.WebSocketTimeoutException:
                error = "WebSocketTimeoutException"
                chunk = b""

            now = time.time()
            if isinstance(chunk, str):
                # The audio endpoint is expected to send binary PCM only; keep text as a note.
                error = f"Unexpected text frame: {chunk[:120]}"
            elif chunk:
                peak, rms = pcm16_stats(chunk)
                chunks_total += 1
                bytes_total += len(chunk)
                window_bytes += len(chunk)
                last_audio_at = now
                last_peak = peak
                last_rms = rms
                max_peak = max(max_peak, peak)
                error = None

            if now - window_started_at >= 1.0:
                bytes_per_second = window_bytes / max(now - window_started_at, 0.001)
                window_bytes = 0
                window_started_at = now

            if now - last_write_at >= args.interval:
                seconds_since_audio = round(now - last_audio_at, 2) if last_audio_at else None
                status = {
                    "stream_online": bool(ws.connected),
                    "heard_sound": last_peak >= args.threshold,
                    "running": True,
                    "error": error,
                    "ws_url": connected_url,
                    "started_at": started_at,
                    "updated_at": now,
                    "last_audio_at": last_audio_at,
                    "seconds_since_audio": seconds_since_audio,
                    "chunks_total": chunks_total,
                    "bytes_total": bytes_total,
                    "bytes_per_second": round(bytes_per_second, 1),
                    "peak_level": last_peak,
                    "rms_level": last_rms,
                    "max_peak_level": max_peak,
                    "threshold": args.threshold,
                }
                write_json_atomic(output, status)
                last_write_at = now

        return 0
    except Exception as exc:  # noqa: BLE001 - write a readable status file for operators.
        now = time.time()
        status.update(
            {
                "stream_online": False,
                "heard_sound": False,
                "running": False,
                "error": f"{exc.__class__.__name__}: {exc}",
                "updated_at": now,
                "seconds_since_audio": round(now - last_audio_at, 2) if last_audio_at else None,
            }
        )
        write_json_atomic(output, status)
        return 2
    finally:
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
        final_now = time.time()
        if output.exists():
            try:
                final_status = json.loads(output.read_text(encoding="utf-8"))
            except Exception:
                final_status = {}
            final_status["running"] = False
            final_status["updated_at"] = final_now
            write_json_atomic(output, final_status)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write camera listen/audio detection status to a JSON file.")
    parser.add_argument("--ws-url", default=os.environ.get("CAMERA_LISTEN_WS_URL", ""), help="Audio listen WebSocket URL.")
    parser.add_argument(
        "--output",
        default=str(Path("tmp_camera_probe") / "camera_listen_status.json"),
        help="Status JSON output path.",
    )
    parser.add_argument("--threshold", type=int, default=3, help="Peak level percentage considered audible.")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between status file writes.")
    parser.add_argument("--timeout", type=float, default=10.0, help="WebSocket connection/read timeout.")
    parser.add_argument("--duration", type=float, default=0.0, help="Optional monitor duration in seconds; 0 means forever.")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(monitor(parse_args()))
