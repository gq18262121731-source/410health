from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agent.analysis_service import HealthDataAnalysisService
from agent.context_assembler import AgentContextAssembler
from agent.langchain_rag_service import LangChainRAGService
from agent.langgraph_health_agent import HealthAgentService
from agent.mcp_adapter import LocalToolAdapter
from agent.model_interfaces import (
    AgentModelSuite,
    RuleBasedAlarmInterpretationModel,
    RuleBasedCareSuggestionModel,
    RuleBasedHealthAssessmentModel,
    RuleBasedRiskScoringModel,
    ServiceBackedAnomalyExplainModel,
)
from ai.anomaly_detector import CommunityHealthClusterer, IntelligentAnomalyScorer, RealtimeAnomalyDetector
from ai.data_generator import SyntheticHealthDataGenerator
from ai.health_score_model import BaselineTracker, HealthScoreService as DemoHealthScoreService
from backend.config import get_settings
from backend.models.auth_model import SessionUser
from backend.models.alarm_model import AlarmLayer, AlarmPriority, AlarmRecord, AlarmType
from backend.models.device_model import DeviceBindStatus, DeviceIngestMode, DeviceRecord, DeviceStatus, ingest_source_matches_mode
from backend.models.health_model import HealthSample, IngestResponse, IngestionSource
from backend.models.analytics_model import AgentElderSubject, WindowKind
from backend.models.user_model import UserRole
from backend.ml.inference import HealthInferenceEngine
from backend.repositories.score_repo import ScoreRepository
from backend.repositories.mobile_push_device_repo import MobilePushDeviceRepository
from backend.repositories.warning_repo import WarningRepository
from backend.repositories.wearable_repo import WearableRepository
from backend.services.alarm_priority_queue import AlarmPriorityQueue
from backend.services.alarm_service import AlarmService
from backend.services.camera_audio_hub import CameraAudioHub
from backend.services.camera_stream_hub import CameraDetectionFrameHub, CameraFrameHub
from backend.services.community_insight_service import CommunityInsightService
from backend.services.care_service import CareService
from backend.services.device_service import DeviceService
from backend.services.explanation_service import ExplanationService
from backend.services.fall_event_catalog_service import FallEventCatalogService
from backend.services.fall_detection_service import FallDetectionService
from backend.services.health_data_repository import HealthDataRepository
from backend.services.health_score_service import HealthScoreService as StructuredHealthScoreService
from backend.services.health_stability_service import HealthStabilityService
from backend.services.notification_service import NotificationService
from backend.services.relation_service import RelationService
from backend.services.stream_service import StreamService
from backend.services.user_service import UserService
from backend.services.voice_service import VoiceService
from backend.services.warning_service import WarningService
from backend.services.websocket_manager import WebSocketManager
from backend.schemas.health import VitalSignsPayload
from iot.parser import T10PacketParser


logger = logging.getLogger(__name__)
_settings = get_settings()
_user_service = UserService()
_relation_service = RelationService(_user_service)
_device_service = DeviceService(_user_service, database_url=_settings.database_url)
_stream_service = StreamService(retention_points=_settings.stream_retention_points)
_websocket_manager = WebSocketManager()
_camera_frame_hub = CameraFrameHub(
    _settings.model_copy(
        update={
            "camera_stream_profile": "quality",
            "camera_stream_rtsp_path": "/udp/av0_0",
            "camera_stream_quality_path": "/udp/av0_0",
            "camera_stream_smooth_path": "/tcp/av0_1",
            "camera_stream_fps": 12.0,
            "camera_stream_width": 1024,
            "camera_stream_jpeg_quality": 6,
            "camera_stream_send_timeout_seconds": 0.8,
        }
    )
)
_camera_detection_frame_hub = CameraDetectionFrameHub(
    _settings.model_copy(
        update={
            "camera_stream_profile": "balanced",
            "camera_stream_rtsp_path": "/tcp/av0_1",
            "camera_stream_quality_path": "/udp/av0_0",
            "camera_stream_smooth_path": "/tcp/av0_1",
            "camera_stream_fps": 12.0,
            "camera_stream_width": 0,
            "camera_stream_send_timeout_seconds": 1.2,
            "camera_stream_keep_warm": False,
        }
    ),
    event_provider=lambda: (
        _fall_detection_service.status().get("last_event")
        if "_fall_detection_service" in globals()
        else None
    ),
)
_camera_audio_hub = CameraAudioHub(_settings)
_alarm_priority_queue = AlarmPriorityQueue(redis_url=_settings.redis_url)
_mobile_push_device_repo = MobilePushDeviceRepository(_settings.database_url)
_notification_service = NotificationService(_mobile_push_device_repo)
_health_data_repository = HealthDataRepository(database_url=_settings.database_url)
_realtime_detector = RealtimeAnomalyDetector(
    window_size=_settings.realtime_window_size,
    zscore_threshold=_settings.zscore_threshold,
)
_alarm_service = AlarmService(
    detector=_realtime_detector,
    queue=_alarm_priority_queue,
    notification_service=_notification_service,
    sos_dedupe_window_seconds=_settings.sos_broadcast_window_seconds,
)
_baseline_tracker = BaselineTracker()
_health_score_service = DemoHealthScoreService(floor=_settings.health_score_floor)
_community_clusterer = CommunityHealthClusterer()
_intelligent_scorer = IntelligentAnomalyScorer()
_data_generator = SyntheticHealthDataGenerator(
    device_count=_settings.mock_device_count,
    mac_prefix=(_settings.allowed_mac_prefixes[0] if _settings.allowed_mac_prefixes else _settings.mock_device_mac_prefix),
)
_parser = T10PacketParser(
    sos_window_seconds=_settings.sos_broadcast_window_seconds,
    merge_timeout_seconds=max(0.3, _settings.serial_packet_merge_timeout_seconds),
)
_analysis_service = HealthDataAnalysisService()
_rag_service = LangChainRAGService(_settings, _settings.data_dir.parent / "docs" / "knowledge-base")
_care_service = CareService(_device_service, _user_service, _relation_service, _settings)
_agent_context_assembler = AgentContextAssembler(
    _stream_service,
    _alarm_service,
    _device_service,
    _care_service,
)
_agent_tool_adapter = LocalToolAdapter()
_agent_tool_adapter.register_tool(name="get_device_realtime", description="Query realtime health sample for a single device", handler=lambda call: _tool_get_device_realtime(call.payload))
_agent_tool_adapter.register_tool(name="get_device_trend", description="Query recent trend points for a single device", handler=lambda call: _tool_get_device_trend(call.payload))
_agent_tool_adapter.register_tool(name="get_device_status", description="Query device ledger, online state and bind state", handler=lambda call: _tool_get_device_status(call.payload))
_agent_tool_adapter.register_tool(name="get_device_bind_history", description="Query device bind history", handler=lambda call: _tool_get_device_bind_history(call.payload))
_agent_tool_adapter.register_tool(name="get_elder_profile", description="Query elder profile with device and family relations", handler=lambda call: _tool_get_elder_profile(call.payload))
_agent_tool_adapter.register_tool(name="get_family_relations", description="Query elder-family relations", handler=lambda call: _tool_get_family_relations(call.payload))
_agent_tool_adapter.register_tool(name="get_active_alarms", description="Query active alarms", handler=lambda call: _tool_get_active_alarms(call.payload))
_agent_tool_adapter.register_tool(name="get_community_overview", description="Query community monitoring overview", handler=lambda call: _tool_get_community_overview(call.payload))
_agent_tool_adapter.register_tool(name="get_care_directory", description="Query care directory summary", handler=lambda call: _care_service.get_directory().model_dump(mode="json"))
_agent_tool_adapter.register_tool(name="weather_lookup", description="Reserved weather context lookup", source="external_placeholder", handler=lambda call: _tool_placeholder_external("weather_lookup", call.payload))
_agent_tool_adapter.register_tool(name="air_quality_lookup", description="Reserved air quality context lookup", source="external_placeholder", handler=lambda call: _tool_placeholder_external("air_quality_lookup", call.payload))
_agent_tool_adapter.register_tool(name="nearby_facility_lookup", description="Reserved nearby facility lookup", source="external_placeholder", handler=lambda call: _tool_placeholder_external("nearby_facility_lookup", call.payload))
_agent_tool_adapter.register_tool(name="holiday_lookup", description="Reserved holiday lookup", source="external_placeholder", handler=lambda call: _tool_holiday_lookup(call.payload))
_agent_tool_adapter.register_tool(name="run_tavily_search", description="Run external web search for complementary context", handler=lambda call: _community_insight_service.tool_run_tavily_search(call.payload))
_agent_tool_adapter.register_tool(name="generate_analysis_report", description="Generate structured analysis report", handler=lambda call: _tool_generate_analysis_report(call.payload))
_agent_model_suite = AgentModelSuite(
    health_assessment=RuleBasedHealthAssessmentModel(_analysis_service),
    risk_scoring=RuleBasedRiskScoringModel(),
    anomaly_explain=ServiceBackedAnomalyExplainModel(_intelligent_scorer, _community_clusterer),
    care_suggestion=RuleBasedCareSuggestionModel(),
    alarm_interpretation=RuleBasedAlarmInterpretationModel(),
)
_agent_service = HealthAgentService(
    _settings,
    _rag_service,
    _analysis_service,
    context_assembler=_agent_context_assembler,
    tool_adapter=_agent_tool_adapter,
    model_suite=_agent_model_suite,
)
_explanation_service = ExplanationService()
_community_insight_service = CommunityInsightService(
    settings=_settings,
    analysis_service=_analysis_service,
    stream_service=_stream_service,
    alarm_service=_alarm_service,
    device_service=_device_service,
    care_service=_care_service,
    rag_service=_rag_service,
    repository=_health_data_repository,
)
_voice_service = VoiceService(_settings, device_service=_device_service)
_fall_event_catalog = FallEventCatalogService(Path(__file__).resolve().parent / "configs" / "fall_event_catalog.json")
_structured_inference_engine = HealthInferenceEngine(_settings)
_structured_stability_service = HealthStabilityService(_settings)
_wearable_repo = WearableRepository(_settings.database_url)
_score_repo = ScoreRepository(_settings.database_url)
_warning_repo = WarningRepository(_settings.database_url)
_structured_health_score_service = StructuredHealthScoreService(
    inference_engine=_structured_inference_engine,
    wearable_repo=_wearable_repo,
    score_repo=_score_repo,
    warning_repo=_warning_repo,
    stability_service=_structured_stability_service,
)
_warning_service = WarningService(health_score_service=_structured_health_score_service)
_last_community_alarm_at: datetime | None = None
_fall_alarm_seen_keys: dict[str, float] = {}
_fall_alarm_dedupe_ttl_seconds = 90.0


@dataclass
class _FallTrackState:
    first_seen_monotonic: float
    last_seen_monotonic: float
    confirmed_hits: list[float] = field(default_factory=list)
    active_incident_id: str | None = None
    admitted_at_monotonic: float | None = None
    last_normal_at_monotonic: float | None = None


_fall_track_states: dict[str, _FallTrackState] = {}


def _fall_event_is_suspected_candidate(event: dict[str, object]) -> bool:
    state = str(event.get("state") or "").strip().lower()
    if state != "suspected_fall":
        return False
    scores = event.get("scores") if isinstance(event.get("scores"), dict) else {}
    fall_score = _coerce_float(event.get("fall_score"), default=0.0)
    posture = _coerce_float(scores.get("posture"), default=0.0)
    detector = _coerce_float(scores.get("detector"), default=0.0)
    down_seconds = _fall_event_down_seconds(event)
    return (
        fall_score >= max(0.18, float(_settings.fall_detection_min_alert_score or 0.0))
        or (posture >= 0.22 and down_seconds >= 0.8)
        or (posture >= 0.3 and detector >= 0.1)
    )


def _fall_event_catalog_match(event: dict[str, object]) -> dict[str, object] | None:
    return _fall_event_catalog.match(event)


def _fall_alert_priority_from_catalog_or_state(
    *,
    catalog_match: dict[str, object] | None,
    severity: str,
    injury_level: str,
    state: str,
) -> AlarmPriority:
    catalog_level = str((catalog_match or {}).get("alert_level") or "").strip().upper()
    if catalog_level == "CRITICAL":
        return AlarmPriority.CRITICAL
    if catalog_level == "WARNING":
        return AlarmPriority.WARNING
    if catalog_level == "NOTICE":
        return AlarmPriority.NOTICE
    return _fall_alarm_priority(severity=severity, injury_level=injury_level, state=state)


def _fall_alert_presentation(
    event: dict[str, object],
    *,
    catalog_match: dict[str, object] | None,
) -> dict[str, object]:
    template = (catalog_match or {}).get("template") if isinstance((catalog_match or {}).get("template"), dict) else {}
    title = str((template or {}).get("title") or "").strip()
    lead = str((template or {}).get("lead") or "").strip()
    actions = (catalog_match or {}).get("recommended_actions")
    return {
        "catalog_code": str((catalog_match or {}).get("code") or "").strip() or "unclassified_fall_event",
        "catalog_name": str((catalog_match or {}).get("name") or "").strip() or "未分类跌倒事件",
        "title": title or "检测到异常事件",
        "lead": lead or "系统已检测到异常姿态，请尽快查看现场。",
        "show_immediate_popup": bool((catalog_match or {}).get("show_immediate_popup")),
        "requires_multimodal_review": bool((catalog_match or {}).get("requires_multimodal_review")),
        "recommended_actions": list(actions) if isinstance(actions, list) else [],
        "review_status": "pending" if bool((catalog_match or {}).get("requires_multimodal_review")) else "not_required",
        "event_state": str(event.get("state") or ""),
    }


async def _broadcast_fall_review_pending(
    *,
    incident_id: str,
    track_id: str,
    event: dict[str, object],
    presentation: dict[str, object],
) -> None:
    await _websocket_manager.broadcast_alarm(
        {
            "type": "fall_alarm_pending_review",
            "device_mac": _settings.fall_detection_target_device_mac,
            "incident_id": incident_id,
            "track_id": track_id,
            "title": "系统正在复核现场，请稍等",
            "lead": "已检测到异常姿态，系统正在结合快照分析老人当前状态。",
            "expected_seconds": max(3, int(_settings.fall_detection_multimodal_timeout_seconds or 8)),
            "catalog_code": presentation.get("catalog_code"),
            "event": event,
        }
    )


async def _broadcast_fall_review_finalized(
    *,
    incident_id: str,
    track_id: str,
    event: dict[str, object],
    presentation: dict[str, object],
    review: dict[str, object] | None,
) -> None:
    await _websocket_manager.broadcast_alarm(
        {
            "type": "fall_alarm_finalized",
            "device_mac": _settings.fall_detection_target_device_mac,
            "incident_id": incident_id,
            "track_id": track_id,
            "catalog_code": presentation.get("catalog_code"),
            "presentation": presentation,
            "event": event,
            "review": review or {},
        }
    )


def _fall_event_is_alarm_candidate(event: dict[str, object]) -> bool:
    event_type = str(event.get("event_type") or "").strip().lower()
    state = str(event.get("state") or "").strip().lower()
    if event_type == "fall_confirmed":
        return True
    if state in {
        "confirmed_fall",
        "post_fall_monitoring",
        "recovery_watch",
        "injury_watch",
        "abnormal_recovery",
        "needs_assistance",
        "emergency",
    }:
        return True
    return _fall_event_is_suspected_candidate(event)


async def _handle_fall_detection_event(event: dict[str, object]) -> None:
    track_state, now_monotonic = _record_fall_track_activity(event)
    event_type = str(event.get("event_type") or "")
    state = str(event.get("state") or "")
    injury = event.get("injury") if isinstance(event.get("injury"), dict) else {}
    injury_level = str(injury.get("level") or "I0") if isinstance(injury, dict) else "I0"
    if not _fall_event_is_alarm_candidate(event):
        return

    filter_reasons = _fall_event_filter_reasons(
        event,
        track_state=track_state,
        now_monotonic=now_monotonic,
    )
    if filter_reasons:
        logger.info(
            "Fall event suppressed before alarm creation: track=%s event=%s state=%s reasons=%s score=%s source=%s",
            event.get("track_id"),
            event_type,
            state,
            ",".join(filter_reasons),
            event.get("fall_score"),
            event.get("source"),
        )
        return

    catalog_match = _fall_event_catalog_match(event)
    severity = str(event.get("severity") or "NONE")
    fall_score = float(event.get("fall_score") or 0.0)
    incident_id = _ensure_fall_incident_id(event, track_state=track_state, now_monotonic=now_monotonic)
    track_id = str(event.get("track_id") or "unknown")
    presentation = _fall_alert_presentation(event, catalog_match=catalog_match)
    event["presentation"] = presentation

    dedupe_key = f"{track_id}:{event_type}:{state}:{injury_level}"
    now_monotonic = time.monotonic()
    expired_keys = [
        key
        for key, seen_at in _fall_alarm_seen_keys.items()
        if now_monotonic - seen_at > _fall_alarm_dedupe_ttl_seconds
    ]
    for key in expired_keys:
        _fall_alarm_seen_keys.pop(key, None)
    if dedupe_key in _fall_alarm_seen_keys:
        logger.info(
            "Fall event suppressed by dedupe: track=%s event=%s state=%s injury=%s",
            track_id,
            event_type,
            state,
            injury_level,
        )
        return
    _fall_alarm_seen_keys[dedupe_key] = now_monotonic

    advice = (
        str(injury.get("advice") or "Please inspect the live camera view as soon as possible.")
        if isinstance(injury, dict)
        else "Please inspect the live camera view as soon as possible."
    )
    priority = _fall_alert_priority_from_catalog_or_state(
        catalog_match=catalog_match,
        severity=severity,
        injury_level=injury_level,
        state=state,
    )
    alarm_type = (
        AlarmType.FALL_INJURY_RISK
        if injury_level in {"I2", "I3", "I4", "I5"}
        or state in {"injury_watch", "abnormal_recovery", "needs_assistance", "emergency"}
        else AlarmType.FALL_DETECTED
    )
    title = str(presentation.get("title") or "跌倒告警").strip()
    lead = str(presentation.get("lead") or "").strip()
    alarm = AlarmRecord(
        device_mac=_settings.fall_detection_target_device_mac,
        alarm_type=alarm_type,
        alarm_level=priority,
        alarm_layer=AlarmLayer.REALTIME,
        message=f"{title}: {lead or advice}",
        anomaly_probability=max(0.0, min(1.0, fall_score)),
        metadata={
            "source": "fall_detection_model",
            "event": event,
            "severity": severity,
            "injury_level": injury_level,
            "track_id": track_id,
            "incident_id": incident_id,
            "presentation": presentation,
        },
    )
    alarms = _alarm_service.evaluate_alarm_records([enrich_alarm_context(alarm)])
    if not alarms:
        logger.info(
            "Fall event produced no active alarm after evaluation: track=%s event=%s state=%s injury=%s score=%.3f",
            track_id,
            event_type,
            state,
            injury_level,
            fall_score,
        )
        return
    _health_data_repository.persist_alerts(alarms)
    for item in alarms:
        await _websocket_manager.broadcast_alarm(item.model_dump(mode="json"))
    await _websocket_manager.broadcast_alarm_queue(
        {
            "type": "alarm_queue",
            "queue": [item.model_dump(mode="json") for item in _alarm_service.queue_items(active_only=True)],
            "snapshot": _alarm_service.queue_snapshot(),
        }
    )

    review_needed = bool((catalog_match or {}).get("requires_multimodal_review")) or catalog_match is None
    if review_needed:
        await _broadcast_fall_review_pending(
            incident_id=incident_id,
            track_id=track_id,
            event=event,
            presentation=presentation,
        )

    multimodal_review: dict[str, object] | None = None
    if review_needed:
        multimodal_review = await _maybe_run_fall_multimodal_review(event)
        if multimodal_review is not None:
            event["multimodal_review"] = multimodal_review
            presentation["review_status"] = "completed"
            if _should_suppress_fall_alarm_after_multimodal_review(event, multimodal_review):
                presentation["title"] = "系统复核后倾向于误报"
                presentation["lead"] = "系统已完成二次复核，当前更像误报或非跌倒动作，但仍建议人工确认。"
        else:
            multimodal_review = {
                "status": "fallback",
                "judgement": "uncertain",
                "confidence": "low",
                "recommended_action": "needs_human_review",
                "reason": "多模态复核暂未返回明确结果，请人工查看现场并继续观察。",
            }
            event["multimodal_review"] = multimodal_review
            presentation["review_status"] = "fallback"
            presentation["title"] = "系统复核暂未完成"
            presentation["lead"] = "系统未能及时给出明确复核结论，请先按跌倒风险处理并人工确认现场。"
        await _broadcast_fall_review_finalized(
            incident_id=incident_id,
            track_id=track_id,
            event=event,
            presentation=presentation,
            review=multimodal_review,
        )

    logger.info(
        "Fall alarm broadcast: count=%d latest_type=%s latest_level=%s track=%s state=%s injury=%s",
        len(alarms),
        alarms[-1].alarm_type.value,
        alarms[-1].alarm_level.value,
        track_id,
        state,
        injury_level,
    )


async def ingest_fall_detection_event(event: dict[str, object]) -> AlarmRecord | None:
    before_ids = {alarm.id for alarm in _alarm_service.list_alarms(active_only=True)}
    await _handle_fall_detection_event(event)
    active_alarms = _alarm_service.list_alarms(active_only=True)
    new_items = [
        alarm for alarm in active_alarms
        if alarm.id not in before_ids
        and alarm.alarm_type in {AlarmType.FALL_DETECTED, AlarmType.FALL_INJURY_RISK}
    ]
    if new_items:
        new_items.sort(key=lambda item: item.created_at, reverse=True)
        return new_items[0]
    incident_id = str(event.get("incident_id") or "").strip()
    if incident_id:
        for alarm in reversed(active_alarms):
            if str((alarm.metadata or {}).get("incident_id") or "") == incident_id:
                return alarm
    return None


def _fall_event_passes_alarm_filters(
    event: dict[str, object],
    *,
    track_state: _FallTrackState | None = None,
    now_monotonic: float | None = None,
) -> bool:
    return (
        _fall_event_passes_score_filter(event)
        and _fall_event_passes_roi_filter(event)
        and _fall_event_passes_bbox_filter(event)
        and _fall_event_passes_branch_support_filter(event)
        and _fall_event_passes_temporal_filter(
            event,
            track_state=track_state,
            now_monotonic=now_monotonic,
        )
    )


def _fall_event_filter_reasons(
    event: dict[str, object],
    *,
    track_state: _FallTrackState | None = None,
    now_monotonic: float | None = None,
) -> list[str]:
    reasons: list[str] = []
    if not _fall_event_passes_score_filter(event):
        reasons.append("score")
    if not _fall_event_passes_roi_filter(event):
        reasons.append("roi")
    if not _fall_event_passes_bbox_filter(event):
        reasons.append("bbox")
    if not _fall_event_passes_branch_support_filter(event):
        reasons.append("support")
    if not _fall_event_passes_temporal_filter(
        event,
        track_state=track_state,
        now_monotonic=now_monotonic,
    ):
        reasons.append("temporal")
    return reasons


def _fall_event_passes_score_filter(event: dict[str, object]) -> bool:
    threshold = max(0.0, min(1.0, float(_settings.fall_detection_min_alert_score or 0.0)))
    if threshold <= 0:
        return True
    try:
        fall_score = float(event.get("fall_score") or 0.0)
    except (TypeError, ValueError):
        return False
    return fall_score >= threshold


def _fall_event_passes_roi_filter(event: dict[str, object]) -> bool:
    if not _settings.fall_detection_roi_enabled:
        return True
    if event.get("source") == "fall_detection_demo" or event.get("demo") is True:
        return True
    if _fall_event_bypasses_roi(event):
        return True

    roi = _parse_fall_detection_roi()
    if roi is None:
        logger.warning("Fall detection ROI is enabled but invalid; event admission is fail-open.")
        return True

    bbox = event.get("bbox")
    normalized_bbox = _normalize_fall_bbox(bbox, event)
    if normalized_bbox is None:
        logger.debug("Fall detection event has no usable bbox; event admission is fail-open.")
        return True

    x1, y1, x2, y2 = normalized_bbox
    bbox_area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if bbox_area <= 0:
        return False

    rx1, ry1, rx2, ry2 = roi
    ix1 = max(x1, rx1)
    iy1 = max(y1, ry1)
    ix2 = min(x2, rx2)
    iy2 = min(y2, ry2)
    intersection_area = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    overlap = intersection_area / bbox_area
    return overlap >= max(0.0, min(1.0, float(_settings.fall_detection_roi_min_overlap or 0.0)))


def _fall_event_passes_bbox_filter(event: dict[str, object]) -> bool:
    if event.get("source") == "fall_detection_demo" or event.get("demo") is True:
        return True

    bbox = event.get("bbox")
    normalized_bbox = _normalize_fall_bbox(bbox, event)
    if normalized_bbox is None:
        return True

    x1, y1, x2, y2 = normalized_bbox
    bbox_width = max(0.0, x2 - x1)
    bbox_height = max(0.0, y2 - y1)
    bbox_area = bbox_width * bbox_height
    min_area = max(0.0, min(1.0, float(_settings.fall_detection_min_bbox_area_ratio or 0.0)))
    if bbox_area < min_area:
        return False

    margin = max(0.0, min(0.25, float(_settings.fall_detection_edge_margin_ratio or 0.0)))
    if margin <= 0:
        return True

    touches_left_or_right = x1 <= margin or x2 >= (1.0 - margin)
    touches_top_or_bottom = y1 <= margin or y2 >= (1.0 - margin)
    touches_edge = touches_left_or_right or touches_top_or_bottom
    min_partial_height = max(0.0, min(1.0, float(_settings.fall_detection_edge_partial_min_height_ratio or 0.0)))
    if touches_top_or_bottom and bbox_height < min_partial_height and not _fall_event_has_detector_support(event):
        return False

    return not touches_edge or _fall_event_is_high_confidence(event)


def _fall_event_passes_branch_support_filter(event: dict[str, object]) -> bool:
    if event.get("source") == "fall_detection_demo" or event.get("demo") is True:
        return True
    if _fall_event_is_high_confidence(event):
        return True

    scores = event.get("scores") if isinstance(event.get("scores"), dict) else {}
    posture = _coerce_float(scores.get("posture"), default=0.0)
    support_max = max(
        _coerce_float(scores.get("gru"), default=0.0),
        _coerce_float(scores.get("hybrid"), default=0.0),
        _coerce_float(scores.get("semantic"), default=0.0),
        _coerce_float(scores.get("detector"), default=0.0),
    )
    if posture < 0.75:
        return True
    return support_max >= 0.12


def _fall_event_has_detector_support(event: dict[str, object]) -> bool:
    scores = event.get("scores") if isinstance(event.get("scores"), dict) else {}
    detector = _coerce_float(scores.get("detector"), default=0.0)
    return detector >= 0.4


def _fall_event_passes_temporal_filter(
    event: dict[str, object],
    *,
    track_state: _FallTrackState | None = None,
    now_monotonic: float | None = None,
) -> bool:
    if event.get("source") == "fall_detection_demo" or event.get("demo") is True:
        return True

    if now_monotonic is None:
        now_monotonic = time.monotonic()

    if track_state and track_state.active_incident_id:
        event.setdefault("incident_id", track_state.active_incident_id)
        return True

    down_seconds = _fall_event_down_seconds(event)
    min_down_seconds = max(0.0, float(_settings.fall_detection_min_down_seconds or 0.0))
    high_confidence = _fall_event_is_high_confidence(event)

    if track_state is None:
        return high_confidence and down_seconds >= min_down_seconds

    track_age = max(0.0, now_monotonic - track_state.first_seen_monotonic)
    confirmation_window = max(1.0, float(_settings.fall_detection_confirmation_window_seconds or 1.0))
    track_state.confirmed_hits = [
        hit for hit in track_state.confirmed_hits if now_monotonic - hit <= confirmation_window
    ]
    confirmed_hits = len(track_state.confirmed_hits)
    min_confirmed_hits = max(1, int(_settings.fall_detection_min_confirmed_hits or 1))
    min_track_age = max(0.0, float(_settings.fall_detection_min_track_age_seconds or 0.0))

    event_type = str(event.get("event_type") or "").strip().lower()
    state = str(event.get("state") or "").strip().lower()
    severity = str(event.get("severity") or "").strip().upper()
    injury = event.get("injury") if isinstance(event.get("injury"), dict) else {}
    injury_level = str(injury.get("level") or "").strip().upper() if isinstance(injury, dict) else ""
    scores = event.get("scores") if isinstance(event.get("scores"), dict) else {}
    fall_score = _coerce_float(event.get("fall_score"), default=0.0)
    hybrid = _coerce_float(scores.get("hybrid"), default=0.0)
    semantic = _coerce_float(scores.get("semantic"), default=0.0)
    explicit_confirmation = event_type == "fall_confirmed" or state == "confirmed_fall"
    if (
        explicit_confirmation
        and confirmed_hits >= 1
        and (
            high_confidence
            or (
                fall_score >= max(0.55, float(_settings.fall_detection_min_alert_score or 0.0))
                and hybrid >= 0.6
                and semantic >= 0.25
                and (severity in {"L2", "L3", "L4", "L5"} or injury_level in {"I2", "I3", "I4", "I5"})
            )
        )
    ):
        return True

    if high_confidence and track_age >= min_track_age:
        return True
    if down_seconds >= min_down_seconds and confirmed_hits >= 1:
        return True
    return confirmed_hits >= min_confirmed_hits and track_age >= min_track_age


def _fall_event_bypasses_roi(event: dict[str, object]) -> bool:
    event_type = str(event.get("event_type") or "")
    state = str(event.get("state") or "")
    if event_type != "fall_confirmed" and state != "confirmed_fall":
        return False
    try:
        fall_score = float(event.get("fall_score") or 0.0)
    except (TypeError, ValueError):
        return False
    threshold = max(0.0, min(1.0, float(_settings.fall_detection_confirmed_roi_bypass_score or 0.0)))
    return fall_score >= threshold


def _parse_fall_detection_roi() -> tuple[float, float, float, float] | None:
    raw = (_settings.fall_detection_roi_rect or "").strip()
    if not raw:
        return None
    try:
        parts = [float(part.strip()) for part in raw.replace(";", ",").split(",")]
    except ValueError:
        return None
    if len(parts) != 4:
        return None
    x1, y1, x2, y2 = parts
    x1, x2 = sorted((max(0.0, min(1.0, x1)), max(0.0, min(1.0, x2))))
    y1, y2 = sorted((max(0.0, min(1.0, y1)), max(0.0, min(1.0, y2))))
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def _normalize_fall_bbox(
    bbox: object,
    event: dict[str, object] | None = None,
) -> tuple[float, float, float, float] | None:
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    try:
        coords = [float(value) for value in bbox]
    except (TypeError, ValueError):
        return None

    x1, y1, x2, y2 = coords
    x1, x2 = sorted((x1, x2))
    y1, y2 = sorted((y1, y2))
    if max(abs(x1), abs(y1), abs(x2), abs(y2)) <= 1.5:
        return (
            max(0.0, min(1.0, x1)),
            max(0.0, min(1.0, y1)),
            max(0.0, min(1.0, x2)),
            max(0.0, min(1.0, y2)),
        )

    frame_width, frame_height = _fall_event_frame_dimensions(event)
    return (
        max(0.0, min(1.0, x1 / frame_width)),
        max(0.0, min(1.0, y1 / frame_height)),
        max(0.0, min(1.0, x2 / frame_width)),
        max(0.0, min(1.0, y2 / frame_height)),
    )


def _fall_event_frame_dimensions(event: dict[str, object] | None = None) -> tuple[float, float]:
    configured_width = max(1.0, float(_settings.fall_detection_frame_width or 1.0))
    configured_height = max(1.0, float(_settings.fall_detection_frame_height or 1.0))
    if isinstance(event, dict):
        try:
            event_width = float(event.get("frame_width") or 0.0)
            event_height = float(event.get("frame_height") or 0.0)
        except (TypeError, ValueError):
            event_width = 0.0
            event_height = 0.0
        if event_width > 1.0 and event_height > 1.0:
            return event_width, event_height

    stream_width = max(0, int(_settings.camera_stream_width or 0))
    source = str(event.get("source") or "") if isinstance(event, dict) else ""
    if stream_width <= 0 or "stream.mjpg" not in source:
        return configured_width, configured_height

    aspect_height = max(1.0, configured_height)
    aspect_width = max(1.0, configured_width)
    stream_height = max(1.0, round(stream_width * (aspect_height / aspect_width)))
    return float(stream_width), float(stream_height)


def _record_fall_track_activity(event: dict[str, object]) -> tuple[_FallTrackState | None, float]:
    now_monotonic = time.monotonic()
    ttl_seconds = max(30.0, float(_settings.fall_detection_track_state_ttl_seconds or 30.0))
    stale_keys = [
        key
        for key, value in _fall_track_states.items()
        if now_monotonic - value.last_seen_monotonic > ttl_seconds
    ]
    for key in stale_keys:
        _fall_track_states.pop(key, None)

    track_key = _fall_track_key(event)
    if not track_key:
        return None, now_monotonic

    state = _fall_track_states.get(track_key)
    if state is None:
        state = _FallTrackState(
            first_seen_monotonic=now_monotonic,
            last_seen_monotonic=now_monotonic,
        )
        _fall_track_states[track_key] = state
    else:
        reopen_seconds = max(1.0, float(_settings.fall_detection_incident_reopen_seconds or 1.0))
        if now_monotonic - state.last_seen_monotonic > reopen_seconds:
            state.first_seen_monotonic = now_monotonic
            state.confirmed_hits.clear()
            state.active_incident_id = None
            state.admitted_at_monotonic = None
        state.last_seen_monotonic = now_monotonic

    event_type = str(event.get("event_type") or "")
    current_state = str(event.get("state") or "")
    if event_type == "fall_confirmed" or current_state in {
        "confirmed_fall",
        "post_fall_monitoring",
        "recovery_watch",
        "injury_watch",
        "abnormal_recovery",
        "needs_assistance",
        "emergency",
    } or _fall_event_is_suspected_candidate(event):
        state.confirmed_hits.append(now_monotonic)

    confirmation_window = max(1.0, float(_settings.fall_detection_confirmation_window_seconds or 1.0))
    state.confirmed_hits = [
        hit for hit in state.confirmed_hits if now_monotonic - hit <= confirmation_window
    ]

    if current_state == "normal":
        state.active_incident_id = None
        state.admitted_at_monotonic = None
        state.last_normal_at_monotonic = now_monotonic

    return state, now_monotonic


def _fall_track_key(event: dict[str, object]) -> str | None:
    track_id = str(event.get("track_id") or "").strip()
    if not track_id:
        return None
    source = str(event.get("source") or "camera").strip() or "camera"
    return f"{source}|{track_id}"


def _ensure_fall_incident_id(
    event: dict[str, object],
    *,
    track_state: _FallTrackState | None = None,
    now_monotonic: float | None = None,
) -> str:
    existing = str(event.get("incident_id") or "").strip()
    if existing:
        return existing

    if now_monotonic is None:
        now_monotonic = time.monotonic()

    if track_state and track_state.active_incident_id:
        event["incident_id"] = track_state.active_incident_id
        return track_state.active_incident_id

    source = str(event.get("source") or "camera").strip() or "camera"
    track_id = str(event.get("track_id") or "unknown").strip() or "unknown"
    source_slug = "".join(ch if ch.isalnum() else "-" for ch in source).strip("-").lower() or "camera"
    incident_id = f"{source_slug}-{track_id}-{int(now_monotonic * 1000)}"
    event["incident_id"] = incident_id
    if track_state is not None:
        track_state.active_incident_id = incident_id
        track_state.admitted_at_monotonic = now_monotonic
    return incident_id


def _fall_event_is_high_confidence(event: dict[str, object]) -> bool:
    if event.get("source") == "fall_detection_demo" or event.get("demo") is True:
        return True

    scores = event.get("scores") if isinstance(event.get("scores"), dict) else {}
    fall_score = _coerce_float(event.get("fall_score"), default=0.0)
    threshold = max(0.0, min(1.0, float(_settings.fall_detection_high_confidence_score or 0.0)))
    injury_level = str((event.get("injury") or {}).get("level") if isinstance(event.get("injury"), dict) else "")
    severity = str(event.get("severity") or "")
    hybrid = _coerce_float(scores.get("hybrid"), default=0.0)
    semantic = _coerce_float(scores.get("semantic"), default=0.0)
    detector = _coerce_float(scores.get("detector"), default=0.0)

    if fall_score >= threshold:
        return True
    if injury_level in {"I3", "I4", "I5"} or severity in {"L3", "L4", "L5"}:
        return True
    if hybrid >= threshold and semantic >= 0.18:
        return True
    return detector >= 0.6 and fall_score >= max(0.45, threshold - 0.12)


def _fall_event_down_seconds(event: dict[str, object]) -> float:
    injury = event.get("injury") if isinstance(event.get("injury"), dict) else {}
    return max(0.0, _coerce_float(injury.get("down_seconds") if isinstance(injury, dict) else 0.0, default=0.0))


def _coerce_float(value: object, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _should_suppress_fall_alarm_after_multimodal_review(
    event: dict[str, object],
    review: dict[str, object],
) -> bool:
    judgement = str(review.get("judgement") or "").strip().lower()
    confidence = str(review.get("confidence") or "").strip().lower()
    action = str(review.get("recommended_action") or "").strip().lower()
    if judgement != "no_fall":
        return False
    if confidence in {"high", "medium"}:
        return True

    scores = event.get("scores") if isinstance(event.get("scores"), dict) else {}
    detector_score = _coerce_float(scores.get("detector"), default=0.0)
    down_seconds = _fall_event_down_seconds(event)
    severity = str(event.get("severity") or "").strip().upper()
    injury = event.get("injury") if isinstance(event.get("injury"), dict) else {}
    injury_level = str(injury.get("level") or "").strip().upper() if isinstance(injury, dict) else ""
    if severity in {"L3", "L4", "L5"} or injury_level in {"I3", "I4", "I5"}:
        return False

    bbox = _normalize_fall_bbox(event.get("bbox"), event)
    bbox_tall = False
    if bbox is not None:
        x1, y1, x2, y2 = bbox
        bbox_width = max(0.0, x2 - x1)
        bbox_height = max(0.0, y2 - y1)
        bbox_tall = bbox_height >= max(0.18, bbox_width * 1.12)

    false_positive_cues = review.get("false_positive_cues")
    benign_false_positive_cues = {
        "快速坐下",
        "弯腰捡东西",
        "坐姿正常",
        "正常坐姿",
        "桌前办公",
        "正常操作电脑",
        "坐着办公",
    }
    review_mentions_known_false_positive = any(
        isinstance(item, str) and item.strip() in benign_false_positive_cues
        for item in (false_positive_cues if isinstance(false_positive_cues, list) else [])
    )
    reason_text = str(review.get("reason") or "").strip()
    reason_looks_benign = any(
        token in reason_text for token in ("操作电脑", "坐姿", "弯腰", "没有明显的跌倒迹象", "无跌倒风险")
    )

    if action == "downgrade" and detector_score <= 0.12 and (bbox_tall or down_seconds < 3.0):
        return True
    if review_mentions_known_false_positive and detector_score <= 0.12 and (bbox_tall or reason_looks_benign):
        return True
    return False


async def _maybe_run_fall_multimodal_review(event: dict[str, object]) -> dict[str, object] | None:
    if not _settings.fall_detection_multimodal_enabled:
        return None

    snapshot_path = str(event.get("snapshot_path") or "").strip()
    if not snapshot_path:
        return None

    if not Path(snapshot_path).is_file():
        return None

    try:
        fall_score = float(event.get("fall_score") or 0.0)
    except (TypeError, ValueError):
        fall_score = 0.0
    if fall_score < max(0.0, min(1.0, float(_settings.fall_detection_multimodal_min_score or 0.0))):
        return None

    provider = _resolve_fall_multimodal_provider()
    if provider in {"disabled", "none"}:
        return None
    if provider == "qwen_omni":
        return await asyncio.to_thread(
            _voice_service.review_fall_snapshot,
            snapshot_path,
            event=event,
        )
    if provider == "siliconflow_script":
        return await _run_legacy_fall_multimodal_review(snapshot_path)
    return None


def _resolve_fall_multimodal_provider() -> str:
    explicit = str(_settings.fall_detection_multimodal_provider or "auto").strip().lower()
    if explicit in {"disabled", "none"}:
        return "disabled"
    if explicit == "qwen_omni":
        return "qwen_omni"
    if explicit == "siliconflow_script":
        return "siliconflow_script"
    if _settings.dashscope_api_key.strip() and _settings.qwen_omni_model_id:
        return "qwen_omni"
    api_key = (_settings.siliconflow_api_key or "").strip() or os.environ.get("SILICONFLOW_API_KEY", "").strip()
    if api_key:
        return "siliconflow_script"
    return "none"


async def _run_legacy_fall_multimodal_review(snapshot_path: str) -> dict[str, object] | None:
    api_key = (_settings.siliconflow_api_key or "").strip() or os.environ.get("SILICONFLOW_API_KEY", "").strip()
    if not api_key:
        return None

    model_root = Path(_settings.fall_detection_model_root)
    python = Path(_settings.fall_detection_python)
    script = model_root / "scripts" / "llm_fall_review.py"
    config = model_root / "configs" / "llm_review.yaml"
    if not script.is_file() or not python.is_file() or not config.is_file():
        logger.info(
            "Multimodal review skipped due to missing assets: python=%s script=%s config=%s",
            python.is_file(),
            script.is_file(),
            config.is_file(),
        )
        return None

    cmd = [
        str(python),
        str(script),
        "--image",
        snapshot_path,
        "--config",
        str(config),
    ]
    env = os.environ.copy()
    env["SILICONFLOW_API_KEY"] = api_key
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(model_root),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=max(5, int(_settings.fall_detection_multimodal_timeout_seconds or 45)),
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        logger.warning("Multimodal review timed out for snapshot=%s", snapshot_path)
        return {"status": "timeout"}

    if process.returncode != 0:
        logger.warning(
            "Multimodal review failed: rc=%s stderr=%s",
            process.returncode,
            stderr.decode("utf-8", errors="replace")[-800:],
        )
        return {"status": "error", "stderr": stderr.decode("utf-8", errors="replace")[-800:]}

    raw = stdout.decode("utf-8", errors="replace").strip()
    if not raw:
        return {"status": "empty"}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Multimodal review returned non-JSON payload: %s", raw[-800:])
        return {"status": "invalid_json", "raw": raw[-800:]}

    review = parsed.get("review") if isinstance(parsed, dict) else None
    if isinstance(review, dict):
        review["status"] = "ok"
        return review
    return {"status": "ok", "raw": parsed}


def _fall_alarm_priority(*, severity: str, injury_level: str, state: str) -> AlarmPriority:
    if injury_level in {"I4", "I5"} or severity == "L4" or state in {"needs_assistance", "emergency"}:
        return AlarmPriority.CRITICAL
    if injury_level == "I3" or severity == "L3" or state == "abnormal_recovery":
        return AlarmPriority.CRITICAL
    if injury_level == "I2" or severity == "L2":
        return AlarmPriority.WARNING
    return AlarmPriority.NOTICE


_fall_detection_service = FallDetectionService(_settings, _handle_fall_detection_event)


# NOTE: ingest_sample is defined further below (after helper functions)
# to access all required services. See the async def ingest_sample(...)
# near the end of this module.

# 始终 seed mock 设备，用于 demo overlay 和 AI 模型预热
# serial/mqtt 模式下 mock 设备以 ingest_mode=mock 标记，与真实串口设备区分
# mock 设备直接设为 ONLINE，overlay 流会持续推数据，不依赖串口
_mock_devices_to_seed = _data_generator.build_devices()
for _mock_index, _mock_dev in enumerate(_mock_devices_to_seed):
    if _device_service.get_device(_mock_dev.mac_address) is None:
        _device_service.seed_devices([_mock_dev])
    # 李建国 (elder01_02) 的设备永远在线
    if _mock_dev.mac_address == "53:57:08:00:00:01":
        seeded_status = DeviceStatus.ONLINE
    else:
        seeded_status = DeviceStatus.OFFLINE if _mock_index % 5 == 0 else DeviceStatus.ONLINE
    _device_service.update_status(_mock_dev.mac_address, seeded_status)
_intelligent_scorer.warmup(_data_generator.build_training_sequences(hours=24, step_minutes=10))

if _settings.data_mode == "mock" and _settings.use_mock_data:
    # 纯 mock 模式：预填充历史数据到 stream，让 UI 启动即有数据
    for device_history in _data_generator.build_history(hours=1, step_minutes=10).values():
        for sample in device_history:
            baseline = _baseline_tracker.observe(sample)
            sample.health_score = _health_score_service.score(sample, baseline)
            _stream_service.publish(sample)


def get_device_service() -> DeviceService:
    return _device_service


def get_user_service() -> UserService:
    return _user_service


def get_relation_service() -> RelationService:
    return _relation_service


def get_stream_service() -> StreamService:
    return _stream_service


def get_alarm_service() -> AlarmService:
    return _alarm_service


def get_websocket_manager() -> WebSocketManager:
    return _websocket_manager


def get_camera_frame_hub() -> CameraFrameHub:
    return _camera_frame_hub


def get_camera_detection_frame_hub() -> CameraFrameHub:
    return _camera_detection_frame_hub


def get_camera_audio_hub() -> CameraAudioHub:
    return _camera_audio_hub


def get_fall_detection_service() -> FallDetectionService:
    return _fall_detection_service


def get_fall_multimodal_review_status() -> dict[str, object]:
    return {
        "enabled": _settings.fall_detection_multimodal_enabled,
        "configured_provider": _settings.fall_detection_multimodal_provider,
        "resolved_provider": _resolve_fall_multimodal_provider(),
        "dashscope_configured": bool(_settings.dashscope_api_key.strip()),
        "qwen_omni_model": _settings.qwen_omni_model_id,
        "siliconflow_configured": bool(
            (_settings.siliconflow_api_key or "").strip() or os.environ.get("SILICONFLOW_API_KEY", "").strip()
        ),
        "min_score": _settings.fall_detection_multimodal_min_score,
        "timeout_seconds": _settings.fall_detection_multimodal_timeout_seconds,
    }


def get_health_data_repository() -> HealthDataRepository:
    return _health_data_repository


def get_data_generator() -> SyntheticHealthDataGenerator:
    return _data_generator


_demo_overlay_cycle_index = 0
_demo_overlay_last_published_at: datetime | None = None
_demo_overlay_last_refresh_at: datetime | None = None


def _eligible_demo_overlay_device_macs() -> list[str]:
    devices = _device_service.list_devices()
    eligible_device_macs = {
        device.mac_address
        for device in devices
        if device.status != DeviceStatus.OFFLINE
    }
    personas = getattr(_data_generator, "personas", None) or []
    eligible: list[str] = []
    for persona in personas:
        mac = str(getattr(persona, "mac_address", "")).strip().upper()
        if mac and mac in eligible_device_macs:
            eligible.append(mac)
    return eligible


def _sample_source_allowed(device: DeviceRecord, sample: HealthSample) -> bool:
    if not _settings.strict_source_match:
        return True
    effective_mode = get_effective_device_ingest_mode(device.mac_address, device.ingest_mode)
    return ingest_source_matches_mode(effective_mode, sample.source)


def _persist_demo_overlay_sample(sample: HealthSample, *, explanation: str, source_label: str) -> None:
    device = _device_service.get_device(sample.device_mac)
    if isinstance(device, DeviceRecord) and not _sample_source_allowed(device, sample):
        return
    _health_data_repository.persist_sample(sample)
    _stream_service.publish(sample)


def refresh_demo_overlay_samples() -> dict[str, object]:
    global _demo_overlay_last_refresh_at
    eligible = _eligible_demo_overlay_device_macs()
    for mac in eligible:
        sample = _data_generator.sample_for_device(mac)
        _persist_demo_overlay_sample(sample, explanation="community sample refresh", source_label="demo_overlay_refresh")
    _demo_overlay_last_refresh_at = datetime.now(timezone.utc)
    return {"device_count": len(eligible), "device_macs": eligible}


def publish_next_demo_overlay_sample() -> None:
    global _demo_overlay_cycle_index, _demo_overlay_last_published_at
    eligible = _eligible_demo_overlay_device_macs()
    if not eligible:
        return
    mac = eligible[_demo_overlay_cycle_index % len(eligible)]
    _demo_overlay_cycle_index = (_demo_overlay_cycle_index + 1) % len(eligible)
    sample = _data_generator.sample_for_device(mac)
    _persist_demo_overlay_sample(sample, explanation="community sample overlay", source_label="demo_overlay_tick")
    _demo_overlay_last_published_at = datetime.now(timezone.utc)


def get_demo_data_status() -> dict[str, object]:
    eligible = _eligible_demo_overlay_device_macs()
    return {
        "device_count": len(eligible),
        "device_macs": eligible,
        "last_refresh_at": _demo_overlay_last_refresh_at.isoformat() if _demo_overlay_last_refresh_at else None,
        "last_published_at": _demo_overlay_last_published_at.isoformat() if _demo_overlay_last_published_at else None,
    }


def ensure_demo_overlay_history_window(*, hours: int = 24, step_minutes: int = 10) -> dict[str, int]:
    """Ensure mock devices keep at least a rolling 24h history in DB."""
    eligible = _eligible_demo_overlay_device_macs()
    if not eligible:
        return {"devices_checked": 0, "devices_backfilled": 0, "inserted_samples": 0}

    now = datetime.now(timezone.utc)
    start_at = now - timedelta(hours=max(1, hours))
    expected_points = max(1, int((hours * 60) / max(1, step_minutes)))
    histories = _data_generator.build_history(hours=max(1, hours), step_minutes=max(1, step_minutes))

    devices_backfilled = 0
    inserted_samples = 0
    for mac in eligible:
        existing = _health_data_repository.list_samples(
            device_mac=mac,
            start_at=start_at,
            end_at=now,
            limit=max(expected_points * 3, 300),
        )
        if len(existing) >= expected_points:
            continue

        history_samples = histories.get(mac, [])
        if not history_samples:
            continue

        for sample in history_samples:
            baseline = _baseline_tracker.observe(sample)
            sample.health_score = _health_score_service.score(sample, baseline)
            _health_data_repository.persist_sample(sample)
            inserted_samples += 1
        devices_backfilled += 1

    return {
        "devices_checked": len(eligible),
        "devices_backfilled": devices_backfilled,
        "inserted_samples": inserted_samples,
    }


def get_settings_dependency():
    return _settings


def get_parser() -> T10PacketParser:
    return _parser


def get_agent_service() -> HealthAgentService:
    return _agent_service


def get_care_service() -> CareService:
    return _care_service


def get_explanation_service() -> ExplanationService:
    return _explanation_service


def get_notification_service() -> NotificationService:
    return _notification_service


def get_community_insight_service() -> CommunityInsightService:
    return _community_insight_service


def get_demo_elder_subjects() -> list[AgentElderSubject]:
    directory = _care_service.get_demo_directory()
    subjects: list[AgentElderSubject] = []
    for elder in directory.elders:
        macs = list(getattr(elder, "device_macs", [])) or ([elder.device_mac] if elder.device_mac else [])
        subjects.append(
            AgentElderSubject(
                elder_id=elder.id,
                elder_name=elder.name,
                apartment=elder.apartment,
                device_macs=[mac for mac in macs if mac],
                has_realtime_device=bool(macs),
                risk_level="unknown",
                is_demo_subject=True,
            )
        )
    return subjects


def require_session_user(authorization: str | None) -> SessionUser:
    if not authorization:
        raise ValueError("AUTH_REQUIRED")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ValueError("AUTH_REQUIRED")
    user = _care_service.resolve_session(token.strip())
    if not user:
        raise ValueError("INVALID_SESSION")
    return user


def require_write_session_user(authorization: str | None) -> SessionUser:
    user = require_session_user(authorization)
    if user.role not in {UserRole.FAMILY, UserRole.COMMUNITY, UserRole.ADMIN}:
        raise ValueError("FORBIDDEN")
    return user


def resolve_session_user_by_token(token: str | None) -> SessionUser | None:
    if not token:
        return None
    normalized = token.strip()
    if not normalized:
        return None
    return _care_service.resolve_session(normalized)


def _demo_accessible_devices_for_alarm_scope(
    elder_ids: set[str],
    devices: list[DeviceRecord],
) -> set[str]:
    demo_directory = _care_service.get_demo_directory()
    demo_elder_device_macs: set[str] = set()
    for elder in demo_directory.elders:
        if elder.id not in elder_ids:
            continue
        for mac in elder.device_macs or ([elder.device_mac] if elder.device_mac else []):
            if mac:
                demo_elder_device_macs.add(str(mac).strip().upper())

    visible: set[str] = set()
    for device in devices:
        if device.mac_address.upper() in demo_elder_device_macs and device.ingest_mode == DeviceIngestMode.MOCK:
            visible.add(device.mac_address.upper())
    return visible


def resolve_alarm_visible_device_macs(user: SessionUser) -> set[str] | None:
    if user.role in {UserRole.COMMUNITY, UserRole.ADMIN}:
        return None

    devices = _device_service.list_devices()
    visible_macs: set[str] = set()

    if user.role == UserRole.ELDER:
        elder_ids = {user.id}
        for device in devices:
            if device.user_id == user.id and device.bind_status == DeviceBindStatus.BOUND:
                visible_macs.add(device.mac_address.upper())
        visible_macs.update(_demo_accessible_devices_for_alarm_scope(elder_ids, devices))
        return visible_macs

    if user.role == UserRole.FAMILY:
        elder_ids = set(_care_service.resolve_family_elder_ids(user.id))
        for device in devices:
            if device.user_id in elder_ids and device.bind_status == DeviceBindStatus.BOUND:
                visible_macs.add(device.mac_address.upper())

        if not elder_ids:
            demo_family_id = user.family_id or user.id
            demo_directory = _care_service.get_demo_directory()
            demo_family = next((family for family in demo_directory.families if family.id == demo_family_id), None)
            if demo_family is not None:
                elder_ids = set(demo_family.elder_ids)

        visible_macs.update(_demo_accessible_devices_for_alarm_scope(elder_ids, devices))
        return visible_macs

    return set()


def _find_directory_elder_for_device(
    directory,
    normalized_mac: str,
    device: DeviceRecord | None,
):
    if device and device.user_id:
        elder = next((item for item in directory.elders if item.id == device.user_id), None)
        if elder is not None:
            return elder

    return next(
        (
            item
            for item in directory.elders
            if normalized_mac == item.device_mac.upper()
            or normalized_mac in {str(mac).strip().upper() for mac in item.device_macs}
        ),
        None,
    )


def _build_alarm_context_from_directory(
    *,
    device_mac: str,
    device: DeviceRecord | None,
    directory,
) -> dict[str, object]:
    normalized_mac = device_mac.strip().upper()
    elder = _find_directory_elder_for_device(directory, normalized_mac, device)
    family_name_by_id = {family.id: family.name for family in directory.families}
    family_ids = list(getattr(elder, "family_ids", []) or []) if elder is not None else []
    family_names = [family_name_by_id[family_id] for family_id in family_ids if family_id in family_name_by_id]

    context: dict[str, object] = {}
    if device is not None and device.device_name.strip():
        context["device_name"] = device.device_name.strip()
    if elder is not None:
        context["elder_id"] = elder.id
        context["elder_name"] = elder.name
        context["apartment"] = elder.apartment
        if family_ids:
            context["family_ids"] = family_ids
        if family_names:
            context["family_names"] = family_names
    return context


def _build_configured_camera_alarm_context(normalized_mac: str, directory) -> dict[str, object]:
    target_mac = _settings.fall_detection_target_device_mac.strip().upper()
    if not target_mac or normalized_mac != target_mac:
        return {}

    context: dict[str, object] = {"device_name": "Home camera"}
    family_name_by_id = {family.id: family.name for family in directory.families}

    configured_elder_id = _settings.fall_detection_target_elder_id.strip()
    elder = next((item for item in directory.elders if item.id == configured_elder_id), None) if configured_elder_id else None

    configured_family_ids = [
        item.strip()
        for item in _settings.fall_detection_target_family_ids.split(",")
        if item.strip()
    ]

    if elder is not None:
        context["elder_id"] = elder.id
        context["elder_name"] = elder.name
        context["apartment"] = elder.apartment
        family_ids = list(getattr(elder, "family_ids", []) or []) or configured_family_ids
    else:
        family_ids = configured_family_ids

    if family_ids:
        context["family_ids"] = family_ids
        family_names = [family_name_by_id[family_id] for family_id in family_ids if family_id in family_name_by_id]
        if family_names:
            context["family_names"] = family_names

    return context


def build_alarm_context(device_mac: str) -> dict[str, object]:
    normalized_mac = device_mac.strip().upper()
    device = _device_service.get_device(normalized_mac)
    directory = _care_service.get_directory()
    context = _build_alarm_context_from_directory(
        device_mac=normalized_mac,
        device=device,
        directory=directory,
    )
    if context:
        return context
    return _build_configured_camera_alarm_context(normalized_mac, directory)


def enrich_alarm_context(alarm: AlarmRecord) -> AlarmRecord:
    context = build_alarm_context(alarm.device_mac)
    if not context:
        return alarm
    metadata = dict(alarm.metadata)
    metadata.update(context)
    return alarm.model_copy(update={"metadata": metadata})


def enrich_alarm_records_context(alarms: list[AlarmRecord]) -> list[AlarmRecord]:
    if not alarms:
        return []
    return [enrich_alarm_context(alarm) for alarm in alarms]


def filter_alarm_records_for_user(
    alarms: list[AlarmRecord],
    user: SessionUser | None,
) -> list[AlarmRecord]:
    if user is None:
        return alarms
    visible_device_macs = resolve_alarm_visible_device_macs(user)
    if visible_device_macs is None:
        return alarms
    return [alarm for alarm in alarms if alarm.device_mac.upper() in visible_device_macs]


def filter_alarm_queue_items_for_user(
    items: list,
    user: SessionUser | None,
) -> list:
    if user is None:
        return items
    visible_device_macs = resolve_alarm_visible_device_macs(user)
    if visible_device_macs is None:
        return items
    return [item for item in items if item.alarm.device_mac.upper() in visible_device_macs]


def get_data_analysis_service() -> HealthDataAnalysisService:
    return _analysis_service


def get_intelligent_scorer() -> IntelligentAnomalyScorer:
    return _intelligent_scorer


def get_community_clusterer() -> CommunityHealthClusterer:
    return _community_clusterer


def get_score_repo() -> ScoreRepository:
    return _score_repo


def get_structured_health_score_service() -> StructuredHealthScoreService:
    return _structured_health_score_service


def get_warning_evaluation_service() -> WarningService:
    return _warning_service


def get_effective_device_ingest_mode(
    device_mac: str,
    stored_mode: DeviceIngestMode | str | None,
) -> DeviceIngestMode | None:
    normalized_mac = device_mac.strip().upper()
    personas = getattr(_data_generator, "personas", None)
    if personas:
        known = {str(persona.mac_address).strip().upper() for persona in personas if getattr(persona, "mac_address", None)}
        if normalized_mac in known:
            return DeviceIngestMode.MOCK
    if stored_mode is None:
        return None
    if isinstance(stored_mode, DeviceIngestMode):
        return stored_mode
    try:
        return DeviceIngestMode(str(stored_mode))
    except ValueError:
        return None


def is_display_ready_sample(sample: HealthSample, ingest_mode: DeviceIngestMode | str | None) -> bool:
    effective = get_effective_device_ingest_mode(sample.device_mac, ingest_mode)
    if effective == DeviceIngestMode.MOCK:
        return True
    if effective == DeviceIngestMode.SERIAL:
        # 串口模式：收到即更新，缺失字段由 _merge_with_latest 回填上一时刻值。
        if sample.heart_rate <= 0 or sample.blood_oxygen <= 0:
            return False
        if sample.temperature <= 0:
            return False
        return True
    return True


def _filter_display_samples(
    samples: list[HealthSample],
    ingest_mode: DeviceIngestMode | str | None,
) -> list[HealthSample]:
    if not samples:
        return []
    effective_mode = get_effective_device_ingest_mode(samples[0].device_mac, ingest_mode)
    ordered = sorted(samples, key=lambda item: item.timestamp)
    if effective_mode != DeviceIngestMode.SERIAL:
        return ordered
    resolved: list[HealthSample] = []
    last_valid_spo2: int | None = None
    for sample in ordered:
        update: dict[str, object] = {}
        if sample.blood_oxygen in (None, 0) and last_valid_spo2 not in (None, 0):
            update["blood_oxygen"] = last_valid_spo2
        resolved_sample = sample.model_copy(update=update) if update else sample
        if resolved_sample.blood_oxygen not in (None, 0):
            last_valid_spo2 = resolved_sample.blood_oxygen
        resolved.append(resolved_sample)
    return resolved


def get_display_latest_sample(
    device_mac: str,
    ingest_mode: DeviceIngestMode | str | None,
) -> HealthSample | None:
    effective_mode = get_effective_device_ingest_mode(device_mac, ingest_mode)
    recent = _stream_service.recent(device_mac, limit=240)
    if not recent:
        now = datetime.now(timezone.utc)
        persisted = _health_data_repository.list_samples(
            device_mac=device_mac.strip().upper(),
            start_at=now - timedelta(hours=24),
            end_at=now,
            limit=240,
        )
        if persisted:
            restored = _filter_display_samples(persisted, effective_mode)
            for sample in restored:
                if is_display_ready_sample(sample, effective_mode):
                    _stream_service.publish(sample)
            recent = restored

    filtered = _filter_display_samples(recent, effective_mode)
    for sample in reversed(filtered):
        if is_display_ready_sample(sample, effective_mode):
            return sample
    return None


def get_display_trend_samples(
    device_mac: str,
    ingest_mode: DeviceIngestMode | str | None,
    *,
    minutes: int,
    limit: int,
) -> list[HealthSample]:
    effective_mode = get_effective_device_ingest_mode(device_mac, ingest_mode)
    requested_limit = max(1, int(limit))
    minutes = max(1, int(minutes))
    samples = _stream_service.recent_in_window(device_mac, minutes=minutes, limit=max(240, requested_limit * 3))
    if not samples:
        now = datetime.now(timezone.utc)
        persisted = _health_data_repository.list_samples(
            device_mac=device_mac.strip().upper(),
            start_at=now - timedelta(minutes=minutes),
            end_at=now,
            limit=max(240, requested_limit * 3),
        )
        restored = _filter_display_samples(persisted, effective_mode)
        for sample in restored:
            if is_display_ready_sample(sample, effective_mode):
                _stream_service.publish(sample)
        samples = restored

    filtered = _filter_display_samples(samples, effective_mode)
    ready = [sample for sample in filtered if is_display_ready_sample(sample, effective_mode)]
    return ready[-requested_limit:]


def _restore_recent_samples_to_stream(*, hours: int = 24, per_device_limit: int = 288) -> None:
    now = datetime.now(timezone.utc)
    devices = _device_service.list_devices()
    histories = _health_data_repository.list_samples_by_devices(
        device_macs=[device.mac_address for device in devices],
        start_at=now - timedelta(hours=hours),
        end_at=now,
        per_device_limit=per_device_limit,
    )
    for device in devices:
        effective_mode = get_effective_device_ingest_mode(device.mac_address, device.ingest_mode)
        samples = histories.get(device.mac_address, [])
        filtered = _filter_display_samples(samples, effective_mode)
        for sample in filtered:
            if is_display_ready_sample(sample, effective_mode):
                _stream_service.publish(sample)


def _normalize_mac_from_payload(payload: dict[str, object]) -> str:
    return str(payload.get("mac_address", "")).strip().upper()


def _tool_get_device_realtime(payload: dict[str, object]) -> dict[str, object]:
    mac = _normalize_mac_from_payload(payload)
    sample = _stream_service.latest(mac)
    device = _device_service.get_device(mac)
    return {
        "mac_address": mac,
        "timestamp": sample.timestamp.isoformat() if sample else None,
        "heart_rate": sample.heart_rate if sample else None,
        "blood_oxygen": sample.blood_oxygen if sample else None,
        "temperature": sample.temperature if sample else None,
        "blood_pressure": sample.blood_pressure if sample else None,
        "battery": sample.battery if sample else None,
        "steps": sample.steps if sample else None,
        "health_score": sample.health_score if sample else None,
        "sos_flag": sample.sos_flag if sample else None,
        "device_status": device.status if device else None,
    }


def _tool_get_device_trend(payload: dict[str, object]) -> dict[str, object]:
    mac = _normalize_mac_from_payload(payload)
    minutes = int(payload.get("minutes", 180) or 180)
    limit = int(payload.get("limit", 120) or 120)
    points = _stream_service.trend(mac, minutes=minutes, limit=limit)
    return {
        "mac_address": mac,
        "minutes": minutes,
        "points": [point.model_dump(mode="json") for point in points],
    }


def _tool_get_device_status(payload: dict[str, object]) -> dict[str, object]:
    mac = _normalize_mac_from_payload(payload)
    device = _device_service.get_device(mac)
    return {
        "mac_address": mac,
        "device_name": device.device_name if device else None,
        "status": device.status if device else None,
        "bind_status": device.bind_status if device else None,
        "user_id": device.user_id if device else None,
    }


def _tool_get_device_bind_history(payload: dict[str, object]) -> dict[str, object]:
    mac = _normalize_mac_from_payload(payload)
    logs = _device_service.list_bind_logs(mac)
    return {
        "mac_address": mac,
        "logs": [log.model_dump(mode="json") for log in logs],
    }


def _tool_get_elder_profile(payload: dict[str, object]) -> dict[str, object]:
    directory = _care_service.get_directory()
    elder_user_id = str(payload.get("elder_user_id", "")).strip()
    mac = _normalize_mac_from_payload(payload)
    elder = None
    if elder_user_id:
        elder = next((item for item in directory.elders if item.id == elder_user_id), None)
    elif mac:
        elder = next(
            (
                item
                for item in directory.elders
                if mac == item.device_mac or mac in getattr(item, "device_macs", [])
            ),
            None,
        )
    return {
        "elder_user_id": elder.id if elder else elder_user_id or None,
        "name": elder.name if elder else None,
        "age": elder.age if elder else None,
        "apartment": elder.apartment if elder else None,
        "community_id": elder.community_id if elder else None,
        "device_mac": elder.device_mac if elder else mac or None,
        "device_macs": list(getattr(elder, "device_macs", [])) if elder else ([mac] if mac else []),
        "family_ids": elder.family_ids if elder else [],
    }


def _tool_get_family_relations(payload: dict[str, object]) -> dict[str, object]:
    elder_user_id = str(payload.get("elder_user_id", "")).strip()
    family_user_id = str(payload.get("family_user_id", "")).strip()
    relations = []
    if elder_user_id:
        relations = _relation_service.list_relations_by_elder(elder_user_id)
    elif family_user_id:
        relations = _relation_service.list_relations_by_family(family_user_id)
    return {
        "relations": [relation.model_dump(mode="json") for relation in relations],
    }


def _tool_get_active_alarms(payload: dict[str, object]) -> dict[str, object]:
    mac = _normalize_mac_from_payload(payload)
    active_only = bool(payload.get("active_only", True))
    alarms = _alarm_service.list_alarms(device_mac=mac or None, active_only=active_only)
    return {
        "mac_address": mac or None,
        "alarms": [alarm.model_dump(mode="json") for alarm in alarms],
    }


def _tool_get_community_overview(payload: dict[str, object]) -> dict[str, object]:
    latest_samples = _stream_service.latest_samples()
    history_by_device = _stream_service.recent_by_devices(minutes=60, per_device_limit=60)
    summary = _community_clusterer.summarize(latest_samples, history_by_device)
    score = _intelligent_scorer.score_sequence(
        [
            [sample.heart_rate, sample.temperature, sample.blood_oxygen, (sample.blood_pressure_pair or (120, 80))[0]]
            for sample in latest_samples
        ]
    ) if latest_samples else 0.0
    return {
        "community_id": str(payload.get("community_id", "community-haitang") or "community-haitang"),
        "device_count": len(latest_samples),
        "intelligent_anomaly_score": score,
        "clusters": summary.clusters,
        "trend": summary.trend,
    }


def _tool_placeholder_external(tool_name: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "tool_name": tool_name,
        "status": "reserved",
        "message": "External provider not connected in current runtime",
        "requested_payload": payload,
    }


def _tool_holiday_lookup(payload: dict[str, object]) -> dict[str, object]:
    target = str(payload.get("date", "")).strip()
    try:
        day = datetime.fromisoformat(target).date() if target else datetime.now(timezone.utc).date()
    except ValueError:
        day = datetime.now(timezone.utc).date()
    is_weekend = day.weekday() >= 5
    return {
        "date": day.isoformat(),
        "is_holiday": is_weekend,
        "is_weekend": is_weekend,
        "label": "weekend" if is_weekend else "workday",
        "source_note": "local_placeholder_calendar",
    }


def _tool_generate_analysis_report(payload: dict[str, object]) -> dict[str, object]:
    scope = str(payload.get("scope", "community"))
    window = str(payload.get("window", "day"))
    if scope != "community":
        title = "老人健康分析报告"
        summary = "窗口内健康态势结构化报告"
        report_payload = {
            "scope": scope,
            "window": window,
            "sections": [
                {"title": "摘要", "content": "关键指标与事件汇总"},
                {"title": "风险评估", "content": "风险等级与触发原因"},
                {"title": "建议动作", "content": "建议的处置与观察措施"},
            ],
        }
        return {
            "report": report_payload,
            "attachments": [
                {
                    "id": f"analysis-report-{scope}-{window}",
                    "title": title,
                    "summary": summary,
                    "render_type": "report_document",
                    "render_payload": report_payload,
                    "source_tool": "generate_analysis_report",
                }
            ],
        }

    window_kind = WindowKind.WEEK if window == "week" else WindowKind.DAY
    device_macs = [str(item).strip().upper() for item in list(payload.get("device_macs", [])) if str(item).strip()]
    window_report = _community_insight_service.build_window_report(window=window_kind, device_macs=device_macs)
    analysis = window_report.analysis.model_dump(mode="json")
    key_metrics = analysis.get("key_metrics", {})
    risk_distribution = analysis.get("risk_distribution", {})
    alert_breakdown = analysis.get("alert_breakdown", {})
    status_distribution = analysis.get("device_status_distribution", {})
    high_risk_entities = analysis.get("high_risk_entities", [])
    trend_findings = analysis.get("trend_findings", [])
    chart_payloads = analysis.get("chart_payloads", [])

    title = f"社区{('过去一周' if window_kind == WindowKind.WEEK else '过去一天')}健康分析报告"

    metric_rows = [
        ("覆盖设备数", key_metrics.get("device_count", 0)),
        ("有效上报设备", key_metrics.get("reported_device_count", 0)),
        ("离线设备", key_metrics.get("offline_device_count", 0)),
        ("高风险对象", key_metrics.get("high_risk_device_count", 0)),
        ("窗口告警数", key_metrics.get("window_alert_count", 0)),
        ("平均健康分", key_metrics.get("average_health_score", "--")),
        ("平均血氧", key_metrics.get("average_blood_oxygen", "--")),
    ]
    metric_markdown = "\n".join(
        [
            "| 指标 | 数值 |",
            "| --- | --- |",
            *[f"| {label} | {value} |" for label, value in metric_rows],
        ]
    )

    risk_rows = [
        {
            "elder_name": str(item.get("elder_name") or "--"),
            "device_mac": str(item.get("device_mac") or "--"),
            "risk_level": str(item.get("risk_level") or "--"),
            "latest_health_score": item.get("latest_health_score") if item.get("latest_health_score") is not None else "--",
            "active_alert_count": int(item.get("active_alert_count", 0) or 0),
            "reasons": "；".join(str(reason) for reason in item.get("reasons", [])[:3]) or "--",
        }
        for item in high_risk_entities[:8]
        if isinstance(item, dict)
    ]
    risk_markdown = (
        "\n".join(
            [
                "| 老人 | 设备 | 风险 | 健康分 | 活跃告警 | 原因 |",
                "| --- | --- | --- | --- | --- | --- |",
                *[
                    f"| {row['elder_name']} | {row['device_mac']} | {row['risk_level']} | {row['latest_health_score']} | {row['active_alert_count']} | {row['reasons']} |"
                    for row in risk_rows
                ],
            ]
        )
        if risk_rows
        else "当前窗口内暂无可排序的高风险对象。"
    )

    alert_rows = [
        {"alarm_type": str(key), "count": int(value or 0)}
        for key, value in alert_breakdown.items()
    ]
    alert_rows.sort(key=lambda item: item["count"], reverse=True)
    alert_markdown = (
        "\n".join(
            [
                "| 告警类型 | 次数 |",
                "| --- | --- |",
                *[f"| {row['alarm_type']} | {row['count']} |" for row in alert_rows[:10]],
            ]
        )
        if alert_rows
        else "当前窗口内暂无告警热点。"
    )

    status_rows = [
        {"status": str(key), "count": int(value or 0)}
        for key, value in status_distribution.items()
    ]
    status_rows.sort(key=lambda item: item["count"], reverse=True)
    status_markdown = (
        "\n".join(
            [
                "| 设备状态 | 数量 |",
                "| --- | --- |",
                *[f"| {row['status']} | {row['count']} |" for row in status_rows[:10]],
            ]
        )
        if status_rows
        else "当前没有设备状态分布数据。"
    )

    advice: list[str] = []
    if risk_rows:
        focus_names = "、".join(row["elder_name"] for row in risk_rows[:3])
        advice.append(f"优先复核 {focus_names} 的最新生命体征和现场状态。")
    if int(key_metrics.get("offline_device_count", 0) or 0) > 0:
        advice.append("尽快排查离线设备链路、佩戴状态与电量，避免持续缺数。")
    if int(key_metrics.get("window_alert_count", 0) or 0) > 0:
        advice.append("结合告警热点安排分级随访，优先处理 SOS、血氧偏低与体温异常。")
    if float(key_metrics.get("average_health_score", 0) or 0) < 75:
        advice.append("建议在下一轮巡检中复测健康评分偏低对象的关键指标。")
    if not advice:
        advice.append("社区整体态势相对平稳，可维持常规巡检并持续观察异常漂移。")

    summary = (
        f"覆盖设备 {key_metrics.get('device_count', 0)} 台，"
        f"有效上报 {key_metrics.get('reported_device_count', 0)} 台，"
        f"高风险对象 {key_metrics.get('high_risk_device_count', 0)} 台，"
        f"窗口告警 {key_metrics.get('window_alert_count', 0)} 条。"
    )

    sections = [
        {"title": "执行摘要", "content": summary},
        {"title": "关键指标表", "content": metric_markdown},
        {"title": "高风险对象表", "content": risk_markdown},
        {"title": "告警热点表", "content": alert_markdown},
        {"title": "设备状态表", "content": status_markdown},
        {"title": "趋势发现", "content": "\n".join(f"- {item}" for item in trend_findings[:8]) or "暂无显著趋势发现。"},
        {"title": "处置建议", "content": "\n".join(f"- {item}" for item in advice[:6])},
    ]

    report_payload = {
        "scope": scope,
        "window": window,
        "document_title": title,
        "generated_at": window_report.generated_at.isoformat(),
        "sections": sections,
        "charts": chart_payloads,
    }

    attachments = [
        {
            "id": f"analysis-report-{scope}-{window}",
            "title": title,
            "summary": summary,
            "render_type": "report_document",
            "render_payload": report_payload,
            "source_tool": "generate_analysis_report",
        },
        {
            "id": f"analysis-report-metrics-{window}",
            "title": "社区关键指标",
            "summary": "窗口内核心监测指标概览",
            "render_type": "metric_cards",
            "render_payload": {
                "items": [
                    {"label": "覆盖设备数", "value": key_metrics.get("device_count", 0)},
                    {"label": "有效上报设备", "value": key_metrics.get("reported_device_count", 0)},
                    {"label": "离线设备", "value": key_metrics.get("offline_device_count", 0)},
                    {"label": "高风险对象", "value": key_metrics.get("high_risk_device_count", 0)},
                    {"label": "窗口告警数", "value": key_metrics.get("window_alert_count", 0)},
                    {"label": "平均健康分", "value": key_metrics.get("average_health_score", "--")},
                ]
            },
            "source_tool": "generate_analysis_report",
        },
    ]

    if risk_rows:
        attachments.append(
            {
                "id": f"analysis-report-risk-table-{window}",
                "title": "高风险对象明细",
                "summary": "按风险等级、健康分和活跃告警排序",
                "render_type": "table",
                "render_payload": {
                    "columns": [
                        {"key": "elder_name", "label": "老人"},
                        {"key": "device_mac", "label": "设备 MAC"},
                        {"key": "risk_level", "label": "风险等级"},
                        {"key": "latest_health_score", "label": "最新健康分"},
                        {"key": "active_alert_count", "label": "活跃告警"},
                        {"key": "reasons", "label": "主要原因"},
                    ],
                    "rows": risk_rows,
                },
                "source_tool": "generate_analysis_report",
            }
        )

    if alert_rows:
        attachments.append(
            {
                "id": f"analysis-report-alert-table-{window}",
                "title": "告警热点统计",
                "summary": "窗口内告警类型分布",
                "render_type": "table",
                "render_payload": {
                    "columns": [
                        {"key": "alarm_type", "label": "告警类型"},
                        {"key": "count", "label": "次数"},
                    ],
                    "rows": alert_rows[:10],
                },
                "source_tool": "generate_analysis_report",
            }
        )

    for index, chart in enumerate(chart_payloads[:6]):
        if not isinstance(chart, dict) or not isinstance(chart.get("echarts_option"), dict):
            continue
        attachments.append(
            {
                "id": str(chart.get("id") or f"analysis-report-chart-{index}"),
                "title": str(chart.get("title") or f"图表 {index + 1}"),
                "summary": str(chart.get("summary") or "报告附带图表"),
                "render_type": "echarts",
                "render_payload": {
                    "id": str(chart.get("id") or f"analysis-report-chart-{index}"),
                    "title": str(chart.get("title") or f"图表 {index + 1}"),
                    "summary": str(chart.get("summary") or ""),
                    "echarts_option": chart.get("echarts_option"),
                },
                "source_tool": "generate_analysis_report",
            }
        )

    return {
        "summary": summary,
        "report": report_payload,
        "attachments": attachments,
    }

def _care_directory_lookup(device_mac: str) -> dict[str, object]:
    directory = _care_service.get_directory()
    normalized = device_mac.upper()
    elder = next(
        (
            item
            for item in directory.elders
            if normalized == item.device_mac or normalized in getattr(item, "device_macs", [])
        ),
        None,
    )
    families = [
        family.model_dump(mode="json")
        for family in directory.families
        if elder and family.id in elder.family_ids
    ]
    return {
        "elder_profile": elder.model_dump(mode="json") if elder else None,
        "family_profiles": families,
    }


def _is_response_packet(packet_type: str | None) -> bool:
    return packet_type in {"response_a", "response_b", "response_ab", "legacy_response"}


def _latest_preferred_response_sample(device_mac: str) -> HealthSample | None:
    recent_samples = _stream_service.recent(device_mac, limit=30)
    for candidate in reversed(recent_samples):
        if _is_response_packet(candidate.packet_type):
            return candidate
    return None


def _merge_with_latest(sample: HealthSample) -> HealthSample:
    latest = _stream_service.latest(sample.device_mac)
    latest_response = _latest_preferred_response_sample(sample.device_mac)
    preferred = latest_response or latest
    if preferred is None:
        return sample

    update: dict[str, object] = {}

    # Prefer response packets for normal vitals.
    # Broadcast is mainly for SOS and fallback when a response sample is not available yet.
    if sample.heart_rate <= 0 and preferred.heart_rate > 0:
        update["heart_rate"] = preferred.heart_rate
    if sample.blood_oxygen <= 0 and preferred.blood_oxygen > 0:
        update["blood_oxygen"] = preferred.blood_oxygen
    if sample.temperature <= 0 and 35.0 <= preferred.temperature <= 45.0:
        update["temperature"] = preferred.temperature

    if (not sample.blood_pressure or sample.blood_pressure == "0/0") and preferred.blood_pressure:
        update["blood_pressure"] = preferred.blood_pressure
    if sample.battery <= 0 and preferred.battery > 0:
        update["battery"] = preferred.battery
    if (sample.steps is None or sample.steps <= 0) and (preferred.steps is not None and preferred.steps > 0):
        update["steps"] = preferred.steps
    if sample.ambient_temperature is None and preferred.ambient_temperature is not None:
        update["ambient_temperature"] = preferred.ambient_temperature
    if sample.surface_temperature is None and preferred.surface_temperature is not None:
        update["surface_temperature"] = preferred.surface_temperature
    if not sample.device_uuid and preferred.device_uuid:
        update["device_uuid"] = preferred.device_uuid

    # Keep SOS responsive: a broadcast-triggered SOS should not disappear immediately
    # just because the next response packet does not carry SOS fields.
    if not sample.sos_flag and latest and latest.sos_flag:
        update["sos_flag"] = True
        if sample.sos_value is None and latest.sos_value is not None:
            update["sos_value"] = latest.sos_value
        if sample.sos_trigger is None and latest.sos_trigger is not None:
            update["sos_trigger"] = latest.sos_trigger

    return sample.model_copy(update=update) if update else sample


def _persist_structured_health_score(sample: HealthSample, device: DeviceRecord) -> None:
    """Persist ML/rule split scores so dashboard can render rule/model breakdown."""
    if (
        sample.heart_rate <= 0
        or sample.blood_oxygen <= 0
        or sample.temperature <= 0
    ):
        logger.info(
            "Skipping structured score persistence for %s due to invalid vitals: hr=%s spo2=%s temp=%s packet_type=%s",
            sample.device_mac,
            sample.heart_rate,
            sample.blood_oxygen,
            sample.temperature,
            sample.packet_type,
        )
        return

    systolic, diastolic = sample.blood_pressure_pair
    vitals = VitalSignsPayload(
        heart_rate=float(sample.heart_rate),
        spo2=float(sample.blood_oxygen),
        sbp=float(systolic),
        dbp=float(diastolic),
        body_temp=float(sample.temperature),
        fall_detection=False,
        data_accuracy=100.0,
    )
    elderly_id = str(device.user_id or f"UNBOUND:{sample.device_mac}")
    try:
        _structured_health_score_service.evaluate_vitals(
            vitals=vitals,
            elderly_id=elderly_id,
            device_id=sample.device_mac,
            timestamp=sample.timestamp,
            persist=True,
            stateful_stability=True,
        )
    except Exception as exc:
        logger.exception(
            "Structured score persistence failed for %s (%s): %s",
            sample.device_mac,
            type(exc).__name__,
            exc,
        )
        fallback_score = float(sample.health_score or 0)
        if fallback_score >= 85:
            fallback_risk_level = "normal"
        elif fallback_score >= 70:
            fallback_risk_level = "attention"
        elif fallback_score >= 55:
            fallback_risk_level = "warning"
        else:
            fallback_risk_level = "critical"

        fallback_tags: list[str] = []
        fallback_reasons: list[str] = []
        if sample.sos_flag:
            fallback_tags.append("sos")
            fallback_reasons.append("Detected SOS signal from device")
        if sample.blood_oxygen < 93:
            fallback_tags.append("spo2_low")
            fallback_reasons.append(f"SpO2 is low ({sample.blood_oxygen}%)")
        if sample.heart_rate > 120 or sample.heart_rate < 50:
            fallback_tags.append("heart_rate_abnormal")
            fallback_reasons.append(f"Heart rate out of preferred range ({sample.heart_rate} bpm)")
        if sample.temperature >= 37.6:
            fallback_tags.append("temperature_high")
            fallback_reasons.append(f"Body temperature elevated ({sample.temperature:.1f} C)")

        fallback_payload = {
            "elderly_id": elderly_id,
            "device_id": sample.device_mac,
            "timestamp": sample.timestamp.isoformat(),
            "health_score": round(fallback_score, 4),
            "final_health_score": round(fallback_score, 4),
            "rule_health_score": round(fallback_score, 4),
            "model_health_score": round(fallback_score, 4),
            "risk_level": fallback_risk_level,
            "risk_score_raw": round(max(0.0, min(1.0, 1.0 - (fallback_score / 100.0))), 6),
            "sub_scores": {
                "rule_health_score": round(fallback_score, 4),
                "model_health_score": round(fallback_score, 4),
                "final_health_score": round(fallback_score, 4),
            },
            "alerts": {
                "hr_alert": {"label": "High" if sample.heart_rate > 120 else ("Low" if sample.heart_rate < 50 else "Normal"), "probability": None},
                "spo2_alert": {"label": "Low" if sample.blood_oxygen < 93 else "Normal", "probability": None},
                "bp_alert": {"label": "Normal", "probability": None},
                "temp_alert": {"label": "Abnormal" if sample.temperature >= 37.6 else "Normal", "probability": None},
                "hard_threshold_level": fallback_risk_level if fallback_risk_level in {"warning", "critical"} else None,
            },
            "abnormal_tags": fallback_tags,
            "trigger_reasons": fallback_reasons,
            "recommendation_code": "EMERGENCY_CONTACT" if sample.sos_flag else "MONITOR",
            "stability_mode": "rule_fallback",
            "stabilized_vitals": {
                "heart_rate": float(sample.heart_rate),
                "spo2": float(sample.blood_oxygen),
                "sbp": float(systolic),
                "dbp": float(diastolic),
                "body_temp": float(sample.temperature),
                "fall_detection": False,
                "data_accuracy": 100.0,
            },
            "active_events": [],
            "score_adjustment_reason": "Structured model artifacts missing; fallback scores are used.",
        }
        try:
            _score_repo.save_result(
                elderly_id=elderly_id,
                device_id=sample.device_mac,
                timestamp=sample.timestamp,
                result=fallback_payload,
            )
        except Exception as fallback_exc:
            logger.warning(
                "Structured fallback persistence failed for %s: %s",
                sample.device_mac,
                fallback_exc,
            )


async def ingest_sample(sample: HealthSample) -> IngestResponse:
    global _last_community_alarm_at

    if _settings.data_mode == "mock" and _settings.use_mock_data:
        device = _device_service.ensure_device(sample.device_mac, device_name=_settings.default_device_name)
    else:
        device = _device_service.get_device(sample.device_mac)
    if not isinstance(device, DeviceRecord):
        raise RuntimeError("Device must be registered before ingest in formal mode")

    _device_service.update_status(sample.device_mac, DeviceStatus.ONLINE)
    _alarm_service.observe_sample(sample)

    realtime_alarm_candidates = enrich_alarm_records_context(_realtime_detector.evaluate(sample))
    realtime_alarms = _alarm_service.evaluate_alarm_records(realtime_alarm_candidates)
    if realtime_alarms:
        _health_data_repository.persist_alerts(realtime_alarms)
        for alarm in realtime_alarms:
            await _websocket_manager.broadcast_alarm(alarm.model_dump(mode="json"))
        await _websocket_manager.broadcast_alarm_queue(
            {
                "type": "alarm_queue",
                "queue": [item.model_dump(mode="json") for item in _alarm_service.queue_items(active_only=True)],
                "snapshot": _alarm_service.queue_snapshot(),
            }
        )

    sample = _merge_with_latest(sample)

    baseline = _baseline_tracker.observe(sample)
    sample.health_score = _health_score_service.score(sample, baseline)
    _health_data_repository.persist_sample(sample)
    _health_data_repository.refresh_rollups_for_sample(
        device_mac=sample.device_mac,
        timestamp=sample.timestamp,
    )
    _stream_service.publish(sample)
    _persist_structured_health_score(sample, device)

    ml_alarms: list[AlarmRecord] = []
    intelligent_result = _intelligent_scorer.infer_device(
        sample.device_mac,
        _stream_service.recent_in_window(sample.device_mac, minutes=60, limit=360),
        now=sample.timestamp,
    )
    if intelligent_result:
        intelligent_alarm = _intelligent_scorer.build_alarm(sample, intelligent_result)
        if intelligent_alarm:
            ml_alarms.extend(_alarm_service.evaluate_alarm_records([enrich_alarm_context(intelligent_alarm)]))

    now = sample.timestamp.astimezone(timezone.utc)
    if _last_community_alarm_at is None or now - _last_community_alarm_at >= timedelta(hours=1):
        community_summary = _community_clusterer.summarize(
            _stream_service.latest_samples(),
            _stream_service.recent_by_devices(minutes=60, per_device_limit=60),
        )
        community_alarm = _community_clusterer.build_alarm(community_summary)
        if community_alarm:
            ml_alarms.extend(_alarm_service.evaluate_alarm_records([enrich_alarm_context(community_alarm)]))
            _last_community_alarm_at = now

    if ml_alarms:
        _health_data_repository.persist_alerts(ml_alarms)
        for alarm in ml_alarms:
            await _websocket_manager.broadcast_alarm(alarm.model_dump(mode="json"))
        await _websocket_manager.broadcast_alarm_queue(
            {
                "type": "alarm_queue",
                "queue": [item.model_dump(mode="json") for item in _alarm_service.queue_items(active_only=True)],
                "snapshot": _alarm_service.queue_snapshot(),
            }
        )

    await _websocket_manager.broadcast_health(sample.device_mac, sample.model_dump(mode="json"))
    return IngestResponse(success=True, message="Sample ingested", device_mac=sample.device_mac)
