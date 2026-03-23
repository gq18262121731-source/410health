from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.api.alarm_api import router as alarm_router
from backend.api.auth_api import router as auth_router
from backend.api.care_api import router as care_router
from backend.api.chat_api import router as chat_router
from backend.api.device_api import router as device_router
from backend.api.health_api import router as health_router
from backend.api.relation_api import router as relation_router
from backend.api.user_api import router as user_router
from backend.config import get_settings
from backend.dependencies import (
    get_alarm_service,
    get_data_generator,
    get_parser,
    get_settings_dependency,
    get_websocket_manager,
    ingest_sample,
)
from iot.mqtt_listener import MQTTGatewayListener
from iot.serial_reader import SerialGatewayReader


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    tasks: list[asyncio.Task] = []
    if settings.data_mode == "mock" and settings.use_mock_data:
        tasks.append(asyncio.create_task(_mock_stream_loop()))
    if settings.data_mode == "serial" and settings.serial_enabled:
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
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(device_router, prefix=settings.api_v1_prefix)
app.include_router(user_router, prefix=settings.api_v1_prefix)
app.include_router(relation_router, prefix=settings.api_v1_prefix)
app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(alarm_router, prefix=settings.api_v1_prefix)
app.include_router(chat_router, prefix=settings.api_v1_prefix)
app.include_router(care_router, prefix=settings.api_v1_prefix)
app.include_router(auth_router, prefix=settings.api_v1_prefix)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


@app.get("/api/v1/system/info")
async def system_info() -> dict[str, object]:
    cfg = get_settings_dependency()
    return {
        "competition_stack": {
            "python": "3.9+",
            "anaconda": "22.9.0",
            "ollama": "0.12.9",
            "approved_local_models": ["qwen3:1.7b", "deepseek-r1:1.5b"],
            "database": "PostgreSQL 15 / TimescaleDB",
        },
        "configured": {
            "data_mode": cfg.data_mode,
            "mock_mode": cfg.data_mode == "mock" and cfg.use_mock_data,
            "serial_mode": cfg.data_mode == "serial" and cfg.serial_enabled,
            "mqtt_mode": cfg.data_mode == "mqtt" and cfg.mqtt_enabled,
            "mac_prefixes": cfg.allowed_mac_prefixes,
            "offline_only_runtime": cfg.offline_only_runtime,
            "local_model_routing": cfg.local_model_routing,
            "local_default_model": cfg.local_default_model,
        },
    }


@app.websocket("/ws/health/{device_mac}")
async def health_stream(device_mac: str, websocket: WebSocket) -> None:
    manager = get_websocket_manager()
    await manager.connect_health(device_mac, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect_health(device_mac, websocket)


@app.websocket("/ws/alarms")
async def alarm_stream(websocket: WebSocket) -> None:
    manager = get_websocket_manager()
    await manager.connect_alarm(websocket)
    try:
        await websocket.send_json(
            {
                "type": "alarm_queue",
                "queue": [item.model_dump(mode="json") for item in get_alarm_service().queue_items(active_only=True)],
                "snapshot": get_alarm_service().queue_snapshot(),
            }
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect_alarm(websocket)


async def _mock_stream_loop() -> None:
    generator = get_data_generator()
    while True:
        sample = generator.next_sample()
        await ingest_sample(sample)
        await asyncio.sleep(settings.mock_push_interval_seconds)


async def _serial_stream_loop() -> None:
    loop = asyncio.get_running_loop()
    reader = SerialGatewayReader(get_parser())

    def publish_from_thread(sample):
        future = asyncio.run_coroutine_threadsafe(ingest_sample(sample), loop)
        future.result()

    await asyncio.to_thread(
        reader.run,
        port=settings.serial_port or None,
        baudrate=settings.serial_baudrate,
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
