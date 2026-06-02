from __future__ import annotations

import argparse
import asyncio
import json
import math
import queue
import threading
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import websockets


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG_DIR = ROOT / "logs" / "human_trial"
DEFAULT_REPORT_PATH = ROOT / "docs" / "controlled_human_trial_report.md"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def finite_values(values: list[Any]) -> list[float]:
    return [
        float(value)
        for value in values
        if isinstance(value, (int, float)) and math.isfinite(float(value))
    ]


def average(values: list[Any]) -> float | None:
    numeric = finite_values(values)
    return round(sum(numeric) / len(numeric), 3) if numeric else None


def minimum(values: list[Any]) -> float | None:
    numeric = finite_values(values)
    return round(min(numeric), 3) if numeric else None


def maximum(values: list[Any]) -> float | None:
    numeric = finite_values(values)
    return round(max(numeric), 3) if numeric else None


def count_truthy(values: list[Any]) -> int:
    return sum(1 for value in values if bool(value))


def build_status_url(base_url: str, camera_id: str) -> str:
    query = urllib.parse.urlencode({"camera_id": camera_id})
    return f"{base_url.rstrip('/')}/status?{query}"


def build_ws_url(base_url: str, camera_id: str) -> str:
    query = urllib.parse.urlencode({"camera_id": camera_id})
    return f"{base_url.rstrip('/')}/ws/results?{query}"


def fetch_json(url: str, timeout: float = 3.0) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def compact_status_sample(status: dict[str, Any]) -> dict[str, Any]:
    main = status.get("main_stream") or {}
    analysis = status.get("analysis_stream") or {}
    pipeline = status.get("pipeline") or {}
    pose = status.get("pose") or {}
    temporal = status.get("temporal") or {}
    streaming = status.get("streaming") or {}
    watchdog = status.get("watchdog") or {}
    diagnostics = status.get("diagnostics") or {}
    workers = status.get("workers") or {}
    detection = (status.get("detection") or [{}])[0]
    tracking = status.get("tracking") or {}

    return {
        "at": now_iso(),
        "service_state": status.get("service_state") or "unknown",
        "diagnostics": diagnostics,
        "main_state": main.get("stream_state"),
        "main_connected": main.get("connected"),
        "main_frame_age_ms": main.get("frame_age_ms"),
        "main_capture_fps": main.get("capture_fps"),
        "main_restart_count": main.get("restart_count"),
        "main_last_error": main.get("last_error"),
        "analysis_state": analysis.get("stream_state"),
        "analysis_connected": analysis.get("connected"),
        "analysis_frame_age_ms": analysis.get("frame_age_ms"),
        "analysis_capture_fps": analysis.get("capture_fps"),
        "analysis_restart_count": analysis.get("restart_count"),
        "analysis_last_error": analysis.get("last_error"),
        "display_source_current": status.get("display_source_current"),
        "display_fallback_active": status.get("display_fallback_active"),
        "detection_worker_fps": pipeline.get("detection_worker_fps"),
        "tracking_worker_fps": pipeline.get("tracking_worker_fps"),
        "result_publish_fps": pipeline.get("result_publish_fps"),
        "detection_to_publish_lag_ms": pipeline.get("detection_to_publish_lag_ms"),
        "pipeline_last_error": pipeline.get("last_error"),
        "detection_fps": detection.get("detection_fps"),
        "detection_latency_ms": detection.get("inference_latency_ms"),
        "tracking_state": tracking.get("tracking_state"),
        "tracked_target_id": tracking.get("tracked_target_id"),
        "tracked_objects_count": tracking.get("tracked_objects_count"),
        "pose_fps": pose.get("pose_fps"),
        "pose_latency_ms": pose.get("last_inference_latency_ms"),
        "pose_skipped_due_to_busy": pose.get("skipped_due_to_busy"),
        "pose_circuit_open": pose.get("circuit_open"),
        "fall_state": temporal.get("fall_state"),
        "fall_probability": temporal.get("fall_probability"),
        "temporal_last_error": temporal.get("last_error"),
        "watchdog_state": watchdog.get("watchdog_state"),
        "watchdog_restart_count": watchdog.get("watchdog_restart_count"),
        "watchdog_suppressed": watchdog.get("watchdog_suppressed"),
        "watchdog_degraded_reason": watchdog.get("degraded_reason"),
        "webrtc_clients": streaming.get("webrtc_clients"),
        "ws_clients": streaming.get("ws_clients"),
        "workers": workers,
    }


def extract_result_sample(payload: dict[str, Any], started_at: float) -> dict[str, Any]:
    objects = payload.get("objects") or []
    target = None
    for item in objects:
        if item.get("is_target"):
            target = item
            break
    if target is None and objects:
        target = objects[0]

    behavior = (target or {}).get("behavior") or {}
    temporal = (target or {}).get("temporal") or {}
    decision = (target or {}).get("fall_decision") or {}
    preview = (target or {}).get("alarm_preview") or {}

    return {
        "at": now_iso(),
        "trial_ms": round((time.monotonic() - started_at) * 1000, 2),
        "frame_seq": payload.get("frame_seq"),
        "object_count": len(objects),
        "track_id": (target or {}).get("track_id"),
        "is_target": (target or {}).get("is_target"),
        "person_id": (target or {}).get("person_id"),
        "behavior_state": behavior.get("state"),
        "behavior_confidence": behavior.get("confidence"),
        "fall_state": decision.get("fall_state") or "normal",
        "risk_level": decision.get("risk_level") or preview.get("risk_level"),
        "fall_probability": temporal.get("fall_probability"),
        "confirmed": bool(preview.get("confirmed") or decision.get("fall_state") == "fallen_confirmed"),
        "countdown_ms": decision.get("countdown_ms") or preview.get("countdown_ms"),
        "analysis_frame_width": payload.get("analysis_frame_width"),
        "analysis_frame_height": payload.get("analysis_frame_height"),
        "display_frame_width": payload.get("display_frame_width"),
        "display_frame_height": payload.get("display_frame_height"),
        "display_source": payload.get("display_source"),
        "analysis_source": payload.get("analysis_source"),
    }


def marker_reader(stop_event: threading.Event, output_queue: queue.Queue[dict[str, Any]]) -> None:
    help_text = (
        "Marker commands: 'start standing', 'end standing', "
        "'note bbox aligned', 'quit'."
    )
    print(help_text, flush=True)
    while not stop_event.is_set():
        try:
            line = input("> ").strip()
        except EOFError:
            return
        if not line:
            continue
        if line.lower() in {"q", "quit", "exit"}:
            output_queue.put({"at": now_iso(), "type": "quit", "text": line})
            stop_event.set()
            return
        parts = line.split(maxsplit=1)
        marker_type = parts[0].lower()
        text = parts[1] if len(parts) > 1 else ""
        if marker_type not in {"start", "end", "note"}:
            marker_type = "note"
            text = line
        output_queue.put({"at": now_iso(), "type": marker_type, "text": text})


async def status_loop(
    *,
    status_url: str,
    interval_sec: float,
    stop_event: threading.Event,
    samples: list[dict[str, Any]],
    failures: list[dict[str, Any]],
) -> None:
    while not stop_event.is_set():
        started = time.monotonic()
        try:
            status = await asyncio.to_thread(fetch_json, status_url, 3.0)
            samples.append(compact_status_sample(status))
        except Exception as exc:
            failures.append({"at": now_iso(), "error": repr(exc)})
            samples.append({"at": now_iso(), "status_error": repr(exc)})
        elapsed = time.monotonic() - started
        await asyncio.sleep(max(0.0, interval_sec - elapsed))


async def websocket_loop(
    *,
    ws_url: str,
    started_at: float,
    stop_event: threading.Event,
    samples: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> None:
    reconnect_attempt = 0
    while not stop_event.is_set():
        try:
            async with websockets.connect(ws_url, ping_interval=10, ping_timeout=10) as websocket:
                reconnect_attempt = 0
                events.append({"at": now_iso(), "event": "ws_connected"})
                while not stop_event.is_set():
                    raw = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    payload = json.loads(raw)
                    samples.append(extract_result_sample(payload, started_at))
        except asyncio.TimeoutError:
            continue
        except Exception as exc:
            events.append({"at": now_iso(), "event": "ws_error", "error": repr(exc)})
            reconnect_attempt += 1
            await asyncio.sleep(min(5.0, reconnect_attempt))


async def marker_loop(
    *,
    marker_queue: queue.Queue[dict[str, Any]],
    stop_event: threading.Event,
    markers: list[dict[str, Any]],
) -> None:
    while not stop_event.is_set():
        try:
            marker = marker_queue.get_nowait()
        except queue.Empty:
            await asyncio.sleep(0.2)
            continue
        markers.append(marker)
        if marker.get("type") == "quit":
            stop_event.set()


def marker_seconds(marker: dict[str, Any], started_iso: str) -> float | None:
    try:
        marker_ts = datetime.fromisoformat(marker["at"])
        start_ts = datetime.fromisoformat(started_iso)
        return round((marker_ts - start_ts).total_seconds(), 3)
    except Exception:
        return None


def summarize_action_windows(
    *,
    markers: list[dict[str, Any]],
    result_samples: list[dict[str, Any]],
    trial_started_iso: str,
) -> list[dict[str, Any]]:
    starts: list[dict[str, Any]] = [item for item in markers if item.get("type") == "start"]
    ends: list[dict[str, Any]] = [item for item in markers if item.get("type") == "end"]
    windows: list[dict[str, Any]] = []
    for start in starts:
        action = start.get("text") or "unknown"
        start_sec = marker_seconds(start, trial_started_iso)
        end = next(
            (
                item
                for item in ends
                if (item.get("text") or "unknown") == action
                and item.get("at", "") >= start.get("at", "")
            ),
            None,
        )
        end_sec = marker_seconds(end, trial_started_iso) if end else None
        if start_sec is None:
            continue
        samples = [
            sample
            for sample in result_samples
            if sample.get("trial_ms") is not None
            and sample["trial_ms"] >= start_sec * 1000
            and (end_sec is None or sample["trial_ms"] <= end_sec * 1000)
        ]
        states = sorted({sample.get("fall_state") or "normal" for sample in samples})
        max_prob = maximum([sample.get("fall_probability") for sample in samples])
        confirmed = any(bool(sample.get("confirmed")) for sample in samples)
        first_state_change_ms = None
        for sample in samples:
            if sample.get("fall_state") not in {None, "normal"}:
                first_state_change_ms = round(sample["trial_ms"] - start_sec * 1000, 2)
                break
        windows.append(
            {
                "action": action,
                "start_sec": start_sec,
                "end_sec": end_sec,
                "samples": len(samples),
                "states_seen": states,
                "max_fall_probability": max_prob,
                "confirmed": confirmed,
                "first_state_change_ms": first_state_change_ms,
            }
        )
    return windows


def restart_delta(samples: list[dict[str, Any]], key: str) -> int | None:
    valid = [sample for sample in samples if isinstance(sample.get(key), int)]
    if len(valid) < 2:
        return None
    return int(valid[-1][key]) - int(valid[0][key])


def summarize_trial(
    *,
    status_samples: list[dict[str, Any]],
    status_failures: list[dict[str, Any]],
    result_samples: list[dict[str, Any]],
    ws_events: list[dict[str, Any]],
    markers: list[dict[str, Any]],
    started_at_monotonic: float,
    started_at_iso: str,
) -> dict[str, Any]:
    valid_status = [sample for sample in status_samples if "status_error" not in sample]
    service_counts = Counter(sample.get("service_state") for sample in valid_status)
    diagnostics_counts: Counter[str] = Counter()
    for sample in valid_status:
        diagnostics = sample.get("diagnostics") or {}
        for key, value in diagnostics.items():
            if value:
                diagnostics_counts[key] += 1

    fall_states = sorted({sample.get("fall_state") or "normal" for sample in result_samples})
    confirmed_count = count_truthy([sample.get("confirmed") for sample in result_samples])
    action_windows = summarize_action_windows(
        markers=markers,
        result_samples=result_samples,
        trial_started_iso=started_at_iso,
    )

    return {
        "duration_sec": round(time.monotonic() - started_at_monotonic, 2),
        "status_sample_count": len(valid_status),
        "status_failures": len(status_failures),
        "ws_result_count": len(result_samples),
        "ws_event_count": len(ws_events),
        "manual_marker_count": len(markers),
        "service_state_counts": dict(service_counts),
        "diagnostics_true_counts": dict(diagnostics_counts),
        "main_max_frame_age_ms": maximum([sample.get("main_frame_age_ms") for sample in valid_status]),
        "analysis_max_frame_age_ms": maximum([sample.get("analysis_frame_age_ms") for sample in valid_status]),
        "main_restart_delta": restart_delta(valid_status, "main_restart_count"),
        "analysis_restart_delta": restart_delta(valid_status, "analysis_restart_count"),
        "watchdog_restart_delta": restart_delta(valid_status, "watchdog_restart_count"),
        "watchdog_suppressed_seen": any(bool(sample.get("watchdog_suppressed")) for sample in valid_status),
        "capture_fps_avg": average([sample.get("analysis_capture_fps") for sample in valid_status]),
        "detection_worker_fps_avg": average([sample.get("detection_worker_fps") for sample in valid_status]),
        "tracking_worker_fps_avg": average([sample.get("tracking_worker_fps") for sample in valid_status]),
        "result_publish_fps_avg": average([sample.get("result_publish_fps") for sample in valid_status]),
        "pose_fps_avg": average([sample.get("pose_fps") for sample in valid_status]),
        "pose_skipped_due_to_busy_delta": restart_delta(valid_status, "pose_skipped_due_to_busy"),
        "pose_circuit_open_seen": any(bool(sample.get("pose_circuit_open")) for sample in valid_status),
        "fall_states_seen": fall_states,
        "max_fall_probability": maximum([sample.get("fall_probability") for sample in result_samples]),
        "confirmed_count": confirmed_count,
        "ws_reconnect_events": sum(1 for event in ws_events if event.get("event") == "ws_connected"),
        "ws_error_events": sum(1 for event in ws_events if event.get("event") == "ws_error"),
        "action_windows": action_windows,
    }


def render_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Controlled Human Trial Report",
        "",
        f"Generated at: {payload['ended_at']}",
        "",
        "## Scope",
        "",
        "This report is for Phase 5.21 controlled human trial logging. It does not train models, does not modify Temporal/FallStateMachine, and does not call alert POST/snapshot paths.",
        "",
        "## Trial Setup",
        "",
        f"- Label: `{payload['label']}`",
        f"- Camera ID: `{payload['camera_id']}`",
        f"- Duration: `{summary['duration_sec']}` seconds",
        f"- Status samples: `{summary['status_sample_count']}`",
        f"- WebSocket result samples: `{summary['ws_result_count']}`",
        f"- Manual markers: `{summary['manual_marker_count']}`",
        "",
        "## Runtime Summary",
        "",
        f"- Service states: `{summary['service_state_counts']}`",
        f"- Diagnostics true counts: `{summary['diagnostics_true_counts']}`",
        f"- Status failures: `{summary['status_failures']}`",
        f"- Main max frame age: `{summary['main_max_frame_age_ms']}` ms",
        f"- Analysis max frame age: `{summary['analysis_max_frame_age_ms']}` ms",
        f"- Main restart delta: `{summary['main_restart_delta']}`",
        f"- Analysis restart delta: `{summary['analysis_restart_delta']}`",
        f"- Watchdog restart delta: `{summary['watchdog_restart_delta']}`",
        f"- Watchdog suppressed seen: `{summary['watchdog_suppressed_seen']}`",
        "",
        "## Pipeline Summary",
        "",
        f"- Analysis capture FPS avg: `{summary['capture_fps_avg']}`",
        f"- Detection worker FPS avg: `{summary['detection_worker_fps_avg']}`",
        f"- Tracking worker FPS avg: `{summary['tracking_worker_fps_avg']}`",
        f"- Result publish FPS avg: `{summary['result_publish_fps_avg']}`",
        f"- Pose FPS avg: `{summary['pose_fps_avg']}`",
        f"- Pose skipped_due_to_busy delta: `{summary['pose_skipped_due_to_busy_delta']}`",
        f"- Pose circuit open seen: `{summary['pose_circuit_open_seen']}`",
        "",
        "## Fall Preview Summary",
        "",
        f"- Fall states seen: `{summary['fall_states_seen']}`",
        f"- Max fall probability: `{summary['max_fall_probability']}`",
        f"- Confirmed count: `{summary['confirmed_count']}`",
        "",
        "## Action Windows",
        "",
        "| Action | Start(s) | End(s) | Samples | States Seen | Max Prob | Confirmed | First State Change(ms) |",
        "| --- | ---: | ---: | ---: | --- | ---: | --- | ---: |",
    ]
    for item in summary.get("action_windows") or []:
        lines.append(
            "| {action} | {start} | {end} | {samples} | {states} | {prob} | {confirmed} | {delay} |".format(
                action=item.get("action"),
                start=item.get("start_sec"),
                end=item.get("end_sec"),
                samples=item.get("samples"),
                states=", ".join(item.get("states_seen") or []),
                prob=item.get("max_fall_probability"),
                confirmed=item.get("confirmed"),
                delay=item.get("first_state_change_ms"),
            )
        )
    if not summary.get("action_windows"):
        lines.append("| _No manual action windows recorded_ | | | | | | | |")

    lines.extend(
        [
            "",
            "## Frontend Observation Checklist",
            "",
            "- Main video is clear and live: TODO",
            "- BBox aligns with person: TODO",
            "- Skeleton aligns with person: TODO",
            "- Fast motion only shows minor overlay delay: TODO",
            "- Browser console has no errors: TODO",
            "- False positive observed: TODO",
            "- Missed high-risk transition observed: TODO",
            "",
            "## Safety Notes",
            "",
            "- Do not ask real elderly users to perform dangerous falls.",
            "- Safe fall simulation should use soft padding and slow controlled motion only.",
            "- Confirmed fall remains preview-only in Phase 5; no official alert POST is triggered.",
            "",
            "## Raw Logs",
            "",
            f"- JSON summary: `{payload['summary_path']}`",
            f"- Status samples JSONL: `{payload['status_jsonl_path']}`",
            f"- WebSocket result samples JSONL: `{payload['result_jsonl_path']}`",
            f"- Markers JSONL: `{payload['markers_jsonl_path']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


async def run_trial(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    started_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = f"{started_slug}_{args.label}"
    status_jsonl = output_dir / f"{prefix}_status.jsonl"
    result_jsonl = output_dir / f"{prefix}_results.jsonl"
    markers_jsonl = output_dir / f"{prefix}_markers.jsonl"
    summary_json = output_dir / f"{prefix}_summary.json"

    status_url = build_status_url(args.http_base, args.camera_id)
    ws_url = build_ws_url(args.ws_base, args.camera_id)
    started_at = time.monotonic()
    started_iso = now_iso()
    stop_event = threading.Event()
    marker_queue: queue.Queue[dict[str, Any]] = queue.Queue()
    status_samples: list[dict[str, Any]] = []
    status_failures: list[dict[str, Any]] = []
    result_samples: list[dict[str, Any]] = []
    ws_events: list[dict[str, Any]] = []
    markers: list[dict[str, Any]] = []

    marker_thread = None
    if args.interactive_markers:
        marker_thread = threading.Thread(
            target=marker_reader,
            args=(stop_event, marker_queue),
            daemon=True,
            name="human-trial-marker-reader",
        )
        marker_thread.start()

    tasks = [
        asyncio.create_task(
            status_loop(
                status_url=status_url,
                interval_sec=args.status_interval_sec,
                stop_event=stop_event,
                samples=status_samples,
                failures=status_failures,
            )
        ),
        asyncio.create_task(
            websocket_loop(
                ws_url=ws_url,
                started_at=started_at,
                stop_event=stop_event,
                samples=result_samples,
                events=ws_events,
            )
        ),
        asyncio.create_task(
            marker_loop(
                marker_queue=marker_queue,
                stop_event=stop_event,
                markers=markers,
            )
        ),
    ]

    print(
        json.dumps(
            {
                "event": "human_trial_started",
                "label": args.label,
                "duration_sec": args.duration_sec,
                "status_url": status_url,
                "ws_url": ws_url,
                "interactive_markers": args.interactive_markers,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    try:
        deadline = started_at + args.duration_sec
        while time.monotonic() < deadline and not stop_event.is_set():
            await asyncio.sleep(1.0)
    except KeyboardInterrupt:
        markers.append({"at": now_iso(), "type": "note", "text": "KeyboardInterrupt stop"})
    finally:
        stop_event.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        if marker_thread and marker_thread.is_alive():
            marker_thread.join(timeout=0.2)

    summary = summarize_trial(
        status_samples=status_samples,
        status_failures=status_failures,
        result_samples=result_samples,
        ws_events=ws_events,
        markers=markers,
        started_at_monotonic=started_at,
        started_at_iso=started_iso,
    )
    payload = {
        "phase": "5.21",
        "label": args.label,
        "camera_id": args.camera_id,
        "started_at": started_iso,
        "ended_at": now_iso(),
        "status_url": status_url,
        "ws_url": ws_url,
        "summary": summary,
        "status_failures": status_failures,
        "ws_events": ws_events,
        "summary_path": str(summary_json),
        "status_jsonl_path": str(status_jsonl),
        "result_jsonl_path": str(result_jsonl),
        "markers_jsonl_path": str(markers_jsonl),
    }

    write_jsonl(status_jsonl, status_samples)
    write_jsonl(result_jsonl, result_samples)
    write_jsonl(markers_jsonl, markers)
    summary_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(payload), encoding="utf-8")

    print(
        json.dumps(
            {
                "event": "human_trial_finished",
                "summary": summary,
                "summary_path": str(summary_json),
                "report_path": str(report_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record Phase 5.21 controlled human trial telemetry.")
    parser.add_argument("--duration-sec", type=int, default=1800)
    parser.add_argument("--camera-id", default="camera_01")
    parser.add_argument("--label", default="controlled_human_trial")
    parser.add_argument("--http-base", default="http://127.0.0.1:8000")
    parser.add_argument("--ws-base", default="ws://127.0.0.1:8000")
    parser.add_argument("--status-interval-sec", type=float, default=1.0)
    parser.add_argument("--output-dir", default=str(DEFAULT_LOG_DIR))
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--interactive-markers", action="store_true")
    return parser.parse_args()


def main() -> int:
    return asyncio.run(run_trial(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
