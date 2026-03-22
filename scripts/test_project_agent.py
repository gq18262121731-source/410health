from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.dependencies import get_agent_service, get_stream_service
from backend.models.user_model import UserRole


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Command-line tester for the project prompt + local KB + local model pipeline."
    )
    parser.add_argument(
        "--mode",
        choices=("analyze", "report"),
        default="analyze",
        help="Run advisory analysis or time-range report generation.",
    )
    parser.add_argument(
        "--role",
        choices=("family", "community", "elder", "admin"),
        default="family",
        help="User role used in the project prompt package.",
    )
    parser.add_argument(
        "--device-mac",
        default="",
        help="Target device MAC. If omitted, the first mock/available device is used.",
    )
    parser.add_argument(
        "--question",
        default="请结合最近监测数据给出离线健康分析。",
        help="Question passed into the analysis flow.",
    )
    parser.add_argument(
        "--history-minutes",
        type=int,
        default=180,
        help="History window used by analyze mode.",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=6,
        help="Report window length in hours for report mode.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON payload only.",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available devices in the current stream and exit.",
    )
    return parser.parse_args()


def choose_device_mac(explicit_mac: str) -> str:
    if explicit_mac.strip():
        return explicit_mac.strip().upper()

    stream = get_stream_service()
    latest_samples = stream.latest_samples()
    if not latest_samples:
        raise RuntimeError("No device samples are available in the current stream.")
    return latest_samples[0].device_mac


def list_devices() -> None:
    stream = get_stream_service()
    latest_samples = sorted(stream.latest_samples(), key=lambda item: item.device_mac)
    if not latest_samples:
        print("No devices available in the current stream.")
        return

    print("Available devices:")
    for sample in latest_samples:
        print(
            f"- {sample.device_mac} | latest={sample.timestamp.astimezone(timezone.utc).isoformat()} "
            f"| hr={sample.heart_rate} | spo2={sample.blood_oxygen} | temp={sample.temperature}"
        )


def run_analyze(role: UserRole, device_mac: str, question: str, history_minutes: int) -> dict[str, object]:
    stream = get_stream_service()
    samples = stream.recent_in_window(device_mac, minutes=history_minutes, limit=240)
    if not samples:
        raise RuntimeError(f"No samples found for device {device_mac} in the last {history_minutes} minutes.")
    return get_agent_service().analyze_device(
        role=role,
        question=question,
        samples=samples,
        mode="local",
    )


def run_report(role: UserRole, device_mac: str, hours: int) -> dict[str, object]:
    stream = get_stream_service()
    samples = stream.recent(device_mac, limit=1000)
    if not samples:
        raise RuntimeError(f"No samples found for device {device_mac}.")
    ordered = sorted(samples, key=lambda item: item.timestamp)
    end_at = ordered[-1].timestamp
    start_at = end_at - timedelta(hours=max(1, hours))
    window_samples = [sample for sample in ordered if start_at <= sample.timestamp <= end_at]
    if not window_samples:
        raise RuntimeError(f"No samples found for device {device_mac} in the report window.")
    return get_agent_service().generate_device_health_report(
        role=role,
        device_mac=device_mac,
        start_at=start_at.astimezone(timezone.utc),
        end_at=end_at.astimezone(timezone.utc),
        samples=window_samples,
        mode="local",
    )


def pretty_print(payload: dict[str, object], mode: str) -> None:
    if mode == "report":
        print(f"report_type: {payload.get('report_type')}")
        print(f"device_mac: {payload.get('device_mac')}")
        print(f"risk_level: {payload.get('risk_level')}")
        print(f"period: {json.dumps(payload.get('period', {}), ensure_ascii=False)}")
        print("\nsummary:")
        print(str(payload.get("summary", "")).strip())
        print("\nkey_findings:")
        for item in payload.get("key_findings", []):
            print(f"- {item}")
        print("\nrecommendations:")
        for item in payload.get("recommendations", []):
            print(f"- {item}")
        print("\nreferences:")
        for item in payload.get("references", []):
            print(f"- {item}")
        return

    print("answer:")
    print(str(payload.get("answer", "")).strip())
    print("\nanalysis:")
    print(json.dumps(payload.get("analysis", {}), ensure_ascii=False, indent=2))
    print("\nreferences:")
    for item in payload.get("references", []):
        print(f"- {item}")


def main() -> int:
    args = parse_args()

    if args.list_devices:
        list_devices()
        return 0

    role = UserRole(args.role)
    device_mac = choose_device_mac(args.device_mac)

    if args.mode == "report":
        payload = run_report(role, device_mac, args.hours)
    else:
        payload = run_analyze(role, device_mac, args.question, args.history_minutes)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        pretty_print(payload, args.mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
