from __future__ import annotations

import socket
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Generator
from urllib.parse import quote

import requests

from backend.config import Settings


@dataclass(frozen=True)
class CameraStatus:
    configured: bool
    online: bool
    ip: str
    port: int
    path: str
    checked_at: datetime
    latency_ms: float | None = None
    error: str | None = None


class CameraService:
    _PROFILE_TOKEN_CACHE: dict[tuple[str, int], str] = {}
    _PTZ_DIRECTIONS = {
        "up": (0.0, 1.0, 0.0),
        "down": (0.0, -1.0, 0.0),
        "left": (-1.0, 0.0, 0.0),
        "right": (1.0, 0.0, 0.0),
        "up_left": (-1.0, 1.0, 0.0),
        "up_right": (1.0, 1.0, 0.0),
        "down_left": (-1.0, -1.0, 0.0),
        "down_right": (1.0, -1.0, 0.0),
        "zoom_in": (0.0, 0.0, 1.0),
        "zoom_out": (0.0, 0.0, -1.0),
    }

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def configured(self) -> bool:
        return bool(
            self._settings.camera_ip.strip()
            and self._settings.camera_user.strip()
            and self._settings.camera_password
            and self._settings.camera_rtsp_port > 0
        )

    @property
    def rtsp_url(self) -> str:
        return self._build_rtsp_url(self._settings.camera_rtsp_path, self._settings.camera_rtsp_port)

    @property
    def fallback_rtsp_urls(self) -> list[str]:
        configured_path = self._normalize_path(self._settings.camera_rtsp_path)
        candidates = [
            (configured_path, self._settings.camera_rtsp_port),
            ("/tcp/av0_0", 10554),
            ("/tcp/av0_1", 10554),
            ("/udp/av0_0", 10554),
            ("/udp/av0_1", 10554),
            ("/av0_0", 10554),
            ("/av0_1", 10554),
            ("/tcp/av0_0", 554),
            ("/tcp/av0_1", 554),
        ]
        urls: list[str] = []
        for path, port in candidates:
            url = self._build_rtsp_url(path, port)
            if url not in urls:
                urls.append(url)
        return urls

    @property
    def stream_rtsp_urls(self) -> list[str]:
        configured_path = self._normalize_path(self._settings.camera_stream_rtsp_path)
        candidates = [
            (configured_path, self._settings.camera_rtsp_port),
            ("/tcp/av0_1", 10554),
            ("/tcp/av0_0", 10554),
            ("/udp/av0_1", 10554),
            ("/udp/av0_0", 10554),
            ("/av0_1", 10554),
            ("/av0_0", 10554),
        ]
        urls: list[str] = []
        for path, port in candidates:
            url = self._build_rtsp_url(path, port)
            if url not in urls:
                urls.append(url)
        return urls

    def _build_rtsp_url(self, path: str, port: int) -> str:
        user = quote(self._settings.camera_user.strip(), safe="")
        password = quote(self._settings.camera_password, safe="")
        normalized_path = self._normalize_path(path)
        return f"rtsp://{user}:{password}@{self._settings.camera_ip.strip()}:{port}{normalized_path}"

    def check_status(self) -> CameraStatus:
        checked_at = datetime.now(timezone.utc)
        ip = self._settings.camera_ip.strip()
        port = self._settings.camera_rtsp_port
        path = self._normalize_path(self._settings.camera_rtsp_path)
        if not self.configured:
            return CameraStatus(
                configured=False,
                online=False,
                ip=ip,
                port=port,
                path=path,
                checked_at=checked_at,
                error="CAMERA_NOT_CONFIGURED",
            )

        started = time.perf_counter()
        try:
            with socket.create_connection((ip, port), timeout=self._settings.camera_probe_timeout_seconds):
                latency_ms = (time.perf_counter() - started) * 1000
            return CameraStatus(
                configured=True,
                online=True,
                ip=ip,
                port=port,
                path=path,
                checked_at=checked_at,
                latency_ms=round(latency_ms, 2),
            )
        except OSError as exc:
            return CameraStatus(
                configured=True,
                online=False,
                ip=ip,
                port=port,
                path=path,
                checked_at=checked_at,
                error=f"{exc.__class__.__name__}: {exc}",
            )

    def capture_jpeg(self) -> tuple[bytes, dict[str, str]]:
        if not self.configured:
            raise RuntimeError("CAMERA_NOT_CONFIGURED")

        image_bytes = self._capture_jpeg_with_ffmpeg()
        if image_bytes:
            return image_bytes, {"Cache-Control": "no-store, max-age=0"}

        return self._capture_jpeg_with_opencv()

    def mjpeg_frames(self) -> Generator[bytes, None, None]:
        if not self.configured:
            raise RuntimeError("CAMERA_NOT_CONFIGURED")

        yield from self._mjpeg_frames_from_snapshots()

    def _mjpeg_frames_with_ffmpeg(self) -> Generator[bytes, None, None]:
        import imageio_ffmpeg

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        fps = max(1.0, min(self._settings.camera_stream_fps, 12.0))
        retry_delay = 0.8

        while True:
            for url in self.fallback_rtsp_urls:
                cmd = [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-rtsp_transport",
                    "tcp",
                    "-timeout",
                    str(int(self._settings.camera_snapshot_timeout_seconds * 1_000_000)),
                    "-i",
                    url,
                    "-an",
                    "-r",
                    f"{fps:.2f}",
                    "-f",
                    "mjpeg",
                    "-q:v",
                    "5",
                    "-",
                ]
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                buffer = b""
                try:
                    if process.stdout is None:
                        continue

                    while True:
                        chunk = process.stdout.read(8192)
                        if not chunk:
                            break
                        buffer += chunk

                        while True:
                            start = buffer.find(b"\xff\xd8")
                            end = buffer.find(b"\xff\xd9", start + 2) if start >= 0 else -1
                            if start < 0:
                                buffer = buffer[-2:]
                                break
                            if end < 0:
                                buffer = buffer[start:]
                                break

                            image = buffer[start : end + 2]
                            buffer = buffer[end + 2 :]
                            yield self._format_mjpeg_part(image)
                finally:
                    process.kill()
                    process.wait(timeout=2)

            time.sleep(retry_delay)

    def _mjpeg_frames_from_snapshots(self) -> Generator[bytes, None, None]:
        fps = max(0.2, min(self._settings.camera_stream_fps, 2.0))
        frame_delay = 1.0 / fps
        while True:
            try:
                image, _headers = self.capture_jpeg()
                yield self._format_mjpeg_part(image)
            except RuntimeError:
                time.sleep(0.8)
                continue
            time.sleep(frame_delay)

    def _mjpeg_frames_with_opencv(self) -> Generator[bytes, None, None]:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("OPENCV_NOT_INSTALLED") from exc

        fps = max(1.0, min(self._settings.camera_stream_fps, 12.0))
        frame_delay = 1.0 / fps
        retry_delay = 0.8

        while True:
            cap = None
            try:
                for url in self.fallback_rtsp_urls:
                    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
                    if cap.isOpened():
                        break
                    cap.release()
                    cap = None

                if cap is None:
                    time.sleep(retry_delay)
                    continue

                while True:
                    started = time.monotonic()
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        break

                    encoded_ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
                    if not encoded_ok:
                        continue

                    image = encoded.tobytes()
                    yield self._format_mjpeg_part(image)

                    elapsed = time.monotonic() - started
                    if elapsed < frame_delay:
                        time.sleep(frame_delay - elapsed)
            finally:
                if cap is not None:
                    cap.release()

            time.sleep(retry_delay)

    @staticmethod
    def _format_mjpeg_part(image: bytes) -> bytes:
        return (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            + f"Content-Length: {len(image)}\r\n\r\n".encode("ascii")
            + image
            + b"\r\n"
        )

    def ptz_move(self, direction: str, mode: str = "pulse") -> dict[str, object]:
        if not self.configured:
            raise RuntimeError("CAMERA_NOT_CONFIGURED")

        normalized = direction.strip().lower().replace("-", "_")
        normalized_mode = mode.strip().lower()
        if normalized == "stop":
            profile_token = self._get_onvif_profile_token()
            self._onvif_stop(profile_token)
            return {"ok": True, "direction": normalized, "mode": normalized_mode}

        if normalized not in self._PTZ_DIRECTIONS:
            raise ValueError("CAMERA_PTZ_DIRECTION_INVALID")
        if normalized_mode not in {"pulse", "continuous"}:
            raise ValueError("CAMERA_PTZ_MODE_INVALID")

        profile_token = self._get_onvif_profile_token()
        pan, tilt, zoom = self._PTZ_DIRECTIONS[normalized]
        speed = max(0.05, min(abs(self._settings.camera_ptz_speed), 1.0))
        self._onvif_continuous_move(profile_token, pan * speed, tilt * speed, zoom * speed)
        if normalized_mode == "pulse":
            time.sleep(max(0.08, min(self._settings.camera_ptz_move_seconds, 1.5)))
            self._onvif_stop(profile_token)
        return {"ok": True, "direction": normalized, "mode": normalized_mode}

    def _get_onvif_profile_token(self) -> str:
        cache_key = (self._settings.camera_ip.strip(), self._settings.camera_onvif_port)
        cached = self._PROFILE_TOKEN_CACHE.get(cache_key)
        if cached:
            return cached

        body = """
        <trt:GetProfiles xmlns:trt="http://www.onvif.org/ver10/media/wsdl" />
        """
        xml_text = self._post_onvif("/onvif/media_service", body)
        root = ET.fromstring(xml_text)
        namespace = {"trt": "http://www.onvif.org/ver10/media/wsdl"}
        profile = root.find(".//trt:Profiles", namespace)
        token = profile.attrib.get("token") if profile is not None else None
        if not token:
            raise RuntimeError("CAMERA_ONVIF_PROFILE_NOT_FOUND")
        self._PROFILE_TOKEN_CACHE[cache_key] = token
        return token

    def _onvif_continuous_move(self, profile_token: str, pan: float, tilt: float, zoom: float) -> None:
        body = f"""
        <tptz:ContinuousMove xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl" xmlns:tt="http://www.onvif.org/ver10/schema">
          <tptz:ProfileToken>{profile_token}</tptz:ProfileToken>
          <tptz:Velocity>
            <tt:PanTilt x="{pan:.3f}" y="{tilt:.3f}" />
            <tt:Zoom x="{zoom:.3f}" />
          </tptz:Velocity>
        </tptz:ContinuousMove>
        """
        self._post_onvif("/onvif/ptz_service", body)

    def _onvif_stop(self, profile_token: str) -> None:
        body = f"""
        <tptz:Stop xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl">
          <tptz:ProfileToken>{profile_token}</tptz:ProfileToken>
          <tptz:PanTilt>true</tptz:PanTilt>
          <tptz:Zoom>true</tptz:Zoom>
        </tptz:Stop>
        """
        self._post_onvif("/onvif/ptz_service", body)

    def _post_onvif(self, path: str, body: str) -> str:
        envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
        <s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
          <s:Body>{body}</s:Body>
        </s:Envelope>
        """
        url = f"http://{self._settings.camera_ip.strip()}:{self._settings.camera_onvif_port}{path}"
        response = requests.post(
            url,
            data=envelope.encode("utf-8"),
            headers={"Content-Type": "application/soap+xml; charset=utf-8"},
            timeout=max(2.0, self._settings.camera_probe_timeout_seconds),
        )
        if response.status_code >= 400:
            raise RuntimeError(f"CAMERA_ONVIF_HTTP_{response.status_code}")
        return response.text

    def _capture_jpeg_with_ffmpeg(self) -> bytes | None:
        try:
            import imageio_ffmpeg
        except ImportError:
            return None

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        last_error = ""
        for url in self.fallback_rtsp_urls:
            cmd = [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-rtsp_transport",
                "tcp",
                "-timeout",
                str(int(self._settings.camera_snapshot_timeout_seconds * 1_000_000)),
                "-i",
                url,
                "-frames:v",
                "1",
                "-f",
                "image2pipe",
                "-vcodec",
                "mjpeg",
                "-",
            ]
            try:
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=self._settings.camera_snapshot_timeout_seconds + 4,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                last_error = f"ffmpeg timeout: {exc}"
                continue

            if result.returncode == 0 and result.stdout.startswith(b"\xff\xd8"):
                return result.stdout
            last_error = result.stderr.decode("utf-8", errors="replace").strip()

        if last_error:
            return None
        return None

    def _capture_jpeg_with_opencv(self) -> tuple[bytes, dict[str, str]]:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("OPENCV_NOT_INSTALLED") from exc

        frame = None
        for url in self.fallback_rtsp_urls:
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                cap.release()
                continue

            deadline = time.monotonic() + self._settings.camera_snapshot_timeout_seconds
            try:
                while time.monotonic() < deadline:
                    ok, candidate = cap.read()
                    if ok and candidate is not None:
                        frame = candidate
                        break
            finally:
                cap.release()

            if frame is not None:
                break

        if frame is None:
            raise RuntimeError("CAMERA_FRAME_READ_TIMEOUT")

        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 86])
        if not ok:
            raise RuntimeError("CAMERA_JPEG_ENCODE_FAILED")

        height, width = frame.shape[:2]
        headers = {
            "Cache-Control": "no-store, max-age=0",
            "X-Camera-Width": str(width),
            "X-Camera-Height": str(height),
        }
        return encoded.tobytes(), headers

    @staticmethod
    def _normalize_path(path: str) -> str:
        normalized = (path or "/tcp/av0_0").strip()
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"
        return normalized
