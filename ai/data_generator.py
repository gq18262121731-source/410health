from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from backend.models.device_model import DeviceRecord
from backend.models.health_model import HealthSample, IngestionSource


@dataclass(slots=True)
class DevicePersona:
    mac_address: str
    heart_rate_base: int
    temperature_base: float
    blood_oxygen_base: int
    systolic_base: int
    diastolic_base: int
    battery: int


@dataclass(slots=True)
class ScenarioPhase:
    name: str
    start_index: int
    end_index: int
    description: str


@dataclass(slots=True)
class HealthDemoScenario:
    name: str
    device_mac: str
    step_minutes: int
    model_window: int
    feature_names: list[str]
    output_scores: list[str]
    alarm_rule: dict[str, object]
    phases: list[ScenarioPhase]
    samples: list[HealthSample]


class SyntheticHealthDataGenerator:
    """Generates realistic elder-care vital signs for demos, tests and model warm-up."""

    def __init__(self, device_count: int = 10, mac_prefix: str = "53:57:08", seed: int = 42) -> None:
        self._rng = random.Random(seed)
        self._device_count = device_count
        self._mac_prefix = mac_prefix
        self._personas = [self._build_persona(index) for index in range(device_count)]

    @property
    def personas(self) -> list[DevicePersona]:
        return self._personas

    def build_devices(self) -> list[DeviceRecord]:
        return [
            DeviceRecord(mac_address=persona.mac_address, device_name="T10-WATCH")
            for persona in self._personas
        ]

    def next_sample(self, now: datetime | None = None) -> HealthSample:
        now = now or datetime.now(timezone.utc)
        persona = self._rng.choice(self._personas)
        return self.sample_for_device(persona.mac_address, now=now)

    def sample_for_device(self, device_mac: str, now: datetime | None = None) -> HealthSample:
        now = now or datetime.now(timezone.utc)
        persona = next((item for item in self._personas if item.mac_address == device_mac.upper()), None)
        if persona is None:
            raise ValueError(f"Unknown device: {device_mac}")
        hour_phase = math.sin((now.hour / 24) * math.pi * 2)

        heart_rate = persona.heart_rate_base + round(hour_phase * 6) + self._rng.randint(-4, 4)
        temperature = round(persona.temperature_base + hour_phase * 0.2 + self._rng.uniform(-0.15, 0.15), 1)
        blood_oxygen = persona.blood_oxygen_base + self._rng.randint(-1, 1)
        systolic = persona.systolic_base + self._rng.randint(-5, 5)
        diastolic = persona.diastolic_base + self._rng.randint(-4, 4)
        sos_flag = False

        scenario_roll = self._rng.random()
        if scenario_roll > 0.99:
            sos_flag = True
            heart_rate = min(190, heart_rate + self._rng.randint(18, 34))
            blood_oxygen = max(84, blood_oxygen - self._rng.randint(6, 10))
            temperature = round(min(39.2, temperature + self._rng.uniform(0.8, 1.4)), 1)
        elif scenario_roll > 0.95:
            heart_rate = min(188, heart_rate + self._rng.randint(22, 36))
            blood_oxygen = max(86, blood_oxygen - self._rng.randint(4, 8))
            systolic += self._rng.randint(18, 35)
            diastolic += self._rng.randint(12, 22)
            temperature = round(min(39.0, temperature + self._rng.uniform(0.6, 1.2)), 1)
        elif scenario_roll > 0.80:
            heart_rate = min(132, heart_rate + self._rng.randint(6, 14))
            blood_oxygen = max(91, blood_oxygen - self._rng.randint(1, 4))
            systolic += self._rng.randint(4, 12)
            diastolic += self._rng.randint(2, 8)
            temperature = round(min(38.1, temperature + self._rng.uniform(0.1, 0.5)), 1)

        persona.battery = max(18, persona.battery - self._rng.choice([0, 0, 1]))
        return HealthSample(
            device_mac=persona.mac_address,
            timestamp=now,
            heart_rate=heart_rate,
            temperature=temperature,
            blood_oxygen=blood_oxygen,
            blood_pressure=f"{systolic}/{diastolic}",
            battery=persona.battery,
            sos_flag=sos_flag,
            source=IngestionSource.MOCK,
        )

    def build_history(
        self,
        *,
        hours: int = 1,
        step_minutes: int = 10,
    ) -> dict[str, list[HealthSample]]:
        history: dict[str, list[HealthSample]] = {}
        now = datetime.now(timezone.utc)
        total_steps = max(1, int((hours * 60) / step_minutes))
        for persona in self._personas:
            device_samples: list[HealthSample] = []
            for index in range(total_steps):
                point_at = now - timedelta(minutes=step_minutes * (total_steps - index))
                device_samples.append(self.sample_for_device(persona.mac_address, now=point_at))
            history[persona.mac_address] = device_samples
        return history

    def build_training_sequences(
        self,
        *,
        hours: int = 24,
        step_minutes: int = 10,
    ) -> dict[str, list[list[float]]]:
        sequences: dict[str, list[list[float]]] = {}
        history = self.build_history(hours=hours, step_minutes=step_minutes)
        for device_mac, samples in history.items():
            windows: list[list[float]] = []
            for sample in samples:
                systolic, _ = sample.blood_pressure_pair or (120, 80)
                windows.append(
                    [
                        float(sample.heart_rate),
                        float(sample.temperature),
                        float(sample.blood_oxygen),
                        float(systolic),
                    ]
                )
            sequences[device_mac] = windows
        return sequences

    def build_sustained_anomaly_demo_scenario(
        self,
        *,
        device_mac: str | None = None,
        start: datetime | None = None,
        step_minutes: int = 10,
    ) -> HealthDemoScenario:
        start = start or datetime.now(timezone.utc).replace(second=0, microsecond=0)
        mac_address = device_mac.upper() if device_mac else self._personas[0].mac_address
        vitals = [
            (74, 36.5, 97, 120, 80, "normal"),
            (75, 36.6, 97, 121, 80, "normal"),
            (73, 36.5, 98, 119, 79, "normal"),
            (76, 36.6, 97, 121, 80, "normal"),
            (74, 36.5, 97, 120, 80, "normal"),
            (75, 36.5, 97, 121, 80, "normal"),
            (88, 37.1, 94, 132, 84, "anomaly"),
            (98, 37.6, 92, 146, 90, "sustained_anomaly"),
            (108, 37.8, 91, 152, 94, "sustained_anomaly"),
            (116, 38.0, 90, 160, 96, "alarm"),
        ]
        samples: list[HealthSample] = []
        for index, (heart_rate, temperature, blood_oxygen, systolic, diastolic, _) in enumerate(vitals):
            samples.append(
                HealthSample(
                    device_mac=mac_address,
                    timestamp=start + timedelta(minutes=index * step_minutes),
                    heart_rate=heart_rate,
                    temperature=temperature,
                    blood_oxygen=blood_oxygen,
                    blood_pressure=f"{systolic}/{diastolic}",
                    battery=max(42, 76 - index),
                    sos_flag=False,
                    source=IngestionSource.MOCK,
                )
            )

        phases = [
            ScenarioPhase(
                name="normal",
                start_index=0,
                end_index=5,
                description="稳定基线窗口，用于形成时序模型输入背景。",
            ),
            ScenarioPhase(
                name="anomaly",
                start_index=6,
                end_index=6,
                description="第一次明显偏移，但持续时间不足，不应直接报警。",
            ),
            ScenarioPhase(
                name="sustained_anomaly",
                start_index=7,
                end_index=8,
                description="异常持续存在且逐步加重，应进入持续异常状态但尚未报警。",
            ),
            ScenarioPhase(
                name="alarm",
                start_index=9,
                end_index=9,
                description="同时满足持续时间与异常程度阈值，触发智能报警。",
            ),
        ]
        return HealthDemoScenario(
            name="sustained-anomaly-escalation",
            device_mac=mac_address,
            step_minutes=step_minutes,
            model_window=6,
            feature_names=["heart_rate", "temperature", "blood_oxygen", "systolic"],
            output_scores=[
                "health_score",
                "anomaly_probability",
                "score",
                "drift_score",
                "reconstruction_score",
            ],
            alarm_rule={
                "duration_minutes": 30,
                "minimum_points": 4,
                "principle": "持续时间 + 异常程度，不依赖单点抖动",
            },
            phases=phases,
            samples=samples,
        )

    def encode_packet_pair(self, sample: HealthSample) -> tuple[str, str]:
        """Encodes a sample into the demo packet layout used by iot/parser.py."""
        systolic, diastolic = sample.blood_pressure_pair
        flags = 0x01 if sample.sos_flag else 0x00
        event_code = 0x02 if sample.sos_flag else 0x00
        temperature_raw = int(round(sample.temperature * 100))
        merged_payload = bytes(
            [
                sample.heart_rate,
                (temperature_raw >> 8) & 0xFF,
                temperature_raw & 0xFF,
                sample.blood_oxygen,
                systolic,
                diastolic,
                sample.battery,
                flags,
                event_code,
                0x00,
                0x00,
                0x00,
            ]
        )
        header = bytes.fromhex("AA55AA55AA55AA55AA55AA55")
        packet_a = header + bytes.fromhex("1803") + merged_payload[:6]
        packet_b = header + bytes.fromhex("0318") + merged_payload[6:]
        return packet_a.hex().upper(), packet_b.hex().upper()

    def _build_persona(self, index: int) -> DevicePersona:
        suffix = f"{index + 1:06X}"
        mac = ":".join([*self._mac_prefix.split(":"), suffix[0:2], suffix[2:4], suffix[4:6]])
        return DevicePersona(
            mac_address=mac,
            heart_rate_base=self._rng.randint(62, 84),
            temperature_base=round(self._rng.uniform(36.2, 36.8), 1),
            blood_oxygen_base=self._rng.randint(95, 99),
            systolic_base=self._rng.randint(108, 128),
            diastolic_base=self._rng.randint(68, 82),
            battery=self._rng.randint(72, 100),
        )
