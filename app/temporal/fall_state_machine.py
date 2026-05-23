from __future__ import annotations

import time
from dataclasses import dataclass

from app.core.config import Settings
from app.temporal.schemas import FallDecision, FallState, RiskLevel, SequencePrediction, TargetFeature


@dataclass
class _FallRuntime:
    state: FallState = FallState.NORMAL
    abnormal_frames: int = 0
    confirm_frames: int = 0
    candidate_started_at: float | None = None
    cooldown_until: float | None = None
    last_probability: float = 0.0
    falling_seen: bool = False
    recent_rapid_descent: bool = False
    rapid_descent_seen_at: float | None = None


class FallStateMachine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._states: dict[str, _FallRuntime] = {}

    def update(
        self,
        key: str,
        feature: TargetFeature,
        prediction: SequencePrediction,
    ) -> FallDecision:
        runtime = self._states.setdefault(key, _FallRuntime())
        now = time.monotonic()
        runtime.last_probability = prediction.fall_probability
        if self._has_rapid_descent(feature):
            runtime.recent_rapid_descent = True
            runtime.rapid_descent_seen_at = now
        elif (
            runtime.rapid_descent_seen_at is not None
            and (now - runtime.rapid_descent_seen_at) * 1000 > self.settings.fall_still_ms * 2
        ):
            runtime.recent_rapid_descent = False

        if runtime.state == FallState.COOLDOWN:
            if runtime.cooldown_until is not None and now < runtime.cooldown_until:
                return self._decision(runtime, now)
            self._reset_runtime(runtime)
            return self._decision(runtime, now)

        strong_falling_evidence = self._is_strong_falling_evidence(feature, prediction)
        abnormal = self._is_abnormal(feature, prediction)
        if abnormal:
            runtime.abnormal_frames += 1
        else:
            runtime.abnormal_frames = max(0, runtime.abnormal_frames - 1)

        if runtime.state == FallState.NORMAL:
            if strong_falling_evidence:
                runtime.state = FallState.FALLING
                runtime.falling_seen = True
            elif runtime.abnormal_frames >= self.settings.unstable_frame_threshold:
                runtime.state = FallState.UNSTABLE
        elif runtime.state == FallState.UNSTABLE:
            if strong_falling_evidence:
                runtime.state = FallState.FALLING
                runtime.falling_seen = True
            elif runtime.abnormal_frames == 0:
                runtime.state = FallState.NORMAL
        elif runtime.state == FallState.FALLING:
            runtime.falling_seen = True
            if self._is_fallen_candidate(feature, prediction, runtime):
                runtime.state = FallState.FALLEN_CANDIDATE
                runtime.candidate_started_at = now
                runtime.confirm_frames = 1
            elif prediction.fall_probability < self.settings.falling_prob_threshold * 0.55:
                runtime.state = FallState.UNSTABLE
        elif runtime.state == FallState.FALLEN_CANDIDATE:
            if self._is_fallen_candidate(feature, prediction, runtime):
                runtime.confirm_frames += 1
            else:
                runtime.confirm_frames = max(0, runtime.confirm_frames - 1)
            still_ms = (
                (now - runtime.candidate_started_at) * 1000
                if runtime.candidate_started_at is not None
                else 0.0
            )
            if (
                runtime.confirm_frames >= self.settings.fall_confirm_frames
                and still_ms >= self.settings.fall_still_ms
            ):
                runtime.state = FallState.FALLEN_CONFIRMED
        elif runtime.state == FallState.FALLEN_CONFIRMED:
            runtime.state = FallState.COOLDOWN
            runtime.cooldown_until = now + self.settings.cooldown_seconds

        return self._decision(runtime, now)

    def clear(self, key: str) -> None:
        self._states.pop(key, None)

    def status(self, key: str) -> FallDecision:
        runtime = self._states.get(key, _FallRuntime())
        return self._decision(runtime, time.monotonic())

    @staticmethod
    def _reset_runtime(runtime: _FallRuntime) -> None:
        runtime.state = FallState.NORMAL
        runtime.abnormal_frames = 0
        runtime.confirm_frames = 0
        runtime.candidate_started_at = None
        runtime.cooldown_until = None
        runtime.falling_seen = False
        runtime.recent_rapid_descent = False
        runtime.rapid_descent_seen_at = None

    def _decision(self, runtime: _FallRuntime, now: float) -> FallDecision:
        countdown_ms = 0
        if runtime.state == FallState.COOLDOWN and runtime.cooldown_until is not None:
            countdown_ms = max(0, int((runtime.cooldown_until - now) * 1000))
        elif runtime.state == FallState.FALLEN_CANDIDATE and runtime.candidate_started_at is not None:
            elapsed_ms = int((now - runtime.candidate_started_at) * 1000)
            countdown_ms = max(0, int(self.settings.fall_still_ms - elapsed_ms))

        return FallDecision(
            fall_state=runtime.state.value,
            risk_level=self._risk_for(runtime.state).value,
            countdown_ms=countdown_ms,
        )

    @staticmethod
    def _risk_for(state: FallState) -> RiskLevel:
        mapping = {
            FallState.NORMAL: RiskLevel.LOW,
            FallState.UNSTABLE: RiskLevel.MEDIUM,
            FallState.FALLING: RiskLevel.HIGH,
            FallState.FALLEN_CANDIDATE: RiskLevel.HIGH,
            FallState.FALLEN_CONFIRMED: RiskLevel.CRITICAL,
            FallState.COOLDOWN: RiskLevel.COOLDOWN,
        }
        return mapping[state]

    def _is_abnormal(self, feature: TargetFeature, prediction: SequencePrediction) -> bool:
        posture_evidence = self._has_posture_evidence(feature)
        return (
            self._is_strong_falling_evidence(feature, prediction)
            or (prediction.fall_probability >= 0.5 and feature.delta_y > 55)
            or (prediction.fall_probability >= 0.5 and posture_evidence)
        )

    @staticmethod
    def _has_posture_evidence(feature: TargetFeature) -> bool:
        return feature.aspect_ratio >= 0.95 or (
            feature.head_height_ratio is not None
            and feature.head_height_ratio > 0.45
            and feature.hip_height_ratio is not None
            and feature.hip_height_ratio > 0.65
        )

    def _is_strong_falling_evidence(
        self,
        feature: TargetFeature,
        prediction: SequencePrediction,
    ) -> bool:
        if prediction.fall_probability < self.settings.falling_prob_threshold:
            return False
        return (
            feature.delta_y >= 52
            or (feature.pose_available and feature.delta_y >= 35)
            or self._has_posture_evidence(feature)
        )

    @staticmethod
    def _has_rapid_descent(feature: TargetFeature) -> bool:
        return feature.delta_y > 40

    def _is_fallen_candidate(
        self,
        feature: TargetFeature,
        prediction: SequencePrediction,
        runtime: _FallRuntime,
    ) -> bool:
        if not runtime.falling_seen:
            return False
        if not runtime.recent_rapid_descent and not self._has_rapid_descent(feature):
            return False
        if prediction.fall_probability < self.settings.falling_prob_threshold:
            return False

        low_by_bbox = feature.aspect_ratio >= 0.95
        low_by_pose = (
            feature.head_height_ratio is not None
            and feature.head_height_ratio > 0.45
            and feature.hip_height_ratio is not None
            and feature.hip_height_ratio > 0.65
        )
        still = feature.speed < 28
        return still and (low_by_bbox or low_by_pose)
