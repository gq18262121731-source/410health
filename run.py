import os
import socket
import urllib.error
import urllib.request

import psutil


SERVER_PORT = 8000


def get_best_local_ip():
    """
    Looks for a plausible non-loopback, non-VM IPv4 address
    assigned to physical/wi-fi adapters.
    """
    best_ip = None
    for interface, snics in psutil.net_if_addrs().items():
        # Skip common VPN / proxy / VM virtual interfaces
        if any(x in interface.lower() for x in ["vethernet", "loopback", "flclash", "wsl", "hyper-v"]):
            continue

        for snic in snics:
            if snic.family == socket.AF_INET:
                ip = snic.address
                # Skip link-local and localhost
                if ip.startswith("169.254.") or ip.startswith("127."):
                    continue
                # If we found a classic home LAN prefix, prefer it immediately
                if ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172."):
                    return ip
                # Fallback to the first valid one we find
                if best_ip is None:
                    best_ip = ip

    return best_ip or "127.0.0.1"


def is_backend_ready(port: int = SERVER_PORT) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def is_port_in_use(port: int = SERVER_PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


if __name__ == "__main__":
    local_ip = get_best_local_ip()
    print("\n" + "=" * 60)
    print("AIoT Health Monitoring System - Backend Launcher")
    print("=" * 60)
    print("\nMobile App should connect to Server IP:")
    print(f"  http://{local_ip}:{SERVER_PORT}")
    print("\nPlease enter this IP in the mobile app's Server Settings (accessible via the Gear icon on the Login screen).")
    print("\n" + "=" * 60 + "\n")

    if is_backend_ready():
        print(f"Backend is already running on http://127.0.0.1:{SERVER_PORT}, skipping duplicate startup.")
        raise SystemExit(0)

    if is_port_in_use():
        print(f"Port {SERVER_PORT} is already in use by another process. Stop that process before starting a new backend.")
        raise SystemExit(1)

    # Start Uvicorn listening on all interfaces with hot-reload enabled.
    os.system(f"python -m uvicorn backend.main:app --host 0.0.0.0 --port {SERVER_PORT} --reload")
