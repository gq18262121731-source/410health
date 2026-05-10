from __future__ import annotations

import os
import socket
import subprocess
import struct
import time
import xml.etree.ElementTree as ET
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Generator
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
    source: str = "rtsp"
    detail: str | None = None


@dataclass(frozen=True)
class CameraAudioStatus:
    configured: bool
    listen_supported: bool
    talk_supported: bool
    checked_url: str | None = None
    audio_codec: str | None = None
    sample_rate: int | None = None
    channels: int | None = None
    source: str = "rtsp"
    sdk_available: bool = False
    sdk_arch: str | None = None
    sdk_loadable: bool = False
    sdk_message: str | None = None
    gateway_configured: bool = False
    activex_available: bool = False
    activex_clsid: str | None = None
    activex_inproc_path: str | None = None
    activex_message: str | None = None
    error: str | None = None


class CameraService:
    _PE_MACHINE_TYPES = {
        0x014C: "x86",
        0x8664: "x64",
        0x01C0: "ARM",
        0x01C4: "ARMv7",
        0xAA64: "ARM64",
    }
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
        # 优化1: HTTP Session连接池 - 复用连接，减少TCP握手开销
        self._http_session = requests.Session()
        # 配置连接池：最大10个连接，每个主机最大5个连接
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=10,
            max_retries=1,
            pool_block=False
        )
        self._http_session.mount('http://', adapter)
        self._http_session.mount('https://', adapter)
        # 设置默认超时
        self._http_session.timeout = max(2.0, settings.camera_probe_timeout_seconds)

    @property
    def configured(self) -> bool:
        source_mode = self._settings.camera_source_mode
        if source_mode == "local":
            return True
        if source_mode == "auto":
            return self._rtsp_configured or self._settings.camera_local_index >= 0
        return self._rtsp_configured

    @property
    def _rtsp_configured(self) -> bool:
        return bool(
            self._settings.camera_ip.strip()
            and self._settings.camera_user.strip()
            and self._settings.camera_password
            and self._settings.camera_rtsp_port > 0
        )

    def resolved_source_mode(self) -> str:
        mode = self._settings.camera_source_mode
        if mode != "auto":
            return mode
        if self._rtsp_target_is_local_machine():
            return "local"
        if self._rtsp_configured:
            return "rtsp"
        return "local"

    def can_use_local_camera_fallback(self) -> bool:
        return self._settings.camera_source_mode in {"auto", "local"} and self._settings.camera_local_index >= 0

    def should_fail_closed_on_rtsp_errors(self) -> bool:
        return self._rtsp_configured and self.resolved_source_mode() == "rtsp"

    @property
    def rtsp_url(self) -> str:
        return self._build_rtsp_url(self._settings.camera_rtsp_path, self._settings.camera_rtsp_port)

    def build_audio_rtsp_url(self) -> str:
        return self._build_rtsp_url(self._settings.camera_audio_rtsp_path, self._settings.camera_rtsp_port)

    @property
    def fallback_rtsp_urls(self) -> list[str]:
        configured_path = self._normalize_path(self._settings.camera_rtsp_path)
        configured_stream_path = self._normalize_path(self._settings.camera_stream_rtsp_path)
        quality_path = self._normalize_path(self._settings.camera_stream_quality_path)
        smooth_path = self._normalize_path(self._settings.camera_stream_smooth_path)
        candidates = [
            (configured_path, self._settings.camera_rtsp_port),
            (configured_stream_path, self._settings.camera_rtsp_port),
            (quality_path, self._settings.camera_rtsp_port),
            (smooth_path, self._settings.camera_rtsp_port),
            ("/udp/av0_0", self._settings.camera_rtsp_port),
            ("/udp/av0_1", self._settings.camera_rtsp_port),
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
        smooth_path = self._normalize_path(self._settings.camera_stream_smooth_path)
        quality_path = self._normalize_path(self._settings.camera_stream_quality_path)

        if self._settings.camera_stream_profile == "quality":
            preferred_paths = [quality_path, configured_path, smooth_path]
        elif self._settings.camera_stream_profile == "smooth":
            preferred_paths = [smooth_path, configured_path, quality_path]
        else:
            preferred_paths = [configured_path, smooth_path, quality_path]

        candidates = [(path, self._settings.camera_rtsp_port) for path in preferred_paths] + [
            ("/udp/av0_1", 10554),
            ("/udp/av0_0", 10554),
            ("/tcp/av0_1", 10554),
            ("/tcp/av0_0", 10554),
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
        source_mode = self.resolved_source_mode()

        if source_mode == "local":
            return self._check_local_camera_status(checked_at)

        if not self._rtsp_configured:
            if self.can_use_local_camera_fallback():
                return self._check_local_camera_status(checked_at)
            return CameraStatus(
                configured=False,
                online=False,
                ip=ip,
                port=port,
                path=path,
                checked_at=checked_at,
                error="CAMERA_NOT_CONFIGURED",
                source="rtsp",
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
                source="rtsp",
                detail=f"RTSP {ip}:{port}{path}",
            )
        except OSError as exc:
            if self.can_use_local_camera_fallback() and not self.should_fail_closed_on_rtsp_errors():
                local_status = self._check_local_camera_status(checked_at, rtsp_error=f"{exc.__class__.__name__}: {exc}")
                if local_status.online:
                    return local_status
            return CameraStatus(
                configured=True,
                online=False,
                ip=ip,
                port=port,
                path=path,
                checked_at=checked_at,
                error=f"{exc.__class__.__name__}: {exc}",
                source="rtsp",
            )

    def check_audio_status(self) -> CameraAudioStatus:
        source_mode = self.resolved_source_mode()
        if source_mode == "local":
            return CameraAudioStatus(
                configured=True,
                listen_supported=False,
                talk_supported=False,
                source="local",
                error="LOCAL_CAMERA_AUDIO_UNSUPPORTED",
            )

        if not self._rtsp_configured:
            return CameraAudioStatus(
                configured=False,
                listen_supported=False,
                talk_supported=False,
                source="rtsp",
                error="CAMERA_NOT_CONFIGURED",
            )

        try:
            status = self._probe_rtsp_audio()
        except Exception as exc:  # noqa: BLE001
            status = CameraAudioStatus(
                configured=True,
                listen_supported=False,
                talk_supported=False,
                source="rtsp",
                error=f"{exc.__class__.__name__}: {exc}",
            )
        sdk_fields = self._probe_audio_sdk_fields()
        activex_fields = self._probe_activex_fields()
        fields = {**status.__dict__, **sdk_fields, **activex_fields}
        fields["talk_supported"] = bool(
            fields.get("talk_supported")
            or fields.get("gateway_configured")
            or fields.get("activex_available")
        )
        return CameraAudioStatus(**fields)

    def capture_jpeg(self) -> tuple[bytes, dict[str, str]]:
        source_mode = self.resolved_source_mode()
        if source_mode == "local":
            return self.capture_local_jpeg()

        if not self._rtsp_configured:
            if self.can_use_local_camera_fallback():
                return self.capture_local_jpeg()
            raise RuntimeError("CAMERA_NOT_CONFIGURED")

        try:
            return self._capture_jpeg_with_opencv()
        except RuntimeError as rtsp_error:
            image_bytes = self._capture_jpeg_with_ffmpeg()
            if image_bytes:
                return image_bytes, {"Cache-Control": "no-store, max-age=0"}
            try:
                return self._capture_jpeg_via_http()
            except RuntimeError:
                pass
            if self.can_use_local_camera_fallback() and not self.should_fail_closed_on_rtsp_errors():
                try:
                    return self.capture_local_jpeg()
                except RuntimeError:
                    raise rtsp_error

        raise RuntimeError("CAMERA_FRAME_READ_TIMEOUT")

    def capture_local_jpeg(self) -> tuple[bytes, dict[str, str]]:
        # 优先使用HTTP快照服务（独立进程，避免OpenCV异步问题）
        local_http_url = getattr(self._settings, 'camera_local_http_url', '').strip()
        if local_http_url:
            try:
                response = self._http_session.get(
                    f"{local_http_url}/snapshot",
                    timeout=max(2.0, self._settings.camera_snapshot_timeout_seconds)
                )
                if response.status_code == 200:
                    content = response.content
                    if content.startswith(b"\xff\xd8") and len(content) > 1000:
                        headers = {
                            "Cache-Control": "no-store, max-age=0",
                            "X-Camera-Source": "local-http",
                        }
                        return content, headers
            except Exception:
                pass  # 失败则继续尝试直接访问
        
        # 回退到直接访问摄像头
        frame = self._capture_local_frame()
        return self._encode_frame_to_jpeg(frame)

    def mjpeg_frames(self) -> Generator[bytes, None, None]:
        if not self.configured:
            raise RuntimeError("CAMERA_NOT_CONFIGURED")

        yield from self._mjpeg_frames_from_snapshots()

    def _mjpeg_frames_from_snapshots(self) -> Generator[bytes, None, None]:
        fps = max(0.2, min(self._settings.camera_stream_fps, 6.0))  # 提高上限到6fps
        frame_delay = 1.0 / fps
        while True:
            try:
                image, _headers = self.capture_jpeg()
                yield self._format_mjpeg_part(image)
            except RuntimeError:
                time.sleep(0.8)
                continue
            time.sleep(frame_delay)

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
        # 优化: 使用Session连接池
        response = self._http_session.post(
            url,
            data=envelope.encode("utf-8"),
            headers={"Content-Type": "application/soap+xml; charset=utf-8"},
            timeout=max(2.0, self._settings.camera_probe_timeout_seconds),
        )
        if response.status_code >= 400:
            raise RuntimeError(f"CAMERA_ONVIF_HTTP_{response.status_code}")
        return response.text

    def _capture_jpeg_via_http(self) -> tuple[bytes, dict[str, str]]:
        """
        通过HTTP接口获取快照（适用于P2P摄像头）
        尝试多个常见的HTTP快照路径
        """
        ip = self._settings.camera_ip.strip()
        user = self._settings.camera_user.strip()
        password = self._settings.camera_password
        timeout = max(2.0, self._settings.camera_snapshot_timeout_seconds)
        
        # 常见的HTTP快照路径
        snapshot_urls = [
            # ONVIF标准快照
            f"http://{ip}:{self._settings.camera_onvif_port}/onvif/snapshot",
            f"http://{ip}:{self._settings.camera_onvif_port}/onvif-http/snapshot",
            # 通用CGI路径
            f"http://{ip}/cgi-bin/snapshot.cgi",
            f"http://{ip}/snapshot.jpg",
            f"http://{ip}/image/jpeg.cgi",
            f"http://{ip}/tmpfs/auto.jpg",
            # 其他常见路径
            f"http://{ip}:{self._settings.camera_onvif_port}/snapshot.jpg",
            f"http://{ip}:{self._settings.camera_rtsp_port}/snapshot.jpg",
        ]
        
        last_error = ""
        for url in snapshot_urls:
            try:
                # 使用Session连接池
                response = self._http_session.get(
                    url,
                    auth=(user, password) if user and password else None,
                    timeout=timeout,
                    allow_redirects=True,
                )
                
                if response.status_code == 200:
                    content = response.content
                    # 验证是否为有效的JPEG
                    if content.startswith(b"\xff\xd8") and len(content) > 1000:
                        headers = {
                            "Cache-Control": "no-store, max-age=0",
                            "X-Camera-Source": "http-snapshot",
                        }
                        return content, headers
                        
            except Exception as exc:
                last_error = f"{exc.__class__.__name__}: {exc}"
                continue
        
        raise RuntimeError(f"HTTP_SNAPSHOT_FAILED: {last_error}")

    def _capture_jpeg_with_ffmpeg(self) -> bytes | None:
        try:
            import imageio_ffmpeg
        except ImportError:
            return None

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
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
            except subprocess.TimeoutExpired:
                continue

            if result.returncode == 0 and result.stdout.startswith(b"\xff\xd8"):
                return result.stdout

        return None

    def _capture_jpeg_with_opencv(self) -> tuple[bytes, dict[str, str]]:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("OPENCV_NOT_INSTALLED") from exc

        frame = None
        previous_options = os.environ.get("OPENCV_FFMPEG_CAPTURE_OPTIONS")
        # 优化3: OpenCV优化配置 - 减少延迟，提高响应速度
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|max_delay;0|fflags;nobuffer|flags;low_delay"
        for url in self.fallback_rtsp_urls:
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            # 优化: 设置缓冲区大小为1，减少延迟
            with suppress(Exception):
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            # 优化: 设置FPS以提高捕获速度
            with suppress(Exception):
                cap.set(cv2.CAP_PROP_FPS, 30)
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
        if previous_options is None:
            os.environ.pop("OPENCV_FFMPEG_CAPTURE_OPTIONS", None)
        else:
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = previous_options

        if frame is None:
            raise RuntimeError("CAMERA_FRAME_READ_TIMEOUT")

        return self._encode_frame_to_jpeg(frame)

    def _probe_rtsp_audio(self) -> CameraAudioStatus:
        try:
            import imageio_ffmpeg
        except ImportError as exc:
            raise RuntimeError("IMAGEIO_FFMPEG_NOT_INSTALLED") from exc

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        last_error = ""
        timeout_seconds = max(2.0, min(self._settings.camera_probe_timeout_seconds, 5.0))
        audio_url = self.build_audio_rtsp_url()
        urls = [audio_url]
        urls.extend(url for url in self.stream_rtsp_urls[:2] if url not in urls)
        for url in urls:
            cmd = [
                ffmpeg,
                "-nostdin",
                "-hide_banner",
                "-rtsp_transport",
                "tcp",
                "-timeout",
                str(int(timeout_seconds * 1_000_000)),
                "-probesize",
                "5000000",
                "-i",
                url,
                "-t",
                "1",
                "-vn",
                "-f",
                "null",
                "-",
            ]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_seconds + 3,
                check=False,
            )
            output = self._mask_url(result.stderr.decode("utf-8", errors="replace")) or ""
            audio_line = self._find_ffmpeg_audio_line(output)
            if audio_line:
                codec, sample_rate, channels = self._parse_ffmpeg_audio_line(audio_line)
                return CameraAudioStatus(
                    configured=True,
                    listen_supported=True,
                    talk_supported=False,
                    checked_url=self._mask_url(url),
                    audio_codec=codec,
                    sample_rate=sample_rate,
                    channels=channels,
                    source="rtsp",
                )
            last_error = output.strip()

        return CameraAudioStatus(
            configured=True,
            listen_supported=False,
            talk_supported=False,
            checked_url=self._mask_url(urls[0]) if urls else None,
            source="rtsp",
            error=(last_error[-500:] if last_error else "CAMERA_AUDIO_TRACK_NOT_FOUND"),
        )

    def _probe_audio_sdk_fields(self) -> dict[str, object]:
        from pathlib import Path

        gateway_url = self._settings.camera_audio_gateway_url.strip()
        configured_dir = self._settings.camera_sdk_dll_dir.strip()
        default_dir = (
            Path(__file__).resolve().parents[2]
            / "摄像头说明书"
            / "extracted"
            / "SDK_phone (2)"
            / "SDK_phone"
            / "Lib"
            / "win32"
        )
        sdk_dir = Path(configured_dir) if configured_dir else default_dir
        dll = sdk_dir / "P2PAPI.dll"
        fields: dict[str, object] = {
            "sdk_available": dll.exists(),
            "sdk_arch": None,
            "sdk_loadable": False,
            "sdk_message": None,
            "gateway_configured": bool(gateway_url),
        }
        if not dll.exists():
            fields["sdk_message"] = f"SDK_DLL_NOT_FOUND: {dll}"
            return fields

        arch = self._read_pe_machine(dll)
        python_arch = f"{struct.calcsize('P') * 8}-bit"
        fields["sdk_arch"] = arch
        if arch == "x86" and struct.calcsize("P") == 8:
            fields["sdk_message"] = "SDK_DLL_X86_WITH_64BIT_BACKEND: use 32-bit gateway process or request x64 SDK"
            return fields

        try:
            import ctypes

            ctypes.WinDLL(str(dll))
            fields["sdk_loadable"] = True
            fields["sdk_message"] = f"SDK_LOADABLE_WITH_{python_arch}_PYTHON"
        except OSError as exc:
            fields["sdk_message"] = f"{exc.__class__.__name__}: {exc}"
        return fields

    def _probe_activex_fields(self) -> dict[str, object]:
        clsid = self._settings.camera_activex_clsid.strip().strip("{}")
        fields: dict[str, object] = {
            "activex_available": False,
            "activex_clsid": clsid or None,
            "activex_inproc_path": None,
            "activex_message": None,
        }
        if not clsid:
            fields["activex_message"] = "ACTIVEX_CLSID_NOT_CONFIGURED"
            return fields

        try:
            import winreg
        except ImportError:
            fields["activex_message"] = "ACTIVEX_WINDOWS_ONLY"
            return fields

        registry_path = f"CLSID\\{{{clsid}}}\\InprocServer32"
        registry_views = [
            ("64-bit", getattr(winreg, "KEY_WOW64_64KEY", 0)),
            ("32-bit", getattr(winreg, "KEY_WOW64_32KEY", 0)),
            ("default", 0),
        ]
        checked: list[str] = []
        for view_name, view_flag in registry_views:
            try:
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, registry_path, 0, winreg.KEY_READ | view_flag) as key:
                    value, _value_type = winreg.QueryValueEx(key, "")
                    fields["activex_available"] = True
                    fields["activex_inproc_path"] = str(value)
                    fields["activex_message"] = f"ACTIVEX_REGISTERED_{view_name.upper()}"
                    return fields
            except OSError as exc:
                checked.append(f"{view_name}: {exc.winerror if hasattr(exc, 'winerror') else exc}")

        fields["activex_message"] = "ACTIVEX_NOT_REGISTERED: " + "; ".join(checked)
        return fields

    def _capture_local_frame(self) -> Any:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("OPENCV_NOT_INSTALLED") from exc

        # 尝试多种后端，解决异步环境下的OpenCV问题
        backends = [
            (cv2.CAP_DSHOW, "DSHOW"),
            (cv2.CAP_MSMF, "MSMF"),  # Windows Media Foundation
            (cv2.CAP_ANY, "ANY"),
        ]
        
        last_error = ""
        for backend, backend_name in backends:
            try:
                cap = cv2.VideoCapture(self._settings.camera_local_index, backend)
                try:
                    if not cap.isOpened():
                        last_error = f"{backend_name}: Camera not opened"
                        continue
                    
                    # 设置较短的超时
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    
                    # 尝试读取帧
                    ok, frame = cap.read()
                    if ok and frame is not None:
                        return frame
                    
                    last_error = f"{backend_name}: Frame read failed"
                finally:
                    cap.release()
            except Exception as exc:
                last_error = f"{backend_name}: {exc.__class__.__name__}: {exc}"
                continue
        
        raise RuntimeError(f"LOCAL_CAMERA_ALL_BACKENDS_FAILED: {last_error}")

    def _encode_frame_to_jpeg(self, frame: Any) -> tuple[bytes, dict[str, str]]:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("OPENCV_NOT_INSTALLED") from exc

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

    def local_source_label(self) -> str:
        backend = self._settings.camera_local_backend.upper()
        return f"local://camera/{self._settings.camera_local_index}?backend={backend}"

    def _check_local_camera_status(self, checked_at: datetime, rtsp_error: str | None = None) -> CameraStatus:
        started = time.perf_counter()
        try:
            frame = self._capture_local_frame()
            latency_ms = (time.perf_counter() - started) * 1000
            height, width = frame.shape[:2]
            detail = f"Local camera #{self._settings.camera_local_index} ({width}x{height})"
            if rtsp_error:
                detail = f"{detail}; RTSP unavailable, using local fallback"
            return CameraStatus(
                configured=True,
                online=True,
                ip="local",
                port=0,
                path=f"/camera/{self._settings.camera_local_index}",
                checked_at=checked_at,
                latency_ms=round(latency_ms, 2),
                source="local",
                detail=detail,
            )
        except RuntimeError as exc:
            return CameraStatus(
                configured=True,
                online=False,
                ip="local",
                port=0,
                path=f"/camera/{self._settings.camera_local_index}",
                checked_at=checked_at,
                error=str(exc) if not rtsp_error else f"{rtsp_error}; local fallback failed: {exc}",
                source="local",
                detail=f"Local camera #{self._settings.camera_local_index}",
            )

    def _rtsp_target_is_local_machine(self) -> bool:
        ip = self._settings.camera_ip.strip().lower()
        if not ip:
            return False
        return ip in self._local_host_addresses()

    def _local_host_addresses(self) -> set[str]:
        addresses = {"127.0.0.1", "localhost", "::1"}
        with suppress(OSError):
            hostname = socket.gethostname()
            addresses.add(hostname.lower())
            for ip in socket.gethostbyname_ex(hostname)[2]:
                if ip:
                    addresses.add(ip.lower())
        return addresses

    def _local_camera_backends(self, cv2_module: Any) -> list[tuple[str, int]]:
        preferred = self._settings.camera_local_backend
        candidates: list[tuple[str, int]] = []
        if preferred == "dshow":
            candidates.append(("dshow", cv2_module.CAP_DSHOW))
        elif preferred == "msmf":
            candidates.append(("msmf", cv2_module.CAP_MSMF))
        elif preferred == "any":
            candidates.append(("any", cv2_module.CAP_ANY))
        else:
            candidates.extend(
                [
                    ("dshow", cv2_module.CAP_DSHOW),
                    ("any", cv2_module.CAP_ANY),
                    ("msmf", cv2_module.CAP_MSMF),
                ]
            )

        defaults = [
            ("dshow", cv2_module.CAP_DSHOW),
            ("any", cv2_module.CAP_ANY),
            ("msmf", cv2_module.CAP_MSMF),
        ]
        for item in defaults:
            if item not in candidates:
                candidates.append(item)
        return candidates

    def _mask_url(self, url: str | None) -> str | None:
        if not url:
            return None
        password = self._settings.camera_password
        return url.replace(password, "***") if password else url

    @staticmethod
    def _find_ffmpeg_audio_line(output: str) -> str | None:
        for line in output.splitlines():
            if " Audio: " in line:
                return line.strip()
        return None

    @staticmethod
    def _parse_ffmpeg_audio_line(line: str) -> tuple[str | None, int | None, int | None]:
        codec = None
        sample_rate = None
        channels = None
        marker = " Audio: "
        index = line.find(marker)
        if index >= 0:
            after = line[index + len(marker) :]
            codec = after.split(",", 1)[0].strip() or None

        for token in line.split(","):
            normalized = token.strip().lower()
            if normalized.endswith("hz"):
                digits = "".join(ch for ch in normalized if ch.isdigit())
                if digits:
                    sample_rate = int(digits)
            if "mono" in normalized:
                channels = 1
            elif "stereo" in normalized:
                channels = 2
        return codec, sample_rate, channels

    @classmethod
    def _read_pe_machine(cls, path: object) -> str | None:
        try:
            with open(path, "rb") as handle:
                handle.seek(0x3C)
                pe_offset = int.from_bytes(handle.read(4), "little")
                handle.seek(pe_offset + 4)
                machine = int.from_bytes(handle.read(2), "little")
        except OSError:
            return None
        return cls._PE_MACHINE_TYPES.get(machine, f"0x{machine:04X}")

    @staticmethod
    def _normalize_path(path: str) -> str:
        normalized = (path or "/tcp/av0_0").strip()
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"
        return normalized
