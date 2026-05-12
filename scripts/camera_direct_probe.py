from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tmp_camera_probe"


def load_dotenv() -> dict[str, str]:
    values: dict[str, str] = {}
    env_path = ROOT / ".env"
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    values.update({k: v for k, v in os.environ.items() if k.startswith("CAMERA")})
    return values


def mask_url(url: str, password: str) -> str:
    return url.replace(password, "***") if password else url


def socket_probe(host: str, ports: list[int], timeout: float) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for port in ports:
        start = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect((host, port))
            rows.append(
                {
                    "host": host,
                    "port": port,
                    "open": True,
                    "ms": round((time.time() - start) * 1000, 1),
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "host": host,
                    "port": port,
                    "open": False,
                    "error": type(exc).__name__,
                    "ms": round((time.time() - start) * 1000, 1),
                }
            )
        finally:
            sock.close()
    return rows


def build_url(host: str, port: int, url_transport: str, stream: str, env: dict[str, str]) -> str:
    user = env.get("CAMERA_USER") or env.get("CAMERA1_USER") or "admin"
    password = env.get("CAMERA_PASSWORD") or env.get("CAMERA1_PASSWORD") or ""
    return f"rtsp://{user}:{password}@{host}:{port}/{url_transport}/{stream}"


def child_probe() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--url-transport", choices=["tcp", "udp"], required=True)
    parser.add_argument("--stream", choices=["av0_0", "av0_1"], required=True)
    parser.add_argument("--seconds", type=float, default=6.0)
    args = parser.parse_args(sys.argv[sys.argv.index("--child") + 1 :])

    # Import cv2 only in the child so a blocked decoder can be killed safely.
    import cv2  # type: ignore

    env = load_dotenv()
    password = env.get("CAMERA_PASSWORD") or env.get("CAMERA1_PASSWORD") or ""
    url = build_url(args.host, args.port, args.url_transport, args.stream, env)

    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
        f"rtsp_transport;{args.url_transport}|stimeout;5000000|max_delay;500000"
    )

    started_at = time.time()
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass

    opened = bool(cap.isOpened())
    frames = 0
    shape = None
    saved = None
    deadline = time.time() + args.seconds

    while opened and time.time() < deadline:
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        frames += 1
        shape = list(frame.shape)
        if saved is None:
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            safe_name = f"direct_{args.host.replace('.', '_')}_{args.port}_{args.url_transport}_{args.stream}.jpg"
            out_path = OUT_DIR / safe_name
            cv2.imwrite(str(out_path), frame)
            saved = str(out_path)

    cap.release()
    elapsed = max(time.time() - started_at, 0.001)
    print(
        json.dumps(
            {
                "url": mask_url(url, password),
                "opened": opened,
                "frames": frames,
                "fps": round(frames / elapsed, 2),
                "shape": shape,
                "saved": saved,
                "elapsed": round(elapsed, 2),
            },
            ensure_ascii=False,
        )
    )
    return 0 if frames else 2


def run_rtsp_child(host: str, port: int, url_transport: str, stream: str, seconds: float, timeout: float) -> dict[str, object]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--child",
        "--host",
        host,
        "--port",
        str(port),
        "--url-transport",
        url_transport,
        "--stream",
        stream,
        "--seconds",
        str(seconds),
    ]
    try:
        result = subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "url": f"rtsp://admin:***@{host}:{port}/{url_transport}/{stream}",
            "opened": False,
            "frames": 0,
            "fps": 0,
            "error": f"timeout after {timeout}s",
        }

    line = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    try:
        payload = json.loads(line)
    except Exception:
        payload = {
            "url": f"rtsp://admin:***@{host}:{port}/{url_transport}/{stream}",
            "opened": False,
            "frames": 0,
            "fps": 0,
            "error": result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}",
        }
    return payload


def main() -> int:
    if "--child" in sys.argv:
        return child_probe()

    env = load_dotenv()
    default_host = env.get("CAMERA_IP") or env.get("CAMERA1_IP") or "192.168.8.252"

    parser = argparse.ArgumentParser(description="Fast LAN/direct-cable probe for the RTSP cameras.")
    parser.add_argument("--hosts", default=default_host, help="Comma-separated camera IP list.")
    parser.add_argument("--ports", default="80,554,10554,10080")
    parser.add_argument("--rtsp-ports", default="10554,554")
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--timeout", type=float, default=12.0)
    args = parser.parse_args()

    hosts = [item.strip() for item in args.hosts.split(",") if item.strip()]
    ports = [int(item.strip()) for item in args.ports.split(",") if item.strip()]
    rtsp_ports = [int(item.strip()) for item in args.rtsp_ports.split(",") if item.strip()]

    print("Camera direct probe")
    print("Passwords are masked. Saved frames go to tmp_camera_probe/.")
    print()

    for host in hosts:
        print(f"[ports] {host}")
        for row in socket_probe(host, ports, timeout=1.5):
            status = "OPEN" if row["open"] else f"FAIL {row.get('error')}"
            print(f"  {row['port']}: {status} ({row['ms']} ms)")
        print()

        best: dict[str, object] | None = None
        print(f"[rtsp] {host}")
        for port in rtsp_ports:
            for url_transport in ["tcp", "udp"]:
                for stream in ["av0_1", "av0_0"]:
                    payload = run_rtsp_child(host, port, url_transport, stream, args.seconds, args.timeout)
                    frames = int(payload.get("frames") or 0)
                    fps = payload.get("fps", 0)
                    opened = payload.get("opened", False)
                    error = payload.get("error")
                    suffix = f" saved={payload.get('saved')}" if payload.get("saved") else ""
                    if error:
                        suffix += f" error={error}"
                    print(f"  {payload.get('url')}: opened={opened} frames={frames} fps={fps}{suffix}")
                    if frames and (best is None or frames > int(best.get("frames") or 0)):
                        best = payload
        if best:
            print(f"BEST {host}: {best.get('url')} fps={best.get('fps')} saved={best.get('saved')}")
        else:
            print(f"BEST {host}: no decodable frame yet")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
