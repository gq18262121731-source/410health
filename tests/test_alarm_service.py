from collections import defaultdict
from datetime import datetime, timedelta, timezone

from ai.anomaly_detector import IntelligentAnomalyScorer, RealtimeAnomalyDetector
from ai.data_generator import SyntheticHealthDataGenerator
from backend.models.alarm_model import AlarmPriority, AlarmType
from backend.models.health_model import HealthSample
from backend.services.alarm_priority_queue import AlarmPriorityQueue
from backend.services.alarm_service import AlarmService
from backend.services.notification_service import NotificationService


def build_alarm_service() -> AlarmService:
    return AlarmService(
        detector=RealtimeAnomalyDetector(),
        queue=AlarmPriorityQueue(redis_url="redis://localhost:6379/0"),
        notification_service=NotificationService(),
    )


def test_alarm_detector_raises_sos_alarm() -> None:
    service = build_alarm_service()
    sample = HealthSample(
        device_mac="53:57:08:00:00:01",
        heart_rate=128,
        temperature=38.8,
        blood_oxygen=89,
        blood_pressure="186/122",
        battery=54,
        sos_flag=True,
    )

    alarms = service.evaluate(sample)
    assert alarms
    assert any(alarm.alarm_type == AlarmType.SOS for alarm in alarms)


def test_alarm_detector_raises_bp_critical_alarm() -> None:
    service = build_alarm_service()
    sample = HealthSample(
        device_mac="53:57:08:00:00:02",
        heart_rate=88,
        temperature=36.7,
        blood_oxygen=97,
        blood_pressure="188/121",
        battery=80,
    )

    alarms = service.evaluate(sample)

    assert any(
        alarm.alarm_type == AlarmType.VITAL_CRITICAL and alarm.metadata.get("metric") == "blood_pressure"
        for alarm in alarms
    )


def test_alarm_queue_sorts_sos_before_warning() -> None:
    service = build_alarm_service()
    early = datetime.now(timezone.utc) - timedelta(seconds=5)

    warning = HealthSample(
        device_mac="53:57:08:00:00:03",
        timestamp=early,
        heart_rate=70,
        temperature=36.5,
        blood_oxygen=97,
        blood_pressure="120/80",
        battery=70,
    )
    for offset in range(6):
        service.evaluate(warning.model_copy(update={"timestamp": early + timedelta(seconds=offset)}))
    zscore_alarm = service.evaluate(
        warning.model_copy(update={"timestamp": early + timedelta(seconds=7), "heart_rate": 120})
    )
    sos_alarm = service.evaluate(
        warning.model_copy(update={"timestamp": early + timedelta(seconds=8), "sos_flag": True, "heart_rate": 85})
    )

    queue = service.queue_items(active_only=True)

    assert zscore_alarm
    assert sos_alarm
    assert queue[0].alarm.alarm_level == AlarmPriority.SOS


def test_intelligent_scorer_describes_transformer_window_and_scores() -> None:
    scorer = IntelligentAnomalyScorer()

    description = scorer.describe_model()

    assert description["model_name"] == "deterministic_temporal_transformer"
    assert description["input_window"] == 6
    assert description["feature_names"] == ["heart_rate", "temperature", "blood_oxygen", "systolic"]
    assert description["output_scores"] == [
        "health_score",
        "anomaly_probability",
        "score",
        "drift_score",
        "reconstruction_score",
    ]
    assert description["alarm_rule"]["principle"] == "持续时间 + 异常程度，不依赖单点抖动"


def test_intelligent_scorer_detects_hidden_drift() -> None:
    scorer = IntelligentAnomalyScorer()
    base_time = datetime.now(timezone.utc)
    history = [
        HealthSample(
            device_mac="53:57:08:00:00:04",
            timestamp=base_time + timedelta(minutes=index * 10),
            heart_rate=72 + (index % 2),
            temperature=36.5,
            blood_oxygen=97,
            blood_pressure="118/78",
            battery=88,
        )
        for index in range(5)
    ]
    history.append(
        HealthSample(
            device_mac="53:57:08:00:00:04",
            timestamp=base_time + timedelta(minutes=50),
            heart_rate=88,
            temperature=37.3,
            blood_oxygen=95,
            blood_pressure="136/88",
            battery=87,
        )
    )

    result = scorer.infer_device("53:57:08:00:00:04", history, now=history[-1].timestamp, force=True)

    assert result is not None
    assert result.probability > 0.5
    assert result.reconstruction_score > 0
    assert "体温" in result.reason or "心率" in result.reason or "血氧" in result.reason


def test_realtime_detector_uses_prior_window_for_zscore_warning() -> None:
    detector = RealtimeAnomalyDetector()
    base_time = datetime.now(timezone.utc)

    for offset in range(6):
        detector.evaluate(
            HealthSample(
                device_mac="53:57:08:00:00:05",
                timestamp=base_time + timedelta(minutes=offset),
                heart_rate=72,
                temperature=36.5,
                blood_oxygen=97,
                blood_pressure="120/80",
                battery=70,
            )
        )

    alarms = detector.evaluate(
        HealthSample(
            device_mac="53:57:08:00:00:05",
            timestamp=base_time + timedelta(minutes=10),
            heart_rate=88,
            temperature=36.5,
            blood_oxygen=97,
            blood_pressure="120/80",
            battery=70,
        )
    )

    assert any(alarm.alarm_type == AlarmType.ZSCORE_WARNING for alarm in alarms)


def test_reproducible_demo_scenario_progresses_from_normal_to_alarm() -> None:
    generator = SyntheticHealthDataGenerator(device_count=1)
    scorer = IntelligentAnomalyScorer()
    scorer.warmup(generator.build_training_sequences(hours=6, step_minutes=10))
    service = build_alarm_service()
    scenario = generator.build_sustained_anomaly_demo_scenario(start=datetime.now(timezone.utc).replace(second=0, microsecond=0))

    phase_lookup: dict[int, str] = {}
    for phase in scenario.phases:
        for index in range(phase.start_index, phase.end_index + 1):
            phase_lookup[index] = phase.name

    history: list[HealthSample] = []
    phase_results: dict[str, list[object]] = defaultdict(list)
    alarm_phases: list[str] = []

    for index, sample in enumerate(scenario.samples):
        history.append(sample)
        result = scorer.infer_device(scenario.device_mac, history, now=sample.timestamp, force=True)
        phase = phase_lookup[index]
        if result is None:
            continue
        phase_results[phase].append(result)
        intelligent_alarm = scorer.build_alarm(sample, result)
        if intelligent_alarm:
            service.evaluate_alarm_records([intelligent_alarm])
            alarm_phases.append(phase)

    assert scenario.model_window == 6
    assert scenario.feature_names == ["heart_rate", "temperature", "blood_oxygen", "systolic"]
    assert phase_results["normal"]
    assert phase_results["anomaly"]
    assert phase_results["sustained_anomaly"]
    assert phase_results["alarm"]
    assert max(result.probability for result in phase_results["normal"]) < phase_results["anomaly"][0].probability
    assert not any(result.alarm_ready for result in phase_results["anomaly"])
    assert not any(result.alarm_ready for result in phase_results["sustained_anomaly"])
    assert any(result.alarm_ready for result in phase_results["alarm"])
    assert alarm_phases == ["alarm"]
    assert any(item.alarm.alarm_type == AlarmType.INTELLIGENT_ANOMALY for item in service.queue_items())
