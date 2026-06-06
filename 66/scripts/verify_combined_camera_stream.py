from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from http.client import HTTPConnection
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


DEFAULT_BASE_URL = "http://127.0.0.1:8000"


@dataclass
class StreamProbeResult:
    endpoint: str
    ok: bool
    frame_bytes: int = 0
    elapsed_ms: int = 0
    error: str | None = None
    saved_to: str | None = None


def _json_request(base_url: str, method: str, path: str, *, timeout: float = 30.0) -> dict[str, Any]:
    parsed = urlparse(base_url)
    conn = HTTPConnection(parsed.hostname or "127.0.0.1", parsed.port or 80, timeout=timeout)
    try:
        conn.request(method, path)
        response = conn.getresponse()
        data = response.read()
        if response.status >= 400:
            raise RuntimeError(f"HTTP {response.status}: {data[:300]!r}")
        return json.loads(data.decode("utf-8"))
    finally:
        conn.close()


def _safe_filename(path: str) -> str:
    return path.strip("/").replace("/", "_").replace(".", "_") or "stream"


def _probe_mjpeg(
    base_url: str,
    path: str,
    *,
    timeout: float = 18.0,
    output_dir: Path | None = None,
) -> StreamProbeResult:
    parsed = urlparse(base_url)
    conn = HTTPConnection(parsed.hostname or "127.0.0.1", parsed.port or 80, timeout=timeout)
    started = time.perf_counter()
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        if response.status >= 400:
            return StreamProbeResult(path, False, error=f"HTTP {response.status}")
        buffer = b""
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            chunk = response.read(4096)
            if not chunk:
                break
            buffer += chunk
            start = buffer.find(b"\xff\xd8")
            end = buffer.find(b"\xff\xd9", start + 2)
            if start >= 0 and end > start:
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                frame = buffer[start : end + 2]
                saved_to = None
                if output_dir is not None:
                    output_dir.mkdir(parents=True, exist_ok=True)
                    target = output_dir / f"{_safe_filename(path)}.jpg"
                    target.write_bytes(frame)
                    saved_to = str(target)
                return StreamProbeResult(path, True, frame_bytes=len(frame), elapsed_ms=elapsed_ms, saved_to=saved_to)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return StreamProbeResult(path, False, elapsed_ms=elapsed_ms, error="NO_JPEG_FRAME")
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return StreamProbeResult(path, False, elapsed_ms=elapsed_ms, error=f"{exc.__class__.__name__}: {exc}")
    finally:
        conn.close()


def main() -> int:
    base_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_URL
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("runtime_logs") / "combined_stream_verify"
    result: dict[str, Any] = {"base_url": base_url}
    result["healthz"] = _json_request(base_url, "GET", "/healthz", timeout=20.0)
    result["before"] = _json_request(base_url, "GET", "/api/v1/camera/processed-overlay/status", timeout=20.0)
    # Warm/probe the raw stream first so priming uses a recent frame.
    raw_stream = _probe_mjpeg(base_url, "/api/v1/camera/stream.mjpg", timeout=25.0, output_dir=output_dir).__dict__
    result["raw_stream"] = raw_stream
    try:
        result["prime"] = _json_request(base_url, "POST", "/api/v1/camera/processed-overlay/prime?include_fall=true", timeout=75.0)
    except Exception as exc:
        result["prime"] = {"ok": False, "error": f"{exc.__class__.__name__}: {exc}"}
    time.sleep(0.8)
    result["after"] = _json_request(base_url, "GET", "/api/v1/camera/processed-overlay/status", timeout=20.0)
    streams = [
        "/api/v1/camera/stream.processed.mjpg",
        "/api/v1/camera/stream.pose.mjpg",
        "/api/v1/camera/stream.detect.mjpg",
    ]
    result["streams"] = [raw_stream] + [
        _probe_mjpeg(base_url, path, timeout=25.0, output_dir=output_dir).__dict__ for path in streams
    ]

    stream_ok = all(item["ok"] for item in result["streams"])
    overlay = result["after"].get("processed_overlay") if isinstance(result["after"], dict) else {}
    processed_frame = next(
        (item for item in result["streams"] if item["endpoint"].endswith("/stream.processed.mjpg")),
        {},
    )
    raw_frame = next(
        (item for item in result["streams"] if item["endpoint"].endswith("/stream.mjpg")),
        {},
    )
    processed_is_decorated = (
        bool(processed_frame.get("ok"))
        and int(processed_frame.get("frame_bytes") or 0) > int(raw_frame.get("frame_bytes") or 0) + 1024
    )
    result["processed_is_decorated"] = processed_is_decorated
    result["note"] = (
        "processed stream is decorated even when no person is detected"
        if processed_is_decorated and not result.get("prime", {}).get("pose_seeded")
        else ""
    )
    overlay_known = isinstance(overlay, dict) and (
        overlay.get("pose_fallback_valid")
        or overlay.get("pose_payload_valid")
        or overlay.get("fall_fallback_valid")
        or overlay.get("fall_payload_valid")
        or result.get("prime", {}).get("pose_seeded")
        or result.get("prime", {}).get("fall_seeded")
        or processed_is_decorated
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["summary_saved_to"] = str(summary_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if stream_ok and overlay_known else 2


if __name__ == "__main__":
    raise SystemExit(main())
