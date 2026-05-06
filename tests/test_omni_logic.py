from __future__ import annotations

import base64
import io
import json
import wave
from types import SimpleNamespace

from backend.config import get_settings
from backend.services.voice_service import VoiceService


class _FakeCompletions:
    def __init__(self, chunks) -> None:
        self._chunks = chunks
        self.last_kwargs: dict[str, object] | None = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return iter(self._chunks)


class _FakeClient:
    def __init__(self, chunks) -> None:
        self.completions = _FakeCompletions(chunks)
        self.chat = SimpleNamespace(completions=self.completions)


class _FakeMessageCompletions:
    def __init__(self, message_content) -> None:
        self._message_content = message_content
        self.last_kwargs: dict[str, object] | None = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self._message_content),
                )
            ]
        )


class _FakeMessageClient:
    def __init__(self, message_content) -> None:
        self.completions = _FakeMessageCompletions(message_content)
        self.chat = SimpleNamespace(completions=self.completions)


def _fake_chunk(*, text: str | None = None, audio_data: str | None = None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(
                    content=text,
                    audio={"data": audio_data} if audio_data is not None else None,
                )
            )
        ]
    )


def test_qwen_omni_defaults_to_qwen25_omni_7b() -> None:
    settings = get_settings().model_copy(update={"qwen_omni_model": ""})
    assert settings.qwen_omni_model_id == "qwen2.5-omni-7b"


def test_qwen_omni_legacy_aliases_fall_back_to_qwen25_omni_7b() -> None:
    legacy_values = (
        "qwen3.5-omni-plus",
        "qwen3.5-omni-plus-realtime",
        "qwen3.5-pmni-plus",
        "qwen-omni",
    )

    for legacy_value in legacy_values:
        settings = get_settings().model_copy(update={"qwen_omni_model": legacy_value})
        assert settings.qwen_omni_model_id == "qwen2.5-omni-7b"


def test_omni_chat_aggregates_text_and_wraps_pcm_audio(monkeypatch) -> None:
    pcm_bytes = b"\x00\x00\xff\x7f\x01\x00\xfe\x7f"
    pcm_b64 = base64.b64encode(pcm_bytes).decode("ascii")
    fake_client = _FakeClient(
        [
            _fake_chunk(text="您好，", audio_data=pcm_b64[:6]),
            _fake_chunk(text="今天状态稳定。", audio_data=pcm_b64[6:]),
            SimpleNamespace(choices=[]),
        ]
    )

    settings = get_settings().model_copy(
        update={
            "dashscope_api_key_env": "test-key",
            "qwen_api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "qwen_omni_model": "qwen2.5-omni-7b",
        }
    )
    service = VoiceService(settings)
    monkeypatch.setattr(service, "_build_compatible_client", lambda: fake_client)

    result = service.omni_chat(
        b"fake wav bytes",
        fmt="wav",
        prompt="请回答我是谁",
        role="elder",
    )

    assert result["ok"] is True
    assert result["text"] == "您好，今天状态稳定。"
    assert result["fmt"] == "wav"
    assert result["voice"] == "Chelsie"
    assert result["provider"] == "dashscope-compatible/qwen2.5-omni-7b"

    request_kwargs = fake_client.completions.last_kwargs
    assert request_kwargs is not None
    assert request_kwargs["model"] == "qwen2.5-omni-7b"
    assert request_kwargs["stream"] is True
    assert request_kwargs["modalities"] == ["text", "audio"]
    assert request_kwargs["audio"] == {"voice": "Chelsie", "format": "wav"}

    messages = request_kwargs["messages"]
    assert isinstance(messages, list)
    system_message = messages[0]
    assert system_message["content"] == "You are a helpful assistant."
    user_message = messages[1]
    user_content = user_message["content"]
    assert user_content[0]["type"] == "input_audio"
    assert user_content[0]["input_audio"]["format"] == "wav"
    assert user_content[0]["input_audio"]["data"].startswith("data:;base64,")
    assert "绝对不要虚构和捏造任何健康数值" in user_content[1]["text"]

    wav_bytes = base64.b64decode(result["audio_b64"])
    with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == 24000
        assert wav_file.readframes(wav_file.getnframes()) == pcm_bytes


def test_omni_chat_uses_text_only_output_for_non_elder(monkeypatch) -> None:
    fake_client = _FakeClient([_fake_chunk(text="已收到。")])
    settings = get_settings().model_copy(
        update={
            "dashscope_api_key_env": "test-key",
            "qwen_omni_model": "qwen2.5-omni-7b",
        }
    )
    service = VoiceService(settings)
    monkeypatch.setattr(service, "_build_compatible_client", lambda: fake_client)

    result = service.omni_chat(
        b"fake mp3 bytes",
        fmt="mp3",
        role="family",
    )

    assert result["ok"] is True
    assert result["text"] == "已收到。"
    assert result["audio_b64"] == ""

    request_kwargs = fake_client.completions.last_kwargs
    assert request_kwargs is not None
    assert request_kwargs["modalities"] == ["text"]
    assert "audio" not in request_kwargs


def test_omni_chat_retries_supported_audio_voice(monkeypatch) -> None:
    pcm_b64 = base64.b64encode(b"\x00\x00\x01\x00").decode("ascii")

    class _RetryingCompletions:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            audio = kwargs.get("audio") or {}
            voice = audio.get("voice") if isinstance(audio, dict) else None
            if voice == "Chelsie":
                raise Exception(
                    "<400> InternalError.Algo.InvalidParameter: Input should be 'Ethan': parameters.audio.voice."
                )
            return iter([_fake_chunk(text="ok", audio_data=pcm_b64)])

    retrying = _RetryingCompletions()
    fake_client = SimpleNamespace(
        completions=retrying,
        chat=SimpleNamespace(completions=retrying),
    )
    settings = get_settings().model_copy(
        update={
            "dashscope_api_key_env": "test-key",
            "qwen_omni_model": "qwen2.5-omni-7b",
        }
    )
    service = VoiceService(settings)
    monkeypatch.setattr(service, "_build_compatible_client", lambda: fake_client)

    result = service.omni_chat(
        b"fake wav bytes",
        fmt="wav",
        role="elder",
    )

    assert result["ok"] is True
    assert result["text"] == "ok"
    assert result["voice"] == "Ethan"
    assert [call["audio"]["voice"] for call in retrying.calls] == ["Chelsie", "Ethan"]


def test_review_fall_snapshot_uses_qwen_omni_and_parses_json(monkeypatch, tmp_path) -> None:
    fake_client = _FakeMessageClient(
        json.dumps(
            {
                "judgement": "no_fall",
                "confidence": "high",
                "reason": "画面更像弯腰动作，没有看到倒地后的持续姿态",
                "recommended_action": "downgrade",
                "visible_person_count": 1,
                "risk_cues": [],
                "false_positive_cues": ["bend"],
            },
            ensure_ascii=False,
        )
    )
    settings = get_settings().model_copy(
        update={
            "dashscope_api_key_env": "test-key",
            "qwen_omni_model": "qwen2.5-omni-7b",
        }
    )
    service = VoiceService(settings)
    monkeypatch.setattr(service, "_build_compatible_client", lambda: fake_client)

    snapshot = tmp_path / "fall-review.jpg"
    snapshot.write_bytes(b"\xff\xd8\xff\xdbfake-jpeg")
    result = service.review_fall_snapshot(
        snapshot,
        event={
            "fall_score": 0.82,
            "state": "confirmed_fall",
            "severity": "L3",
            "injury": {"level": "I3", "down_seconds": 2.1},
        },
    )

    assert result["status"] == "ok"
    assert result["provider"] == "dashscope-compatible"
    assert result["model"] == "qwen2.5-omni-7b"
    assert result["judgement"] == "no_fall"
    assert result["confidence"] == "high"
    assert result["recommended_action"] == "downgrade"

    request_kwargs = fake_client.completions.last_kwargs
    assert request_kwargs is not None
    assert request_kwargs["model"] == "qwen2.5-omni-7b"
    assert request_kwargs["stream"] is False
    messages = request_kwargs["messages"]
    assert isinstance(messages, list)
    user_content = messages[1]["content"]
    assert user_content[0]["type"] == "text"
    assert user_content[1]["type"] == "image_url"
    assert user_content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_review_fall_snapshot_accepts_fenced_json(monkeypatch, tmp_path) -> None:
    fake_client = _FakeMessageClient(
        """```json
{"judgement":"可能跌倒","confidence":"中等","reason":"人体姿态接近侧倒","recommended_action":"人工复核","visible_person_count":1}
```"""
    )
    settings = get_settings().model_copy(
        update={
            "dashscope_api_key_env": "test-key",
            "qwen_omni_model": "qwen2.5-omni-7b",
        }
    )
    service = VoiceService(settings)
    monkeypatch.setattr(service, "_build_compatible_client", lambda: fake_client)

    snapshot = tmp_path / "fall-review.png"
    snapshot.write_bytes(b"\x89PNG\r\n\x1a\nfake-png")
    result = service.review_fall_snapshot(snapshot)

    assert result["status"] == "ok"
    assert result["judgement"] == "possible_fall"
    assert result["confidence"] == "medium"
    assert result["recommended_action"] == "needs_human_review"
