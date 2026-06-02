from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs" / "runtime_debug" / "freeze_snapshots"


@dataclass
class ProbeResult:
    ok: bool
    data: Any = None
    error: str | None = None
    elapsed_ms: float | None = None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture a one-shot freeze diagnostic snapshot without refreshing the demo page.",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--camera-id", default="camera_01")
    parser.add_argument("--output-dir", default=str(LOG_DIR))
    parser.add_argument(
        "--devtools-port",
        type=int,
        default=None,
        help="Optional Chromium/Edge remote debugging port. If omitted, common ports are probed.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    status_probe = timed(lambda: fetch_status(args.base_url, args.camera_id))
    frontend_probe = timed(lambda: fetch_frontend_snapshot(args.devtools_port))
    process_probe = timed(fetch_process_snapshot)
    gpu_probe = timed(fetch_gpu_snapshot)

    report = {
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "note": "Do not refresh the page before running this during a stall.",
        "status_probe": status_probe.__dict__,
        "frontend_probe": frontend_probe.__dict__,
        "process_probe": process_probe.__dict__,
        "gpu_probe": gpu_probe.__dict__,
        "triage": triage(status_probe.data if status_probe.ok else None, frontend_probe),
    }
    path = output_dir / f"freeze_snapshot_{timestamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"snapshot": str(path), "triage": report["triage"]}, ensure_ascii=False, indent=2))
    return 0


def timed(callback) -> ProbeResult:
    started = time.monotonic()
    try:
        data = callback()
        return ProbeResult(ok=True, data=data, elapsed_ms=round((time.monotonic() - started) * 1000, 2))
    except Exception as exc:  # diagnostic script should keep collecting other layers
        return ProbeResult(ok=False, error=str(exc), elapsed_ms=round((time.monotonic() - started) * 1000, 2))


def fetch_status(base_url: str, camera_id: str) -> dict[str, Any]:
    response = requests.get(f"{base_url.rstrip('/')}/status", params={"camera_id": camera_id}, timeout=3)
    response.raise_for_status()
    status = sanitize_status(response.json())
    return {
        "raw": status,
        "focused": focused_status(status),
    }


def focused_status(status: dict[str, Any]) -> dict[str, Any]:
    camera = first(status.get("cameras")) or {}
    detection = first(status.get("detection")) or {}
    return {
        "service_state": status.get("service_state"),
        "display_source_current": status.get("display_source_current"),
        "diagnostics": status.get("diagnostics"),
        "main_stream": pick_stream(status.get("main_stream") or {}),
        "analysis_stream": pick_stream(status.get("analysis_stream") or {}),
        "camera": {
            "stream_state": camera.get("stream_state"),
            "connected": camera.get("connected"),
            "capture_fps": camera.get("capture_fps"),
            "source_fps": camera.get("capture_process_source_fps"),
            "frame_age_ms": camera.get("frame_age_ms"),
            "reconnect_count": camera.get("reconnect_count"),
            "dropped_frames": camera.get("capture_ipc_dropped_frames"),
            "last_error": camera.get("last_error") or camera.get("capture_process_last_error"),
            "width": camera.get("frame_width"),
            "height": camera.get("frame_height"),
        },
        "detection": {
            "detection_fps": detection.get("detection_fps"),
            "detection_latency_ms": detection.get("inference_latency_ms"),
            "loop_latency_ms": detection.get("loop_latency_ms"),
            "last_lock_wait_ms": detection.get("last_lock_wait_ms"),
            "last_error": detection.get("last_error"),
        },
        "tracking": status.get("tracking"),
        "pose": status.get("pose"),
        "pipeline": status.get("pipeline"),
        "streaming": status.get("streaming"),
        "workers": status.get("workers"),
    }


def sanitize_status(value: Any) -> Any:
    if isinstance(value, list):
        return [sanitize_status(item) for item in value]
    if not isinstance(value, dict):
        return value

    sanitized: dict[str, Any] = {}
    for key, item in value.items():
        if key == "source_url":
            sanitized[key] = value.get("source_url_masked") or mask_url(str(item))
        else:
            sanitized[key] = sanitize_status(item)
    return sanitized


def mask_url(value: str) -> str:
    if "://" not in value or "@" not in value:
        return value
    scheme, rest = value.split("://", 1)
    user_info, host = rest.split("@", 1)
    user = user_info.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"


def pick_stream(stream: dict[str, Any]) -> dict[str, Any]:
    return {
        "stream_state": stream.get("stream_state"),
        "connected": stream.get("connected"),
        "capture_fps": stream.get("capture_fps"),
        "frame_age_ms": stream.get("frame_age_ms"),
        "restart_count": stream.get("restart_count"),
        "last_error": stream.get("last_error"),
        "width": stream.get("frame_width"),
        "height": stream.get("frame_height"),
    }


def fetch_frontend_snapshot(devtools_port: int | None) -> dict[str, Any]:
    ports = [devtools_port] if devtools_port else [9222, 9223, 9224, 9229, 9333]
    errors: list[str] = []
    for port in ports:
        if port is None:
            continue
        try:
            tab = find_demo_tab(port)
            return evaluate_cdp(
                tab["webSocketDebuggerUrl"],
                """
                (() => {
                  const debug = window.__VISION_DEBUG__;
                  return {
                    href: window.location.href,
                    title: document.title,
                    pageResponsiveAt: Date.now(),
                    snapshot: debug?.snapshot?.() || null,
                    dom: debug?.snapshot?.().dom || null,
                  };
                })()
                """,
            )
        except Exception as exc:
            errors.append(f"port {port}: {exc}")
    raise RuntimeError("; ".join(errors) or "no devtools port available")


def find_demo_tab(port: int) -> dict[str, Any]:
    payload = http_json(f"http://127.0.0.1:{port}/json/list", timeout=1)
    if not isinstance(payload, list):
        raise RuntimeError("devtools /json/list did not return a tab list")
    for tab in payload:
        url = str(tab.get("url") or "")
        if "127.0.0.1:8000/demo" in url or "localhost:8000/demo" in url:
            if not tab.get("webSocketDebuggerUrl"):
                raise RuntimeError("demo tab has no websocket debugger url")
            return tab
    raise RuntimeError("demo tab not found")


def evaluate_cdp(websocket_url: str, expression: str) -> dict[str, Any]:
    try:
        import websocket  # type: ignore
    except Exception as exc:
        raise RuntimeError(f"websocket-client unavailable: {exc}") from exc

    ws = websocket.create_connection(websocket_url, timeout=2)
    try:
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": expression,
                        "awaitPromise": True,
                        "returnByValue": True,
                    },
                }
            )
        )
        response = json.loads(ws.recv())
        result = response.get("result", {}).get("result", {})
        if "exceptionDetails" in response.get("result", {}):
            raise RuntimeError(json.dumps(response["result"]["exceptionDetails"], ensure_ascii=False))
        return result.get("value")
    finally:
        ws.close()


def fetch_process_snapshot() -> dict[str, Any]:
    command = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -in @('python.exe','msedge.exe','node.exe') } | "
        "ForEach-Object { $p = Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue; "
        "if ($p) { [pscustomobject]@{ Name=$_.Name; ProcessId=$_.ProcessId; CPU=$p.CPU; "
        "WSMB=[math]::Round($p.WorkingSet64/1MB,1); PMMB=[math]::Round($p.PrivateMemorySize64/1MB,1); "
        "CommandLine=$_.CommandLine } } } | ConvertTo-Json -Depth 4"
    )
    result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True, timeout=8)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"powershell exited {result.returncode}")
    text = result.stdout.strip()
    if not text:
        return {"processes": []}
    parsed = json.loads(text)
    return {"processes": parsed if isinstance(parsed, list) else [parsed]}


def fetch_gpu_snapshot() -> dict[str, Any] | None:
    command = [
        "nvidia-smi",
        "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
        "--format=csv,noheader,nounits",
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=3)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    util, mem_used, mem_total, temp, power = [part.strip() for part in result.stdout.splitlines()[0].split(",")[:5]]
    return {
        "gpu_util_percent": to_float(util),
        "gpu_memory_used_mb": to_float(mem_used),
        "gpu_memory_total_mb": to_float(mem_total),
        "gpu_temp_c": to_float(temp),
        "gpu_power_w": to_float(power),
    }


def triage(status_payload: dict[str, Any] | None, frontend_probe: ProbeResult) -> dict[str, Any]:
    if not status_payload:
        return {"layer": "backend_unreachable", "reason": "status request failed"}
    focused = status_payload.get("focused") or {}
    pipeline = focused.get("pipeline") or {}
    camera = focused.get("camera") or {}
    streaming = focused.get("streaming") or {}
    frontend_ok = frontend_probe.ok

    reasons: list[str] = []
    layer = "undetermined"
    if (camera.get("capture_fps") or 0) <= 0 or (camera.get("frame_age_ms") or 0) > 3000:
        layer = "capture_layer"
        reasons.append("capture_fps is zero or frame_age_ms is stale")
    elif (pipeline.get("detection_worker_fps") or 0) <= 0:
        layer = "inference_layer"
        reasons.append("detection_worker_fps is zero")
    elif (pipeline.get("result_publish_fps") or 0) <= 0 or (pipeline.get("detection_to_publish_lag_ms") or 0) > 3000:
        layer = "publish_layer"
        reasons.append("publish fps is zero or detection_to_publish_lag_ms is high")
    elif not frontend_ok and ((streaming.get("webrtc_clients") or 0) > 0 or (streaming.get("ws_clients") or 0) > 0):
        layer = "frontend_render_or_main_thread"
        reasons.append("backend has frontend clients but frontend probe did not respond")
    elif frontend_ok:
        layer = "no_freeze_captured"
        reasons.append("backend and frontend probes responded")
    else:
        reasons.append("insufficient evidence")
    return {"layer": layer, "reasons": reasons}


def http_json(url: str, timeout: float) -> Any:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.URLError as exc:
        raise RuntimeError(str(exc)) from exc


def first(value: Any) -> dict[str, Any] | None:
    if isinstance(value, list) and value:
        return value[0]
    return None


def to_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
