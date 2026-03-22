from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Application settings aligned with the 2026 competition platform."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AIoT Elder Care Monitoring System"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    debug: bool = True

    host: str = "0.0.0.0"
    port: int = 8000

    allowed_mac_prefixes: list[str] = Field(default_factory=lambda: ["53:57:08"])
    default_device_name: str = "T10-WATCH"
    device_uuid: str = "52616469-6F6C-616E-642D-541000000000"
    service_uuid: str = "00001803-494c-4f47-4943-544543480000"

    database_url: str = f"sqlite+aiosqlite:///{(BASE_DIR / 'data' / 'app.db').as_posix()}"
    redis_url: str = "redis://localhost:6379/0"
    chroma_path: str = str(BASE_DIR / "data" / "chroma")

    offline_only_runtime: bool = True
    local_model_routing: Literal["single", "task_router"] = "task_router"
    local_report_routing: Literal["fixed", "role_router"] = "fixed"
    local_approved_models: Annotated[
        list[str],
        NoDecode,
    ] = Field(default_factory=lambda: ["qwen3:1.7b", "deepseek-r1:1.5b"])
    local_default_model: str = "qwen3:1.7b"
    local_reasoning_model: str = "deepseek-r1:1.5b"
    local_report_model: str = "deepseek-r1:1.5b"

    qwen_api_base: str = ""
    qwen_api_key: str = ""
    qwen_model: str = ""
    qwen_embedding_model: str = ""
    qwen_rerank_model: str = ""
    qwen_rerank_api: str = ""
    qwen_enable_rerank: bool = False

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:1.7b"

    llm_timeout_seconds: int = 10
    dialogue_max_predict_tokens: int = 320
    dialogue_max_output_chars: int = 900
    rag_timeout_seconds: int = 15
    rag_top_k: int = 3
    rag_fetch_k: int = 8
    rag_chunk_size: int = 700
    rag_chunk_overlap: int = 150

    network_probe_url: str = ""
    network_probe_timeout_seconds: int = 3
    network_probe_cache_seconds: int = 20

    jwt_secret: str = "replace-me-in-production"
    ws_heartbeat_seconds: int = 30

    realtime_window_size: int = 30
    zscore_threshold: float = 2.4
    mock_device_count: int = 10
    mock_push_interval_seconds: float = 1.2
    use_mock_data: bool = True
    data_mode: Literal["mock", "serial", "mqtt"] = "mock"
    serial_enabled: bool = False
    serial_port: str = ""
    serial_baudrate: int = 115200
    serial_packet_type: int = 5
    serial_mac_filter: str = "535708000000"
    serial_detection_keywords: list[str] = Field(
        default_factory=lambda: ["cp210", "usb serial", "nrf", "silicon labs"]
    )
    serial_fallback_device_mac: str = ""
    serial_auto_configure: bool = True
    serial_disable_uuid_output: bool = True
    serial_apply_mac_filter: bool = False
    serial_apply_packet_type: bool = False
    serial_enable_broadcast_sos_overlay: bool = True
    serial_response_cycle_seconds: float = 8.0
    serial_broadcast_cycle_seconds: float = 2.0

    mqtt_enabled: bool = False
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    mqtt_topic: str = "t10-gateway"
    mqtt_username: str = ""
    mqtt_password: str = ""
    mqtt_keepalive_seconds: int = 60

    sos_broadcast_window_seconds: int = 15
    health_score_floor: int = 35
    stream_retention_points: int = 600

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug_flag(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production", "off", "false", "0", "no"}:
                return False
            if normalized in {"debug", "dev", "development", "on", "true", "1", "yes"}:
                return True
        return value

    @field_validator("local_approved_models", mode="before")
    @classmethod
    def normalize_local_approved_models(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip().lower() for item in value.split(",") if item.strip()]
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip().lower() for item in value if str(item).strip()]
        return value

    @field_validator("local_default_model", "local_reasoning_model", "local_report_model", "ollama_model", mode="before")
    @classmethod
    def normalize_model_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @model_validator(mode="after")
    def validate_local_model_policy(self) -> "Settings":
        approved = set(self.supported_local_models)
        for model_name in (self.local_default_model, self.local_reasoning_model, self.local_report_model, self.ollama_model):
            if model_name not in approved:
                raise ValueError(
                    f"Unsupported local model '{model_name}'. Approved models: {', '.join(sorted(approved))}"
                )
        return self

    @property
    def data_dir(self) -> Path:
        return BASE_DIR / "data"

    @property
    def supported_local_models(self) -> tuple[str, ...]:
        approved = tuple(dict.fromkeys(model for model in self.local_approved_models if model))
        if approved:
            return approved
        return ("qwen3:1.7b", "deepseek-r1:1.5b")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
