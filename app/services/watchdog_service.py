from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from app.camera.source_manager import CameraSourceManager
from app.core.config import Settings
from app.core.logger import get_logger
from app.monitoring.worker_health import WorkerHealthSnapshot
from app.services.detection_service import DetectionService
from app.services.pose_worker_service import PoseWorkerService
from app.services.result_publisher_service import ResultPublisherService

logger = get_logger(__name__)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WatchdogStatus:
    watchdog_enabled: bool = False
    watchdog_state: str = "disabled"
    watchdog_last_action: str | None = None
    watchdog_restart_count: int = 0
    watchdog_suppressed: bool = False
    degraded_reason: str | None = None
    last_checked_at: str | None = None
    last_action_at: str | None = None
    suppressed_workers: list[str] = field(default_factory=list)


class WatchdogService:
    def __init__(
        self,
        settings: Settings,
        source_manager: CameraSourceManager,
        detection_service: DetectionService,
        pose_worker_service: PoseWorkerService,
        result_publisher_service: ResultPublisherService,
    ) -> None:
        self.settings = settings
        self.source_manager = source_manager
        self.detection_service = detection_service
        self.pose_worker_service = pose_worker_service
        self.result_publisher_service = result_publisher_service
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._restart_history: dict[str, deque[float]] = defaultdict(deque)
        self._suppressed: set[str] = set()
        self._status = WatchdogStatus(watchdog_enabled=settings.watchdog_enabled)
        self._lock = threading.Lock()

    def start(self) -> None:
        if not self.settings.watchdog_enabled:
            with self._lock:
                self._status.watchdog_enabled = False
                self._status.watchdog_state = "disabled"
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="worker-watchdog", daemon=True)
        self._thread.start()
        with self._lock:
            self._status.watchdog_enabled = True
            self._status.watchdog_state = "normal"
        logger.info("watchdog_started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        with self._lock:
            self._status.watchdog_state = "disabled"
        logger.info("watchdog_stopped")

    def status(self) -> WatchdogStatus:
        with self._lock:
            return WatchdogStatus(
                watchdog_enabled=self._status.watchdog_enabled,
                watchdog_state=self._status.watchdog_state,
                watchdog_last_action=self._status.watchdog_last_action,
                watchdog_restart_count=self._status.watchdog_restart_count,
                watchdog_suppressed=self._status.watchdog_suppressed,
                degraded_reason=self._status.degraded_reason,
                last_checked_at=self._status.last_checked_at,
                last_action_at=self._status.last_action_at,
                suppressed_workers=sorted(self._suppressed),
            )

    def _run_loop(self) -> None:
        interval = max(0.1, self.settings.watchdog_check_interval_ms / 1000)
        while not self._stop_event.is_set():
            try:
                self._check_once()
            except Exception as exc:
                logger.exception("watchdog_check_failed")
                with self._lock:
                    self._status.watchdog_state = "degraded"
                    self._status.degraded_reason = f"watchdog_check_failed: {exc}"
            self._stop_event.wait(interval)

    def _check_once(self) -> None:
        with self._lock:
            self._status.last_checked_at = utc_now_iso()

        runtimes = self.source_manager.list_runtimes()
        if not runtimes:
            self._set_normal_if_possible()
            return

        for runtime in runtimes:
            camera_id = runtime.config.camera_id
            self._check_capture(camera_id)
            self._check_worker(
                worker_key=f"{camera_id}:detection",
                health=self.detection_service.status(camera_id).health,
                restart=lambda cid=camera_id: self._restart_detection(cid),
            )
            self._check_worker(
                worker_key=f"{camera_id}:pose",
                health=self.pose_worker_service.health(camera_id),
                restart=lambda cid=camera_id: self._restart_pose(cid),
            )
            self._check_worker(
                worker_key=f"{camera_id}:result_publisher",
                health=self.result_publisher_service.health(camera_id),
                restart=lambda cid=camera_id: self._restart_result_publisher(cid),
            )

        self._set_normal_if_possible()

    def _check_capture(self, camera_id: str) -> None:
        runtime = self.source_manager.get_runtime(camera_id)
        if runtime is None:
            return
        seen_workers: set[int] = set()
        for label, worker in (
            ("main_capture", runtime.main_worker),
            ("analysis_capture", runtime.analysis_worker),
        ):
            if worker is None:
                continue
            worker_id = id(worker)
            if worker_id in seen_workers:
                continue
            seen_workers.add(worker_id)
            status = worker.status()
            last_success_age_ms = self._iso_age_ms(status.last_frame_at)
            has_never_received_frame = status.last_frame_at is None
            stale = (
                not status.running
                or status.stream_state == "stale"
                or (
                    status.stream_state == "connecting"
                    and not has_never_received_frame
                    and last_success_age_ms > self.settings.watchdog_capture_stale_ms
                )
                or (status.frame_age_ms is not None and status.frame_age_ms > self.settings.watchdog_capture_stale_ms)
            )
            if stale:
                self._restart_if_allowed(
                    worker_key=f"{camera_id}:{label}",
                    reason=f"{label}_stale",
                    restart=lambda w=worker: self._restart_capture_worker(w),
                )

    def _check_worker(
        self,
        *,
        worker_key: str,
        health: WorkerHealthSnapshot | None,
        restart: Callable[[], None],
    ) -> None:
        if health is None:
            return
        stale = not health.worker_alive or self._iso_age_ms(health.heartbeat_at) > self.settings.watchdog_worker_heartbeat_timeout_ms
        if stale:
            self._restart_if_allowed(worker_key=worker_key, reason="heartbeat_timeout", restart=restart)

    def _restart_if_allowed(self, *, worker_key: str, reason: str, restart: Callable[[], None]) -> None:
        if worker_key in self._suppressed:
            self._mark_degraded(worker_key, f"suppressed_after_restarts:{reason}")
            return
        if not self._allow_restart(worker_key):
            self._suppressed.add(worker_key)
            self._mark_degraded(worker_key, f"max_restart_count_exceeded:{reason}")
            return

        try:
            restart()
            now = time.monotonic()
            self._restart_history[worker_key].append(now)
            action = f"restart {worker_key} reason={reason}"
            with self._lock:
                self._status.watchdog_state = "recovering"
                self._status.watchdog_last_action = action
                self._status.watchdog_restart_count += 1
                self._status.last_action_at = utc_now_iso()
                self._status.degraded_reason = None
                self._status.watchdog_suppressed = bool(self._suppressed)
            logger.warning("watchdog_action action=%s", action)
        except Exception as exc:
            logger.exception("watchdog_restart_failed worker=%s", worker_key)
            self._mark_degraded(worker_key, f"restart_failed:{exc}")

    def _allow_restart(self, worker_key: str) -> bool:
        max_count = self.settings.watchdog_max_restart_count
        if max_count <= 0:
            return True
        now = time.monotonic()
        window_sec = max(1.0, self.settings.watchdog_restart_window_ms / 1000)
        history = self._restart_history[worker_key]
        while history and now - history[0] > window_sec:
            history.popleft()
        return len(history) < max_count

    def _restart_capture_worker(self, worker) -> None:
        worker.stop()
        worker.start()

    def _restart_detection(self, camera_id: str) -> None:
        if not self.detection_service.restart_for_camera(camera_id):
            raise RuntimeError("detection worker did not stop before restart")

    def _restart_pose(self, camera_id: str) -> None:
        if not self.pose_worker_service.restart_for_camera(camera_id):
            raise RuntimeError("pose worker did not stop before restart")

    def _restart_result_publisher(self, camera_id: str) -> None:
        if not self.result_publisher_service.restart_for_camera(camera_id):
            raise RuntimeError("result publisher worker did not stop before restart")

    def _mark_degraded(self, worker_key: str, reason: str) -> None:
        with self._lock:
            self._status.watchdog_state = "degraded"
            self._status.watchdog_suppressed = True
            self._status.degraded_reason = f"{worker_key}:{reason}"
            self._status.last_action_at = utc_now_iso()
            self._status.suppressed_workers = sorted(self._suppressed)

    def _set_normal_if_possible(self) -> None:
        with self._lock:
            if self._suppressed:
                self._status.watchdog_state = "degraded"
                self._status.watchdog_suppressed = True
                return
            if self._status.watchdog_state in {"recovering", "normal"}:
                self._status.watchdog_state = "normal"
                self._status.watchdog_suppressed = False
                self._status.degraded_reason = None

    @staticmethod
    def _iso_age_ms(value: str | None) -> float:
        if not value:
            return float("inf")
        try:
            parsed = datetime.fromisoformat(value)
            return (datetime.now(timezone.utc) - parsed).total_seconds() * 1000
        except Exception:
            return float("inf")
