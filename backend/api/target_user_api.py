from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile

from backend.config import get_settings
from backend.dependencies import (
    get_external_camera_bridge_service,
    get_target_user_fall_service,
    get_target_user_service,
)
from backend.models.target_user_model import TargetUserCreateResponse, TargetUserDeleteResponse, TargetUserMatchResult, TargetUserRecord
from backend.services.camera_service import CameraService


router = APIRouter(prefix="/target-users", tags=["target-users"])


@router.get("", response_model=list[TargetUserRecord])
async def list_target_users() -> list[TargetUserRecord]:
    return get_target_user_service().list_users()


@router.get("/status")
async def target_user_status() -> dict:
    service = get_target_user_service()
    return {
        "user_count": len(service.list_users()),
        "face_model": service.face_model_status(),
    }


@router.post("", response_model=TargetUserCreateResponse)
async def create_target_user(
    display_name: str = Form(...),
    group: str = Form("default"),
    note: str = Form(""),
    files: list[UploadFile] = File(...),
) -> TargetUserCreateResponse:
    image_blobs: list[bytes] = []
    for file in files:
        content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
        if content_type and content_type not in {"image/jpeg", "image/jpg", "image/png", "image/webp", "application/octet-stream"}:
            raise HTTPException(status_code=400, detail="UNSUPPORTED_IMAGE_FORMAT")
        blob = await file.read()
        if len(blob) < 100:
            continue
        image_blobs.append(blob)

    if not image_blobs:
        raise HTTPException(status_code=400, detail="TARGET_USER_IMAGES_REQUIRED")

    try:
        return get_target_user_service().create_user(
            display_name=display_name,
            group=group,
            note=note,
            image_blobs=image_blobs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{user_id}", response_model=TargetUserDeleteResponse)
async def delete_target_user(user_id: str) -> TargetUserDeleteResponse:
    try:
        return get_target_user_service().delete_user(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/match", response_model=TargetUserMatchResult)
async def match_target_user(file: UploadFile = File(...)) -> TargetUserMatchResult:
    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if content_type and content_type not in {"image/jpeg", "image/jpg", "image/png", "image/webp", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="UNSUPPORTED_IMAGE_FORMAT")

    blob = await file.read()
    if len(blob) < 100:
        raise HTTPException(status_code=400, detail="TARGET_USER_IMAGES_REQUIRED")
    return get_target_user_service().match_target_from_image(blob)


@router.post("/fall-detect")
async def target_user_fall_detect(
    file: UploadFile = File(...),
    mode: str = "metadata",
    target_only: bool = True,
    session_id: str = "default",
) -> dict:
    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if content_type and content_type not in {"image/jpeg", "image/jpg", "image/png", "image/webp", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="UNSUPPORTED_IMAGE_FORMAT")
    blob = await file.read()
    if len(blob) < 100:
        raise HTTPException(status_code=400, detail="TARGET_USER_IMAGES_REQUIRED")
    include_annotated_image = mode.strip().lower() != "metadata"
    return get_target_user_fall_service().detect(
        blob,
        include_annotated_image=include_annotated_image,
        target_only=target_only,
        session_id=session_id,
    )


@router.get("/external-camera/health")
async def external_camera_health() -> dict:
    return get_external_camera_bridge_service().health()


@router.post("/external-camera/fall-detect")
async def external_camera_fall_detect(
    target_only: bool = True,
    session_id: str = "default",
    mode: str = "metadata",
) -> dict:
    include_annotated_image = mode.strip().lower() != "metadata"
    return get_external_camera_bridge_service().detect_latest(
        session_id=session_id,
        target_only=target_only,
        include_annotated_image=include_annotated_image,
    )


@router.get("/local-camera/snapshot")
async def local_camera_snapshot() -> Response:
    settings = get_settings().model_copy(update={"camera_source_mode": "local"})
    try:
        image_bytes, headers = await __import__("asyncio").to_thread(CameraService(settings).capture_local_jpeg)
    except RuntimeError as exc:
        code = str(exc)
        raise HTTPException(status_code=503, detail=code) from exc
    return Response(content=image_bytes, media_type="image/jpeg", headers=headers)


@router.post("/local-camera/pose-detect")
async def local_camera_pose_detect(
    target_only: bool = True,
    session_id: str = "default",
    mode: str = "metadata",
) -> dict:
    settings = get_settings().model_copy(update={"camera_source_mode": "local"})
    try:
        image_bytes, _headers = await __import__("asyncio").to_thread(CameraService(settings).capture_local_jpeg)
    except RuntimeError as exc:
        code = str(exc)
        raise HTTPException(status_code=503, detail=code) from exc

    include_annotated_image = mode.strip().lower() != "metadata"
    api_base = f"http://127.0.0.1:{settings.port}{settings.api_v1_prefix}"
    return get_external_camera_bridge_service().detect_image_bytes(
        image_bytes,
        session_id=session_id,
        target_only=target_only,
        include_annotated_image=include_annotated_image,
        camera_source={
            "viewer_url": f"{api_base}/camera/stream.mjpg",
            "snapshot_url": f"{api_base}/target-users/local-camera/snapshot",
            "mjpeg_url": f"{api_base}/camera/stream.mjpg",
            "source_kind": "local_camera",
        },
    )
