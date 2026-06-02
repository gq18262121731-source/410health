from __future__ import annotations

import argparse
import os
import queue
import sys
import threading
import time
from dataclasses import dataclass

import cv2

from app.camera.capture_process_protocol import pack_frame


@dataclass(frozen=True)
class CaptureProcessConfig:
    rtsp_url: str
    output_height: int
    jpeg_quality: int
    write_fps: float
    buffersize: int


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _mask_url(url: str) -> str:
    import re

    return re.sub(r"://([^:/@]+):([^@]+)@", r"://\1:***@", url)


def _resize_to_height(frame, output_height: int):
    if output_height <= 0:
        return frame
    height, width = frame.shape[:2]
    if height <= output_height:
        return frame
    scale = output_height / height
    new_width = max(1, int(width * scale))
    return cv2.resize(frame, (new_width, output_height), interpolation=cv2.INTER_AREA)


def _configure_ffmpeg_capture_options() -> None:
    options = os.getenv("OPENCV_FFMPEG_CAPTURE_OPTIONS", "").strip()
    if not options:
        return
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = options


def _configure_capture_timeouts(cap) -> None:
    timeout_ms = int(os.getenv("STREAM_STALE_THRESHOLD_MS", "3000"))
    buffersize = int(os.getenv("OPENCV_CAPTURE_BUFFERSIZE", "1"))
    try:
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_ms)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_ms)
    except Exception:
        pass
    if buffersize > 0:
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, buffersize)
        except Exception:
            pass


def _capture_loop(
    config: CaptureProcessConfig,
    stop_event: threading.Event,
    latest_queue: queue.Queue[tuple[int, int, int, int, bytes]],
) -> None:
    started_at = time.monotonic()
    _log(
        "capture_process_open_start "
        f"url={_mask_url(config.rtsp_url)} "
        f"output_height={config.output_height} "
        f"write_fps={config.write_fps} "
        f"buffersize={config.buffersize}"
    )
    _configure_ffmpeg_capture_options()
    cap = cv2.VideoCapture(config.rtsp_url, cv2.CAP_FFMPEG)
    _configure_capture_timeouts(cap)
    if not cap.isOpened():
        _log(
            "capture_process_open_failed "
            f"url={_mask_url(config.rtsp_url)} "
            f"elapsed_ms={round((time.monotonic() - started_at) * 1000, 2)}"
        )
        stop_event.set()
        return

    seq = 0
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), max(1, min(100, config.jpeg_quality))]
    source_fps = cap.get(cv2.CAP_PROP_FPS)
    _log(
        "capture_process_open_ok "
        f"url={_mask_url(config.rtsp_url)} "
        f"source_fps={round(float(source_fps), 2) if source_fps else 0.0} "
        f"elapsed_ms={round((time.monotonic() - started_at) * 1000, 2)}"
    )
    try:
        while not stop_event.is_set():
            ok, frame = cap.read()
            if not ok or frame is None:
                _log(
                    "capture_process_read_failed "
                    f"url={_mask_url(config.rtsp_url)} "
                    f"seq={seq} "
                    f"elapsed_ms={round((time.monotonic() - started_at) * 1000, 2)}"
                )
                stop_event.set()
                return
            frame = _resize_to_height(frame, config.output_height)
            ok, encoded = cv2.imencode(".jpg", frame, encode_params)
            if not ok:
                _log(
                    "capture_process_encode_failed "
                    f"url={_mask_url(config.rtsp_url)} "
                    f"seq={seq}"
                )
                continue
            seq += 1
            height, width = frame.shape[:2]
            payload = bytes(encoded)
            item = (seq, int(time.time() * 1000), width, height, payload)
            if seq == 1:
                _log(
                    "capture_process_first_frame_ok "
                    f"url={_mask_url(config.rtsp_url)} "
                    f"width={width} height={height} "
                    f"elapsed_ms={round((time.monotonic() - started_at) * 1000, 2)}"
                )
            while True:
                try:
                    latest_queue.get_nowait()
                except queue.Empty:
                    break
            try:
                latest_queue.put_nowait(item)
            except queue.Full:
                pass
    finally:
        cap.release()


def _writer_loop(
    config: CaptureProcessConfig,
    stop_event: threading.Event,
    latest_queue: queue.Queue[tuple[int, int, int, int, bytes]],
) -> None:
    min_interval = 1.0 / config.write_fps if config.write_fps > 0 else 0.0
    last_written_at = 0.0
    stdout = sys.stdout.buffer
    while not stop_event.is_set():
        try:
            item = latest_queue.get(timeout=0.2)
        except queue.Empty:
            continue
        now = time.monotonic()
        wait_for = min_interval - (now - last_written_at)
        if wait_for > 0:
            stop_event.wait(wait_for)
            if stop_event.is_set():
                return
        seq, timestamp_ms, width, height, payload = item
        packet = pack_frame(
            seq=seq,
            timestamp_ms=timestamp_ms,
            width=width,
            height=height,
            payload=payload,
        )
        try:
            stdout.write(packet)
            stdout.flush()
            last_written_at = time.monotonic()
        except BrokenPipeError:
            stop_event.set()
            return


def parse_args() -> CaptureProcessConfig:
    parser = argparse.ArgumentParser(description="OpenCV RTSP capture subprocess.")
    parser.add_argument("--rtsp-url", required=True)
    parser.add_argument("--output-height", type=int, default=int(os.getenv("CAPTURE_PROCESS_OUTPUT_HEIGHT", "720")))
    parser.add_argument("--jpeg-quality", type=int, default=int(os.getenv("CAPTURE_JPEG_QUALITY", "60")))
    parser.add_argument("--write-fps", type=float, default=float(os.getenv("CAPTURE_PROCESS_WRITE_FPS", "10")))
    parser.add_argument("--buffersize", type=int, default=int(os.getenv("OPENCV_CAPTURE_BUFFERSIZE", "1")))
    args = parser.parse_args()
    return CaptureProcessConfig(
        rtsp_url=args.rtsp_url,
        output_height=args.output_height,
        jpeg_quality=args.jpeg_quality,
        write_fps=args.write_fps,
        buffersize=args.buffersize,
    )


def main() -> int:
    config = parse_args()
    latest_queue: queue.Queue[tuple[int, int, int, int, bytes]] = queue.Queue(maxsize=1)
    stop_event = threading.Event()
    capture_thread = threading.Thread(
        target=_capture_loop,
        args=(config, stop_event, latest_queue),
        name="capture-process-reader",
        daemon=True,
    )
    writer_thread = threading.Thread(
        target=_writer_loop,
        args=(config, stop_event, latest_queue),
        name="capture-process-writer",
        daemon=True,
    )
    capture_thread.start()
    writer_thread.start()
    while not stop_event.is_set():
        if not capture_thread.is_alive():
            stop_event.set()
            break
        stop_event.wait(0.5)
    capture_thread.join(timeout=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
