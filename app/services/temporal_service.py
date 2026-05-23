from __future__ import annotations

import time

from app.core.config import Settings
from app.core.logger import get_logger
from app.schemas.vision_result import DetectedObject
from app.temporal.fall_state_machine import FallStateMachine
from app.temporal.feature_window import FeatureWindow
from app.temporal.mock_sequence_model import MockSequenceModel
from app.temporal.schemas import FallDecision, RiskLevel, SequencePrediction, TemporalStatus
from app.temporal.target_feature_extractor import TargetFeatureExtractor

logger = get_logger(__name__)


class TemporalService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.extractor = TargetFeatureExtractor()
        self.window = FeatureWindow(settings.feature_window_size)
        self.model = MockSequenceModel()
        self.state_machine = FallStateMachine(settings)
        self._feature_extractor_ok = True
        self._last_error: str | None = None
        self._last_key: str | None = None
        self._last_decision = FallDecision()
        self._last_prediction = SequencePrediction(fall_probability=0.0)

    def enrich(self, camera_id: str, objects: list[DetectedObject]) -> list[DetectedObject]:
        if not self.settings.enable_temporal:
            return objects

        start = time.perf_counter()
        try:
            target = self._select_target(objects)
            if target is None:
                return objects
            key = self._temporal_key(camera_id, target)
            if key is None:
                return objects

            previous = self.window.previous(key)
            feature = self.extractor.extract(
                camera_id=camera_id,
                target_object=target,
                timestamp=time.monotonic(),
                previous_feature=previous,
            )
            self.window.append(key, feature)
            window = self.window.get_window(key)
            prediction = self.model.predict(window)
            decision = self.state_machine.update(key, feature, prediction)

            temporal_payload = {
                "fall_probability": prediction.fall_probability,
                "source": prediction.source,
                "features": feature.model_dump(exclude={"monotonic_time"}),
            }
            fall_decision_payload = decision.model_dump()
            alarm_preview = {
                "risk_level": decision.risk_level,
                "countdown_ms": decision.countdown_ms,
                "confirmed": decision.fall_state == "fallen_confirmed",
            }

            enriched: list[DetectedObject] = []
            for item in objects:
                if item is target:
                    enriched.append(
                        item.model_copy(
                            update={
                                "temporal": temporal_payload,
                                "fall_decision": fall_decision_payload,
                                "alarm_preview": alarm_preview,
                            }
                        )
                    )
                else:
                    enriched.append(item)

            self._feature_extractor_ok = True
            self._last_error = None
            self._last_key = key
            self._last_decision = decision
            self._last_prediction = prediction

            elapsed_ms = (time.perf_counter() - start) * 1000
            if elapsed_ms > 5:
                logger.warning("temporal_enrich_slow camera_id=%s elapsed_ms=%.2f", camera_id, elapsed_ms)
            return enriched
        except Exception as exc:
            logger.exception("temporal_enrich_failed camera_id=%s", camera_id)
            self._feature_extractor_ok = False
            self._last_error = str(exc)
            return objects

    def status(self, camera_id: str | None = None) -> TemporalStatus:
        del camera_id
        window_status = self.window.status()
        return TemporalStatus(
            enabled=self.settings.enable_temporal,
            feature_extractor_ok=self._feature_extractor_ok,
            window_size=window_status["window_size"],
            active_tracks=window_status["active_tracks"],
            fall_state=self._last_decision.fall_state,
            fall_probability=self._last_prediction.fall_probability,
            risk_level=self._last_decision.risk_level,
            last_error=self._last_error,
        )

    def reset_camera(self, camera_id: str) -> None:
        prefix = f"track:{camera_id}:"
        for key in list(self.window.keys()):
            if key.startswith(prefix):
                self.window.clear(key)
                self.state_machine.clear(key)
        if self._last_key and self._last_key.startswith(prefix):
            self._last_key = None
            self._last_decision = FallDecision()
            self._last_prediction = SequencePrediction(fall_probability=0.0)
            self._last_error = None
            self._feature_extractor_ok = True

    @staticmethod
    def _select_target(objects: list[DetectedObject]) -> DetectedObject | None:
        targets = [item for item in objects if item.is_target]
        if targets:
            return max(targets, key=TemporalService._area)
        candidates = [item for item in objects if item.track_id is not None]
        if not candidates:
            return None
        return max(candidates, key=TemporalService._area)

    @staticmethod
    def _temporal_key(camera_id: str, obj: DetectedObject) -> str | None:
        if obj.is_target and obj.person_id:
            return f"person:{obj.person_id}"
        if obj.track_id is not None:
            return f"track:{camera_id}:{obj.track_id}"
        return None

    @staticmethod
    def _area(item: DetectedObject) -> float:
        x1, y1, x2, y2 = item.bbox
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)
