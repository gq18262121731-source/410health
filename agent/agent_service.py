from __future__ import annotations

from agent.analysis_service import HealthDataAnalysisService
from agent.langgraph_health_agent import HealthAgentService as OfflineHealthAgentService
from agent.rag_service import RAGService
from backend.config import Settings


class HealthAgentService(OfflineHealthAgentService):
    """Compatibility wrapper around the supported offline-only health agent."""

    def __init__(
        self,
        settings: Settings,
        rag_service: RAGService,
        analysis_service: HealthDataAnalysisService | None = None,
    ) -> None:
        super().__init__(
            settings,
            rag_service,
            analysis_service,
        )
