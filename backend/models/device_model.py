from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import re
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from backend.config import get_settings


MAC_ADDRESS_PATTERN = re.compile(r"^[0-9A-F]{2}(?::[0-9A-F]{2}){5}$")


def normalize_and_validate_mac(value: str) -> str:
    normalized = value.strip().upper()
    if not MAC_ADDRESS_PATTERN.fullmatch(normalized):
        raise ValueError("INVALID_MAC_ADDRESS")

    allowed_prefixes = [prefix.strip().upper() for prefix in get_settings().allowed_mac_prefixes if prefix.strip()]
    if allowed_prefixes and not any(normalized.startswith(prefix) for prefix in allowed_prefixes):
        raise ValueError("INVALID_MAC_PREFIX")
    return normalized


class DeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    WARNING = "warning"


class DeviceBindStatus(str, Enum):
    UNBOUND = "unbound"
    BOUND = "bound"
    DISABLED = "disabled"


class DeviceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    mac_address: str
    device_name: str = "T10-WATCH"
    user_id: str | None = None
    status: DeviceStatus = DeviceStatus.OFFLINE
    bind_status: DeviceBindStatus = DeviceBindStatus.UNBOUND
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("mac_address")
    @classmethod
    def normalize_mac(cls, value: str) -> str:
        return normalize_and_validate_mac(value)


class DeviceRegisterRequest(BaseModel):
    mac_address: str
    device_name: str = "T10-WATCH"
    user_id: str | None = None

    @field_validator("mac_address")
    @classmethod
    def validate_mac_address(cls, value: str) -> str:
        return normalize_and_validate_mac(value)
