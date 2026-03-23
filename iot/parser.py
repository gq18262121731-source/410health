from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from backend.models.health_model import HealthSample, IngestionSource


class PacketKind(str, Enum):
    BROADCAST = "broadcast"
    RESPONSE_A = "response_a"
    RESPONSE_B = "response_b"
    LEGACY_RESPONSE_A = "legacy_response_a"
    LEGACY_RESPONSE_B = "legacy_response_b"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class PacketLayout:
    legacy_marker_offset: int = 12
    legacy_header_length: int = 14
    legacy_response_a_marker: bytes = bytes.fromhex("1803")
    legacy_response_b_marker: bytes = bytes.fromhex("0318")
    response_scan_limit: int = 18
    broadcast_prefix: bytes = bytes.fromhex("0201061AFF4C000215")
    default_uuid: str = "52616469-6F6C-616E-642D-541000000000"


@dataclass(slots=True)
class PartialPacket:
    first_seen: datetime
    packet_a: bytes | None = None
    packet_b: bytes | None = None
    raw_a: str | None = None
    raw_b: str | None = None
    sample: HealthSample | None = None


class T10PacketParser:
    """Parser for the T10 bracelet broadcast and response frames."""

    def __init__(
        self,
        layout: PacketLayout | None = None,
        merge_timeout_seconds: float = 2.5,
        sos_window_seconds: int = 15,
    ) -> None:
        self._layout = layout or PacketLayout()
        self._merge_timeout = merge_timeout_seconds
        self._partials: dict[str, PartialPacket] = {}
        self._sos_events: dict[str, deque[datetime]] = defaultdict(deque)
        self._sos_window = timedelta(seconds=sos_window_seconds)

    def feed(
        self,
        device_mac: str | None,
        payload: str | bytes,
        *,
        source: IngestionSource = IngestionSource.BLE,
        timestamp: datetime | None = None,
    ) -> HealthSample | None:
        timestamp = timestamp or datetime.now(timezone.utc)
        packet = self._normalize_payload(payload)
        kind = self.identify_packet(packet)

        if kind is PacketKind.UNKNOWN:
            return None

        if kind is PacketKind.BROADCAST:
            return self._decode_broadcast(device_mac, packet, timestamp, source)

        if kind is PacketKind.RESPONSE_A:
            return self._handle_response_a(packet, timestamp, source)

        if kind is PacketKind.RESPONSE_B:
            return self._handle_response_b(device_mac, packet, timestamp, source)

        return self._decode_legacy(device_mac, packet, kind, timestamp, source)

    def identify_packet(self, payload: bytes) -> PacketKind:
        if payload.startswith(self._layout.broadcast_prefix) and len(payload) >= 30:
            return PacketKind.BROADCAST

        if payload.startswith(bytes.fromhex("0A09")) or payload.startswith(bytes.fromhex("0909")):
            marker_index = self._find_response_marker(payload, self._layout.legacy_response_a_marker)
            if marker_index != -1 and len(payload) >= marker_index + 19:
                return PacketKind.RESPONSE_A

        if payload.startswith(bytes.fromhex("0716")) or payload.startswith(bytes.fromhex("0909")):
            marker_index = self._find_response_marker(payload, self._layout.legacy_response_b_marker)
            if marker_index != -1 and len(payload) >= marker_index + 6:
                return PacketKind.RESPONSE_B

        if payload.startswith(bytes.fromhex("0A09")):
            marker_index = self._find_response_marker(payload, self._layout.legacy_response_b_marker)
            if marker_index != -1 and len(payload) >= marker_index + 6:
                return PacketKind.RESPONSE_B

        if len(payload) <= self._layout.legacy_marker_offset + 1:
            return PacketKind.UNKNOWN

        marker = payload[
            self._layout.legacy_marker_offset : self._layout.legacy_marker_offset + 2
        ]
        if marker == self._layout.legacy_response_a_marker:
            return PacketKind.LEGACY_RESPONSE_A
        if marker == self._layout.legacy_response_b_marker:
            return PacketKind.LEGACY_RESPONSE_B
        return PacketKind.UNKNOWN

    @staticmethod
    def _normalize_payload(payload: str | bytes) -> bytes:
        if isinstance(payload, bytes):
            return payload
        compact = payload.replace(" ", "").replace(":", "").replace("-", "")
        return bytes.fromhex(compact)

    def _decode_broadcast(
        self,
        device_mac: str | None,
        payload: bytes,
        timestamp: datetime,
        source: IngestionSource,
    ) -> HealthSample | None:
        if not device_mac:
            return None

        uuid_bytes = payload[9:25]
        heart_rate = payload[25]
        blood_oxygen = payload[26]
        temperature = round(int.from_bytes(payload[27:29], byteorder="big") / 100.0, 2)
        sos_value = payload[29]

        normalized_mac = self._normalize_mac(device_mac)
        return HealthSample(
            device_mac=normalized_mac,
            timestamp=timestamp,
            heart_rate=heart_rate,
            temperature=temperature,
            blood_oxygen=blood_oxygen,
            battery=0,
            sos_flag=bool(sos_value),
            source=source,
            device_uuid=self._format_uuid(uuid_bytes),
            packet_type=PacketKind.BROADCAST.value,
            raw_packet_a=payload.hex().upper(),
        )

    def _decode_response_a(
        self,
        payload: bytes,
        timestamp: datetime,
        source: IngestionSource,
    ) -> HealthSample | None:
        marker_index = self._find_response_marker(payload, self._layout.legacy_response_a_marker)
        if marker_index == -1 or len(payload) < marker_index + 19:
            return None

        ambient_temperature = round(
            int.from_bytes(payload[marker_index + 2 : marker_index + 4], byteorder="big") / 100.0,
            2,
        )
        battery = payload[marker_index + 4]
        surface_temperature = round(
            int.from_bytes(payload[marker_index + 5 : marker_index + 7], byteorder="big") / 100.0,
            2,
        )
        sample_temperature = surface_temperature if 30.0 <= surface_temperature <= 45.0 else 30.0
        heart_rate = int.from_bytes(payload[marker_index + 7 : marker_index + 9], byteorder="big")
        blood_oxygen = int.from_bytes(payload[marker_index + 9 : marker_index + 11], byteorder="big")
        device_mac = self._format_mac(payload[marker_index + 11 : marker_index + 17])
        steps = int.from_bytes(payload[marker_index + 17 : marker_index + 19], byteorder="big")

        return HealthSample(
            device_mac=device_mac,
            timestamp=timestamp,
            heart_rate=heart_rate,
            temperature=sample_temperature,
            blood_oxygen=blood_oxygen,
            battery=battery,
            sos_flag=False,
            source=source,
            device_uuid=self._layout.default_uuid,
            ambient_temperature=ambient_temperature,
            surface_temperature=surface_temperature,
            steps=steps,
            packet_type=PacketKind.RESPONSE_A.value,
            raw_packet_a=payload.hex().upper(),
        )

    def _handle_response_a(
        self,
        payload: bytes,
        timestamp: datetime,
        source: IngestionSource,
    ) -> HealthSample | None:
        sample = self._decode_response_a(payload, timestamp, source)
        if sample is None:
            return None

        partial = self._partials.get(sample.device_mac)
        if not partial or timestamp - partial.first_seen > timedelta(seconds=self._merge_timeout):
            partial = PartialPacket(first_seen=timestamp)

        partial.first_seen = timestamp
        partial.packet_a = payload
        partial.raw_a = payload.hex().upper()
        partial.sample = sample
        self._partials[sample.device_mac] = partial

        if partial.packet_b:
            merged = self._merge_response_b(sample, partial.packet_b, partial.raw_b)
            del self._partials[sample.device_mac]
            return merged

        return sample

    def _handle_response_b(
        self,
        device_mac: str | None,
        payload: bytes,
        timestamp: datetime,
        source: IngestionSource,
    ) -> HealthSample | None:
        if not device_mac:
            return None

        normalized_mac = self._normalize_mac(device_mac)
        partial = self._partials.get(normalized_mac)
        if not partial or timestamp - partial.first_seen > timedelta(seconds=self._merge_timeout):
            partial = PartialPacket(first_seen=timestamp)

        partial.first_seen = timestamp
        partial.packet_b = payload
        partial.raw_b = payload.hex().upper()
        self._partials[normalized_mac] = partial

        if partial.sample:
            merged = self._merge_response_b(partial.sample, payload, partial.raw_b)
            del self._partials[normalized_mac]
            return merged

        return None

    def _merge_response_b(
        self,
        sample: HealthSample,
        payload: bytes,
        raw_packet_b: str | None,
    ) -> HealthSample:
        marker_index = self._find_response_marker(payload, self._layout.legacy_response_b_marker)
        if marker_index == -1 or len(payload) < marker_index + 6:
            return sample

        systolic = payload[marker_index + 2]
        diastolic = payload[marker_index + 3]
        body_temperature = round(
            int.from_bytes(payload[marker_index + 4 : marker_index + 6], byteorder="big") / 100.0,
            2,
        )
        return sample.model_copy(
            update={
                "temperature": body_temperature,
                "blood_pressure": f"{systolic}/{diastolic}",
                "packet_type": "response_ab",
                "raw_packet_b": raw_packet_b,
            }
        )

    def _decode_legacy(
        self,
        device_mac: str | None,
        packet: bytes,
        kind: PacketKind,
        timestamp: datetime,
        source: IngestionSource,
    ) -> HealthSample | None:
        if not device_mac:
            return None

        normalized_mac = self._normalize_mac(device_mac)
        partial = self._partials.get(normalized_mac)
        if not partial or timestamp - partial.first_seen > timedelta(seconds=self._merge_timeout):
            partial = PartialPacket(first_seen=timestamp)

        if kind is PacketKind.LEGACY_RESPONSE_A:
            partial.packet_a = packet
            partial.raw_a = packet.hex().upper()
        else:
            partial.packet_b = packet
            partial.raw_b = packet.hex().upper()

        self._partials[normalized_mac] = partial
        if not partial.packet_a or not partial.packet_b:
            return None

        merged = (
            partial.packet_a[self._layout.legacy_header_length :]
            + partial.packet_b[self._layout.legacy_header_length :]
        )
        del self._partials[normalized_mac]
        return self._decode_legacy_payload(
            normalized_mac,
            merged,
            timestamp,
            source,
            raw_a=partial.raw_a,
            raw_b=partial.raw_b,
        )

    def _decode_legacy_payload(
        self,
        device_mac: str,
        merged: bytes,
        timestamp: datetime,
        source: IngestionSource,
        *,
        raw_a: str | None = None,
        raw_b: str | None = None,
    ) -> HealthSample | None:
        if len(merged) < 9:
            return None

        heart_rate = merged[0]
        temperature = round(((merged[1] << 8) | merged[2]) / 100.0, 1)
        blood_oxygen = merged[3]
        battery = merged[6]
        flags = merged[7]
        event_code = merged[8]
        sos_flag = bool(flags & 0x01) or event_code == 0x02 or self._register_sos(
            device_mac,
            timestamp,
            flags,
            event_code,
        )

        return HealthSample(
            device_mac=device_mac,
            timestamp=timestamp,
            heart_rate=heart_rate,
            temperature=temperature,
            blood_oxygen=blood_oxygen,
            blood_pressure=f"{merged[4]}/{merged[5]}",
            battery=battery,
            sos_flag=sos_flag,
            source=source,
            packet_type="legacy_response",
            raw_packet_a=raw_a,
            raw_packet_b=raw_b,
        )

    def _register_sos(self, device_mac: str, timestamp: datetime, flags: int, event_code: int) -> bool:
        if not (flags & 0x01 or event_code == 0x02):
            return False
        events = self._sos_events[device_mac]
        events.append(timestamp)
        while events and timestamp - events[0] > self._sos_window:
            events.popleft()
        return True

    def parse_dict(self, device_mac: str | None, payload: str | bytes, **kwargs: Any) -> dict[str, Any] | None:
        sample = self.feed(device_mac, payload, **kwargs)
        return sample.model_dump(mode="json") if sample else None

    def _find_response_marker(self, payload: bytes, marker: bytes) -> int:
        return payload.find(marker, 0, self._layout.response_scan_limit)

    @staticmethod
    def _format_mac(raw: bytes) -> str:
        return ":".join(f"{value:02X}" for value in raw)

    @staticmethod
    def _normalize_mac(device_mac: str) -> str:
        compact = device_mac.replace("-", "").replace(":", "").upper()
        if len(compact) != 12:
            return device_mac.upper()
        return ":".join(compact[index : index + 2] for index in range(0, 12, 2))

    @staticmethod
    def _format_uuid(raw: bytes) -> str:
        hex_value = raw.hex().upper()
        return (
            f"{hex_value[0:8]}-"
            f"{hex_value[8:12]}-"
            f"{hex_value[12:16]}-"
            f"{hex_value[16:20]}-"
            f"{hex_value[20:32]}"
        )
