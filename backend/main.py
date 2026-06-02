from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse, urlunparse

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)
_serial_logger = logging.getLogger("serial_runtime")

from backend.api.alarm_api import router as alarm_router
from backend.api.agent_api import router as agent_router
from backend.api.auth_api import router as auth_router
from backend.api.camera_api import router as camera_router
from backend.api.camera_source_api import router as camera_source_router
from backend.api.care_api import router as care_router
from backend.api.chat_api import router as chat_router
from backend.api.device_api import router as device_router
from backend.api.health_api import router as health_router
from backend.api.model_finetune_api import router as model_finetune_router
from backend.api.relation_api import router as relation_router
from backend.api.target_user_api import router as target_user_router
from backend.api.user_api import router as user_router
from backend.api.video_bridge_api import router as video_bridge_router
from backend.api.voice_api import router as voice_router
from backend.api.omni_api import router as omni_router
from backend.config import get_settings
from backend.models.device_model import DeviceIngestMode, DeviceStatus
from backend.dependencies import (
    ensure_demo_overlay_history_window,
    resolve_alarm_visible_elder_ids,
    resolve_alarm_visible_family_ids,
    get_alarm_service,
    get_camera_audio_hub,
    get_camera_detection_frame_hub,
    get_camera_processed_frame_hub,
    get_camera_pose_frame_hub,
    get_camera_source_audio_hub,
    get_camera_source_frame_hub,
    get_camera_source_processed_frame_hub,
    get_camera_source_registry,
    get_care_service,
    get_camera_frame_hub,
    get_data_generator,
    get_demo_data_status,
    get_device_service,
    get_external_camera_bridge_service,
    get_fall_detection_service,
    get_pose_detection_service,
    get_parser,
    get_settings_dependency,
    get_target_user_fall_service,
    get_video_bridge_service,
    get_websocket_manager,
    ingest_sample,
    publish_next_demo_overlay_sample,
    refresh_demo_overlay_samples,
    resolve_alarm_visible_device_macs,
    resolve_session_user_by_token,
    shutdown_camera_source_hubs,
)
from iot.mqtt_listener import MQTTGatewayListener
from iot.serial_reader import SerialGatewayReader
from backend.serial_runtime_lock import SerialRuntimeLock, SerialRuntimeLockError


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


async def _start_fall_detection_after_startup() -> None:
    await asyncio.sleep(1.0)
    await get_fall_detection_service().start()


async def _start_pose_detection_after_startup() -> None:
    await asyncio.sleep(1.0)
    await get_pose_detection_service().start()


async def _warmup_target_user_vision_after_startup() -> None:
    await asyncio.sleep(2.0)
    try:
        result = await asyncio.to_thread(get_target_user_fall_service().warmup, speed_mode="low_latency")
        logger.info("Target-user realtime vision warmup finished: %s", result)
    except Exception:
        logger.exception("Target-user realtime vision warmup failed")


async def _ensure_demo_history_after_startup() -> None:
    await asyncio.sleep(0.5)
    try:
        result = await asyncio.to_thread(ensure_demo_overlay_history_window, hours=24, step_minutes=10)
        logger.info("Demo overlay history ensure finished: %s", result)
    except Exception:
        logger.exception("Demo overlay history ensure failed")


async def _recover_external_camera_runtime_after_startup() -> None:
    await asyncio.sleep(1.5)
    try:
        result = await asyncio.to_thread(get_external_camera_bridge_service().startup_recover)
        logger.info("External camera runtime bootstrap finished: %s", result)
    except Exception:
        logger.exception("External camera runtime bootstrap failed")


async def _mobile_safe_startup_supervisor(app: FastAPI) -> None:
    """Start optional workers only after the API is already responsive.

    On Windows, serial collectors, demo backfill, camera recovery, and pose
    subprocess startup can be slow. If they run directly in lifespan, the
    socket may be open while /healthz and the phone settings page still time
    out. The phone must be able to reconnect first; heavier workers can follow.
    """
    tasks: list[asyncio.Task] = app.state.background_tasks
    await asyncio.sleep(5.0)

    # Do not auto-start serial, MQTT, pose, fall, demo history, or external
    # camera probing from lifespan. In practice these workers can be CPU-heavy
    # or spawn child processes on Windows; starting them automatically made the
    # API become unresponsive shortly after /healthz first succeeded. The UI
    # and explicit API controls start detection/runtime work on demand instead.
    if settings.mock_runtime_enabled:
        tasks.append(asyncio.create_task(_mock_stream_loop()))


async def _vision_service_pull_loop() -> None:
    interval_seconds = 1.0 / max(0.2, min(5.0, float(settings.vision_service_poll_hz or 2.0)))
    service = get_video_bridge_service()
    while True:
        await asyncio.to_thread(service.poll_once)
        await asyncio.sleep(interval_seconds)


def _vision_service_frames_ws_url() -> str:
    base_url = settings.vision_service_base_url.rstrip("/")
    parsed = urlparse(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    query = urlencode(
        {
            "camera_id": settings.vision_service_camera_id or "camera_01",
            "source": "display",
            "fps": "5",
        }
    )
    return urlunparse((scheme, parsed.netloc, "/ws/frames", "", query, ""))


async def _vision_service_frame_relay_loop() -> None:
    import websockets

    ws_url = _vision_service_frames_ws_url()
    raw_hub = get_camera_source_frame_hub("active")
    processed_hub = get_camera_processed_frame_hub()
    while True:
        try:
            async with websockets.connect(
                ws_url,
                open_timeout=max(1.0, settings.vision_service_timeout_seconds),
                ping_interval=None,
                max_size=2_500_000,
            ) as websocket:
                logger.info("Vision frame relay connected: %s", ws_url)
                async for message in websocket:
                    if isinstance(message, str):
                        continue
                    await raw_hub.publish_external_frame(
                        message,
                        source_label="vision-service-ws-display",
                        decorate=False,
                    )
                    await processed_hub.publish_external_frame(
                        message,
                        source_label="vision-service-ws-display-light",
                        decorate=False,
                    )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Vision frame relay failed, retrying: %s", exc)
            await asyncio.sleep(1.5)


async def _vision_service_frame_proxy(websocket: WebSocket) -> None:
    import websockets

    await websocket.accept()
    ws_url = _vision_service_frames_ws_url()
    try:
        async with websockets.connect(
            ws_url,
            open_timeout=max(1.0, settings.vision_service_timeout_seconds),
            ping_interval=None,
            max_size=2_500_000,
        ) as upstream:
            logger.info("Vision frame proxy connected: %s", ws_url)
            async for message in upstream:
                if isinstance(message, str):
                    continue
                await websocket.send_bytes(message)
    except WebSocketDisconnect:
        return
    except Exception as exc:
        logger.warning("Vision frame proxy failed: %s", exc)
        with suppress(Exception):
            await websocket.close(code=1011, reason="vision_frame_proxy_failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    # 启动即保证虚拟设备至少有 24h 可分析历史
    tasks: list[asyncio.Task] = []
    uses_backend_camera_stream = getattr(settings, "camera_source_mode", "auto") != "local"
    camera_stream_keep_warm = bool(getattr(settings, "camera_stream_keep_warm", True))
    if camera_stream_keep_warm and uses_backend_camera_stream and not settings.vision_service_poll_enabled:
        # Keep only the raw active source warm. Processed/pose/fall streams are
        # comparatively expensive because they can trigger overlay inference;
        # starting them eagerly was starving the 8000 API layer and making the
        # mobile snapshot/stream proxy appear much slower than the 8090 runtime.
        await get_camera_source_frame_hub("active").start_keep_warm()
    app.state.background_tasks = tasks
    if settings.vision_service_poll_enabled:
        tasks.append(asyncio.create_task(_vision_service_pull_loop()))
    tasks.append(asyncio.create_task(_mobile_safe_startup_supervisor(app)))
    try:
        yield
    finally:
        await get_fall_detection_service().stop()
        await get_pose_detection_service().stop()
        await get_camera_audio_hub().shutdown()
        if camera_stream_keep_warm and uses_backend_camera_stream:
            await get_camera_source_frame_hub("active").stop_keep_warm()
            await get_camera_frame_hub().stop_keep_warm()
            await get_camera_processed_frame_hub().stop_keep_warm()
        await get_camera_detection_frame_hub().stop_keep_warm()
        await get_camera_pose_frame_hub().stop_keep_warm()
        await shutdown_camera_source_hubs()
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
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(device_router, prefix=settings.api_v1_prefix)
app.include_router(user_router, prefix=settings.api_v1_prefix)
app.include_router(relation_router, prefix=settings.api_v1_prefix)
app.include_router(target_user_router, prefix=settings.api_v1_prefix)
app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(alarm_router, prefix=settings.api_v1_prefix)
app.include_router(agent_router, prefix=settings.api_v1_prefix)
app.include_router(chat_router, prefix=settings.api_v1_prefix)
app.include_router(care_router, prefix=settings.api_v1_prefix)
app.include_router(voice_router, prefix=settings.api_v1_prefix)
app.include_router(omni_router, prefix=settings.api_v1_prefix)
app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(camera_router, prefix=settings.api_v1_prefix)
app.include_router(camera_source_router, prefix=settings.api_v1_prefix)
app.include_router(model_finetune_router, prefix=settings.api_v1_prefix)
app.include_router(video_bridge_router, prefix=settings.api_v1_prefix)


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
            "dual_collector_enabled": cfg.serial_dual_collector_enabled,
            "broadcast_port": cfg.serial_broadcast_port or None,
            "response_port": cfg.serial_response_port or None,
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
async def alarm_stream(websocket: WebSocket) -> None:
    manager = get_websocket_manager()
    query_token = websocket.query_params.get("token")
    auth_header = websocket.headers.get("authorization")
    header_token = None
    if auth_header:
        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() == "bearer" and token.strip():
            header_token = token.strip()

    session_token = query_token or header_token
    session_user = resolve_session_user_by_token(session_token)
    if session_token and session_user is None:
        await websocket.close(code=4401, reason="invalid_session")
        return

    visible_device_macs = resolve_alarm_visible_device_macs(session_user) if session_user else None
    visible_family_ids = resolve_alarm_visible_family_ids(session_user) if session_user else None
    visible_elder_ids = resolve_alarm_visible_elder_ids(session_user) if session_user else None
    allow_all = session_user is None or session_user.role.value in {"community", "admin"}
    await manager.connect_alarm(
        websocket,
        allow_all=allow_all,
        visible_device_macs=visible_device_macs,
        visible_family_ids=visible_family_ids,
        visible_elder_ids=visible_elder_ids,
    )
    try:
        initial_payload = {
            "type": "alarm_queue",
            "queue": [item.model_dump(mode="json") for item in get_alarm_service().queue_items(active_only=True)],
            "snapshot": get_alarm_service().queue_snapshot(),
        }
        scoped_initial_payload = manager.scope_alarm_payload_for_viewer(
            initial_payload,
            allow_all=allow_all,
            visible_device_macs=visible_device_macs,
            visible_family_ids=visible_family_ids,
            visible_elder_ids=visible_elder_ids,
        )
        if scoped_initial_payload is not None:
            await websocket.send_json(scoped_initial_payload)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect_alarm(websocket)


@app.websocket("/ws/camera")
async def camera_frame_stream(websocket: WebSocket) -> None:
    if settings.vision_service_poll_enabled:
        await _vision_service_frame_proxy(websocket)
        return
    hub = get_camera_source_frame_hub("active")
    await hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(websocket)
    finally:
        await hub.disconnect(websocket)


@app.websocket("/ws/camera/processed")
async def camera_processed_frame_stream(websocket: WebSocket) -> None:
    if settings.vision_service_poll_enabled:
        await _vision_service_frame_proxy(websocket)
        return
    hub = get_camera_processed_frame_hub()
    await hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(websocket)
    finally:
        await hub.disconnect(websocket)


@app.websocket("/ws/camera/pose")
async def camera_pose_frame_stream(websocket: WebSocket) -> None:
    hub = get_camera_pose_frame_hub()
    await hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(websocket)
    finally:
        await hub.disconnect(websocket)


@app.websocket("/ws/camera/detection")
async def camera_detection_frame_stream(websocket: WebSocket) -> None:
    hub = get_camera_detection_frame_hub()
    await hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(websocket)
    finally:
        await hub.disconnect(websocket)


@app.websocket("/ws/camera/audio/listen")
async def camera_audio_stream(websocket: WebSocket) -> None:
    hub = get_camera_source_audio_hub("active")
    await hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(websocket)
    finally:
        await hub.disconnect(websocket)


@app.websocket("/ws/camera-sources/{camera_id}")
async def camera_source_frame_stream(camera_id: str, websocket: WebSocket) -> None:
    try:
        hub = get_camera_source_frame_hub(camera_id)
    except KeyError:
        await websocket.close(code=4404, reason="camera_source_not_found")
        return
    await hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(websocket)
    finally:
        await hub.disconnect(websocket)


@app.websocket("/ws/camera-sources/{camera_id}/processed")
async def camera_source_processed_frame_stream(camera_id: str, websocket: WebSocket) -> None:
    try:
        hub = get_camera_source_processed_frame_hub(camera_id)
    except KeyError:
        await websocket.close(code=4404, reason="camera_source_not_found")
        return
    await hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(websocket)
    finally:
        await hub.disconnect(websocket)


@app.websocket("/ws/camera-sources/active")
async def active_camera_source_frame_stream(websocket: WebSocket) -> None:
    active = get_camera_source_registry().active_source()
    await camera_source_frame_stream(active.camera_id, websocket)


@app.websocket("/ws/camera-sources/{camera_id}/audio/listen")
async def camera_source_audio_stream(camera_id: str, websocket: WebSocket) -> None:
    try:
        hub = get_camera_source_audio_hub(camera_id)
    except KeyError:
        await websocket.close(code=4404, reason="camera_source_not_found")
        return
    await hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(websocket)


@app.websocket("/ws/camera-sources/active/audio/listen")
async def active_camera_source_audio_stream(websocket: WebSocket) -> None:
    active = get_camera_source_registry().active_source()
    await camera_source_audio_stream(active.camera_id, websocket)


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

        await asyncio.to_thread(publish_next_demo_overlay_sample)
        now_monotonic = asyncio.get_running_loop().time()
        # 每小时补齐一次，保证数据库中始终有至少一天 mock 历史
        if now_monotonic - last_history_ensure >= 3600:
            await asyncio.to_thread(ensure_demo_overlay_history_window, hours=24, step_minutes=10)
            last_history_ensure = now_monotonic
        await asyncio.sleep(settings.mock_push_interval_seconds)


async def _serial_stream_loop() -> None:
    lock_path = settings.data_dir / "locks" / "serial-runtime.lock"
    lock_retry_seconds = 5.0

    while True:
        try:
            with SerialRuntimeLock(lock_path):
                _serial_logger.info("Serial runtime lock acquired: %s", lock_path)
                await _run_serial_stream_locked()
        except SerialRuntimeLockError:
            _serial_logger.warning(
                "Serial runtime already active in another backend process, retrying in %.1fs: %s",
                lock_retry_seconds,
                lock_path,
            )
            await asyncio.sleep(lock_retry_seconds)


async def _run_serial_stream_locked() -> None:
    loop = asyncio.get_running_loop()
    reader = SerialGatewayReader(get_parser())

    def publish_from_thread(sample, collector_role: str = "serial"):
        _serial_logger.info(
            'Serial sample[%s]: mac=%s type=%s hr=%s spo2=%s temp=%s steps=%s bp=%s sos=%s',
            collector_role,
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
                'SOS DETECTED[%s] from %s (trigger=%s, value=%s, type=%s) forwarding to ingest immediately',
                collector_role,
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

    if settings.serial_dual_collector_enabled:
        broadcast_port = (settings.serial_broadcast_port or "").strip() or None
        response_port = (settings.serial_response_port or settings.serial_port or "").strip() or None
        if not broadcast_port or not response_port:
            raise RuntimeError(
                "Dual serial collector mode requires both SERIAL_BROADCAST_PORT and SERIAL_RESPONSE_PORT."
            )
        _serial_logger.info(
            "Dual serial collectors enabled: broadcast_port=%s (TYPE=4), response_port=%s (TYPE=5), mac_filter=%s",
            broadcast_port,
            response_port,
            settings.serial_mac_filter,
        )

        await asyncio.gather(
            asyncio.to_thread(
                reader.run,
                port=broadcast_port,
                baudrate=settings.serial_baudrate,
                collection_strategy=settings.serial_collection_strategy,
                packet_type=4,
                mac_filter=settings.serial_mac_filter,
                detection_keywords=settings.serial_detection_keywords,
                fallback_device_mac=settings.serial_fallback_device_mac or None,
                auto_configure=settings.serial_auto_configure,
                disable_uuid_output=settings.serial_disable_uuid_output,
                apply_mac_filter=settings.serial_apply_mac_filter,
                apply_packet_type=True,
                enable_broadcast_sos_overlay=False,
                response_cycle_seconds=settings.serial_response_cycle_seconds,
                broadcast_cycle_seconds=settings.serial_broadcast_cycle_seconds,
                command_delay_seconds=settings.serial_command_delay_seconds,
                target_mac_provider=lambda: get_device_service().get_active_serial_target_mac(),
                on_sample=lambda sample: publish_from_thread(sample, "broadcast"),
            ),
            asyncio.to_thread(
                reader.run,
                port=response_port,
                baudrate=settings.serial_baudrate,
                collection_strategy=settings.serial_collection_strategy,
                packet_type=5,
                mac_filter=settings.serial_mac_filter,
                detection_keywords=settings.serial_detection_keywords,
                fallback_device_mac=settings.serial_fallback_device_mac or None,
                auto_configure=settings.serial_auto_configure,
                disable_uuid_output=settings.serial_disable_uuid_output,
                apply_mac_filter=settings.serial_apply_mac_filter,
                apply_packet_type=True,
                enable_broadcast_sos_overlay=False,
                response_cycle_seconds=settings.serial_response_cycle_seconds,
                broadcast_cycle_seconds=settings.serial_broadcast_cycle_seconds,
                command_delay_seconds=settings.serial_command_delay_seconds,
                target_mac_provider=lambda: get_device_service().get_active_serial_target_mac(),
                on_sample=lambda sample: publish_from_thread(sample, "response"),
            ),
        )
        return

    _serial_logger.info(
        "Single serial collector enabled: port=%s, packet_type=%s, overlay=%s, mac_filter=%s",
        settings.serial_port or "auto-detect",
        settings.serial_packet_type,
        settings.serial_enable_broadcast_sos_overlay,
        settings.serial_mac_filter,
    )
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
        on_sample=lambda sample: publish_from_thread(sample, "single"),
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
