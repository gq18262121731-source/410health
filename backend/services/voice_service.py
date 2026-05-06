from __future__ import annotations

import base64
import io
import json
import mimetypes
import re
import logging
import wave
from pathlib import Path
from typing import Any, Literal

from openai import OpenAI

from backend.config import Settings

logger = logging.getLogger(__name__)


class VoiceService:
    """DashScope voice service for ASR, Omni, and TTS flows."""

    _OMNI_AUDIO_VOICE_CANDIDATES = ("Chelsie", "Ethan")

    def __init__(self, settings: Settings, device_service: Any | None = None) -> None:
        self._settings = settings
        self._device_service = device_service

    @property
    def _api_key(self) -> str:
        return self._settings.dashscope_api_key.strip()

    @property
    def _configured(self) -> bool:
        return bool(self._api_key)

    @property
    def _compatible_base_url(self) -> str:
        return self._settings.qwen_api_base.strip() or "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def _build_compatible_client(self) -> OpenAI:
        return OpenAI(
            api_key=self._api_key,
            base_url=self._compatible_base_url,
        )

    @staticmethod
    def _normalize_audio_format(fmt: str) -> str:
        normalized = (fmt or "wav").strip().lower()
        if normalized in {"wav", "wave"}:
            return "wav"
        if normalized in {"mp3", "mpeg"}:
            return "mp3"
        if normalized in {"m4a", "aac", "mp4"}:
            return "aac"
        if normalized in {"amr", "3gp", "3gpp"}:
            return normalized
        return "wav"

    @staticmethod
    def _extract_text_delta(content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                    continue
                if not isinstance(item, dict):
                    continue
                text_value = item.get("text")
                if isinstance(text_value, str):
                    parts.append(text_value)
                    continue
                nested_text = item.get("content")
                if isinstance(nested_text, str):
                    parts.append(nested_text)
            return "".join(parts)
        return str(content)

    @staticmethod
    def _extract_audio_delta(audio: Any) -> str:
        if audio is None:
            return ""
        if isinstance(audio, dict):
            return str(audio.get("data") or "")
        data = getattr(audio, "data", None)
        if isinstance(data, str):
            return data
        if hasattr(audio, "get"):
            try:
                return str(audio.get("data") or "")
            except Exception:
                return ""
        return ""

    @staticmethod
    def _pcm_b64_to_wav_b64(audio_b64: str, *, sample_rate: int = 24000) -> str:
        if not audio_b64:
            return ""

        pcm_bytes = base64.b64decode(audio_b64)
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_bytes)
        return base64.b64encode(buffer.getvalue()).decode("ascii")

    @staticmethod
    def _extract_message_text(content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                    continue
                if not isinstance(item, dict):
                    continue
                text_value = item.get("text")
                if isinstance(text_value, str):
                    parts.append(text_value)
                    continue
                nested_text = item.get("content")
                if isinstance(nested_text, str):
                    parts.append(nested_text)
            return "".join(parts)
        return str(content)

    @staticmethod
    def _strip_code_fence(raw: str) -> str:
        text = (raw or "").strip()
        if not text.startswith("```"):
            return text
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return text.strip()

    @classmethod
    def _extract_json_payload(cls, raw: str) -> dict[str, object] | None:
        text = cls._strip_code_fence(raw)
        if not text:
            return None
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        candidate = text[start : end + 1]
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _normalize_review_value(value: object, mapping: dict[str, str], *, default: str) -> str:
        normalized = str(value or "").strip().lower()
        if not normalized:
            return default
        return mapping.get(normalized, default)

    @classmethod
    def _normalize_fall_review_payload(
        cls,
        payload: dict[str, object],
        *,
        raw_text: str,
        model_id: str,
    ) -> dict[str, object]:
        judgement_map = {
            "fall": "fall",
            "confirmed_fall": "fall",
            "real_fall": "fall",
            "跌倒": "fall",
            "确认跌倒": "fall",
            "possible_fall": "possible_fall",
            "possible": "possible_fall",
            "suspected_fall": "possible_fall",
            "疑似跌倒": "possible_fall",
            "可能跌倒": "possible_fall",
            "no_fall": "no_fall",
            "non_fall": "no_fall",
            "not_fall": "no_fall",
            "false_alarm": "no_fall",
            "不是跌倒": "no_fall",
            "非跌倒": "no_fall",
            "uncertain": "uncertain",
            "unknown": "uncertain",
            "inconclusive": "uncertain",
            "无法判断": "uncertain",
            "不确定": "uncertain",
        }
        confidence_map = {
            "high": "high",
            "medium": "medium",
            "low": "low",
            "高": "high",
            "中": "medium",
            "中等": "medium",
            "低": "low",
        }
        action_map = {
            "keep_alarm": "keep_alarm",
            "keep": "keep_alarm",
            "保留告警": "keep_alarm",
            "维持告警": "keep_alarm",
            "downgrade": "downgrade",
            "no_fall": "downgrade",
            "cancel_alarm": "downgrade",
            "cancel": "downgrade",
            "false_alarm": "downgrade",
            "dismiss": "downgrade",
            "suppress": "downgrade",
            "降级": "downgrade",
            "取消告警": "downgrade",
            "needs_human_review": "needs_human_review",
            "review": "needs_human_review",
            "人工复核": "needs_human_review",
        }

        judgement = cls._normalize_review_value(
            payload.get("judgement"),
            judgement_map,
            default="uncertain",
        )
        confidence = cls._normalize_review_value(
            payload.get("confidence"),
            confidence_map,
            default="low",
        )
        recommended_action = cls._normalize_review_value(
            payload.get("recommended_action"),
            action_map,
            default="needs_human_review",
        )

        if judgement == "no_fall" and confidence in {"high", "medium"}:
            recommended_action = "downgrade"
        elif judgement == "fall":
            recommended_action = "keep_alarm"

        risk_cues = payload.get("risk_cues")
        false_positive_cues = payload.get("false_positive_cues")
        return {
            "status": "ok",
            "provider": "dashscope-compatible",
            "model": model_id,
            "judgement": judgement,
            "confidence": confidence,
            "recommended_action": recommended_action,
            "reason": str(payload.get("reason") or "").strip(),
            "visible_person_count": int(payload.get("visible_person_count") or 0),
            "risk_cues": list(risk_cues) if isinstance(risk_cues, list) else [],
            "false_positive_cues": list(false_positive_cues) if isinstance(false_positive_cues, list) else [],
            "raw_text": raw_text,
        }

    @staticmethod
    def _build_fall_review_prompt(event: dict[str, object] | None) -> str:
        event = event or {}
        injury = event.get("injury") if isinstance(event.get("injury"), dict) else {}
        fall_score = event.get("fall_score")
        state = event.get("state")
        severity = event.get("severity")
        injury_level = injury.get("level") if isinstance(injury, dict) else None
        down_seconds = injury.get("down_seconds") if isinstance(injury, dict) else None
        context_lines = [
            "请作为养老监护系统的第二道跌倒复核器，只根据这张抓拍图判断是否应该维持跌倒告警。",
            "重点识别误报场景：弯腰捡东西、快速坐下、躺床、蹲下、画面边缘半身、遮挡、非人体目标、监控畸变。",
            "如果单张图片证据不足，不要强行判定为真实跌倒，应返回 uncertain 或 no_fall。",
            "下面是第一道检测的参考信息，你可以参考，但不要盲从：",
            f"- fall_score: {fall_score}",
            f"- state: {state}",
            f"- severity: {severity}",
            f"- injury_level: {injury_level}",
            f"- down_seconds: {down_seconds}",
            "请严格只返回 JSON，不要输出解释文字，不要使用 Markdown 代码块。",
            (
                'JSON 格式：'
                '{"judgement":"fall|possible_fall|no_fall|uncertain",'
                '"confidence":"high|medium|low",'
                '"reason":"一句简短理由",'
                '"recommended_action":"keep_alarm|downgrade|needs_human_review",'
                '"visible_person_count":0,'
                '"risk_cues":["最多3个短词"],'
                '"false_positive_cues":["最多3个短词"]}'
            ),
        ]
        return "\n".join(context_lines)

    def _build_health_context(self, device_mac: str | None) -> str:
        if not device_mac or self._device_service is None:
            return ""

        try:
            from backend.dependencies import get_display_latest_sample

            normalized_mac = device_mac.strip().upper()
            device = None
            if hasattr(self._device_service, "get_device"):
                device = self._device_service.get_device(normalized_mac)
            ingest_mode = getattr(device, "ingest_mode", None)
            sample = get_display_latest_sample(normalized_mac, ingest_mode)
            if sample is None:
                return ""

            blood_pressure = sample.blood_pressure or "--"
            steps = sample.steps if sample.steps is not None else "--"
            score = sample.health_score if sample.health_score is not None else "--"
            return (
                "\n当前可用的健康监测数据："
                f"心率 {sample.heart_rate} 次/分，"
                f"血氧 {sample.blood_oxygen}%，"
                f"体温 {sample.temperature:.1f} 摄氏度，"
                f"血压 {blood_pressure}，"
                f"步数 {steps}，"
                f"健康分 {score}。"
            )
        except Exception as exc:
            logger.debug("Failed to build health context for omni chat: %s", exc)
            return ""

    def review_fall_snapshot(
        self,
        snapshot_path: str | Path,
        *,
        event: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Use the configured Qwen omni model to review a fall snapshot."""
        if not self._configured:
            return {"status": "not_configured", "provider": "dashscope-compatible"}

        path = Path(snapshot_path).expanduser().resolve()
        if not path.is_file():
            return {"status": "snapshot_missing", "snapshot_path": str(path)}

        mime_type, _encoding = mimetypes.guess_type(path.name)
        mime_type = mime_type or "image/jpeg"
        image_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        model_id = self._settings.qwen_omni_model_id
        prompt = self._build_fall_review_prompt(event)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a safety-critical fall alarm reviewer for an elder-care monitoring system. "
                    "Reply in Simplified Chinese JSON only. "
                    "Base the decision on the visible image evidence first, and use the provided detector fields only as weak reference. "
                    "Do not invent motion that is not visible in the image."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_b64}",
                        },
                    },
                ],
            },
        ]

        try:
            client = self._build_compatible_client()
            response = client.chat.completions.create(
                model=model_id,
                messages=messages,
                stream=False,
                temperature=0.1,
                max_tokens=280,
            )
        except Exception as exc:
            logger.warning("Fall snapshot review failed: %s", exc)
            return {
                "status": "error",
                "provider": "dashscope-compatible",
                "model": model_id,
                "error": str(exc),
            }

        choices = getattr(response, "choices", None) or []
        if not choices:
            return {
                "status": "empty",
                "provider": "dashscope-compatible",
                "model": model_id,
            }

        message = getattr(choices[0], "message", None)
        raw_text = self._extract_message_text(getattr(message, "content", None)).strip()
        if not raw_text:
            return {
                "status": "empty",
                "provider": "dashscope-compatible",
                "model": model_id,
            }

        payload = self._extract_json_payload(raw_text)
        if payload is None:
            logger.warning("Fall snapshot review returned non-JSON payload: %s", raw_text[-800:])
            return {
                "status": "invalid_json",
                "provider": "dashscope-compatible",
                "model": model_id,
                "raw_text": raw_text[-800:],
            }

        return self._normalize_fall_review_payload(
            payload,
            raw_text=raw_text,
            model_id=model_id,
        )

    @staticmethod
    def _build_elder_voice_style_prompt(*, has_health_context: bool) -> str:
        prompt = (
            "你是面向老人的健康说明助手、AI健康守护助手，当前正处于智慧康养项目的演示体验环节。\n"
            "无论用户说什么，必须优先理解用户的语音，然后基于提供的健康监测数据进行自然、口语化的语音反馈。\n"
            "你的任务是用简单、温和、充满关怀的拟人化口语和体验者（代入老人角色）对话，展现系统的智能化与温度。\n\n"
            "约束要求：\n"
            "1. 用简单词语和短句，不使用复杂医学术语。一切回答必须使用简体中文。\n"
            "2. 语气温和、安抚、好理解，不制造恐慌。必须控制在2到3个短句以内，适合直接转换为语音念给老人听。\n"
            "3. 优先告诉老人现在身体大概稳不稳、指标的情况。一次只强调最关键的结论，如果指标异常需要复测或求助时，直接给出最简单的下一步动作（如：帮您呼叫家属）。\n"
            "4. 如果用户询问当天状态，使用诸如“整体指标看起来很平稳”、“血压确实有点小波动，别担心”等高视角的口语描述，不要生硬地朗读数值。\n"
            "5. 绝对不要虚构和捏造任何健康数值、诊断、症状或未发生的事情。\n"
        )
        if has_health_context:
            prompt += (
                "6. 请将下方的监测数据自然地融入长者的关怀回复中。\n"
            )
        else:
            prompt += (
                "6. 目前未能获取到有效的最新体征数据，请坦诚告知，并用温和安抚的口吻回应。\n"
            )
        return prompt

    def transcribe(self, audio_bytes: bytes, *, fmt: str = "wav") -> dict[str, object]:
        """Call DashScope Paraformer ASR to transcribe audio bytes."""
        if not self._configured:
            return {"ok": False, "text": "", "error": "DASHSCOPE_API_KEY not configured"}

        model_id = self._settings.qwen_asr_model_id.strip().lower()
        try:
            import dashscope
            import os
            import tempfile

            dashscope.api_key = self._api_key

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{fmt}")
            try:
                tmp.write(audio_bytes)
                tmp.close()
                from dashscope.audio.asr import Recognition, RecognitionCallback

                recognizer = Recognition(
                    model=model_id,
                    callback=RecognitionCallback(),
                    format=fmt,
                    sample_rate=16000,
                )
                result = recognizer.call(tmp.name)
                if getattr(result, "status_code", None) == 200:
                    sentences = result.get_sentence()
                    text = " ".join(
                        sentence.get("text", "")
                        for sentence in (sentences or [])
                        if isinstance(sentence, dict)
                    ).strip()
                    return {"ok": True, "text": text, "provider": f"dashscope/{model_id}"}
                return {"ok": False, "text": "", "error": getattr(result, "message", "ASR failed")}
            finally:
                if os.path.exists(tmp.name):
                    os.unlink(tmp.name)
        except Exception as exc:
            logger.warning("ASR failed: %s", exc)
            return {"ok": False, "text": "", "error": str(exc)}

    def omni_chat(
        self,
        audio_bytes: bytes,
        *,
        prompt: str = "请先理解我的语音，再结合已有的健康监测数据，用自然、温和、好懂的话给出简短回答。",
        fmt: str = "wav",
        device_mac: str | None = None,
        role: str = "elder",
    ) -> dict[str, object]:
        """Call the configured DashScope omni model through the OpenAI-compatible API."""
        if not self._configured:
            return {"ok": False, "text": "", "error": "DASHSCOPE_API_KEY not configured"}

        model_id = self._settings.qwen_omni_model_id
        input_format = self._normalize_audio_format(fmt)
        normalized_role = (role or "elder").strip().lower()
        health_context = self._build_health_context(device_mac)
        prompt_text = (prompt or "").strip() or "请先理解我的语音，再结合已有的健康监测数据，用自然、温和、好懂的话给出简短回答。"
        system_prompt = (
            self._build_elder_voice_style_prompt(has_health_context=bool(health_context))
            if normalized_role == "elder"
            else (
                "You are a health monitoring assistant. "
                "Reply in Simplified Chinese. "
                "Base your answer only on the provided data and context. "
                "Be clear, concise, and easy to understand. "
                "Do not invent unavailable facts."
            )
        )
        if health_context:
            system_prompt += health_context

        if normalized_role == "elder":
            # Force Qwen-Omni to obey the persona by injecting it directly alongside the audio
            prompt_text = f"【系统指令与约束（必须严格遵守）】\n{system_prompt}\n\n【用户附加要求】\n{prompt_text}"

        audio_input_b64 = base64.b64encode(audio_bytes).decode("ascii")
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": f"data:;base64,{audio_input_b64}",
                            "format": input_format,
                        },
                    },
                    {"type": "text", "text": prompt_text},
                ],
            },
        ]

        try:
            client = self._build_compatible_client()
            request_kwargs: dict[str, object] = {
                "model": model_id,
                "messages": messages,
                "modalities": ["text", "audio"] if normalized_role == "elder" else ["text"],
                "stream": True,
                "stream_options": {"include_usage": True},
            }
            selected_voice: str | None = None
            if normalized_role == "elder":
                completion = None
                last_voice_error: Exception | None = None
                for voice_name in self._OMNI_AUDIO_VOICE_CANDIDATES:
                    try:
                        request_kwargs["audio"] = {
                            "voice": voice_name,
                            "format": "wav",
                        }
                        completion = client.chat.completions.create(**request_kwargs)
                        selected_voice = voice_name
                        break
                    except Exception as exc:
                        message = str(exc).lower()
                        if "parameters.audio.voice" not in message:
                            raise
                        last_voice_error = exc
                if completion is None:
                    if last_voice_error is not None:
                        raise last_voice_error
                    raise RuntimeError("Failed to select a supported omni audio voice")
            else:
                completion = client.chat.completions.create(**request_kwargs)

            text_parts: list[str] = []
            audio_pcm_parts: list[str] = []

            for chunk in completion:
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue

                delta = getattr(choices[0], "delta", None)
                if delta is None:
                    continue

                text_delta = self._extract_text_delta(getattr(delta, "content", None))
                if text_delta:
                    text_parts.append(text_delta)

                audio_delta = self._extract_audio_delta(getattr(delta, "audio", None))
                if audio_delta:
                    audio_pcm_parts.append(audio_delta)

            answer_text = "".join(text_parts).strip()
            audio_pcm_b64 = "".join(audio_pcm_parts)
            audio_wav_b64 = self._pcm_b64_to_wav_b64(audio_pcm_b64) if audio_pcm_b64 else ""

            return {
                "ok": True,
                "text": answer_text,
                "answer": answer_text,
                "audio_b64": audio_wav_b64,
                "audio_pcm_b64": audio_pcm_b64,
                "audio_url": f"data:audio/wav;base64,{audio_wav_b64}" if audio_wav_b64 else "",
                "audio_sample_rate": 24000 if audio_wav_b64 else None,
                "fmt": "wav" if audio_wav_b64 else None,
                "voice": selected_voice if audio_wav_b64 else None,
                "provider": f"dashscope-compatible/{model_id}",
                "model": model_id,
            }
        except Exception as exc:
            logger.error("Omni chat failed: %s", exc)
            message = str(exc)
            lower_message = message.lower()
            if "access_denied" in lower_message or "access denied" in lower_message:
                message = f"当前 DashScope 账号尚未开通 {model_id} 调用权限，请先在阿里云百炼控制台开通模型后再试。"
            return {"ok": False, "text": "", "error": message}

    def synthesize(
        self,
        text: str,
        *,
        voice: str = "longxiaochun",
        speed: float = 1.0,
        fmt: Literal["mp3", "wav", "pcm"] = "mp3",
        workspace: str | None = None,
    ) -> dict[str, object]:
        """Call DashScope TTS and return audio data."""
        if not self._configured:
            return {"ok": False, "audio_b64": "", "error": "DASHSCOPE_API_KEY not configured"}

        if not text.strip():
            return {"ok": False, "audio_b64": "", "error": "empty text"}

        model_id = self._settings.qwen_tts_model_id.strip().lower()
        try:
            import dashscope

            dashscope.api_key = self._api_key

            if "qwen-tts" in model_id or "qwen3-tts" in model_id:
                voice_map = {
                    "longxiaochun": "Cherry",
                    "longwan": "Cherry",
                    "longcheng": "Genny",
                    "longhua": "Genny",
                    "longyingtian": "Genny",
                }
                target_voice = voice_map.get(voice.lower(), "Cherry")

                response = dashscope.MultiModalConversation.call(
                    model=model_id,
                    text=text,
                    voice=target_voice,
                    language_type="Chinese",
                    parameters={
                        "format": fmt,
                        "sample_rate": 16000,
                    },
                    stream=False,
                )

                if response.status_code == 200:
                    output = getattr(response, "output", None)
                    if output and hasattr(output, "audio") and hasattr(output.audio, "data"):
                        audio_b64 = output.audio.data
                        if not audio_b64:
                            return {
                                "ok": False,
                                "audio_b64": "",
                                "error": "Model returned empty audio data",
                            }
                        return {
                            "ok": True,
                            "audio_b64": audio_b64,
                            "fmt": fmt,
                            "provider": f"dashscope/{model_id}",
                            "voice": target_voice,
                        }
                    return {
                        "ok": False,
                        "audio_b64": "",
                        "error": "Invalid response structure from Qwen-TTS",
                    }

                return {"ok": False, "audio_b64": "", "error": response.message}

            if model_id.startswith("cosyvoice"):
                from dashscope.audio.tts_v2 import AudioFormat, ResultCallback, SpeechSynthesizer

                voice_id = (voice or "").strip() or "longwan"
                if voice_id not in ["longwan", "longxiaochun", "longcheng", "longhua", "longyingtian"]:
                    voice_id = "longwan"

                if fmt == "mp3":
                    audio_format = AudioFormat.MP3_24000HZ_MONO_256KBPS
                elif fmt == "wav":
                    audio_format = AudioFormat.WAV_24000HZ_MONO_16BIT
                else:
                    audio_format = AudioFormat.PCM_16000HZ_MONO_16BIT

                class _Callback(ResultCallback):
                    def __init__(self) -> None:
                        self.err = ""

                    def on_error(self, message) -> None:
                        self.err = str(message)

                callback = _Callback()
                synthesizer = SpeechSynthesizer(
                    model=model_id,
                    voice=voice_id,
                    format=audio_format,
                    speech_rate=speed,
                    callback=callback,
                )
                audio_bytes = synthesizer.call(text)
                if not audio_bytes:
                    return {"ok": False, "audio_b64": "", "error": callback.err or "CosyVoice empty audio"}

                audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
                return {
                    "ok": True,
                    "audio_b64": audio_b64,
                    "fmt": fmt,
                    "provider": f"dashscope/{model_id}",
                    "voice": voice_id,
                }

            response = dashscope.SpeechSynthesizer.call(
                model=model_id,
                text=text,
                voice=voice,
                format=fmt,
                sample_rate=16000,
            )
            if response.get_audio_data():
                audio_b64 = base64.b64encode(response.get_audio_data()).decode("ascii")
                return {"ok": True, "audio_b64": audio_b64, "fmt": fmt, "provider": f"dashscope/{model_id}"}

            return {"ok": False, "audio_b64": "", "error": "TTS failed to generate audio"}
        except Exception as exc:
            logger.error("TTS failed: %s", exc)
            return {"ok": False, "audio_b64": "", "error": str(exc)}
