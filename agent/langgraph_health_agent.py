from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, TypedDict
from urllib import error, request
from uuid import uuid4

from agent.analysis_service import HealthDataAnalysisService
from agent.context_assembler import AgentContextAssembler
from agent.langchain_rag_service import LangChainRAGService
from agent.mcp_adapter import ToolAdapter, ToolInvocation
from agent.model_interfaces import AgentModelInput, AgentModelSuite
from agent.prompting import build_prompt_package
from agent.response_normalizer import sanitize_agent_response, sanitize_device_health_report
from backend.config import Settings
from backend.models.health_model import HealthSample
from backend.models.user_model import UserRole

try:
    from langchain_core.prompts import ChatPromptTemplate
except Exception:
    ChatPromptTemplate = None

try:
    from langchain_ollama import ChatOllama
except Exception:
    ChatOllama = None


def _alarm_from_payload(payload: dict[str, Any]):
    class _AlarmStub:
        def __init__(self, row: dict[str, Any]) -> None:
            self.id = row.get("id", "")
            self.device_mac = str(row.get("device_mac", ""))
            self.alarm_type = row.get("alarm_type", "")
            self.alarm_level = int(row.get("alarm_level", 0) or 0)
            self.message = str(row.get("message", ""))
            self.acknowledged = bool(row.get("acknowledged", False))

    return _AlarmStub(payload)


class AgentState(TypedDict, total=False):
    scope: str
    role: UserRole
    question: str
    target_device_mac: str
    target_device_macs: list[str]
    samples: list[HealthSample]
    community_samples: dict[str, list[HealthSample]]
    route_mode: str
    network_online: bool
    selected_mode: str
    selected_model: str
    context_bundle: dict[str, Any]
    tool_results: list[dict[str, Any]]
    model_results: dict[str, dict[str, Any]]
    degraded_notes: list[str]
    analysis_payload: dict[str, Any]
    analysis_context: str
    dialogue_events: list[dict[str, Any]]
    dialogue_action_labels: list[str]
    dialogue_expression: dict[str, Any]
    retrieval_query: str
    knowledge_hits: list[str]
    system_prompt: str
    user_prompt: str
    prompt_text: str
    messages: list[Any]
    answer: str
    final_payload: dict[str, object]


class HealthAgentService:
    """Offline-only health agent pinned to local Ollama models."""

    def __init__(
        self,
        settings: Settings,
        rag_service: LangChainRAGService,
        analysis_service: HealthDataAnalysisService | None = None,
        *,
        context_assembler: AgentContextAssembler | None = None,
        tool_adapter: ToolAdapter | None = None,
        model_suite: AgentModelSuite | None = None,
    ) -> None:
        self._settings = settings
        self._rag = rag_service
        self._analysis = analysis_service or HealthDataAnalysisService()
        self._context_assembler = context_assembler
        self._tool_adapter = tool_adapter
        self._model_suite = model_suite
        self._local_llms: dict[str, Any] = {}

    def analyze(
        self,
        *,
        role: UserRole,
        question: str,
        samples: list[HealthSample],
        mode: str = "local",
    ) -> dict[str, object]:
        return self.analyze_device(role=role, question=question, samples=samples, mode=mode)

    def analyze_device(
        self,
        *,
        role: UserRole,
        question: str,
        samples: list[HealthSample],
        mode: str = "local",
    ) -> dict[str, object]:
        state = self._execute(
            {
                "scope": "device",
                "role": role,
                "question": question,
                "target_device_mac": samples[-1].device_mac if samples else "",
                "samples": samples,
                "route_mode": mode,
            }
        )
        return self._format_result(state)

    def analyze_community(
        self,
        *,
        role: UserRole,
        question: str,
        device_samples: dict[str, list[HealthSample]],
        mode: str = "local",
    ) -> dict[str, object]:
        state = self._execute(
            {
                "scope": "community",
                "role": role,
                "question": question,
                "target_device_macs": sorted(device_samples.keys()),
                "community_samples": device_samples,
                "route_mode": mode,
            }
        )
        return self._format_result(state)

    def generate_device_health_report(
        self,
        *,
        role: UserRole,
        device_mac: str,
        start_at: datetime,
        end_at: datetime,
        samples: list[HealthSample],
        mode: str = "local",
    ) -> dict[str, object]:
        ordered = sorted(samples, key=lambda item: item.timestamp)
        analysis_payload = self._analysis.summarize_device(ordered)

        context_bundle: dict[str, Any] = {}
        if self._context_assembler is not None:
            try:
                context_bundle = self._context_assembler.build_device_context(
                    device_mac=device_mac,
                    samples=ordered,
                ).summary
            except Exception:
                context_bundle = {}

        model_signals = self._build_report_model_signals(
            role=role,
            device_mac=device_mac,
            samples=ordered,
            context_bundle=context_bundle,
        )
        health_model_evidence = self._build_report_health_model_evidence(
            device_mac=device_mac,
            samples=ordered,
            analysis_payload=analysis_payload,
            model_signals=model_signals,
        )
        knowledge_hits = self._rag.search(
            self._build_report_retrieval_query(
                role=role,
                device_mac=device_mac,
                start_at=start_at,
                end_at=end_at,
                analysis_payload=analysis_payload,
                model_signals=model_signals,
                health_model_evidence=health_model_evidence,
            ),
            top_k=self._settings.rag_top_k,
            network_online=False,
            allow_rerank=False,
        )

        prompt = self._build_report_prompt(
            role=role,
            device_mac=device_mac,
            start_at=start_at,
            end_at=end_at,
            analysis_payload=analysis_payload,
            knowledge_hits=knowledge_hits,
            context_bundle=context_bundle,
            model_signals=model_signals,
            health_model_evidence=health_model_evidence,
        )
        selected_model = self._select_report_model(
            role=role,
            requested_mode=mode,
        )
        summary = self._invoke_local(
            prompt["prompt_text"],
            prompt["messages"],
            selected_model=selected_model,
            system_prompt=prompt["system_prompt"],
            user_prompt=prompt["user_prompt"],
            max_predict_tokens=None,
            max_output_chars=None,
        )
        if not summary:
            summary = self._fallback_report_summary_with_model_signals(
                analysis_payload,
                model_signals=model_signals,
                health_model_evidence=health_model_evidence,
            )

        latest = analysis_payload.get("latest", {}) if isinstance(analysis_payload, dict) else {}
        averages = analysis_payload.get("averages", {}) if isinstance(analysis_payload, dict) else {}
        ranges = analysis_payload.get("ranges", {}) if isinstance(analysis_payload, dict) else {}
        trend = analysis_payload.get("trend", {}) if isinstance(analysis_payload, dict) else {}
        elder_profile = context_bundle.get("elder_profile", {}) if isinstance(context_bundle, dict) else {}
        device_row = context_bundle.get("device", {}) if isinstance(context_bundle, dict) else {}
        key_findings = self._build_report_key_findings(
            analysis_payload,
            model_signals=model_signals,
            health_model_evidence=health_model_evidence,
        )
        recommendations = self._build_report_recommendations(
            analysis_payload,
            model_signals=model_signals,
            health_model_evidence=health_model_evidence,
        )

        metrics = self._build_report_metrics(
            latest=latest if isinstance(latest, dict) else {},
            averages=averages if isinstance(averages, dict) else {},
            ranges=ranges if isinstance(ranges, dict) else {},
            trend=trend if isinstance(trend, dict) else {},
        )

        raw_report = {
            "report_type": "device_health_report",
            "device_mac": device_mac.upper(),
            "subject_name": elder_profile.get("name") if isinstance(elder_profile, dict) else None,
            "device_name": device_row.get("device_name") if isinstance(device_row, dict) else None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period": {
                "start_at": start_at.astimezone(timezone.utc).isoformat(),
                "end_at": end_at.astimezone(timezone.utc).isoformat(),
                "duration_minutes": max(int((end_at - start_at).total_seconds() // 60), 0),
                "sample_count": int(analysis_payload.get("sample_count", len(ordered))) if isinstance(analysis_payload, dict) else len(ordered),
            },
            "summary": summary,
            "risk_level": health_model_evidence.get("risk_level", "unknown"),
            "risk_flags": list(health_model_evidence.get("risk_flags", [])),
            "key_findings": key_findings,
            "recommendations": recommendations,
            "metrics": metrics,
            "references": knowledge_hits,
        }
        return sanitize_device_health_report(raw_report)

    def capability_report(self) -> dict[str, object]:
        return {
            "framework": {
                "langchain_prompt_available": ChatPromptTemplate is not None,
            },
            "llm_adapters": {
                "langchain_ollama": ChatOllama is not None,
            },
            "configured_models": {
                "ollama_base_url": self._settings.ollama_base_url,
                "ollama_model": self._settings.ollama_model,
                "default_local_model": self._settings.local_default_model,
                "reasoning_local_model": self._settings.local_reasoning_model,
                "report_local_model": self._settings.local_report_model,
                "approved_local_models": list(self._settings.supported_local_models),
                "local_model_routing": self._settings.local_model_routing,
                "local_report_routing": self._settings.local_report_routing,
                "execution_mode": "local_only",
            },
            "retrieval": self._rag.stats(),
            "extensions": {
                "context_assembler": self._context_assembler is not None,
                "tool_adapter": self._tool_adapter is not None,
                "model_suite": self._model_suite is not None,
                "mcp_connected": False,
                "cloud_mode_enabled": False,
                "offline_only_runtime": self._settings.offline_only_runtime,
            },
            "tool_specs": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "source": tool.source,
                }
                for tool in (self._tool_adapter.list_tools() if self._tool_adapter is not None else [])
            ],
        }

    def _execute(self, initial_state: AgentState) -> AgentState:
        state: AgentState = dict(initial_state)
        state.update(self._route_node(state))
        state.update(self._context_node(state))
        state.update(self._tool_node(state))
        state.update(self._analysis_node(state))
        state.update(self._model_node(state))
        state.update(self._dialogue_event_node(state))
        state.update(self._retrieve_node(state))
        state.update(self._prompt_node(state))
        state.update(self._generate_node(state))
        state.update(self._aggregate_node(state))
        return state

    def _route_node(self, state: AgentState) -> AgentState:
        selected_model = self._select_local_model(
            scope=str(state.get("scope", "device")),
            question=str(state.get("question", "")),
            requested_mode=str(state.get("route_mode", "local")),
        )
        return {
            "network_online": False,
            "selected_mode": "local",
            "selected_model": selected_model,
            "degraded_notes": ["offline_only_runtime"],
        }

    def _select_local_model(self, *, scope: str, question: str, requested_mode: str) -> str:
        del requested_mode

        approved = self._settings.supported_local_models
        default_model = self._settings.local_default_model
        reasoning_model = self._settings.local_reasoning_model

        if self._settings.local_model_routing == "single":
            return default_model

        question_text = question.lower()
        reasoning_keywords = (
            "community",
            "社区",
            "summary",
            "summarize",
            "汇总",
            "排序",
            "priorit",
            "trend",
            "原因",
            "归因",
            "explain",
        )
        if scope == "community" or any(keyword in question_text for keyword in reasoning_keywords):
            if reasoning_model in approved:
                return reasoning_model
        return default_model

    def _select_report_model(
        self,
        *,
        role: UserRole,
        requested_mode: str,
    ) -> str:
        del requested_mode

        approved = self._settings.supported_local_models
        report_model = self._settings.local_report_model
        reasoning_model = self._settings.local_reasoning_model

        if self._settings.local_report_routing == "role_router":
            if role in {UserRole.COMMUNITY, UserRole.ADMIN} and reasoning_model in approved:
                return reasoning_model

        if report_model in approved:
            return report_model
        return self._settings.local_default_model

    def _context_node(self, state: AgentState) -> AgentState:
        if self._context_assembler is None:
            return {"context_bundle": {}, "degraded_notes": ["context_assembler_not_configured"]}

        scope = str(state.get("scope", "device"))
        try:
            if scope == "community":
                bundle = self._context_assembler.build_community_context(
                    device_macs=list(state.get("target_device_macs", [])),
                    device_samples=dict(state.get("community_samples", {})),
                )
            else:
                device_mac = str(state.get("target_device_mac", "")).strip()
                if not device_mac and state.get("samples"):
                    device_mac = list(state.get("samples", []))[-1].device_mac
                bundle = self._context_assembler.build_device_context(
                    device_mac=device_mac,
                    samples=list(state.get("samples", [])),
                )
            return {
                "context_bundle": bundle.summary,
                "degraded_notes": list(bundle.degraded),
            }
        except Exception as exc:
            return {
                "context_bundle": {},
                "degraded_notes": [f"context_build_failed:{exc.__class__.__name__}"],
            }

    def _tool_node(self, state: AgentState) -> AgentState:
        if self._tool_adapter is None:
            return {"tool_results": []}

        scope = str(state.get("scope", "device"))
        role = str(state.get("role", ""))
        community_id = None
        context_bundle = state.get("context_bundle", {})
        if isinstance(context_bundle, dict):
            community_value = context_bundle.get("community")
            if isinstance(community_value, dict):
                community_id = str(community_value.get("id", "")) or None

        calls: list[ToolInvocation] = []
        if scope == "community":
            calls.extend(
                [
                    ToolInvocation(name="get_community_overview", request_id=str(uuid4()), operator_role=role, community_id=community_id),
                    ToolInvocation(name="get_active_alarms", request_id=str(uuid4()), operator_role=role, community_id=community_id, payload={"active_only": True}),
                    ToolInvocation(name="get_care_directory", request_id=str(uuid4()), operator_role=role, community_id=community_id),
                ]
            )
        else:
            device_mac = str(state.get("target_device_mac", "")).strip()
            calls.extend(
                [
                    ToolInvocation(name="get_device_realtime", request_id=str(uuid4()), operator_role=role, community_id=community_id, payload={"mac_address": device_mac}),
                    ToolInvocation(name="get_device_status", request_id=str(uuid4()), operator_role=role, community_id=community_id, payload={"mac_address": device_mac}),
                    ToolInvocation(name="get_active_alarms", request_id=str(uuid4()), operator_role=role, community_id=community_id, payload={"mac_address": device_mac, "active_only": True}),
                    ToolInvocation(name="get_elder_profile", request_id=str(uuid4()), operator_role=role, community_id=community_id, payload={"mac_address": device_mac}),
                ]
            )

        results = self._tool_adapter.invoke_many(calls)
        return {
            "tool_results": [
                {
                    "request_id": call.request_id,
                    "name": item.name,
                    "status": item.status,
                    "success": item.success,
                    "source": item.source,
                    "data": item.data,
                    "error_code": item.error_code,
                    "error_message": item.error_message,
                }
                for call, item in zip(calls, results, strict=False)
            ]
        }

    def _analysis_node(self, state: AgentState) -> AgentState:
        scope = str(state.get("scope", "device"))
        question = str(state.get("question", "")).strip()
        if scope == "community":
            payload = self._analysis.summarize_community_history(dict(state.get("community_samples", {})))
        else:
            payload = self._analysis.summarize_device(list(state.get("samples", [])))

        context_bundle = dict(state.get("context_bundle", {}))
        context_bundle["analysis_recommendations"] = payload.get("recommendations", []) if isinstance(payload, dict) else []

        return {
            "context_bundle": context_bundle,
            "analysis_payload": payload,
            "analysis_context": json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            "retrieval_query": self._build_retrieval_query(scope=scope, question=question, analysis_payload=payload),
        }

    def _model_node(self, state: AgentState) -> AgentState:
        if self._model_suite is None:
            return {"model_results": {}}

        model_input = AgentModelInput(
            scope=str(state.get("scope", "device")),
            role=state.get("role", UserRole.FAMILY),
            question=str(state.get("question", "")),
            device_mac=str(state.get("target_device_mac", "")).strip() or None,
            device_macs=list(state.get("target_device_macs", [])),
            samples=list(state.get("samples", [])),
            community_samples=dict(state.get("community_samples", {})),
            alarms=[],
            context=dict(state.get("context_bundle", {})),
        )
        tool_alarm_payloads = [
            item.get("data", {}).get("alarms", [])
            for item in state.get("tool_results", [])
            if item.get("name") == "get_active_alarms"
        ]
        flat_alarm_payloads = [alarm for batch in tool_alarm_payloads if isinstance(batch, list) for alarm in batch]
        model_input.alarms = [_alarm_from_payload(payload) for payload in flat_alarm_payloads]
        results = self._model_suite.run_all(model_input)
        return {
            "model_results": {
                key: {
                    "model_name": value.model_name,
                    "status": value.status,
                    "source": value.source,
                    "summary": value.summary,
                    "payload": value.payload,
                    "confidence": value.confidence,
                    "degraded_reason": value.degraded_reason,
                }
                for key, value in results.items()
            }
        }

    def _dialogue_event_node(self, state: AgentState) -> AgentState:
        analysis_payload = dict(state.get("analysis_payload", {}))
        model_results = dict(state.get("model_results", {}))
        context_bundle = dict(state.get("context_bundle", {}))
        scope = str(state.get("scope", "device"))
        role = state.get("role", UserRole.FAMILY)
        question = str(state.get("question", "")).strip()

        event_layer = self._build_dialogue_event_layer(
            scope=scope,
            role=role,
            analysis_payload=analysis_payload,
            model_results=model_results,
            context_bundle=context_bundle,
        )
        expression = self._build_dialogue_expression(
            scope=scope,
            role=role,
            analysis_payload=analysis_payload,
            event_layer=event_layer,
        )
        retrieval_query = self._build_dialogue_retrieval_query(
            scope=scope,
            question=question,
            analysis_payload=analysis_payload,
            event_layer=event_layer,
        )
        return {
            "dialogue_events": list(event_layer.get("events", [])),
            "dialogue_action_labels": list(event_layer.get("action_labels", [])),
            "dialogue_expression": expression,
            "retrieval_query": retrieval_query or str(state.get("retrieval_query", "")),
        }

    def _build_dialogue_event_layer(
        self,
        *,
        scope: str,
        role: UserRole,
        analysis_payload: dict[str, Any],
        model_results: dict[str, dict[str, Any]],
        context_bundle: dict[str, Any],
    ) -> dict[str, Any]:
        del role
        if scope == "community":
            return self._build_community_dialogue_events(analysis_payload)
        return self._build_device_dialogue_events(
            analysis_payload=analysis_payload,
            model_results=model_results,
            context_bundle=context_bundle,
        )

    def _build_device_dialogue_events(
        self,
        *,
        analysis_payload: dict[str, Any],
        model_results: dict[str, dict[str, Any]],
        context_bundle: dict[str, Any],
    ) -> dict[str, Any]:
        latest = analysis_payload.get("latest", {})
        trend = analysis_payload.get("trend", {})
        data_quality = analysis_payload.get("data_quality", {})
        risk_flags = [str(item) for item in analysis_payload.get("risk_flags", [])]
        risk_level = str(analysis_payload.get("risk_level", "unknown"))

        anomaly_result = model_results.get("anomaly_explain", {})
        anomaly_payload = anomaly_result.get("payload", {}) if isinstance(anomaly_result, dict) else {}
        alarm_payloads = [
            item.get("data", {}).get("alarms", [])
            for item in context_bundle.get("tool_results", [])
        ] if False else []
        active_alarm_rows = context_bundle.get("active_alarms", []) if isinstance(context_bundle, dict) else []
        active_alarm_count = len(active_alarm_rows) if isinstance(active_alarm_rows, list) else 0

        events: list[dict[str, Any]] = []

        spo2 = latest.get("blood_oxygen") if isinstance(latest, dict) else None
        spo2_trend = trend.get("blood_oxygen", {}) if isinstance(trend, dict) else {}
        if (
            isinstance(spo2, (int, float)) and spo2 <= 94
            or "blood_oxygen_warning" in risk_flags
            or "blood_oxygen_critical" in risk_flags
            or (isinstance(spo2_trend, dict) and str(spo2_trend.get("label", "")) == "falling")
        ):
            severity = "low"
            urgency = "routine"
            if isinstance(spo2, (int, float)):
                if spo2 <= 88:
                    severity, urgency = "critical", "immediate"
                elif spo2 <= 90:
                    severity, urgency = "high", "soon"
                elif spo2 <= 92:
                    severity, urgency = "medium", "today"
            if str(spo2_trend.get("label", "")) == "falling" and severity == "low":
                severity, urgency = "medium", "today"
            events.append(
                {
                    "event_code": "low_oxygen_risk",
                    "event_name": "低氧风险",
                    "severity": severity,
                    "urgency": urgency,
                    "status": "active",
                    "summary": "当前血氧偏低并呈下降趋势" if str(spo2_trend.get("label", "")) == "falling" else "当前血氧偏低",
                    "evidence": {
                        "current_spo2": spo2,
                        "trend_label": str(spo2_trend.get("label", "")),
                        "trend_delta": spo2_trend.get("delta"),
                    },
                    "recommended_action_levels": [
                        "rest_in_sitting_position",
                        "remeasure_spo2_30min",
                        "watch_breathing_symptoms",
                        "seek_medical_help_if_persistent",
                    ],
                }
            )

        temp = latest.get("temperature") if isinstance(latest, dict) else None
        temp_trend = trend.get("temperature", {}) if isinstance(trend, dict) else {}
        if (
            isinstance(temp, (int, float)) and temp >= 37.5
            or "temperature_warning" in risk_flags
            or "temperature_critical" in risk_flags
            or (isinstance(temp_trend, dict) and str(temp_trend.get("label", "")) == "rising" and isinstance(temp, (int, float)) and temp >= 37.2)
        ):
            severity = "low"
            urgency = "routine"
            if isinstance(temp, (int, float)):
                if temp >= 39.0:
                    severity, urgency = "critical", "immediate"
                elif temp >= 38.5:
                    severity, urgency = "high", "soon"
                elif temp >= 38.0:
                    severity, urgency = "medium", "today"
            events.append(
                {
                    "event_code": "temperature_warning",
                    "event_name": "体温异常",
                    "severity": severity,
                    "urgency": urgency,
                    "status": "active",
                    "summary": "体温偏高，需要继续观察变化",
                    "evidence": {
                        "current_temperature": temp,
                        "trend_label": str(temp_trend.get("label", "")),
                        "trend_delta": temp_trend.get("delta"),
                    },
                    "recommended_action_levels": [
                        "remeasure_temperature_30min",
                        "watch_fever_symptoms",
                        "notify_family_member",
                    ],
                }
            )

        if isinstance(anomaly_payload, dict):
            probability = anomaly_payload.get("probability")
            sustained_minutes = anomaly_payload.get("sustained_minutes")
            alarm_ready = bool(anomaly_payload.get("alarm_ready", False))
            if isinstance(probability, (int, float)) and probability >= 0.45:
                events.append(
                    {
                        "event_code": "single_abnormality",
                        "event_name": "异常波动",
                        "severity": "medium" if probability >= 0.6 else "low",
                        "urgency": "today" if probability >= 0.6 else "routine",
                        "status": "active",
                        "summary": str(anomaly_payload.get("reason", "")).strip() or "出现值得继续观察的异常波动",
                        "evidence": {
                            "probability": probability,
                            "sustained_minutes": sustained_minutes,
                        },
                        "recommended_action_levels": ["continue_observation", "remeasure_vitals_60min"],
                    }
                )
            if isinstance(sustained_minutes, (int, float)) and sustained_minutes >= 20:
                events.append(
                    {
                        "event_code": "sustained_abnormality",
                        "event_name": "持续异常",
                        "severity": "high" if sustained_minutes >= 40 else "medium",
                        "urgency": "soon" if sustained_minutes >= 40 else "today",
                        "status": "active",
                        "summary": f"异常状态已持续约 {sustained_minutes:.0f} 分钟",
                        "evidence": {
                            "sustained_minutes": sustained_minutes,
                            "reason": str(anomaly_payload.get("reason", "")).strip(),
                        },
                        "recommended_action_levels": ["community_followup_needed", "notify_family_member"],
                    }
                )
            if alarm_ready or active_alarm_count > 0:
                events.append(
                    {
                        "event_code": "alarm_ready",
                        "event_name": "需要立即复核",
                        "severity": "high",
                        "urgency": "immediate",
                        "status": "active",
                        "summary": "当前异常已达到需要立即复核的程度",
                        "evidence": {
                            "alarm_ready": alarm_ready,
                            "active_alarm_count": active_alarm_count,
                        },
                        "recommended_action_levels": [
                            "community_followup_needed",
                            "notify_family_member",
                            "seek_medical_help_if_persistent",
                        ],
                    }
                )

        score_trend = trend.get("health_score", {}) if isinstance(trend, dict) else {}
        active_problem_count = len(events)
        if active_problem_count >= 2 or (
            isinstance(score_trend, dict) and str(score_trend.get("label", "")) == "falling" and active_problem_count >= 1
        ):
            events.append(
                {
                    "event_code": "multi_signal_deterioration",
                    "event_name": "多指标联动恶化",
                    "severity": "high" if active_problem_count >= 3 or risk_level == "high" else "medium",
                    "urgency": "soon" if active_problem_count >= 3 else "today",
                    "status": "active",
                    "summary": "近一段时间多项指标同时变差，整体状态较前走弱",
                    "evidence": {
                        "event_count": active_problem_count,
                        "risk_level": risk_level,
                        "health_score_trend": str(score_trend.get("label", "")) if isinstance(score_trend, dict) else "",
                    },
                    "recommended_action_levels": [
                        "notify_family_member",
                        "community_followup_needed",
                        "seek_medical_help_if_persistent",
                    ],
                }
            )

        if not events and (
            (isinstance(score_trend, dict) and str(score_trend.get("label", "")) == "falling")
            or list(analysis_payload.get("recommendations", []))
        ):
            events.append(
                {
                    "event_code": "followup_needed",
                    "event_name": "需要继续观察",
                    "severity": "low" if risk_level == "low" else "medium",
                    "urgency": "today",
                    "status": "active",
                    "summary": "当前未到高危，但趋势提示还需要继续观察",
                    "evidence": {
                        "risk_level": risk_level,
                        "health_score_trend": str(score_trend.get("label", "")) if isinstance(score_trend, dict) else "",
                    },
                    "recommended_action_levels": ["continue_observation", "remeasure_vitals_60min"],
                }
            )

        if isinstance(data_quality, dict) and int(data_quality.get("gaps_over_30_minutes", 0) or 0) > 0:
            events.append(
                {
                    "event_code": "data_quality_limited",
                    "event_name": "数据质量受限",
                    "severity": "low",
                    "urgency": "routine",
                    "status": "active",
                    "summary": "当前数据存在时间缺口，需要先核对设备与采集情况",
                    "evidence": {
                        "gaps_over_30_minutes": int(data_quality.get("gaps_over_30_minutes", 0) or 0),
                    },
                    "recommended_action_levels": ["check_device_wearing", "remeasure_after_device_check"],
                }
            )

        action_labels = self._collect_dialogue_action_labels(events)
        return {
            "events": events,
            "action_labels": action_labels,
            "primary_event": self._pick_primary_dialogue_event(events),
        }

    def _build_community_dialogue_events(self, analysis_payload: dict[str, Any]) -> dict[str, Any]:
        distribution = analysis_payload.get("risk_distribution", {}) if isinstance(analysis_payload, dict) else {}
        priority_devices = list(analysis_payload.get("priority_devices", [])) if isinstance(analysis_payload, dict) else []
        device_count = int(analysis_payload.get("device_count", 0)) if isinstance(analysis_payload, dict) else 0
        high_count = int(distribution.get("high", 0)) if isinstance(distribution, dict) else 0
        medium_count = int(distribution.get("medium", 0)) if isinstance(distribution, dict) else 0

        events: list[dict[str, Any]] = []
        if high_count > 0:
            events.append(
                {
                    "event_code": "community_followup_needed",
                    "event_name": "社区优先跟进",
                    "severity": "high",
                    "urgency": "soon",
                    "status": "active",
                    "summary": f"当前有 {high_count} 台高风险设备需要优先处理",
                    "evidence": {
                        "device_count": device_count,
                        "high_count": high_count,
                        "medium_count": medium_count,
                    },
                    "recommended_action_levels": ["prioritize_phone_followup", "arrange_onsite_review"],
                }
            )
        elif medium_count > 0:
            events.append(
                {
                    "event_code": "followup_needed",
                    "event_name": "需要继续跟进",
                    "severity": "medium",
                    "urgency": "today",
                    "status": "active",
                    "summary": f"当前有 {medium_count} 台中风险设备需要今天内继续跟进",
                    "evidence": {
                        "device_count": device_count,
                        "medium_count": medium_count,
                    },
                    "recommended_action_levels": ["prioritize_phone_followup"],
                }
            )
        if not events:
            events.append(
                {
                    "event_code": "single_abnormality",
                    "event_name": "整体基本平稳",
                    "severity": "low",
                    "urgency": "routine",
                    "status": "active",
                    "summary": "当前社区整体风险较低，以常规观察为主",
                    "evidence": {
                        "device_count": device_count,
                    },
                    "recommended_action_levels": ["continue_observation"],
                }
            )
        return {
            "events": events,
            "action_labels": self._collect_dialogue_action_labels(events),
            "primary_event": self._pick_primary_dialogue_event(events),
            "priority_devices": priority_devices,
        }

    @staticmethod
    def _severity_rank(level: str) -> int:
        return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(level, 0)

    def _pick_primary_dialogue_event(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        if not events:
            return {}
        return sorted(events, key=lambda item: (self._severity_rank(str(item.get("severity", ""))), str(item.get("urgency", ""))), reverse=True)[0]

    def _collect_dialogue_action_labels(self, events: list[dict[str, Any]]) -> list[str]:
        labels: list[str] = []
        seen: set[str] = set()
        for event in events:
            for item in event.get("recommended_action_levels", []):
                code = str(item).strip()
                if not code or code in seen:
                    continue
                seen.add(code)
                labels.append(code)
        return labels

    def _build_dialogue_expression(
        self,
        *,
        scope: str,
        role: UserRole,
        analysis_payload: dict[str, Any],
        event_layer: dict[str, Any],
    ) -> dict[str, Any]:
        if scope == "community":
            answer = self._render_community_dialogue(role=role, analysis_payload=analysis_payload, event_layer=event_layer)
        else:
            answer = self._render_device_dialogue(role=role, analysis_payload=analysis_payload, event_layer=event_layer)
        return {
            "answer": answer,
            "primary_event_code": str(event_layer.get("primary_event", {}).get("event_code", "")),
        }

    def _render_device_dialogue(
        self,
        *,
        role: UserRole,
        analysis_payload: dict[str, Any],
        event_layer: dict[str, Any],
    ) -> str:
        latest = analysis_payload.get("latest", {}) if isinstance(analysis_payload, dict) else {}
        primary_event = event_layer.get("primary_event", {}) if isinstance(event_layer, dict) else {}
        actions = list(event_layer.get("action_labels", [])) if isinstance(event_layer, dict) else []
        event_code = str(primary_event.get("event_code", ""))
        severity = str(primary_event.get("severity", "low"))
        summary = str(primary_event.get("summary", "")).strip() or "当前还需要继续观察。"

        if role == UserRole.ELDER:
            first = {
                "low_oxygen_risk": "现在血氧有点偏低。",
                "temperature_warning": "现在体温有点不稳。",
                "sustained_abnormality": "现在状态需要多留意一下。",
                "alarm_ready": "现在情况不太稳定。",
                "multi_signal_deterioration": "最近身体状态有点变差。",
            }.get(event_code, "现在还需要再看看。")
            action_text = self._render_action_sentence(role, actions[0] if actions else "continue_observation")
            escalate = ""
            if severity in {"high", "critical"}:
                escalate = "如果还是不舒服，可以马上请家人或社区人员帮你看看。"
            return " ".join(part for part in [first, action_text, escalate] if part).strip()

        if role == UserRole.COMMUNITY:
            overall = {
                "critical": "当前为紧急风险。",
                "high": "当前为高风险。",
                "medium": "当前为中风险。",
            }.get(severity, "当前为低风险。")
            priority = "建议优先处理当前对象。" if severity in {"medium", "high", "critical"} else ""
            reason = f"主要问题是：{summary}"
            action = self._render_action_sentence(role, actions[0] if actions else "continue_observation")
            next_action = self._render_action_sentence(role, actions[1] if len(actions) > 1 else "")
            return " ".join(part for part in [overall, priority, reason, action, next_action] if part).strip()

        # family
        stable_text = {
            "critical": "当前整体状态不稳定，需要立即处理。",
            "high": "当前整体风险较高，需要尽快处理。",
            "medium": "当前整体存在中等风险，需要重点关注。",
        }.get(severity, "当前整体还算平稳，但需要继续观察。")
        reason = f"主要原因是：{summary}"
        action = self._render_action_sentence(role, actions[0] if actions else "continue_observation")
        escalate = self._render_escalation_sentence(event_code=event_code, latest=latest)
        return " ".join(part for part in [stable_text, reason, action, escalate] if part).strip()

    def _render_community_dialogue(
        self,
        *,
        role: UserRole,
        analysis_payload: dict[str, Any],
        event_layer: dict[str, Any],
    ) -> str:
        distribution = analysis_payload.get("risk_distribution", {}) if isinstance(analysis_payload, dict) else {}
        priority_devices = list(event_layer.get("priority_devices", [])) if isinstance(event_layer, dict) else []
        primary_event = event_layer.get("primary_event", {}) if isinstance(event_layer, dict) else {}
        actions = list(event_layer.get("action_labels", [])) if isinstance(event_layer, dict) else []
        if role == UserRole.FAMILY:
            return "当前主要是社区侧的整体风险判断，如果你是家属，请优先关注与你家老人相关的设备提示。"
        if role == UserRole.ELDER:
            return "现在社区正在关注整体情况，如果你感觉不舒服，可以先请家人或社区工作人员帮你看看。"

        high_count = int(distribution.get("high", 0)) if isinstance(distribution, dict) else 0
        medium_count = int(distribution.get("medium", 0)) if isinstance(distribution, dict) else 0
        overall = (
            f"当前社区整体判断为：高风险设备 {high_count} 台，中风险设备 {medium_count} 台。"
            if high_count or medium_count
            else "当前社区整体风险较低，以常规观察为主。"
        )
        priority_text = ""
        if priority_devices:
            first = priority_devices[0]
            if isinstance(first, dict):
                priority_text = (
                    f"优先处理设备 {first.get('device_mac', '')}，"
                    f"原因是 {', '.join(str(item) for item in first.get('notable_events', [])[:1]) or str(primary_event.get('summary', '存在较高关注需求'))}。"
                )
        action = self._render_action_sentence(role, actions[0] if actions else "continue_observation")
        next_action = self._render_action_sentence(role, actions[1] if len(actions) > 1 else "")
        return " ".join(part for part in [overall, priority_text, action, next_action] if part).strip()

    def _render_action_sentence(self, role: UserRole, action_code: str) -> str:
        if not action_code:
            return ""
        mapping = {
            "rest_in_sitting_position": {
                UserRole.ELDER: "建议先坐着休息一下。",
                UserRole.FAMILY: "建议先让老人保持坐位或半卧位休息。",
                UserRole.COMMUNITY: "建议先指导老人保持坐位休息。",
            },
            "remeasure_spo2_30min": {
                UserRole.ELDER: "建议 30 分钟后再量一次。",
                UserRole.FAMILY: "建议每 30 分钟复测 1 次血氧。",
                UserRole.COMMUNITY: "建议 30 分钟内完成一次复测并记录结果。",
            },
            "watch_breathing_symptoms": {
                UserRole.ELDER: "如果觉得喘不过气，要马上告诉家人。",
                UserRole.FAMILY: "请留意是否出现气短、胸闷或呼吸不顺。",
                UserRole.COMMUNITY: "电话核实时要重点询问呼吸症状变化。",
            },
            "seek_medical_help_if_persistent": {
                UserRole.ELDER: "如果一直没有好转，可以请家人尽快带你去看医生。",
                UserRole.FAMILY: "如果持续异常没有改善，请尽快联系医生或就医。",
                UserRole.COMMUNITY: "若持续异常，应升级为转诊或现场干预。",
            },
            "notify_family_member": {
                UserRole.ELDER: "可以请家人现在帮你看一下。",
                UserRole.FAMILY: "建议现在把情况同步给主要照护家属。",
                UserRole.COMMUNITY: "建议同步通知家属参与后续处理。",
            },
            "community_followup_needed": {
                UserRole.ELDER: "可以请社区人员帮忙留意一下。",
                UserRole.FAMILY: "如家里处理不便，可请社区人员跟进。",
                UserRole.COMMUNITY: "建议尽快列入社区跟进清单。",
            },
            "prioritize_phone_followup": {
                UserRole.COMMUNITY: "建议先电话随访核实当前状态。",
            },
            "arrange_onsite_review": {
                UserRole.COMMUNITY: "如电话随访无法确认状态，建议安排上门复核。",
            },
            "continue_observation": {
                UserRole.ELDER: "现在先继续观察一下就好。",
                UserRole.FAMILY: "建议继续观察接下来几次测量变化。",
                UserRole.COMMUNITY: "先纳入常规观察即可。",
            },
            "remeasure_vitals_60min": {
                UserRole.ELDER: "可以晚一点再量一次看看。",
                UserRole.FAMILY: "建议 1 小时内再复测一次关键指标。",
                UserRole.COMMUNITY: "建议在下一轮巡查前完成一次复测。",
            },
            "remeasure_temperature_30min": {
                UserRole.ELDER: "建议过一会再量一下体温。",
                UserRole.FAMILY: "建议 30 分钟后复测体温。",
                UserRole.COMMUNITY: "建议尽快复测体温并记录变化。",
            },
            "watch_fever_symptoms": {
                UserRole.ELDER: "如果觉得发冷、发热或更不舒服，要告诉家人。",
                UserRole.FAMILY: "请同时留意精神状态、食欲和发热症状。",
                UserRole.COMMUNITY: "随访时重点核实发热相关症状和持续时间。",
            },
            "check_device_wearing": {
                UserRole.ELDER: "先看看设备有没有戴好。",
                UserRole.FAMILY: "建议先检查设备佩戴状态和电量。",
                UserRole.COMMUNITY: "建议先排查设备佩戴和采集链路。",
            },
            "remeasure_after_device_check": {
                UserRole.ELDER: "调整好设备后再量一次。",
                UserRole.FAMILY: "排查设备后建议重新测一次。",
                UserRole.COMMUNITY: "排查设备后再复测一次，确认是否仍异常。",
            },
        }
        role_mapping = mapping.get(action_code, {})
        return role_mapping.get(role, role_mapping.get(UserRole.FAMILY, ""))

    def _render_escalation_sentence(self, *, event_code: str, latest: dict[str, Any]) -> str:
        spo2 = latest.get("blood_oxygen") if isinstance(latest, dict) else None
        if event_code == "low_oxygen_risk":
            if isinstance(spo2, (int, float)):
                if spo2 <= 92:
                    return "如果连续两次低于 92%，或出现气短、胸闷，请尽快就医。"
            return "如果继续下降或伴随不适，请尽快联系医生或社区人员。"
        if event_code in {"alarm_ready", "sustained_abnormality", "multi_signal_deterioration"}:
            return "如果接下来仍持续变差，建议尽快联系医生或社区人员处理。"
        return ""

    def _build_dialogue_retrieval_query(
        self,
        *,
        scope: str,
        question: str,
        analysis_payload: dict[str, Any],
        event_layer: dict[str, Any],
    ) -> str:
        primary_event = event_layer.get("primary_event", {}) if isinstance(event_layer, dict) else {}
        action_labels = list(event_layer.get("action_labels", [])) if isinstance(event_layer, dict) else []
        if scope == "community":
            distribution = analysis_payload.get("risk_distribution", {}) if isinstance(analysis_payload, dict) else {}
            return " ".join(
                part
                for part in [
                    question,
                    str(primary_event.get("event_code", "")),
                    str(primary_event.get("summary", "")),
                    f"high={distribution.get('high', 0)}" if isinstance(distribution, dict) else "",
                    f"medium={distribution.get('medium', 0)}" if isinstance(distribution, dict) else "",
                    *action_labels[:3],
                ]
                if part
            )
        return " ".join(
            part
            for part in [
                question,
                str(primary_event.get("event_code", "")),
                str(primary_event.get("summary", "")),
                str(primary_event.get("severity", "")),
                *action_labels[:4],
            ]
            if part
        )

    def _retrieve_node(self, state: AgentState) -> AgentState:
        query = str(state.get("retrieval_query") or state.get("question", "")).strip()
        if not query:
            return {"knowledge_hits": []}

        hits = self._rag.search(
            query,
            top_k=self._settings.rag_top_k,
            network_online=False,
            allow_rerank=False,
        )
        return {"knowledge_hits": hits}

    def _prompt_node(self, state: AgentState) -> AgentState:
        package = build_prompt_package(
            role=state.get("role", UserRole.FAMILY),
            scope=str(state.get("scope", "device")),
            question=str(state.get("question", "")),
            analysis_context=self._compose_analysis_context(state),
            knowledge_context="\n\n".join(state.get("knowledge_hits", [])),
        )
        system_text = package["system"]
        user_text = package["user"]
        prompt_text = f"{system_text}\n\n{user_text}".strip()
        messages: list[Any] = []
        if ChatPromptTemplate is not None:
            try:
                prompt = ChatPromptTemplate.from_messages([("system", system_text), ("human", user_text)])
                messages = prompt.format_messages()
            except Exception:
                messages = []
        return {
            "system_prompt": system_text,
            "user_prompt": user_text,
            "prompt_text": prompt_text,
            "messages": messages,
        }

    def _generate_node(self, state: AgentState) -> AgentState:
        prompt_text = str(state.get("prompt_text", "")).strip()
        system_prompt = str(state.get("system_prompt", "")).strip()
        user_prompt = str(state.get("user_prompt", "")).strip()
        messages = list(state.get("messages", []))
        scope = str(state.get("scope", "device"))
        selected_model = str(state.get("selected_model", self._settings.local_default_model))
        dialogue_expression = dict(state.get("dialogue_expression", {}))

        if not prompt_text:
            fallback = str(dialogue_expression.get("answer", "")).strip() or self._fallback_answer(state.get("analysis_payload", {}), scope)
            return {"answer": fallback, "selected_mode": "local"}

        _ = self._invoke_local(
            prompt_text,
            messages,
            selected_model=selected_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_predict_tokens=self._settings.dialogue_max_predict_tokens,
            max_output_chars=self._settings.dialogue_max_output_chars,
        )
        event_answer = str(dialogue_expression.get("answer", "")).strip()
        if event_answer:
            return {"answer": event_answer, "selected_mode": "local"}
        return {"answer": self._fallback_answer(state.get("analysis_payload", {}), scope), "selected_mode": "local"}

    def _aggregate_node(self, state: AgentState) -> AgentState:
        final_payload = {
            "scope": str(state.get("scope", "device")),
            "mode": str(state.get("selected_mode", "local")),
            "network_online": False,
            "selected_model": str(state.get("selected_model", self._settings.local_default_model)),
            "answer": str(state.get("answer", "")).strip(),
            "references": list(state.get("knowledge_hits", [])),
            "analysis": dict(state.get("analysis_payload", {})),
            "context": dict(state.get("context_bundle", {})),
            "tool_results": list(state.get("tool_results", [])),
            "model_results": dict(state.get("model_results", {})),
            "degraded": list(state.get("degraded_notes", [])),
        }
        return {"final_payload": final_payload}

    def _invoke_local(
        self,
        prompt_text: str,
        messages: list[Any],
        *,
        selected_model: str,
        system_prompt: str = "",
        user_prompt: str = "",
        max_predict_tokens: int | None = None,
        max_output_chars: int | None = None,
    ) -> str | None:
        if ChatOllama is not None:
            local_llm = self._build_local_llm(selected_model, max_predict_tokens=max_predict_tokens)
            if local_llm is not None:
                try:
                    response = local_llm.invoke(messages or prompt_text)
                    answer = self._extract_message_text(response)
                    if answer:
                        return self._truncate_output(answer, max_output_chars)
                except Exception:
                    pass
        return self._truncate_output(
            self._call_ollama_http(
                prompt_text,
                selected_model=selected_model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_predict_tokens=max_predict_tokens,
            ),
            max_output_chars,
        )

    def _build_local_llm(self, model_name: str, *, max_predict_tokens: int | None = None):
        if ChatOllama is None:
            return None
        cache_key = f"{model_name}|{max_predict_tokens or 'default'}"
        if cache_key in self._local_llms:
            return self._local_llms[cache_key]
        try:
            kwargs: dict[str, Any] = {
                "model": model_name,
                "base_url": self._settings.ollama_base_url,
                "temperature": 0.2,
            }
            if max_predict_tokens is not None:
                kwargs["num_predict"] = max_predict_tokens
            llm = ChatOllama(**kwargs)
            self._local_llms[cache_key] = llm
            return llm
        except Exception:
            return None

    def _call_ollama_http(
        self,
        prompt_text: str,
        *,
        selected_model: str,
        system_prompt: str = "",
        user_prompt: str = "",
        max_predict_tokens: int | None = None,
    ) -> str | None:
        url = f"{self._settings.ollama_base_url.rstrip('/')}/api/chat"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if user_prompt:
            messages.append({"role": "user", "content": user_prompt})
        if not messages:
            messages.append({"role": "user", "content": prompt_text})
        payload = json.dumps(
            {
                "model": selected_model,
                "stream": False,
                "messages": messages,
                "options": {"num_predict": max_predict_tokens} if max_predict_tokens is not None else {},
            },
            ensure_ascii=False,
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        return self._post_json(
            url,
            payload,
            headers,
            parser=lambda body: body.get("message", {}).get("content"),
        )

    @staticmethod
    def _truncate_output(text: str | None, max_output_chars: int | None) -> str | None:
        if text is None:
            return None
        value = str(text).strip()
        if not value:
            return None
        if max_output_chars is None or max_output_chars <= 0 or len(value) <= max_output_chars:
            return value
        clipped = value[:max_output_chars]
        sentence_break = max(
            clipped.rfind("。"),
            clipped.rfind("！"),
            clipped.rfind("？"),
            clipped.rfind(". "),
            clipped.rfind("! "),
            clipped.rfind("? "),
            clipped.rfind("；"),
            clipped.rfind(";"),
        )
        if sentence_break >= max(0, max_output_chars // 2):
            clipped = clipped[: sentence_break + 1]
        clipped = clipped.rstrip(" \n，,;；:：")
        return f"{clipped}…"

    def _post_json(self, url: str, payload: bytes, headers: dict[str, str], parser) -> str | None:
        req = request.Request(url=url, data=payload, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=self._settings.llm_timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
                parsed = parser(body)
                return str(parsed).strip() if parsed else None
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
            return None

    def _build_report_model_signals(
        self,
        *,
        role: UserRole,
        device_mac: str,
        samples: list[HealthSample],
        context_bundle: dict[str, Any],
    ) -> dict[str, Any]:
        if self._model_suite is None or not samples:
            return {}
        active_alarm_rows = context_bundle.get("active_alarms", []) if isinstance(context_bundle, dict) else []
        alarms = [_alarm_from_payload(row) for row in active_alarm_rows if isinstance(row, dict)]
        try:
            results = self._model_suite.run_all(
                AgentModelInput(
                    scope="device",
                    role=role,
                    question="health report",
                    device_mac=device_mac.upper(),
                    samples=samples,
                    alarms=alarms,
                    context=context_bundle if isinstance(context_bundle, dict) else {},
                )
            )
        except Exception:
            return {}

        payload: dict[str, Any] = {}
        for key in (
            "health_assessment",
            "risk_scoring",
            "anomaly_explain",
            "care_suggestion",
            "alarm_interpretation",
        ):
            result = results.get(key)
            if result is None:
                continue
            payload[key] = {
                "status": result.status,
                "source": result.source,
                "summary": result.summary,
                "payload": dict(result.payload),
                "confidence": result.confidence,
            }
        return payload

    def _build_report_health_model_evidence(
        self,
        *,
        device_mac: str,
        samples: list[HealthSample],
        analysis_payload: dict[str, Any],
        model_signals: dict[str, Any],
    ) -> dict[str, Any]:
        risk_level = str(analysis_payload.get("risk_level", "unknown")) if isinstance(analysis_payload, dict) else "unknown"
        raw_risk_flags = list(analysis_payload.get("risk_flags", [])) if isinstance(analysis_payload, dict) else []
        risk_flags = self._unique_texts(
            [flag for flag in raw_risk_flags if str(flag).strip() and str(flag) != "within_expected_range"],
            limit=8,
        )
        latest = analysis_payload.get("latest", {}) if isinstance(analysis_payload, dict) else {}
        averages = analysis_payload.get("averages", {}) if isinstance(analysis_payload, dict) else {}
        trend = analysis_payload.get("trend", {}) if isinstance(analysis_payload, dict) else {}
        notable_events = list(analysis_payload.get("notable_events", [])) if isinstance(analysis_payload, dict) else []
        recommendations = list(analysis_payload.get("recommendations", [])) if isinstance(analysis_payload, dict) else []

        health_assessment_signal = model_signals.get("health_assessment", {})
        risk_signal = model_signals.get("risk_scoring", {})
        care_signal = model_signals.get("care_suggestion", {})
        alarm_signal = model_signals.get("alarm_interpretation", {})
        anomaly_payload = self._extract_report_anomaly_payload(model_signals)

        health_assessment_payload = health_assessment_signal.get("payload", {}) if isinstance(health_assessment_signal, dict) else {}
        risk_signal_payload = risk_signal.get("payload", {}) if isinstance(risk_signal, dict) else {}
        care_signal_payload = care_signal.get("payload", {}) if isinstance(care_signal, dict) else {}
        alarm_signal_payload = alarm_signal.get("payload", {}) if isinstance(alarm_signal, dict) else {}

        latest_health_score = latest.get("health_score") if isinstance(latest, dict) else None
        if not isinstance(latest_health_score, (int, float)):
            latest_health_score = risk_signal_payload.get("score") if isinstance(risk_signal_payload, dict) else None
        average_health_score = averages.get("health_score") if isinstance(averages, dict) else None

        trend_evidence = self._build_report_trend_evidence(trend if isinstance(trend, dict) else {})
        derived_sustained = self._derive_report_sustained_abnormality(samples=samples, anomaly_payload=anomaly_payload)
        anomaly_reason = str(anomaly_payload.get("reason", "")).strip()
        anomaly_probability = anomaly_payload.get("probability")
        if not isinstance(anomaly_probability, (int, float)):
            anomaly_probability = None
        sustained_minutes = anomaly_payload.get("sustained_minutes")
        if isinstance(sustained_minutes, (int, float)) and sustained_minutes > 0:
            sustained_minutes = float(sustained_minutes)
        else:
            sustained_minutes = float(derived_sustained["sustained_minutes"])
        alarm_ready = bool(anomaly_payload.get("alarm_ready", False)) or bool(derived_sustained["alarm_ready"])
        normalized_anomaly_payload = dict(anomaly_payload)
        normalized_anomaly_payload["sustained_minutes"] = sustained_minutes
        normalized_anomaly_payload["alarm_ready"] = alarm_ready
        normalized_anomaly_payload["abnormal_points"] = derived_sustained["abnormal_points"]
        anomaly_stage = self._classify_report_anomaly_stage(
            risk_level=risk_level,
            anomaly_payload=normalized_anomaly_payload,
            risk_flags=risk_flags,
        )
        active_alarm_count = (
            int(alarm_signal_payload.get("active_alarm_count", 0))
            if isinstance(alarm_signal_payload, dict)
            else 0
        )
        care_recommendations = (
            [str(item) for item in care_signal_payload.get("recommendations", [])]
            if isinstance(care_signal_payload, dict) and isinstance(care_signal_payload.get("recommendations"), list)
            else []
        )

        key_evidence: list[str] = []
        if isinstance(latest_health_score, (int, float)):
            key_evidence.append(f"当前健康评分为 {round(float(latest_health_score), 1)} 分。")
        if risk_flags:
            key_evidence.append(f"当前主要风险标志包括：{'、'.join(risk_flags[:3])}。")
        if isinstance(health_assessment_signal, dict) and str(health_assessment_signal.get("summary", "")).strip():
            key_evidence.append(str(health_assessment_signal.get("summary", "")).strip())
        key_evidence.extend(trend_evidence[:2])
        if isinstance(anomaly_probability, (int, float)):
            key_evidence.append(
                f"时序模型评估异常概率约为 {anomaly_probability:.0%}，"
                f"主要依据：{anomaly_reason or '多指标联合偏移'}。"
            )
        if sustained_minutes > 0:
            key_evidence.append(f"持续异常已累计约 {sustained_minutes:.0f} 分钟。")
        if alarm_ready:
            key_evidence.append("持续异常已达到智能告警条件。")
        if active_alarm_count > 0:
            key_evidence.append(f"当前仍有 {active_alarm_count} 条未确认告警需要复核。")

        summary_inputs: list[str] = [f"综合风险等级为 {self._risk_label(risk_level)}。"]
        if isinstance(latest_health_score, (int, float)):
            summary_inputs.append(f"当前健康评分 {round(float(latest_health_score), 1)}。")
        if notable_events:
            summary_inputs.append(str(notable_events[0]))
        summary_inputs.extend(trend_evidence[:2])
        if alarm_ready:
            summary_inputs.append("时序模型判断当前异常已达到持续告警条件。")
        elif isinstance(anomaly_probability, (int, float)) and anomaly_stage != "normal":
            summary_inputs.append(f"时序模型异常概率约 {anomaly_probability:.0%}。")

        report_recommendations: list[str] = []
        if alarm_ready:
            report_recommendations.append("时序模型判断已达到持续异常告警条件，建议优先按告警流程复核老人当前状态，并确认是否需要现场干预。")
        elif anomaly_stage == "sustained_abnormal":
            report_recommendations.append("时序模型提示异常趋势已持续，建议缩短复测间隔并尽快电话核查。")
        elif anomaly_stage == "abnormal":
            report_recommendations.append("时序模型提示存在早期异常波动，建议继续复测并重点观察趋势变化。")
        if alarm_ready:
            report_recommendations.append("建议优先按照持续异常告警流程复核老人当前状态，并确认是否需要现场干预。")
        elif anomaly_stage == "sustained_abnormal":
            report_recommendations.append("时序模型提示异常趋势已持续，建议缩短复测间隔并尽快电话核查。")
        elif anomaly_stage == "abnormal":
            report_recommendations.append("时序模型提示存在早期异常波动，建议继续复测并重点观察趋势变化。")
        if active_alarm_count > 0:
            report_recommendations.append("建议同步核对当前未确认告警，避免遗漏需要立即处理的异常。")
        report_recommendations.extend(care_recommendations[:3])
        report_recommendations.extend(recommendations[:3])

        return {
            "evidence_version": "hm_report_v2",
            "device_mac": device_mac.upper(),
            "input_window": {
                "report_sample_count": len(samples),
                "transformer_window": 6,
                "feature_names": ["heart_rate", "temperature", "blood_oxygen", "systolic"],
            },
            "health_score": {
                "latest": latest_health_score,
                "average": average_health_score,
                "source": "health_score_model",
            },
            "risk_level": risk_level,
            "risk_flags": risk_flags,
            "anomaly_stage": anomaly_stage,
            "health_assessment_summary": str(health_assessment_signal.get("summary", "")).strip() if isinstance(health_assessment_signal, dict) else "",
            "risk_scoring_summary": str(risk_signal.get("summary", "")).strip() if isinstance(risk_signal, dict) else "",
            "alarm_summary": str(alarm_signal.get("summary", "")).strip() if isinstance(alarm_signal, dict) else "",
            "active_alarm_count": active_alarm_count,
            "sustained_abnormality": {
                "alarm_ready": alarm_ready,
                "sustained_minutes": sustained_minutes,
                "probability": anomaly_probability,
                "score": anomaly_payload.get("score"),
                "reason": anomaly_reason or None,
                "abnormal_points": derived_sustained["abnormal_points"],
            },
            "trend_evidence": trend_evidence,
            "key_evidence": self._unique_texts(key_evidence, limit=8),
            "summary_inputs": self._unique_texts(summary_inputs, limit=6),
            "key_findings": self._unique_texts(key_evidence + notable_events, limit=6),
            "recommendations": self._unique_texts(report_recommendations, limit=5),
            "care_recommendations": self._unique_texts(care_recommendations, limit=4),
            "model_payloads": {
                "health_assessment": health_assessment_payload if isinstance(health_assessment_payload, dict) else {},
                "risk_scoring": risk_signal_payload if isinstance(risk_signal_payload, dict) else {},
                "anomaly_explain": normalized_anomaly_payload if isinstance(normalized_anomaly_payload, dict) else {},
                "care_suggestion": care_signal_payload if isinstance(care_signal_payload, dict) else {},
                "alarm_interpretation": alarm_signal_payload if isinstance(alarm_signal_payload, dict) else {},
            },
        }

    def _build_report_trend_evidence(self, trend: dict[str, Any]) -> list[str]:
        evidence: list[str] = []
        for metric_name in ("blood_oxygen", "temperature", "heart_rate", "health_score"):
            row = trend.get(metric_name, {})
            if not isinstance(row, dict):
                continue
            label = self._trend_label_for_report(str(row.get("label", "")))
            if label in {"稳定", "数据不足", ""}:
                continue
            delta = row.get("delta")
            delta_text = f"{delta:+.2f}" if isinstance(delta, (int, float)) else ""
            metric_label = self._metric_label_for_report(metric_name)
            if delta_text:
                evidence.append(f"{metric_label}趋势{label}，变化幅度 {delta_text}。")
            else:
                evidence.append(f"{metric_label}趋势{label}。")
        return evidence

    @staticmethod
    def _metric_label_for_report(metric_name: str) -> str:
        return {
            "blood_oxygen": "血氧",
            "temperature": "体温",
            "heart_rate": "心率",
            "health_score": "健康评分",
        }.get(metric_name, metric_name)

    @staticmethod
    def _trend_label_for_report(label: str) -> str:
        return {
            "rising": "上升",
            "falling": "下降",
            "stable": "稳定",
            "insufficient_data": "数据不足",
        }.get(label, label)

    def _derive_report_sustained_abnormality(
        self,
        *,
        samples: list[HealthSample],
        anomaly_payload: dict[str, Any],
    ) -> dict[str, object]:
        if not samples:
            return {"sustained_minutes": 0.0, "alarm_ready": False, "abnormal_points": 0}

        abnormal_points = []
        for sample in samples:
            flags = [flag for flag in self._analysis._risk_flags(sample) if flag != "within_expected_range"]
            if flags:
                abnormal_points.append(sample)

        if not abnormal_points:
            return {"sustained_minutes": 0.0, "alarm_ready": False, "abnormal_points": 0}

        sustained_minutes = max(
            (abnormal_points[-1].timestamp - abnormal_points[0].timestamp).total_seconds() / 60.0,
            0.0,
        )
        probability = anomaly_payload.get("probability")
        alarm_ready = len(abnormal_points) >= 3 and sustained_minutes >= 20
        if isinstance(probability, (int, float)) and probability >= 0.8 and len(abnormal_points) >= 2:
            alarm_ready = True
        return {
            "sustained_minutes": sustained_minutes,
            "alarm_ready": alarm_ready,
            "abnormal_points": len(abnormal_points),
        }

    def _classify_report_anomaly_stage(
        self,
        *,
        risk_level: str,
        anomaly_payload: dict[str, Any],
        risk_flags: list[str],
    ) -> str:
        if anomaly_payload.get("alarm_ready") is True:
            return "alarm"
        sustained_minutes = anomaly_payload.get("sustained_minutes")
        probability = anomaly_payload.get("probability")
        if isinstance(sustained_minutes, (int, float)) and sustained_minutes >= 20:
            return "sustained_abnormal"
        if isinstance(probability, (int, float)) and probability >= 0.45:
            return "abnormal"
        if risk_level in {"high", "medium"} or any(flag.endswith("_warning") or flag.endswith("_critical") for flag in risk_flags):
            return "abnormal"
        return "normal"

    def _build_report_key_findings(
        self,
        analysis_payload: dict[str, Any],
        *,
        model_signals: dict[str, Any],
        health_model_evidence: dict[str, Any],
    ) -> list[str]:
        del model_signals
        findings = list(health_model_evidence.get("key_findings", []))
        if isinstance(analysis_payload, dict):
            findings.extend(list(analysis_payload.get("notable_events", [])))
        return self._unique_texts(findings, limit=6)

    def _build_report_recommendations(
        self,
        analysis_payload: dict[str, Any],
        *,
        model_signals: dict[str, Any],
        health_model_evidence: dict[str, Any],
    ) -> list[str]:
        del model_signals
        recommendations = list(health_model_evidence.get("recommendations", []))
        if isinstance(analysis_payload, dict):
            recommendations.extend(list(analysis_payload.get("recommendations", [])))
        return self._unique_texts(recommendations, limit=5)

    def _build_retrieval_query(self, *, scope: str, question: str, analysis_payload: dict[str, Any]) -> str:
        if scope == "community":
            distribution = analysis_payload.get("risk_distribution", {})
            priority_devices = analysis_payload.get("priority_devices", [])
            focus_terms: list[str] = []
            if isinstance(priority_devices, list):
                for item in priority_devices[:3]:
                    if not isinstance(item, dict):
                        continue
                    flags = item.get("risk_flags", [])
                    joined_flags = " ".join(str(flag) for flag in flags)
                    focus_terms.append(f"{item.get('device_mac', '')} {joined_flags}".strip())
            return " ".join(
                part
                for part in [
                    question or "summarize recent community health data",
                    "community elder care prioritization risk distribution patrol follow-up",
                    f"high={distribution.get('high', 0)}",
                    f"medium={distribution.get('medium', 0)}",
                    *focus_terms,
                ]
                if part
            )

        risk_flags = analysis_payload.get("risk_flags", [])
        notable_events = analysis_payload.get("notable_events", [])
        return " ".join(
            part
            for part in [
                question or "analyze recent device health data",
                "elder health monitoring trends risk follow-up suggestions",
                *(str(flag) for flag in risk_flags[:4]),
                *(str(event) for event in notable_events[:2]),
            ]
            if part
        )

    def _build_report_retrieval_query(
        self,
        *,
        role: UserRole,
        device_mac: str,
        start_at: datetime,
        end_at: datetime,
        analysis_payload: dict[str, Any],
        model_signals: dict[str, Any],
        health_model_evidence: dict[str, Any],
    ) -> str:
        risk_flags = analysis_payload.get("risk_flags", [])
        notable_events = analysis_payload.get("notable_events", [])
        recommendations = analysis_payload.get("recommendations", [])
        trend = analysis_payload.get("trend", {})
        duration_minutes = max(int((end_at - start_at).total_seconds() // 60), 0)
        role_hint = "family report template wording follow-up guidance" if role == UserRole.FAMILY else "community report template handoff wording patrol follow-up"
        anomaly_summary = ""
        anomaly_reason = ""
        anomaly_payload = self._extract_report_anomaly_payload(model_signals)
        anomaly_signal = model_signals.get("anomaly_explain", {})
        if isinstance(anomaly_signal, dict):
            anomaly_summary = str(anomaly_signal.get("summary", ""))
        if anomaly_payload:
            anomaly_reason = str(anomaly_payload.get("reason", ""))
        trend_terms: list[str] = []
        if isinstance(trend, dict):
            for metric_name, row in trend.items():
                if not isinstance(row, dict):
                    continue
                trend_terms.append(f"{metric_name} {row.get('label', '')}".strip())
        return " ".join(
            part
            for part in [
                "health report report template wording guide event interpretation follow-up guidance",
                "时间段 健康报告 指标解释 趋势含义 风险说明 报告措辞模板",
                role_hint,
                device_mac,
                f"duration_minutes={duration_minutes}",
                *(str(flag) for flag in risk_flags[:4]),
                *(str(event) for event in notable_events[:2]),
                *(str(item) for item in recommendations[:2]),
                anomaly_summary,
                anomaly_reason,
                f"sustained_minutes={anomaly_payload.get('sustained_minutes', '')}",
                "transformer temporal attention sustained anomaly report wording",
                *(str(item) for item in health_model_evidence.get("summary_inputs", [])[:3]),
                *(str(item) for item in health_model_evidence.get("key_evidence", [])[:3]),
                *trend_terms[:4],
            ]
            if part
        )

    def _format_result(self, result: AgentState) -> dict[str, object]:
        final_payload = result.get("final_payload")
        if isinstance(final_payload, dict) and final_payload:
            answer = str(final_payload.get("answer", "")).strip()
            if not answer:
                final_payload["answer"] = self._fallback_answer(
                    result.get("analysis_payload", {}),
                    str(result.get("scope", "device")),
                )
            return sanitize_agent_response(final_payload)

        answer = str(result.get("answer", "")).strip()
        scope = str(result.get("scope", "device"))
        if not answer:
            answer = self._fallback_answer(result.get("analysis_payload", {}), scope)
        return sanitize_agent_response(
            {
                "scope": scope,
                "mode": str(result.get("selected_mode", "local")),
                "network_online": False,
                "selected_model": str(result.get("selected_model", self._settings.local_default_model)),
                "answer": answer,
                "references": list(result.get("knowledge_hits", [])),
                "analysis": dict(result.get("analysis_payload", {})),
            }
        )

    def _compose_analysis_context(self, state: AgentState) -> str:
        sections = [
            "### Analysis",
            str(state.get("analysis_context", "{}")),
        ]
        dialogue_events = state.get("dialogue_events", [])
        if dialogue_events:
            sections.extend(
                [
                    "### Health Events",
                    json.dumps(dialogue_events, ensure_ascii=False, indent=2, default=str),
                ]
            )
        dialogue_action_labels = state.get("dialogue_action_labels", [])
        if dialogue_action_labels:
            sections.extend(
                [
                    "### Action Labels",
                    json.dumps(dialogue_action_labels, ensure_ascii=False, indent=2, default=str),
                ]
            )
        context_bundle = state.get("context_bundle", {})
        if context_bundle:
            sections.extend(
                [
                    "### Business Context",
                    json.dumps(context_bundle, ensure_ascii=False, indent=2, default=str),
                ]
            )
        tool_results = state.get("tool_results", [])
        if tool_results:
            sections.extend(
                [
                    "### Tool Results",
                    json.dumps(tool_results, ensure_ascii=False, indent=2, default=str),
                ]
            )
        model_results = state.get("model_results", {})
        if model_results:
            sections.extend(
                [
                    "### Model Results",
                    json.dumps(model_results, ensure_ascii=False, indent=2, default=str),
                ]
            )
        degraded_notes = state.get("degraded_notes", [])
        if degraded_notes:
            sections.extend(
                [
                    "### Degraded Notes",
                    json.dumps(degraded_notes, ensure_ascii=False, indent=2, default=str),
                ]
            )
        return "\n\n".join(section for section in sections if section)

    def _build_report_prompt(
        self,
        *,
        role: UserRole,
        device_mac: str,
        start_at: datetime,
        end_at: datetime,
        analysis_payload: dict[str, Any],
        knowledge_hits: list[str],
        context_bundle: dict[str, Any],
        model_signals: dict[str, Any],
        health_model_evidence: dict[str, Any],
    ) -> dict[str, Any]:
        role_prompt = "Generate a family health report for this time window." if role == UserRole.FAMILY else "Generate a community-facing health report for this time window."
        report_context = {
            "device_mac": device_mac.upper(),
            "period": {
                "start_at": start_at.astimezone(timezone.utc).isoformat(),
                "end_at": end_at.astimezone(timezone.utc).isoformat(),
                "duration_minutes": max(int((end_at - start_at).total_seconds() // 60), 0),
            },
            "analysis_payload": analysis_payload,
            "context_bundle": context_bundle,
            "model_signals": model_signals,
            "health_model_evidence": health_model_evidence,
            "report_requirements": {
                "audience": "family" if role == UserRole.FAMILY else "community operator",
                "must_cover": [
                    "summary",
                    "indicator interpretation",
                    "risk judgment",
                    "recommended actions",
                    "uncertainty or data quality note",
                ],
            },
        }
        package = build_prompt_package(
            role=role,
            scope="device",
            question=role_prompt,
            analysis_context=json.dumps(report_context, ensure_ascii=False, indent=2, default=str),
            knowledge_context="\n\n".join(knowledge_hits),
        )
        system_text = package["system"]
        user_text = package["user"]
        prompt_text = f"{system_text}\n\n{user_text}".strip()
        messages: list[Any] = []
        if ChatPromptTemplate is not None:
            try:
                prompt = ChatPromptTemplate.from_messages([("system", system_text), ("human", user_text)])
                messages = prompt.format_messages()
            except Exception:
                messages = []
        return {
            "system_prompt": system_text,
            "user_prompt": user_text,
            "prompt_text": prompt_text,
            "messages": messages,
        }

    def _build_report_metrics(
        self,
        *,
        latest: dict[str, Any],
        averages: dict[str, Any],
        ranges: dict[str, Any],
        trend: dict[str, Any],
    ) -> dict[str, dict[str, object]]:
        metric_map = {
            "heart_rate": "heart_rate",
            "temperature": "temperature",
            "blood_oxygen": "blood_oxygen",
            "health_score": "health_score",
        }
        metrics: dict[str, dict[str, object]] = {}
        for public_key, source_key in metric_map.items():
            range_row = ranges.get(source_key, {})
            trend_row = trend.get(source_key, {})
            if not isinstance(range_row, dict):
                range_row = {}
            if not isinstance(trend_row, dict):
                trend_row = {}
            metrics[public_key] = {
                "latest": latest.get(source_key),
                "average": averages.get(source_key),
                "min": range_row.get("min"),
                "max": range_row.get("max"),
                "trend": trend_row.get("label"),
            }
        return metrics

    def _extract_report_anomaly_payload(self, model_signals: dict[str, Any]) -> dict[str, Any]:
        anomaly_signal = model_signals.get("anomaly_explain", {})
        if not isinstance(anomaly_signal, dict):
            return {}
        payload = anomaly_signal.get("payload", {})
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _unique_texts(items: list[object], *, limit: int) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for item in items:
            text = str(item).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            normalized.append(text)
            if len(normalized) >= limit:
                break
        return normalized

    def _fallback_report_summary_with_model_signals(
        self,
        analysis_payload: dict[str, Any],
        *,
        model_signals: dict[str, Any],
        health_model_evidence: dict[str, Any],
    ) -> str:
        del model_signals
        risk_level = self._risk_label(str(health_model_evidence.get("risk_level") or analysis_payload.get("risk_level", "unknown")))
        latest = analysis_payload.get("latest", {}) if isinstance(analysis_payload, dict) else {}
        if not isinstance(latest, dict):
            latest = {}

        summary_inputs = list(health_model_evidence.get("summary_inputs", []))
        if summary_inputs:
            return " ".join(str(item) for item in summary_inputs if str(item).strip()).strip()
        key_evidence = list(health_model_evidence.get("key_evidence", []))
        transformer_line = next((item for item in key_evidence if "时序模型" in item), "")
        recommendations = list(health_model_evidence.get("recommendations", []))
        if not recommendations and isinstance(analysis_payload, dict):
            recommendations = list(analysis_payload.get("recommendations", []))

        summary_parts = [
            f"本时段健康报告结论：综合风险等级为{risk_level}。",
            (
                f"关键指标显示血氧 {latest.get('blood_oxygen', '--')}%，"
                f"体温 {latest.get('temperature', '--')}℃，"
                f"健康评分 {latest.get('health_score', '--')}。"
            ),
            *summary_inputs[:2],
            transformer_line,
            key_evidence[0] if key_evidence else "",
            f"建议动作：{'；'.join(str(item) for item in recommendations[:2])}" if recommendations else "建议继续结合后续监测与线下观察综合判断。",
        ]
        return " ".join(part for part in summary_parts if part).strip()

    def _fallback_answer(self, analysis_payload: dict[str, Any], scope: str) -> str:
        if scope == "community":
            device_count = int(analysis_payload.get("device_count", 0))
            distribution = analysis_payload.get("risk_distribution", {})
            priority_devices = analysis_payload.get("priority_devices", [])
            recommendations = analysis_payload.get("recommendations", [])
            focus = "、".join(
                str(item.get("device_mac"))
                for item in priority_devices[:3]
                if isinstance(item, dict) and item.get("device_mac")
            )
            return (
                f"本次社区汇总覆盖 {device_count} 台设备，"
                f"其中高风险 {distribution.get('high', 0)} 台、中风险 {distribution.get('medium', 0)} 台、低风险 {distribution.get('low', 0)} 台。"
                f"优先关注：{focus or '当前暂无明确重点对象'}。"
                f"建议：{'；'.join(str(item) for item in recommendations[:3]) or '继续保持常规巡检。'}"
            )

        latest = analysis_payload.get("latest", {})
        risk_level = self._risk_label(str(analysis_payload.get("risk_level", "unknown")))
        window = analysis_payload.get("window", {})
        notable_events = analysis_payload.get("notable_events", [])
        recommendations = analysis_payload.get("recommendations", [])
        return (
            f"当前综合风险等级为{risk_level}。"
            f"最近监测窗口约 {window.get('duration_minutes', 0)} 分钟，"
            f"最新指标为心率 {latest.get('heart_rate', '--')} bpm、"
            f"体温 {latest.get('temperature', '--')}℃、"
            f"血氧 {latest.get('blood_oxygen', '--')}%、"
            f"血压 {latest.get('blood_pressure', '--')}。"
            f"重点情况：{notable_events[0] if notable_events else '暂无明显异常事件。'}"
            f"建议：{'；'.join(str(item) for item in recommendations[:3]) or '继续监测。'}"
        )

    @staticmethod
    def _risk_label(level: str) -> str:
        return {
            "low": "低",
            "medium": "中",
            "high": "高",
            "unknown": "未知",
        }.get(level, level)

    @staticmethod
    def _extract_message_text(message: Any) -> str | None:
        content = getattr(message, "content", None)
        if isinstance(content, str):
            value = content.strip()
            return value or None
        if isinstance(content, list):
            parts: list[str] = []
            for row in content:
                if isinstance(row, str) and row.strip():
                    parts.append(row.strip())
                elif isinstance(row, dict):
                    text = row.get("text") or row.get("content")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
            if parts:
                return "\n".join(parts)
        if isinstance(message, str):
            value = message.strip()
            return value or None
        return None
