from __future__ import annotations

import re
import time
from collections.abc import Callable

from backend.models.health_model import HealthSample, IngestionSource
from iot.parser import T10PacketParser

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None


MAC_PATTERN = re.compile(r"(?i)\b((?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}|53(?:57|:57)(?:08|:08)[0-9a-f:-]{6,})\b")
BROADCAST_MARKER = "0201061AFF4C000215"
RESPONSE_HEADER = "0A09"
RESPONSE_A_MARKER = "1803"
RESPONSE_B_MARKER = "0318"


class SerialGatewayReader:
    """Serial adapter for nRF52832 transparent transmission collectors."""

    def __init__(self, parser: T10PacketParser) -> None:
        self._parser = parser

    def list_candidate_ports(self, keywords: list[str] | None = None) -> list[object]:
        if list_ports is None:
            raise RuntimeError("pyserial 未安装，无法枚举串口。")
        normalized_keywords = [keyword.lower() for keyword in (keywords or [])]
        ports = list(list_ports.comports())
        if not normalized_keywords:
            return ports
        return [
            port
            for port in ports
            if any(
                keyword in " ".join(
                    [
                        str(getattr(port, "device", "")),
                        str(getattr(port, "description", "")),
                        str(getattr(port, "manufacturer", "")),
                        str(getattr(port, "hwid", "")),
                    ]
                ).lower()
                for keyword in normalized_keywords
            )
        ]

    def detect_port(self, preferred_port: str | None = None, keywords: list[str] | None = None) -> str:
        if preferred_port:
            return preferred_port

        candidates = self.list_candidate_ports(keywords)
        if not candidates:
            raise RuntimeError("未检测到可用蓝牙采集器串口。")
        return str(candidates[0].device)

    def initialize_collector(
        self,
        connection,
        *,
        mac_filter: str,
        packet_type: int,
        disable_uuid_output: bool = True,
        apply_mac_filter: bool = False,
        apply_packet_type: bool = False,
        command_delay_seconds: float = 0.2,
    ) -> None:
        commands = ["AT+SCANSTOP"]
        if disable_uuid_output:
            commands.append("AT+UUID=NO")
        if apply_mac_filter:
            commands.append(f"AT+MAC={mac_filter}")
        if apply_packet_type:
            commands.append(f"AT+TYPE={packet_type}")
        commands.append("AT+SCANSTART")

        for command in commands:
            connection.write(f"{command}\r\n".encode("utf-8"))
            connection.flush()
            time.sleep(command_delay_seconds)
            self._drain_feedback(connection)

    def switch_packet_type(
        self,
        connection,
        *,
        packet_type: int,
        command_delay_seconds: float = 0.2,
    ) -> None:
        for command in ("AT+SCANSTOP", f"AT+TYPE={packet_type}", "AT+SCANSTART"):
            connection.write(f"{command}\r\n".encode("utf-8"))
            connection.flush()
            time.sleep(command_delay_seconds)
            self._drain_feedback(connection)

    def run(
        self,
        *,
        port: str | None = None,
        baudrate: int = 115200,
        packet_type: int = 5,
        mac_filter: str = "535708000000",
        detection_keywords: list[str] | None = None,
        fallback_device_mac: str | None = None,
        auto_configure: bool = True,
        disable_uuid_output: bool = True,
        apply_mac_filter: bool = False,
        apply_packet_type: bool = False,
        enable_broadcast_sos_overlay: bool = False,
        response_cycle_seconds: float = 8.0,
        broadcast_cycle_seconds: float = 2.0,
        on_sample: Callable[[HealthSample], None] | None = None,
    ) -> None:
        if serial is None:
            raise RuntimeError("pyserial 未安装，无法启用串口采集模式。")

        selected_port = self.detect_port(port, detection_keywords)
        with serial.Serial(port=selected_port, baudrate=baudrate, timeout=1) as connection:
            active_packet_type = packet_type
            if auto_configure:
                self.initialize_collector(
                    connection,
                    mac_filter=mac_filter,
                    packet_type=packet_type,
                    disable_uuid_output=disable_uuid_output,
                    apply_mac_filter=apply_mac_filter,
                    apply_packet_type=apply_packet_type,
                )
            cycle_started_at = time.monotonic()

            while True:
                if enable_broadcast_sos_overlay:
                    elapsed = time.monotonic() - cycle_started_at
                    target_packet_type = 5
                    if active_packet_type == 5 and elapsed >= response_cycle_seconds:
                        target_packet_type = 4
                    elif active_packet_type == 4 and elapsed >= broadcast_cycle_seconds:
                        target_packet_type = 5

                    if target_packet_type != active_packet_type:
                        self.switch_packet_type(connection, packet_type=target_packet_type)
                        active_packet_type = target_packet_type
                        cycle_started_at = time.monotonic()

                line = connection.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                payload, line_mac = self._extract_payload_and_mac(line)
                if not payload:
                    continue

                sample = self._parser.feed(
                    line_mac or fallback_device_mac,
                    payload,
                    source=IngestionSource.SERIAL,
                )
                if sample and on_sample:
                    on_sample(sample)

    @staticmethod
    def _drain_feedback(connection) -> None:
        started = time.time()
        while time.time() - started < 0.2:
            waiting = getattr(connection, "in_waiting", 0)
            if not waiting:
                break
            connection.readline()

    @staticmethod
    def _extract_payload_and_mac(line: str) -> tuple[str | None, str | None]:
        upper_line = line.upper()
        if upper_line.startswith("AT+") or upper_line in {"OK", "ERROR"}:
            return None, None

        compact = re.sub(r"[^0-9A-Fa-f]", "", line).upper()
        if len(compact) < 12:
            return None, None

        collector_payload, collector_mac = SerialGatewayReader._extract_prefixed_payload(compact)
        if collector_payload:
            return collector_payload, collector_mac

        mac_match = MAC_PATTERN.search(line)
        mac = None
        if mac_match:
            compact_mac = re.sub(r"[^0-9A-Fa-f]", "", mac_match.group(1)).upper()
            if len(compact_mac) == 12:
                mac = ":".join(compact_mac[index : index + 2] for index in range(0, 12, 2))

        payload = SerialGatewayReader._extract_embedded_payload(compact)
        if not payload or len(payload) % 2 != 0:
            return None, mac
        return payload, mac

    @staticmethod
    def _extract_prefixed_payload(compact: str) -> tuple[str | None, str | None]:
        if len(compact) < 16:
            return None, None

        # nRF52832 collector format observed in the field:
        # RSSI(1 byte) + device MAC(6 bytes) + advertising payload
        candidate_mac = compact[2:14]
        candidate_payload = compact[14:]
        if len(candidate_payload) % 2 != 0:
            return None, None

        if candidate_payload.startswith(BROADCAST_MARKER):
            return candidate_payload, SerialGatewayReader._format_mac(candidate_mac)

        if RESPONSE_A_MARKER in candidate_payload[:40] or RESPONSE_B_MARKER in candidate_payload[:40]:
            return candidate_payload, SerialGatewayReader._format_mac(candidate_mac)

        return None, None

    @staticmethod
    def _extract_embedded_payload(compact: str) -> str | None:
        broadcast_index = compact.find(BROADCAST_MARKER)
        if broadcast_index != -1:
            return compact[broadcast_index:]

        response_a_index = compact.find(RESPONSE_HEADER)
        while response_a_index != -1:
            marker_index = compact.find(RESPONSE_A_MARKER, response_a_index)
            if marker_index != -1:
                return compact[response_a_index:]
            response_a_index = compact.find(RESPONSE_HEADER, response_a_index + 1)

        response_b_index = compact.find(RESPONSE_HEADER)
        while response_b_index != -1:
            marker_index = compact.find(RESPONSE_B_MARKER, response_b_index)
            if marker_index != -1:
                return compact[response_b_index:]
            response_b_index = compact.find(RESPONSE_HEADER, response_b_index + 1)

        if re.fullmatch(r"[0-9A-F]+", compact):
            return compact
        return None

    @staticmethod
    def _format_mac(compact_mac: str) -> str:
        return ":".join(compact_mac[index : index + 2] for index in range(0, 12, 2))
