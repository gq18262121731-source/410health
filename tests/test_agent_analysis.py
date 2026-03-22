from datetime import datetime, timedelta, timezone

from agent.analysis_service import HealthDataAnalysisService
from ai.anomaly_detector import CommunityHealthClusterer, IntelligentAnomalyScorer
from ai.health_score_model import BaselineTracker, HealthScoreService
from backend.models.health_model import HealthSample


BASE_TIME = datetime(2026, 3, 13, 8, 0, tzinfo=timezone.utc)


def build_sample(
    *,
    device_mac: str,
    minutes: int,
    heart_rate: int,
    temperature: float,
    blood_oxygen: int,
    blood_pressure: str,
    health_score: int,
    sos_flag: bool = False,
) -> HealthSample:
    return HealthSample(
        device_mac=device_mac,
        timestamp=BASE_TIME + timedelta(minutes=minutes),
        heart_rate=heart_rate,
        temperature=temperature,
        blood_oxygen=blood_oxygen,
        blood_pressure=blood_pressure,
        battery=72,
        sos_flag=sos_flag,
        health_score=health_score,
    )


def test_device_summary_reports_risk_and_recommendations() -> None:
    service = HealthDataAnalysisService()
    samples = [
        build_sample(
            device_mac="53:57:08:00:00:01",
            minutes=0,
            heart_rate=96,
            temperature=36.8,
            blood_oxygen=95,
            blood_pressure="132/84",
            health_score=83,
        ),
        build_sample(
            device_mac="53:57:08:00:00:01",
            minutes=30,
            heart_rate=118,
            temperature=38.2,
            blood_oxygen=91,
            blood_pressure="168/102",
            health_score=61,
        ),
        build_sample(
            device_mac="53:57:08:00:00:01",
            minutes=60,
            heart_rate=126,
            temperature=38.6,
            blood_oxygen=88,
            blood_pressure="172/108",
            health_score=55,
            sos_flag=True,
        ),
    ]

    summary = service.summarize_device(samples)

    assert summary["risk_level"] == "high"
    assert "sos_active" in summary["risk_flags"]
    assert summary["event_counts"]["blood_oxygen_critical"] >= 1
    assert summary["recommendations"]


def test_community_summary_prioritizes_high_risk_devices() -> None:
    service = HealthDataAnalysisService()
    histories = {
        "53:57:08:00:00:01": [
            build_sample(
                device_mac="53:57:08:00:00:01",
                minutes=0,
                heart_rate=90,
                temperature=36.7,
                blood_oxygen=96,
                blood_pressure="128/80",
                health_score=86,
            ),
            build_sample(
                device_mac="53:57:08:00:00:01",
                minutes=45,
                heart_rate=122,
                temperature=38.4,
                blood_oxygen=89,
                blood_pressure="170/104",
                health_score=58,
                sos_flag=True,
            ),
        ],
        "53:57:08:00:00:02": [
            build_sample(
                device_mac="53:57:08:00:00:02",
                minutes=0,
                heart_rate=76,
                temperature=36.5,
                blood_oxygen=98,
                blood_pressure="122/78",
                health_score=90,
            ),
            build_sample(
                device_mac="53:57:08:00:00:02",
                minutes=45,
                heart_rate=78,
                temperature=36.6,
                blood_oxygen=97,
                blood_pressure="124/80",
                health_score=88,
            ),
        ],
    }

    summary = service.summarize_community_history(histories)

    assert summary["device_count"] == 2
    assert summary["risk_distribution"]["high"] == 1
    assert summary["priority_devices"][0]["device_mac"] == "53:57:08:00:00:01"


def test_device_summary_recommends_battery_follow_up_when_vitals_are_stable() -> None:
    service = HealthDataAnalysisService()
    samples = [
        build_sample(
            device_mac="53:57:08:00:00:03",
            minutes=0,
            heart_rate=74,
            temperature=36.5,
            blood_oxygen=98,
            blood_pressure="120/78",
            health_score=92,
        ),
        HealthSample(
            device_mac="53:57:08:00:00:03",
            timestamp=BASE_TIME + timedelta(minutes=20),
            heart_rate=75,
            temperature=36.6,
            blood_oxygen=98,
            blood_pressure="121/78",
            battery=18,
            sos_flag=False,
            health_score=91,
        ),
    ]

    summary = service.summarize_device(samples)

    assert summary["risk_level"] == "low"
    assert summary["risk_flags"] == ["within_expected_range"]
    assert any("充电" in item for item in summary["recommendations"])


def test_health_score_penalizes_sos_and_abnormal_vitals() -> None:
    tracker = BaselineTracker()
    scorer = HealthScoreService()
    baseline_sample = HealthSample(
        device_mac="53:57:08:00:00:04",
        timestamp=BASE_TIME,
        heart_rate=74,
        temperature=36.5,
        blood_oxygen=98,
        blood_pressure="120/78",
        battery=90,
        sos_flag=False,
        health_score=95,
    )
    baseline = tracker.observe(baseline_sample)

    stable_score = scorer.score(baseline_sample, baseline)
    critical_sample = HealthSample(
        device_mac="53:57:08:00:00:04",
        timestamp=BASE_TIME + timedelta(minutes=10),
        heart_rate=132,
        temperature=38.7,
        blood_oxygen=88,
        blood_pressure="172/106",
        battery=24,
        sos_flag=True,
        health_score=None,
    )

    critical_score = scorer.score(critical_sample, baseline)

    assert stable_score > critical_score
    assert critical_score == scorer._floor


def test_health_score_keeps_penalizing_persistent_low_oxygen_against_shifted_baseline() -> None:
    tracker = BaselineTracker()
    scorer = HealthScoreService()
    device_mac = "53:57:08:00:00:09"

    for minutes, spo2 in enumerate((92, 91, 91, 92, 91), start=0):
        tracker.observe(
            HealthSample(
                device_mac=device_mac,
                timestamp=BASE_TIME + timedelta(minutes=minutes * 10),
                heart_rate=84,
                temperature=36.8,
                blood_oxygen=spo2,
                blood_pressure="132/84",
                battery=78,
                sos_flag=False,
            )
        )

    shifted_baseline = tracker.observe(
        HealthSample(
            device_mac=device_mac,
            timestamp=BASE_TIME + timedelta(minutes=60),
            heart_rate=84,
            temperature=36.8,
            blood_oxygen=91,
            blood_pressure="132/84",
            battery=78,
            sos_flag=False,
        )
    )

    persistent_abnormal = HealthSample(
        device_mac=device_mac,
        timestamp=BASE_TIME + timedelta(minutes=70),
        heart_rate=85,
        temperature=36.9,
        blood_oxygen=90,
        blood_pressure="134/86",
        battery=76,
        sos_flag=False,
    )

    score = scorer.score(persistent_abnormal, shifted_baseline)

    assert score < 80


def test_intelligent_anomaly_scorer_detects_drift_for_abnormal_sequence() -> None:
    scorer = IntelligentAnomalyScorer()
    normal_windows = [
        [74.0, 36.5, 98.0, 118.0],
        [75.0, 36.6, 97.0, 120.0],
        [73.0, 36.5, 98.0, 119.0],
        [76.0, 36.6, 97.0, 121.0],
        [74.0, 36.4, 98.0, 118.0],
        [75.0, 36.5, 97.0, 120.0],
    ]
    scorer.warmup({"53:57:08:00:00:05": normal_windows})

    abnormal_samples = [
        HealthSample(
            device_mac="53:57:08:00:00:05",
            timestamp=BASE_TIME + timedelta(minutes=index * 10),
            heart_rate=heart_rate,
            temperature=temperature,
            blood_oxygen=blood_oxygen,
            blood_pressure=f"{systolic}/96",
            battery=68,
            sos_flag=False,
            health_score=score,
        )
        for index, (heart_rate, temperature, blood_oxygen, systolic, score) in enumerate(
            [
                (78, 36.7, 97, 124, 88),
                (82, 37.0, 96, 130, 84),
                (95, 37.4, 94, 142, 77),
                (108, 37.9, 92, 150, 70),
                (118, 38.3, 90, 162, 63),
                (126, 38.6, 88, 170, 56),
            ]
        )
    ]

    result = scorer.infer_device("53:57:08:00:00:05", abnormal_samples, force=True)

    assert result is not None
    assert result.probability > 0.68
    assert result.score > 0
    assert result.drift_score > 1.5


def test_community_clusterer_heatmap_marks_danger_and_attention_devices() -> None:
    clusterer = CommunityHealthClusterer()
    latest_samples = [
        build_sample(
            device_mac="53:57:08:00:00:06",
            minutes=0,
            heart_rate=78,
            temperature=36.5,
            blood_oxygen=98,
            blood_pressure="122/78",
            health_score=90,
        ),
        build_sample(
            device_mac="53:57:08:00:00:07",
            minutes=0,
            heart_rate=114,
            temperature=37.8,
            blood_oxygen=93,
            blood_pressure="144/92",
            health_score=75,
        ),
        build_sample(
            device_mac="53:57:08:00:00:08",
            minutes=0,
            heart_rate=126,
            temperature=38.7,
            blood_oxygen=88,
            blood_pressure="182/110",
            health_score=54,
            sos_flag=True,
        ),
    ]
    history_by_device = {
        "53:57:08:00:00:06": [
            build_sample(
                device_mac="53:57:08:00:00:06",
                minutes=-10,
                heart_rate=77,
                temperature=36.5,
                blood_oxygen=98,
                blood_pressure="121/78",
                health_score=91,
            ),
            latest_samples[0],
        ],
        "53:57:08:00:00:07": [
            build_sample(
                device_mac="53:57:08:00:00:07",
                minutes=-10,
                heart_rate=98,
                temperature=37.0,
                blood_oxygen=95,
                blood_pressure="136/88",
                health_score=82,
            ),
            latest_samples[1],
        ],
        "53:57:08:00:00:08": [
            build_sample(
                device_mac="53:57:08:00:00:08",
                minutes=-10,
                heart_rate=110,
                temperature=38.0,
                blood_oxygen=91,
                blood_pressure="168/100",
                health_score=65,
            ),
            latest_samples[2],
        ],
    }

    summary = clusterer.summarize(latest_samples, history_by_device)

    assert "53:57:08:00:00:08" in summary.clusters["danger"]
    assert "53:57:08:00:00:07" in summary.clusters["attention"]
    heatmap = {item["device_mac"]: item for item in summary.risk_heatmap}
    assert heatmap["53:57:08:00:00:08"]["risk"] == "danger"
    assert heatmap["53:57:08:00:00:07"]["trend_delta"]["heart_rate"] > 0


def test_community_priority_prefers_sos_and_critical_oxygen_with_same_risk_level() -> None:
    service = HealthDataAnalysisService()
    histories = {
        "53:57:08:00:00:10": [
            build_sample(
                device_mac="53:57:08:00:00:10",
                minutes=0,
                heart_rate=96,
                temperature=36.8,
                blood_oxygen=94,
                blood_pressure="132/84",
                health_score=78,
            ),
            build_sample(
                device_mac="53:57:08:00:00:10",
                minutes=45,
                heart_rate=118,
                temperature=38.1,
                blood_oxygen=88,
                blood_pressure="168/102",
                health_score=63,
            ),
        ],
        "53:57:08:00:00:11": [
            build_sample(
                device_mac="53:57:08:00:00:11",
                minutes=0,
                heart_rate=92,
                temperature=36.7,
                blood_oxygen=95,
                blood_pressure="128/82",
                health_score=80,
            ),
            build_sample(
                device_mac="53:57:08:00:00:11",
                minutes=45,
                heart_rate=112,
                temperature=37.9,
                blood_oxygen=90,
                blood_pressure="162/96",
                health_score=58,
                sos_flag=True,
            ),
        ],
    }

    summary = service.summarize_community_history(histories)

    assert summary["risk_distribution"]["high"] == 2
    assert summary["priority_devices"][0]["device_mac"] == "53:57:08:00:00:11"


def test_device_summary_recommendations_follow_falling_oxygen_and_rising_temperature() -> None:
    service = HealthDataAnalysisService()
    samples = [
        build_sample(
            device_mac="53:57:08:00:00:12",
            minutes=0,
            heart_rate=82,
            temperature=36.8,
            blood_oxygen=96,
            blood_pressure="126/80",
            health_score=88,
        ),
        build_sample(
            device_mac="53:57:08:00:00:12",
            minutes=30,
            heart_rate=88,
            temperature=37.6,
            blood_oxygen=94,
            blood_pressure="130/82",
            health_score=78,
        ),
        build_sample(
            device_mac="53:57:08:00:00:12",
            minutes=60,
            heart_rate=92,
            temperature=38.1,
            blood_oxygen=92,
            blood_pressure="132/84",
            health_score=70,
        ),
    ]

    summary = service.summarize_device(samples)

    assert any("血氧呈下降趋势" in item for item in summary["recommendations"])
    assert any("体温持续走高" in item for item in summary["recommendations"])
