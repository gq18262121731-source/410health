from __future__ import annotations

import re
from dataclasses import dataclass


def mask_source_url(source_url: str | None) -> str | None:
    if not source_url:
        return source_url
    return re.sub(r"://([^:/@]+):([^@]+)@", r"://\1:***@", source_url)


@dataclass(frozen=True)
class CameraSourceConfig:
    camera_id: str
    source_url: str
    main_source_url: str | None = None
    analysis_source_url: str | None = None
    output_height: int | None = None
    jpeg_quality: int | None = None
    write_fps: float | None = None
