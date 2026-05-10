from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass

import cv2


@dataclass
class ProbeResult:
    url: str
    opened: bool
    frames: int


def try_url(url: str, read_attempts: int = 6, timeout_seconds: float = 6.0) -> ProbeResult:
    cap = cv2.VideoCapture()
    if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(timeout_seconds * 1000))
    if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, int(timeout_seconds * 1000))
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap.open(url, cv2.CAP_FFMPEG)
    opened = cap.isOpened()
    frames = 0
    if opened:
        deadline = time.perf_counter() + timeout_seconds
        for _ in range(read_attempts):
            if time.perf_counter() >= deadline:
                break
            ok, frame = cap.read()
            if ok and frame is not None:
                frames += 1
                break
    cap.release()
    return ProbeResult(url=url, opened=opened, frames=frames)


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe a matrix of RTSP URLs.")
    parser.add_argument("--host", required=True)
    parser.add_argument("--usernames", nargs="+", default=["admin"])
    parser.add_argument("--passwords", nargs="+", required=True)
    parser.add_argument("--ports", nargs="+", type=int, default=[10554, 554])
    parser.add_argument("--transports", nargs="+", default=["tcp", "udp"])
    parser.add_argument("--streams", nargs="+", default=["av0_1", "av0_0"])
    parser.add_argument("--timeout-seconds", type=float, default=6.0)
    args = parser.parse_args()

    results: list[ProbeResult] = []
    for username in args.usernames:
        for password in args.passwords:
            for port in args.ports:
                for transport in args.transports:
                    for stream in args.streams:
                        url = f"rtsp://{username}:{password}@{args.host}:{port}/{transport}/{stream}"
                        results.append(try_url(url, timeout_seconds=args.timeout_seconds))

    print(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

