from __future__ import annotations

import argparse
import base64
import hashlib
import os
import re
import socket
import sys
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

import requests


ROOT = Path(__file__).resolve().parents[1]
SOAP12 = "http://www.w3.org/2003/05/soap-envelope"
SOAP11 = "http://schemas.xmlsoap.org/soap/envelope/"


def load_env() -> dict[str, str]:
    env = os.environ.copy()
    env_path = ROOT / ".env"
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def envelope(body: str, soap_ns: str = SOAP12) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="{soap_ns}">
  <s:Body>
{body}
  </s:Body>
</s:Envelope>
"""


def summarize_xml(xml_text: str, max_chars: int = 1600) -> str:
    compact = re.sub(r">\s+<", "><", xml_text.strip())
    compact = re.sub(r"\s+", " ", compact)
    return compact[:max_chars] + ("..." if len(compact) > max_chars else "")


def soap_fault(xml_text: str) -> str | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    for element in root.iter():
        if element.tag.endswith("Fault"):
            text = " ".join(t.strip() for t in element.itertext() if t.strip())
            return text or "SOAP Fault"
    return None


class OnvifProbe:
    def __init__(self, ip: str, port: int, timeout: float) -> None:
        self.base = f"http://{ip}:{port}"
        self.timeout = timeout

    def post(self, path: str, body: str, label: str, soap_ns: str = SOAP12) -> str | None:
        url = f"{self.base}{path}"
        content_type = "application/soap+xml; charset=utf-8" if soap_ns == SOAP12 else "text/xml; charset=utf-8"
        print(f"\n[{label}] POST {url}")
        try:
            response = requests.post(
                url,
                data=envelope(textwrap.indent(body.strip(), "    "), soap_ns).encode("utf-8"),
                headers={"Content-Type": content_type},
                timeout=self.timeout,
            )
        except Exception as exc:  # noqa: BLE001 - this is a diagnostic script.
            print(f"  ERROR {exc.__class__.__name__}: {exc}")
            return None

        print(f"  HTTP {response.status_code}, {len(response.content)} bytes")
        if response.status_code >= 400:
            print("  HTTP_ERROR_BODY", summarize_xml(response.text, 600))
            return None

        fault = soap_fault(response.text)
        if fault:
            print(f"  SOAP_FAULT {fault}")
        else:
            print("  OK", summarize_xml(response.text, 900))
        return response.text


def find_texts(xml_text: str | None, local_names: Iterable[str]) -> dict[str, list[str]]:
    found = {name: [] for name in local_names}
    if not xml_text:
        return found
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return found
    for element in root.iter():
        local = element.tag.rsplit("}", 1)[-1]
        if local in found:
            value = (element.text or "").strip()
            if value:
                found[local].append(value)
            token = element.attrib.get("token")
            if token:
                found[local].append(f"token={token}")
    return found


def rtsp_request(
    ip: str,
    port: int,
    path: str,
    user: str,
    password: str,
    method: str,
    cseq: int,
    require_backchannel: bool = False,
    authorization: str = "",
) -> str:
    url = f"rtsp://{ip}:{port}{path}"
    auth = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii") if password else ""
    headers = [
        f"{method} {url} RTSP/1.0",
        f"CSeq: {cseq}",
        "User-Agent: ai-health-onvif-talk-probe",
    ]
    if method == "DESCRIBE":
        headers.append("Accept: application/sdp")
    if authorization:
        headers.append(f"Authorization: {authorization}")
    elif auth:
        headers.append(f"Authorization: Basic {auth}")
    if require_backchannel:
        headers.append("Require: www.onvif.org/ver20/backchannel")
    request = "\r\n".join(headers) + "\r\n\r\n"

    with socket.create_connection((ip, port), timeout=5) as sock:
        sock.settimeout(5)
        sock.sendall(request.encode("ascii", errors="ignore"))
        chunks: list[bytes] = []
        data = b""
        while True:
            try:
                chunk = sock.recv(8192)
            except socket.timeout:
                break
            if not chunk:
                break
            chunks.append(chunk)
            data = b"".join(chunks)
            header, _, rest = data.partition(b"\r\n\r\n")
            content_length = 0
            for line in header.decode("iso-8859-1", errors="ignore").splitlines():
                if line.lower().startswith("content-length:"):
                    try:
                        content_length = int(line.split(":", 1)[1].strip())
                    except ValueError:
                        content_length = 0
            if header and (content_length == 0 or len(rest) >= content_length):
                break
        return data.decode("utf-8", errors="replace")


def _parse_auth_params(header: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for match in re.finditer(r'(\w+)=(?:"([^"]*)"|([^,\s]+))', header):
        values[match.group(1).lower()] = match.group(2) if match.group(2) is not None else match.group(3)
    return values


def _digest_authorization(challenge_response: str, method: str, uri: str, user: str, password: str) -> str:
    match = re.search(r'WWW-Authenticate:\s*Digest\s+(.+)', challenge_response, re.IGNORECASE)
    if not match:
        return ""
    params = _parse_auth_params(match.group(1))
    realm = params.get("realm", "")
    nonce = params.get("nonce", "")
    qop = params.get("qop", "").split(",", 1)[0].strip()
    if not realm or not nonce:
        return ""

    def md5(value: str) -> str:
        return hashlib.md5(value.encode("utf-8")).hexdigest()  # noqa: S324 - RTSP Digest requires MD5.

    ha1 = md5(f"{user}:{realm}:{password}")
    ha2 = md5(f"{method}:{uri}")
    if qop:
        nc = "00000001"
        cnonce = "aihealth"
        response = md5(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}")
        return (
            f'Digest username="{user}", realm="{realm}", nonce="{nonce}", uri="{uri}", '
            f'response="{response}", qop={qop}, nc={nc}, cnonce="{cnonce}"'
        )
    response = md5(f"{ha1}:{nonce}:{ha2}")
    return f'Digest username="{user}", realm="{realm}", nonce="{nonce}", uri="{uri}", response="{response}"'


def rtsp_describe(
    ip: str,
    port: int,
    path: str,
    user: str,
    password: str,
    cseq: int,
    require_backchannel: bool = False,
) -> str:
    first = rtsp_request(ip, port, path, user, password, "DESCRIBE", cseq, require_backchannel)
    if "401 Unauthorized" not in first or "WWW-Authenticate:" not in first:
        return first
    uri = f"rtsp://{ip}:{port}{path}"
    authorization = _digest_authorization(first, "DESCRIBE", uri, user, password)
    if not authorization:
        return first
    return rtsp_request(
        ip,
        port,
        path,
        user,
        password,
        "DESCRIBE",
        cseq + 10,
        require_backchannel,
        authorization,
    )


def probe_rtsp_backchannel(ip: str, port: int, path: str, user: str, password: str) -> None:
    print("\n[RTSP OPTIONS]")
    try:
        options = rtsp_request(ip, port, path, user, password, "OPTIONS", 1)
        print(summarize_xml(options, 1000))
    except Exception as exc:  # noqa: BLE001
        print(f"  ERROR {exc.__class__.__name__}: {exc}")

    print("\n[RTSP DESCRIBE] normal")
    try:
        normal = rtsp_describe(ip, port, path, user, password, 2)
        print(summarize_xml(normal, 1000))
    except Exception as exc:  # noqa: BLE001
        print(f"  ERROR {exc.__class__.__name__}: {exc}")
        normal = ""

    print("\n[RTSP DESCRIBE] with ONVIF backchannel Require")
    try:
        backchannel = rtsp_describe(ip, port, path, user, password, 3, True)
        print(summarize_xml(backchannel, 1600))
        if "200 OK" in backchannel and "backchannel" not in backchannel.lower():
            print("  NOTE: DESCRIBE accepted the Require header, but SDP did not explicitly mention backchannel.")
        if "551" in backchannel or "Option not supported" in backchannel:
            print("  RESULT: RTSP server rejected ONVIF backchannel Require.")
    except Exception as exc:  # noqa: BLE001
        print(f"  ERROR {exc.__class__.__name__}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe ONVIF talkback/audio-output capabilities.")
    parser.add_argument("--ip", default="")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--rtsp-port", type=int, default=0)
    parser.add_argument("--rtsp-path", default="")
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()

    env = load_env()
    ip = args.ip or env.get("CAMERA_IP", "")
    port = args.port or int(env.get("CAMERA_ONVIF_PORT", "10080"))
    rtsp_port = args.rtsp_port or int(env.get("CAMERA_RTSP_PORT", "10554"))
    rtsp_path = args.rtsp_path or env.get("CAMERA_RTSP_PATH", "/tcp/av0_0")
    user = env.get("CAMERA_USER", "admin")
    password = env.get("CAMERA_PASSWORD", "")

    if not ip:
        print("CAMERA_IP is not configured.", file=sys.stderr)
        return 2

    probe = OnvifProbe(ip, port, args.timeout)

    services_xml = probe.post(
        "/onvif/device_service",
        """
<tds:GetServices xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
  <tds:IncludeCapability>true</tds:IncludeCapability>
</tds:GetServices>
""",
        "Device.GetServices",
    )
    caps_xml = probe.post(
        "/onvif/device_service",
        """
<tds:GetCapabilities xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
  <tds:Category>All</tds:Category>
</tds:GetCapabilities>
""",
        "Device.GetCapabilities",
    )
    profiles_xml = probe.post(
        "/onvif/media_service",
        '<trt:GetProfiles xmlns:trt="http://www.onvif.org/ver10/media/wsdl" />',
        "Media.GetProfiles",
    )
    media_caps_xml = probe.post(
        "/onvif/media_service",
        '<trt:GetServiceCapabilities xmlns:trt="http://www.onvif.org/ver10/media/wsdl" />',
        "Media.GetServiceCapabilities",
    )
    audio_outputs_xml = probe.post(
        "/onvif/media_service",
        '<trt:GetAudioOutputs xmlns:trt="http://www.onvif.org/ver10/media/wsdl" />',
        "Media.GetAudioOutputs",
    )
    audio_output_configs_xml = probe.post(
        "/onvif/media_service",
        '<trt:GetAudioOutputConfigurations xmlns:trt="http://www.onvif.org/ver10/media/wsdl" />',
        "Media.GetAudioOutputConfigurations",
    )
    receiver_xml = probe.post(
        "/onvif/receiver_service",
        '<trv:GetReceivers xmlns:trv="http://www.onvif.org/ver10/receiver/wsdl" />',
        "Receiver.GetReceivers",
    )

    print("\n[SUMMARY]")
    interesting = {
        "services": find_texts(services_xml, ["Namespace", "XAddr", "Capabilities"]),
        "capabilities": find_texts(caps_xml, ["XAddr", "RTP_RTSP_TCP", "RTP_TCP"]),
        "profiles": find_texts(profiles_xml, ["Name", "AudioSourceConfiguration", "AudioEncoderConfiguration", "AudioOutputConfiguration"]),
        "media_caps": find_texts(media_caps_xml, ["RTPMulticast", "RTP_TCP", "RTP_RTSP_TCP"]),
        "audio_outputs": find_texts(audio_outputs_xml, ["AudioOutputs", "Name"]),
        "audio_output_configs": find_texts(audio_output_configs_xml, ["Configurations", "Name"]),
        "receivers": find_texts(receiver_xml, ["Receivers", "Token", "Mode"]),
    }
    for group, values in interesting.items():
        print(f"- {group}:")
        any_value = False
        for key, items in values.items():
            if items:
                any_value = True
                print(f"  {key}: {items[:8]}")
        if not any_value:
            print("  (none)")

    probe_rtsp_backchannel(ip, rtsp_port, rtsp_path, user, password)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
