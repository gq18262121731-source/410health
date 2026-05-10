from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import BASE_DIR, Settings


@dataclass(frozen=True, slots=True)
class CameraSourceConfig:
    """A neutral camera source. Business consumers decide how to use it."""

    camera_id: str
    name: str
    ip: str
    user: str
    password: str
    rtsp_port: int
    onvif_port: int
    rtsp_path: str
    stream_rtsp_path: str
    audio_rtsp_path: str
    source: str
    source_mode: str = "rtsp"
    device_id: str = ""
    enabled: bool = True


class CameraSourceRegistry:
    """Build camera sources from runtime registration plus safe env fallbacks."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._registry_path = settings.data_dir / "camera_registry.json"

    def list_sources(self) -> list[CameraSourceConfig]:
        sources = [self._local_camera()]
        sources.extend(self._registered_external_sources())
        sources.extend([self._camera1(), self._camera2()])
        deduped: dict[str, CameraSourceConfig] = {}
        for source in sources:
            if source.enabled and source.camera_id not in deduped:
                deduped[source.camera_id] = source
        return list(deduped.values())

    def get_source(self, camera_id: str) -> CameraSourceConfig:
        normalized = camera_id.strip().lower()
        if normalized == "active":
            return self.active_source()
        for source in self.list_sources():
            if source.camera_id == normalized:
                return source
        raise KeyError("CAMERA_SOURCE_NOT_FOUND")

    def active_source(self) -> CameraSourceConfig:
        payload = self._load_registry()
        active_camera_id = str(payload.get("active_camera_id") or "").strip().lower()
        if active_camera_id and active_camera_id != "active":
            try:
                return self.get_source(active_camera_id)
            except KeyError:
                pass
        for source in self.list_sources():
            if source.camera_id != "local":
                return source
        return self.get_source("local")

    def settings_for(self, camera_id: str) -> Settings:
        source = self.get_source(camera_id)
        if source.source_mode == "local":
            return self._settings.model_copy(
                update={
                    "camera_source_mode": "local",
                    "camera_ip": "",
                    "camera_rtsp_path": "",
                    "camera_stream_rtsp_path": "",
                    "camera_audio_rtsp_path": "",
                }
            )
        return self._settings.model_copy(
            update={
                "camera_ip": source.ip,
                "camera_user": source.user,
                "camera_password": source.password,
                "camera_rtsp_port": source.rtsp_port,
                "camera_onvif_port": source.onvif_port,
                "camera_rtsp_path": source.rtsp_path,
                "camera_stream_rtsp_path": source.stream_rtsp_path,
                "camera_audio_rtsp_path": source.audio_rtsp_path,
                "camera_source_mode": "rtsp",
            }
        )

    def active_settings(self) -> Settings:
        return self.settings_for(self.active_source().camera_id)

    def public_source(self, source: CameraSourceConfig) -> dict[str, Any]:
        return {
            "camera_id": source.camera_id,
            "name": source.name,
            "enabled": source.enabled,
            "source": source.source,
            "ip": source.ip,
            "rtsp_port": source.rtsp_port,
            "onvif_port": source.onvif_port,
            "rtsp_path": source.rtsp_path,
            "stream_rtsp_path": source.stream_rtsp_path,
            "audio_rtsp_path": source.audio_rtsp_path,
            "has_password": bool(source.password),
            "source_mode": source.source_mode,
            "device_id": source.device_id,
        }

    def registration_status(self) -> dict[str, Any]:
        active = self.active_source()
        return {
            "active_camera_id": active.camera_id,
            "active_source": self.public_source(active),
            "sources": [self.public_source(source) for source in self.list_sources()],
            "registry_path": str(self._registry_path),
        }

    def select_source(self, camera_id: str) -> dict[str, Any]:
        source = self.get_source(camera_id)
        payload = self._load_registry()
        payload["active_camera_id"] = source.camera_id
        self._save_registry(payload)
        return self.registration_status()

    def select_local(self) -> dict[str, Any]:
        return self.select_source("local")

    def register_external(self, device_id: str, name: str = "") -> dict[str, Any]:
        normalized_device_id = device_id.strip()
        if not normalized_device_id:
            raise ValueError("CAMERA_DEVICE_ID_REQUIRED")
        payload = self._load_registry()
        devices = list(payload.get("external_devices") or [])
        camera_id = self._external_camera_id(normalized_device_id)
        next_record = {
            "camera_id": camera_id,
            "device_id": normalized_device_id,
            "name": name.strip() or f"外接摄像头 {normalized_device_id}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        replaced = False
        for index, item in enumerate(devices):
            if str(item.get("device_id") or "").strip().lower() == normalized_device_id.lower():
                devices[index] = {**item, **next_record}
                replaced = True
                break
        if not replaced:
            devices.append(next_record)
        payload["external_devices"] = devices
        payload["active_camera_id"] = camera_id
        self._save_registry(payload)
        return self.registration_status()

    def delete_external(self, camera_id: str) -> dict[str, Any]:
        normalized = camera_id.strip().lower()
        if normalized == "local":
            raise ValueError("LOCAL_CAMERA_CANNOT_BE_DELETED")
        payload = self._load_registry()
        devices = [item for item in list(payload.get("external_devices") or []) if str(item.get("camera_id") or "").lower() != normalized]
        payload["external_devices"] = devices
        if str(payload.get("active_camera_id") or "").lower() == normalized:
            payload["active_camera_id"] = "local"
        self._save_registry(payload)
        return self.registration_status()

    def _local_camera(self) -> CameraSourceConfig:
        return CameraSourceConfig(
            camera_id="local",
            name="本地摄像头",
            ip="",
            user="",
            password="",
            rtsp_port=0,
            onvif_port=0,
            rtsp_path="",
            stream_rtsp_path="",
            audio_rtsp_path="",
            source="built-in-local",
            source_mode="local",
            enabled=True,
        )

    def _registered_external_sources(self) -> list[CameraSourceConfig]:
        sources: list[CameraSourceConfig] = []
        for record in list(self._load_registry().get("external_devices") or []):
            device_id = str(record.get("device_id") or "").strip()
            if not device_id:
                continue
            base = self._camera1()
            sources.append(
                CameraSourceConfig(
                    camera_id=str(record.get("camera_id") or self._external_camera_id(device_id)).strip().lower(),
                    name=str(record.get("name") or f"外接摄像头 {device_id}").strip(),
                    ip=base.ip,
                    user=base.user,
                    password=base.password,
                    rtsp_port=base.rtsp_port,
                    onvif_port=base.onvif_port,
                    rtsp_path=base.rtsp_path,
                    stream_rtsp_path=base.stream_rtsp_path,
                    audio_rtsp_path=base.audio_rtsp_path,
                    source="registered-external",
                    source_mode="rtsp",
                    device_id=device_id,
                    enabled=bool(base.ip),
                )
            )
        return sources

    def _camera1(self) -> CameraSourceConfig:
        settings = self._settings
        ip = settings.camera1_ip.strip() or settings.camera_ip.strip()
        return CameraSourceConfig(
            camera_id="camera1",
            name=settings.camera1_name.strip() or "camera1",
            ip=ip,
            user=settings.camera1_user.strip() or settings.camera_user.strip() or "admin",
            password=settings.camera1_password or settings.camera_password,
            rtsp_port=settings.camera1_rtsp_port or settings.camera_rtsp_port,
            onvif_port=settings.camera1_onvif_port or settings.camera_onvif_port,
            rtsp_path=self._path_or_default(settings.camera1_rtsp_path, settings.camera_rtsp_path),
            stream_rtsp_path=self._path_or_default(settings.camera1_stream_rtsp_path, settings.camera_stream_rtsp_path),
            audio_rtsp_path=self._path_or_default(settings.camera1_audio_rtsp_path, settings.camera_audio_rtsp_path),
            source="legacy-env" if not settings.camera1_ip.strip() else "camera1-env",
            enabled=bool(ip),
        )

    def _camera2(self) -> CameraSourceConfig:
        settings = self._settings
        external = self._load_external_runtime_camera()
        ip = settings.camera2_ip.strip() or str(external.get("host") or "").strip()
        user = settings.camera2_user.strip() or str(external.get("username") or "").strip() or "admin"
        password = settings.camera2_password or str(external.get("password") or "")
        rtsp_port = settings.camera2_rtsp_port or int(external.get("rtsp_port") or 10554)
        fallback_path = self._external_runtime_path(external)
        return CameraSourceConfig(
            camera_id="camera2",
            name=settings.camera2_name.strip() or "camera2",
            ip=ip,
            user=user,
            password=password,
            rtsp_port=rtsp_port,
            onvif_port=settings.camera2_onvif_port or 10080,
            rtsp_path=self._path_or_default(settings.camera2_rtsp_path, fallback_path),
            stream_rtsp_path=self._path_or_default(settings.camera2_stream_rtsp_path, fallback_path),
            audio_rtsp_path=self._path_or_default(settings.camera2_audio_rtsp_path, fallback_path),
            source="camera2-env" if settings.camera2_ip.strip() else "external-runtime-config",
            enabled=bool(ip),
        )

    def _load_external_runtime_camera(self) -> dict[str, Any]:
        for filename in ["camera_live_config.runtime.json", "camera_live_config.json"]:
            path = BASE_DIR / "camera_runtime_external" / filename
            if not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            camera = payload.get("camera")
            if isinstance(camera, dict):
                return camera
        return {}

    def _external_runtime_path(self, payload: dict[str, Any]) -> str:
        transport = str(payload.get("transport") or "tcp").strip().strip("/")
        stream = str(payload.get("stream") or "av0_1").strip().strip("/")
        return f"/{transport or 'tcp'}/{stream or 'av0_1'}"

    def _path_or_default(self, value: str, fallback: str) -> str:
        selected = (value or fallback or "/tcp/av0_1").strip()
        return selected if selected.startswith("/") else f"/{selected}"

    def _load_registry(self) -> dict[str, Any]:
        if not self._registry_path.is_file():
            return {"active_camera_id": "", "external_devices": []}
        try:
            payload = json.loads(self._registry_path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {"active_camera_id": "", "external_devices": []}
        if not isinstance(payload, dict):
            return {"active_camera_id": "", "external_devices": []}
        if not isinstance(payload.get("external_devices"), list):
            payload["external_devices"] = []
        return payload

    def _save_registry(self, payload: dict[str, Any]) -> None:
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._registry_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _external_camera_id(self, device_id: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", device_id.strip()).strip("-").lower()
        return f"external-{slug or 'camera'}"
