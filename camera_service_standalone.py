from __future__ import annotations

import argparse
import logging
import time
from contextlib import suppress

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, Response
from fastapi.responses import StreamingResponse


logger = logging.getLogger("camera_service_standalone")


def build_app(*, camera_index: int, backend_name: str, fps: float, jpeg_quality: int) -> FastAPI:
    app = FastAPI(title="Camera Service")
    backend = _resolve_backend(backend_name)
    state = _CameraState(
        camera_index=camera_index,
        backend_name=backend_name,
        backend=backend,
        fps=max(0.5, fps),
        jpeg_quality=max(50, min(jpeg_quality, 95)),
    )

    @app.get("/")
    def root() -> dict[str, object]:
        return {
            "status": "running",
            "camera_initialized": state.camera is not None and state.camera.isOpened(),
            "camera_index": state.camera_index,
            "backend": state.backend_name,
            "fps": state.fps,
        }

    @app.get("/snapshot")
    def snapshot() -> Response:
        frame = state.get_frame_bytes()
        if frame is None:
            return Response(content="Camera not available", status_code=503)
        return Response(
            content=frame,
            media_type="image/jpeg",
            headers={
                "Cache-Control": "no-store, max-age=0",
                "X-Camera-Source": "local-standalone",
            },
        )

    @app.get("/stream.mjpg")
    def stream() -> StreamingResponse:
        def generate():
            frame_delay = 1.0 / state.fps
            while True:
                frame = state.get_frame_bytes()
                if frame is not None:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        + f"Content-Length: {len(frame)}\r\n\r\n".encode()
                        + frame
                        + b"\r\n"
                    )
                time.sleep(frame_delay)

        return StreamingResponse(
            generate(),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    @app.on_event("shutdown")
    def shutdown() -> None:
        state.release()

    return app


class _CameraState:
    def __init__(
        self,
        *,
        camera_index: int,
        backend_name: str,
        backend: int,
        fps: float,
        jpeg_quality: int,
    ) -> None:
        self.camera_index = camera_index
        self.backend_name = backend_name
        self.backend = backend
        self.fps = fps
        self.jpeg_quality = jpeg_quality
        self.camera: cv2.VideoCapture | None = None
        self.last_frame: bytes | None = None
        self.last_frame_time = 0.0
        self.frame_cache_ttl = min(0.3, max(0.05, 1.0 / max(2.0, fps)))

    def init_camera(self) -> bool:
        if self.camera is not None and self.camera.isOpened():
            return True

        self.release()
        try:
            self.camera = cv2.VideoCapture(self.camera_index, self.backend)
            if self.camera.isOpened():
                with suppress(Exception):
                    self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                with suppress(Exception):
                    self.camera.set(cv2.CAP_PROP_FPS, max(2.0, self.fps))
                logger.info(
                    "Camera initialized index=%s backend=%s",
                    self.camera_index,
                    self.backend_name,
                )
                return True
            logger.error(
                "Failed to open camera index=%s backend=%s",
                self.camera_index,
                self.backend_name,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error initializing camera: %s", exc)
        self.release()
        return False

    def get_frame_bytes(self) -> bytes | None:
        current_time = time.time()
        if self.last_frame is not None and (current_time - self.last_frame_time) < self.frame_cache_ttl:
            return self.last_frame

        if not self.init_camera():
            return None

        assert self.camera is not None
        try:
            deadline = time.monotonic() + 2.5
            while time.monotonic() < deadline:
                ok, frame = self.camera.read()
                if ok and frame is not None and _usable_frame(frame):
                    encoded = self._encode(frame)
                    if encoded is not None:
                        self.last_frame = encoded
                        self.last_frame_time = current_time
                        return encoded
                time.sleep(0.04)
            logger.warning("Frame read failed, reinitializing camera...")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error reading frame: %s", exc)
        self.release()
        return None

    def _encode(self, frame: np.ndarray) -> bytes | None:
        ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
        if not ok:
            return None
        return jpeg.tobytes()

    def release(self) -> None:
        if self.camera is not None:
            with suppress(Exception):
                self.camera.release()
        self.camera = None


def _usable_frame(frame: np.ndarray) -> bool:
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return float(np.mean(gray)) >= 8.0 and float(np.std(gray)) >= 6.0
    except Exception:  # noqa: BLE001
        return False


def _resolve_backend(name: str) -> int:
    normalized = name.strip().lower()
    if normalized == "dshow":
        return cv2.CAP_DSHOW
    if normalized == "msmf":
        return cv2.CAP_MSMF
    return cv2.CAP_ANY


def main() -> None:
    parser = argparse.ArgumentParser(description="Standalone local camera relay service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--backend", default="any", choices=["auto", "any", "dshow", "msmf"])
    parser.add_argument("--fps", type=float, default=6.0)
    parser.add_argument("--jpeg-quality", type=int, default=85)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    app = build_app(
        camera_index=args.camera_index,
        backend_name=args.backend,
        fps=args.fps,
        jpeg_quality=args.jpeg_quality,
    )
    logger.info(
        "Starting standalone camera service host=%s port=%s camera_index=%s backend=%s",
        args.host,
        args.port,
        args.camera_index,
        args.backend,
    )
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
