from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)
_serial_logger = logging.getLogger("serial_runtime")

from backend.api.alarm_api import router as alarm_router
from backend.api.agent_api import router as agent_router
from backend.api.auth_api import router as auth_router
from backend.api.care_api import router as care_router
from backend.api.chat_api import router as chat_router
from backend.api.device_api import router as device_router
from backend.api.health_api import router as health_router
from backend.api.relation_api import router as relation_router
from backend.api.user_api import router as user_router
from backend.api.voice_api import router as voice_router
from backend.api.omni_api import router as omni_router
from backend.config import get_settings
from backend.models.device_model import DeviceIngestMode, DeviceStatus
from backend.dependencies import (
    ensure_demo_overlay_history_window,
    get_alarm_service,
    get_care_service,
    get_data_generator,
    get_demo_data_status,
    get_device_service,
    get_parser,
    get_settings_dependency,
    get_websocket_manager,
    ingest_sample,
    publish_next_demo_overlay_sample,
    refresh_demo_overlay_samples,
    _serialize_alarm_queue_items,
)
from iot.mqtt_listener import MQTTGatewayListener
from iot.serial_reader import SerialGatewayReader


settings = get_settings()

_active_mock_watchers: dict[str, int] = defaultdict(int)
_active_mock_lock = asyncio.Lock()


async def _update_mock_watcher(device_mac: str, delta: int) -> None:
    normalized = device_mac.strip().upper()
    if not normalized:
        return
    async with _active_mock_lock:
        current = _active_mock_watchers.get(normalized, 0) + delta
        if current <= 0:
            _active_mock_watchers.pop(normalized, None)
        else:
            _active_mock_watchers[normalized] = current


async def _list_active_mock_macs() -> list[str]:
    async with _active_mock_lock:
        return [mac for mac, count in _active_mock_watchers.items() if count > 0]


def _resolve_alarm_subscription_macs(token: str | None) -> set[str] | None:
    normalized_token = str(token or "").strip()
    if not normalized_token:
        return None

    user = get_care_service().resolve_session(normalized_token)
    if user is None:
        return set()

    if user.role in {"community", "admin"}:
        return None

    if user.role == "family":
        family_id = user.family_id or user.id
        directory = get_care_service().get_family_directory(family_id)
        return {
            mac.upper()
            for elder in directory.elders
            for mac in (elder.device_macs or ([elder.device_mac] if elder.device_mac else []))
            if mac
        }

    if user.role == "elder":
        directory = get_care_service().get_directory()
        elder = next((item for item in directory.elders if item.id == user.id), None)
        return {
            mac.upper()
            for mac in ((elder.device_macs if elder else []) or ([elder.device_mac] if elder and elder.device_mac else []))
            if mac
        }

    return None


def _filter_alarm_queue_for_allowed_macs(
    queue: list[dict[str, object]],
    allowed_macs: set[str] | None,
) -> list[dict[str, object]]:
    if allowed_macs is None:
        return queue
    filtered: list[dict[str, object]] = []
    for item in queue:
        alarm = item.get("alarm", item)
        if not isinstance(alarm, dict):
            continue
        device_mac = str(alarm.get("device_mac", "")).strip().upper()
        if device_mac and device_mac in allowed_macs:
            filtered.append(item)
    return filtered


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    # 启动即保证虚拟设备至少有 24h 可分析历史
    ensure_demo_overlay_history_window(hours=24, step_minutes=10)
    tasks: list[asyncio.Task] = []
    if settings.mock_runtime_enabled:
        tasks.append(asyncio.create_task(_mock_stream_loop()))
    elif settings.enable_mock_overlay:
        tasks.append(asyncio.create_task(_demo_overlay_stream_loop()))
    if settings.serial_runtime_enabled:
        tasks.append(asyncio.create_task(_serial_stream_loop()))
    if settings.data_mode == "mqtt" and settings.mqtt_enabled:
        tasks.append(asyncio.create_task(_mqtt_stream_loop()))
    app.state.background_tasks = tasks
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.debug,
    summary="AIoT elder-care monitoring backend for the 2026 competition project.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(device_router, prefix=settings.api_v1_prefix)
app.include_router(user_router, prefix=settings.api_v1_prefix)
app.include_router(relation_router, prefix=settings.api_v1_prefix)
app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(alarm_router, prefix=settings.api_v1_prefix)
app.include_router(agent_router, prefix=settings.api_v1_prefix)
app.include_router(chat_router, prefix=settings.api_v1_prefix)
app.include_router(care_router, prefix=settings.api_v1_prefix)
app.include_router(voice_router, prefix=settings.api_v1_prefix)
app.include_router(omni_router, prefix=settings.api_v1_prefix)
app.include_router(auth_router, prefix=settings.api_v1_prefix)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


@app.get("/api/v1/system/info")
async def system_info() -> dict[str, object]:
    cfg = get_settings_dependency()
    active_target = get_device_service().get_active_serial_target()
    active_target_mac = active_target.mac_address if active_target else None
    active_target_name = active_target.device_name if active_target else None
    return {
        "runtime_mode": cfg.runtime_mode,
        "bootstrap_source": cfg.bootstrap_source,
        "bootstrap_status": cfg.bootstrap_status,
        "bootstrap_reason": cfg.bootstrap_reason,
        "competition_stack": {
            "python": "3.9+",
            "anaconda": "22.9.0",
            "ollama": "0.12.9",
            "approved_local_models": ["qwen3:1.7b", "deepseek-r1:1.5b"],
            "database": "PostgreSQL 15 / TimescaleDB",
        },
        "configured": {
            "data_mode": cfg.data_mode,
            "runtime_mode": cfg.runtime_mode,
            "mock_mode": cfg.mock_runtime_enabled,
            "mock_overlay_enabled": cfg.enable_mock_overlay,
            "serial_mode": cfg.serial_runtime_enabled,
            "mqtt_mode": cfg.data_mode == "mqtt" and cfg.mqtt_enabled,
            "mac_prefixes": cfg.allowed_mac_prefixes,
            "offline_only_runtime": cfg.offline_only_runtime,
            "llm_provider": cfg.llm_provider,
            "preferred_llm_provider": cfg.preferred_llm_provider,
            "default_agent_provider": "qwen",
            "qwen_configured": cfg.qwen_llm_configured,
            "qwen_missing_config_fields": cfg.qwen_missing_config_fields,
            "qwen_model": cfg.qwen_model,
            "local_model_routing": cfg.local_model_routing,
            "local_default_model": cfg.local_default_model,
            "strict_source_match": cfg.strict_source_match,
        },
        "serial_runtime": {
            "enabled": cfg.serial_runtime_enabled,
            "port": cfg.serial_port or "auto-detect",
            "baudrate": cfg.serial_baudrate,
            "collection_strategy": cfg.serial_collection_strategy,
            "packet_type": cfg.serial_packet_type,
            "mac_filter": cfg.serial_mac_filter,
            "auto_configure": cfg.serial_auto_configure,
            "broadcast_sos_overlay": cfg.serial_enable_broadcast_sos_overlay,
            "response_cycle_seconds": cfg.serial_response_cycle_seconds,
            "broadcast_cycle_seconds": cfg.serial_broadcast_cycle_seconds,
            "command_delay_seconds": cfg.serial_command_delay_seconds,
            "active_target_mac": active_target_mac,
            "active_target_device_name": active_target_name,
            "target_locked": active_target_mac is not None,
            "merge_mode": "wait_for_ab",
            "runtime_mode": cfg.runtime_mode,
            "bootstrap_source": cfg.bootstrap_source,
            "bootstrap_status": cfg.bootstrap_status,
            "bootstrap_reason": cfg.bootstrap_reason,
        },
        "demo_data": get_demo_data_status(),
    }


@app.get("/api/v1/system/demo-data/status")
async def demo_data_status() -> dict[str, object]:
    return get_demo_data_status()


@app.post("/api/v1/system/demo-data/refresh")
async def refresh_demo_data() -> dict[str, object]:
    refresh_summary = refresh_demo_overlay_samples()
    return {
        "status": "ok",
        "message": "community sample window refreshed",
        "refresh_summary": refresh_summary,
        "data": get_demo_data_status(),
    }


@app.websocket("/ws/health/{device_mac}")
async def health_stream(device_mac: str, websocket: WebSocket) -> None:
    manager = get_websocket_manager()
    normalized_mac = device_mac.strip().upper()
    device = get_device_service().get_device(normalized_mac)
    is_mock_device = bool(device and device.ingest_mode == DeviceIngestMode.MOCK)
    await manager.connect_health(normalized_mac, websocket)
    if is_mock_device:
        await _update_mock_watcher(normalized_mac, 1)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect_health(normalized_mac, websocket)
    finally:
        if is_mock_device:
            await _update_mock_watcher(normalized_mac, -1)


@app.websocket("/ws/alarms")
async def alarm_stream(websocket: WebSocket, token: str | None = Query(default=None)) -> None:
    manager = get_websocket_manager()
    allowed_macs = _resolve_alarm_subscription_macs(token)
    await manager.connect_alarm(websocket, allowed_macs=allowed_macs)
    try:
        queue = _serialize_alarm_queue_items(active_only=True)
        filtered_queue = _filter_alarm_queue_for_allowed_macs(queue, allowed_macs)
        await websocket.send_json(
            {
                "type": "alarm_queue",
                "queue": filtered_queue,
                "snapshot": {
                    **get_alarm_service().queue_snapshot(),
                    "length": len(filtered_queue),
                    "head": [
                        str(item.get("alarm", item).get("id", "")).strip()
                        for item in filtered_queue[:5]
                        if isinstance(item.get("alarm", item), dict)
                    ],
                },
            }
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect_alarm(websocket)


async def _mock_stream_loop() -> None:
    generator = get_data_generator()
    device_service = get_device_service()
    while True:
        now = datetime.now(timezone.utc)
        for persona in generator.personas:
            device = device_service.get_device(persona.mac_address)
            if device and device.status == DeviceStatus.OFFLINE:
                continue
            sample = generator.sample_for_device(persona.mac_address, now=now)
            await ingest_sample(sample)
        await asyncio.sleep(settings.mock_push_interval_seconds)


async def _demo_overlay_stream_loop() -> None:
    last_history_ensure = 0.0
    while True:
        active_mock_macs = await _list_active_mock_macs()
        if active_mock_macs:
            generator = get_data_generator()
            now = datetime.now(timezone.utc)
            device_service = get_device_service()
            for mac in active_mock_macs:
                device = device_service.get_device(mac)
                if not device or device.status == DeviceStatus.OFFLINE:
                    continue
                sample = generator.sample_for_device(mac, now=now)
                await ingest_sample(sample)

        publish_next_demo_overlay_sample()
        now_monotonic = asyncio.get_running_loop().time()
        # 每小时补齐一次，保证数据库中始终有至少一天 mock 历史
        if now_monotonic - last_history_ensure >= 3600:
            ensure_demo_overlay_history_window(hours=24, step_minutes=10)
            last_history_ensure = now_monotonic
        await asyncio.sleep(settings.mock_push_interval_seconds)


async def _serial_stream_loop() -> None:
    loop = asyncio.get_running_loop()
    reader = SerialGatewayReader(get_parser())

    def publish_from_thread(sample):
        _serial_logger.info(
            'Serial sample: mac=%s type=%s hr=%s spo2=%s temp=%s steps=%s bp=%s sos=%s',
            sample.device_mac,
            sample.packet_type,
            sample.heart_rate,
            sample.blood_oxygen,
            sample.temperature,
            sample.steps,
            sample.blood_pressure,
            sample.sos_flag,
        )
        if sample.sos_flag:
            _serial_logger.warning(
                '🚨 SOS DETECTED from %s (trigger=%s, value=%s, type=%s) — forwarding to ingest immediately',
                sample.device_mac,
                sample.sos_trigger,
                sample.sos_value,
                sample.packet_type,
            )
        future = asyncio.run_coroutine_threadsafe(ingest_sample(sample), loop)
        # Fire-and-forget: do NOT block the serial reader thread.
        # Attach an error callback so ingestion failures are logged
        # without stalling the serial data pipeline.
        def _on_done(fut):
            exc = fut.exception()
            if exc:
                _serial_logger.error("Ingest failed for %s: %s", sample.device_mac, exc)
        future.add_done_callback(_on_done)

    await asyncio.to_thread(
        reader.run,
        port=settings.serial_port or None,
        baudrate=settings.serial_baudrate,
        collection_strategy=settings.serial_collection_strategy,
        packet_type=settings.serial_packet_type,
        mac_filter=settings.serial_mac_filter,
        detection_keywords=settings.serial_detection_keywords,
        fallback_device_mac=settings.serial_fallback_device_mac or None,
        auto_configure=settings.serial_auto_configure,
        disable_uuid_output=settings.serial_disable_uuid_output,
        apply_mac_filter=settings.serial_apply_mac_filter,
        apply_packet_type=settings.serial_apply_packet_type,
        enable_broadcast_sos_overlay=settings.serial_enable_broadcast_sos_overlay,
        response_cycle_seconds=settings.serial_response_cycle_seconds,
        broadcast_cycle_seconds=settings.serial_broadcast_cycle_seconds,
        command_delay_seconds=settings.serial_command_delay_seconds,
        target_mac_provider=lambda: get_device_service().get_active_serial_target_mac(),
        on_sample=publish_from_thread,
    )


async def _mqtt_stream_loop() -> None:
    loop = asyncio.get_running_loop()
    listener = MQTTGatewayListener(get_parser())

    def publish_from_thread(sample):
        future = asyncio.run_coroutine_threadsafe(ingest_sample(sample), loop)
        future.result()

    await asyncio.to_thread(
        listener.run,
        settings.mqtt_broker_host,
        settings.mqtt_broker_port,
        settings.mqtt_topic,
        username=settings.mqtt_username or None,
        password=settings.mqtt_password or None,
        keepalive_seconds=settings.mqtt_keepalive_seconds,
        on_sample=publish_from_thread,
    )
