from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from backend.dependencies import get_device_service, require_write_session_user
from backend.models.auth_model import SessionUser
from backend.models.device_bind_model import DeviceBindLogRecord, DeviceBindRequest, DeviceRebindRequest, DeviceUnbindRequest
from backend.models.device_model import DeviceRecord, DeviceRegisterRequest


router = APIRouter(prefix="/devices", tags=["devices"])


def _require_writer(authorization: str | None) -> SessionUser:
    try:
        return require_write_session_user(authorization)
    except ValueError as exc:
        code = str(exc)
        if code in {"AUTH_REQUIRED", "INVALID_SESSION"}:
            raise HTTPException(status_code=401, detail=code) from exc
        raise HTTPException(status_code=403, detail=code) from exc


@router.get("", response_model=list[DeviceRecord])
async def list_devices() -> list[DeviceRecord]:
    return get_device_service().list_devices()


@router.get("/{mac_address}", response_model=DeviceRecord)
async def get_device(mac_address: str) -> DeviceRecord:
    device = get_device_service().get_device(mac_address)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.get("/{mac_address}/bind-logs", response_model=list[DeviceBindLogRecord])
async def list_device_bind_logs(mac_address: str) -> list[DeviceBindLogRecord]:
    return get_device_service().list_bind_logs(mac_address)


@router.post("/register", response_model=DeviceRecord)
async def register_device(payload: DeviceRegisterRequest, authorization: str | None = Header(default=None)) -> DeviceRecord:
    operator = _require_writer(authorization)
    try:
        return get_device_service().register_device(payload, operator_id=operator.id)
    except ValueError as exc:
        code = str(exc)
        if code == "DEVICE_ALREADY_EXISTS":
            raise HTTPException(status_code=409, detail=code) from exc
        if code == "TARGET_USER_ALREADY_HAS_DEVICE_OF_SAME_MODEL":
            raise HTTPException(status_code=409, detail=code) from exc
        if code == "USER_NOT_FOUND":
            raise HTTPException(status_code=404, detail=code) from exc
        raise HTTPException(status_code=400, detail=code) from exc


@router.post("/bind", response_model=DeviceBindLogRecord)
async def bind_device(payload: DeviceBindRequest, authorization: str | None = Header(default=None)) -> DeviceBindLogRecord:
    _require_writer(authorization)
    try:
        return get_device_service().bind_device(payload)
    except ValueError as exc:
        code = str(exc)
        if code in {"DEVICE_NOT_FOUND", "USER_NOT_FOUND"}:
            raise HTTPException(status_code=404, detail=code) from exc
        if code in {"DEVICE_ALREADY_BOUND", "DEVICE_ALREADY_BOUND_TO_TARGET", "TARGET_USER_ALREADY_HAS_DEVICE_OF_SAME_MODEL"}:
            raise HTTPException(status_code=409, detail=code) from exc
        raise HTTPException(status_code=400, detail=code) from exc


@router.post("/unbind", response_model=DeviceBindLogRecord)
async def unbind_device(payload: DeviceUnbindRequest, authorization: str | None = Header(default=None)) -> DeviceBindLogRecord:
    _require_writer(authorization)
    try:
        return get_device_service().unbind_device(payload)
    except ValueError as exc:
        code = str(exc)
        if code == "DEVICE_NOT_FOUND":
            raise HTTPException(status_code=404, detail=code) from exc
        raise HTTPException(status_code=400, detail=code) from exc


@router.post("/rebind", response_model=DeviceBindLogRecord)
async def rebind_device(payload: DeviceRebindRequest, authorization: str | None = Header(default=None)) -> DeviceBindLogRecord:
    _require_writer(authorization)
    try:
        return get_device_service().rebind_device(payload)
    except ValueError as exc:
        code = str(exc)
        if code in {"DEVICE_NOT_FOUND", "USER_NOT_FOUND"}:
            raise HTTPException(status_code=404, detail=code) from exc
        if code in {"DEVICE_ALREADY_BOUND_TO_TARGET", "TARGET_USER_ALREADY_HAS_DEVICE_OF_SAME_MODEL"}:
            raise HTTPException(status_code=409, detail=code) from exc
        raise HTTPException(status_code=400, detail=code) from exc


@router.delete("/{mac_address}", response_model=DeviceRecord)
async def delete_device(mac_address: str, authorization: str | None = Header(default=None)) -> DeviceRecord:
    _require_writer(authorization)
    try:
        return get_device_service().delete_device(mac_address)
    except ValueError as exc:
        code = str(exc)
        if code == "DEVICE_NOT_FOUND":
            raise HTTPException(status_code=404, detail=code) from exc
        raise HTTPException(status_code=400, detail=code) from exc
