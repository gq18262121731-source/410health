from __future__ import annotations

from pydantic import BaseModel, Field


class StreamStartRequest(BaseModel):
    camera_id: str = Field(default="camera_01")
    rtsp_url: str | None = Field(
        default=None,
        description="RTSP URL, local file path, or mock://colorbars.",
    )


class StreamStopRequest(BaseModel):
    camera_id: str = Field(default="camera_01")


class StreamControlResponse(BaseModel):
    camera_id: str
    status: str
    message: str

