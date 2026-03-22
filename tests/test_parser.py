from ai.data_generator import SyntheticHealthDataGenerator
from iot.parser import T10PacketParser
from iot.serial_reader import SerialGatewayReader


def test_parser_decodes_t10_broadcast_packet() -> None:
    parser = T10PacketParser()
    packet = "0201061AFF4C000215526164696F6C616E642D54100000000054630E4201"

    decoded = parser.feed("53:57:08:03:00:01", packet)

    assert decoded is not None
    assert decoded.device_mac == "53:57:08:03:00:01"
    assert decoded.device_uuid == "52616469-6F6C-616E-642D-541000000000"
    assert decoded.heart_rate == 84
    assert decoded.blood_oxygen == 99
    assert decoded.temperature == 36.5
    assert decoded.sos_flag is True
    assert decoded.packet_type == "broadcast"


def test_parser_decodes_t10_response_packet() -> None:
    parser = T10PacketParser()
    packet = "0A095431302D5741544348141618030ACB640DD400540063535708020001061A"

    decoded = parser.feed(None, packet)

    assert decoded is not None
    assert decoded.device_mac == "53:57:08:02:00:01"
    assert decoded.ambient_temperature == 27.63
    assert decoded.surface_temperature == 35.4
    assert decoded.temperature == 35.4
    assert decoded.battery == 100
    assert decoded.heart_rate == 84
    assert decoded.blood_oxygen == 99
    assert decoded.steps == 1562
    assert decoded.packet_type == "response_a"


def test_parser_merges_t10_response_b_packet() -> None:
    parser = T10PacketParser()
    packet_a = "0A095431302D5741544348141618030ACB640DD400540063535708020001061A"
    packet_b = "0A095431302D5741544348071603187C5F0E42"

    first = parser.feed(None, packet_a)
    decoded = parser.feed("53:57:08:02:00:01", packet_b)

    assert first is not None
    assert decoded is not None
    assert decoded.device_mac == "53:57:08:02:00:01"
    assert decoded.blood_pressure == "124/95"
    assert decoded.temperature == 36.5
    assert decoded.surface_temperature == 35.4
    assert decoded.packet_type == "response_ab"


def test_serial_reader_extracts_prefixed_type5_response_packets() -> None:
    line = "C15410260100DF090954313057415443481416180300005F0000004B00005410260100DF00EB"

    payload, device_mac = SerialGatewayReader._extract_payload_and_mac(line)
    parser = T10PacketParser()
    decoded = parser.feed(device_mac, payload)

    assert device_mac == "54:10:26:01:00:DF"
    assert payload == "090954313057415443481416180300005F0000004B00005410260100DF00EB"
    assert decoded is not None
    assert decoded.device_mac == "54:10:26:01:00:DF"
    assert decoded.battery == 95
    assert decoded.heart_rate == 75
    assert decoded.steps == 235
    assert decoded.packet_type == "response_a"


def test_serial_reader_merges_prefixed_type5_response_b_packets() -> None:
    parser = T10PacketParser()
    line_a = "C15410260100DF090954313057415443481416180300005F0000004B00005410260100DF00EB"
    line_b = "C25410260100DF0909543130574154434807160318784B0E4500000000000000000000000000"

    payload_a, mac_a = SerialGatewayReader._extract_payload_and_mac(line_a)
    payload_b, mac_b = SerialGatewayReader._extract_payload_and_mac(line_b)

    first = parser.feed(mac_a, payload_a)
    decoded = parser.feed(mac_b, payload_b)

    assert first is not None
    assert decoded is not None
    assert decoded.device_mac == "54:10:26:01:00:DF"
    assert decoded.blood_pressure == "120/75"
    assert decoded.temperature == 36.53
    assert decoded.battery == 95
    assert decoded.steps == 235
    assert decoded.packet_type == "response_ab"


def test_parser_merges_legacy_dual_packets() -> None:
    generator = SyntheticHealthDataGenerator(device_count=1)
    sample = generator.next_sample()
    packet_a, packet_b = generator.encode_packet_pair(sample)

    parser = T10PacketParser()
    assert parser.feed(sample.device_mac, packet_a) is None
    decoded = parser.feed(sample.device_mac, packet_b)

    assert decoded is not None
    assert decoded.device_mac == sample.device_mac
    assert decoded.heart_rate == sample.heart_rate
    assert decoded.temperature == sample.temperature
    assert decoded.blood_oxygen == sample.blood_oxygen
    assert decoded.blood_pressure == sample.blood_pressure
    assert decoded.packet_type == "legacy_response"
