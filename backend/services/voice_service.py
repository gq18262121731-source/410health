from __future__ import annotations

import base64
import logging
from typing import Literal

import httpx

from backend.config import Settings

logger = logging.getLogger(__name__)


class VoiceService:
    """Qwen/DashScope ASR + TTS voice service."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def _api_key(self) -> str:
        return self._settings.dashscope_api_key.strip()

    @property
    def _configured(self) -> bool:
        return bool(self._api_key)

    # ------------------------------------------------------------------ #
    # ASR  (audio -> text)                                                #
    # ------------------------------------------------------------------ #
    def transcribe(self, audio_bytes: bytes, *, fmt: str = "wav") -> dict[str, object]:
        """Call DashScope Paraformer ASR to transcribe audio bytes.

        Returns {"text": str, "provider": str, "ok": bool}.
        Falls back to a browser-side note when the API key is not set.
        """
        if not self._configured:
            return {
                "ok": False,
                "text": "",
                "provider": "none",
                "error": "DASHSCOPE_API_KEY/QWEN_API_KEY not configured",
            }

        model_id = self._settings.qwen_asr_model_id.strip().lower()
        try:
            import dashscope
            if model_id.startswith("qwen3-asr-flash-realtime"):
                from dashscope.audio.qwen_omni import OmniRealtimeConversation, OmniRealtimeCallback, AudioFormat, MultiModality
                from dashscope.audio.qwen_omni.omni_realtime import TranscriptionParams

                dashscope.api_key = self._api_key

                class _Cb(OmniRealtimeCallback):
                    def __init__(self) -> None:
                        self.text = ""
                        self.done = False
                        self.err = ""

                    def on_event(self, response: dict) -> None:
                        t = str((response or {}).get("type") or "")
                        if t == "conversation.item.input_audio_transcription.completed":
                            txt = str((response or {}).get("transcript") or (response or {}).get("text") or "")
                            self.text = txt.strip()
                            self.done = True
                        elif t == "error":
                            self.err = str((response or {}).get("error") or (response or {}).get("message") or "")
                            self.done = True

                cb = _Cb()
                conv = OmniRealtimeConversation(
                    model=model_id,
                    callback=cb,
                    url="wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
                    api_key=self._api_key,
                )
                conv.connect()
                conv.update_session(
                    output_modalities=[MultiModality.TEXT],
                    input_audio_format=AudioFormat.PCM_16000HZ_MONO_16BIT,
                    output_audio_format=AudioFormat.PCM_16000HZ_MONO_16BIT,
                    enable_input_audio_transcription=True,
                    enable_turn_detection=False,
                    transcription_params=TranscriptionParams(sample_rate=16000, input_audio_format="pcm"),
                )
                import base64 as _b64
                raw_bytes = audio_bytes
                if fmt == "wav":
                    try:
                        import io as _io, wave as _wave
                        _buf = _io.BytesIO(audio_bytes)
                        with _wave.open(_buf, "rb") as wf:
                            raw_bytes = wf.readframes(wf.getnframes())
                    except Exception:
                        raw_bytes = audio_bytes
                chunk_bytes = 48_000
                for offset in range(0, len(raw_bytes), chunk_bytes):
                    chunk = raw_bytes[offset : offset + chunk_bytes]
                    conv.append_audio(_b64.b64encode(chunk).decode("ascii"))
                conv.commit()

                import time
                deadline = time.time() + 15.0
                while time.time() < deadline and not cb.done:
                    time.sleep(0.05)
                try:
                    conv.end_session(timeout=5)
                except Exception:
                    pass
                conv.close()
                if cb.text:
                    return {"ok": True, "text": cb.text, "provider": f"dashscope/{model_id}"}
                return {"ok": False, "text": "", "provider": f"dashscope/{model_id}", "error": cb.err or "ASR realtime failed"}

            from dashscope.audio.asr import Recognition, RecognitionCallback
            dashscope.api_key = self._api_key
            import tempfile, os
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{fmt}")
            try:
                tmp.write(audio_bytes)
                tmp.close()
                recognizer = Recognition(model=model_id, callback=RecognitionCallback(), format=fmt, sample_rate=16000)
                result = recognizer.call(tmp.name)
                if getattr(result, "status_code", None) == 200:
                    sentences = result.get_sentence()
                    text = " ".join(s.get("text", "") for s in (sentences or []) if isinstance(s, dict)).strip()
                    return {"ok": True, "text": text, "provider": f"dashscope/{model_id}"}
                return {
                    "ok": False,
                    "text": "",
                    "provider": f"dashscope/{model_id}",
                    "error": getattr(result, "message", "ASR failed"),
                }
            finally:
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass
        except Exception as exc:
            logger.warning("ASR failed: %s", exc)
            return {"ok": False, "text": "", "provider": f"dashscope/{model_id}", "error": str(exc)}

    # ------------------------------------------------------------------ #
    # TTS  (text -> audio)                                                #
    # ------------------------------------------------------------------ #
    def synthesize(
        self,
        text: str,
        *,
        voice: str = "longxiaochun",
        speed: float = 1.0,
        fmt: Literal["mp3", "wav", "pcm"] = "mp3",
        workspace: str | None = None,
    ) -> dict[str, object]:
        """Call DashScope TTS.

        Returns {"audio_b64": str, "fmt": str, "provider": str, "ok": bool}.
        """
        if not self._configured:
            return {
                "ok": False,
                "audio_b64": "",
                "fmt": fmt,
                "provider": "none",
                "error": "DASHSCOPE_API_KEY/QWEN_API_KEY not configured",
            }

        if not text.strip():
            model_id = self._settings.qwen_tts_model_id.strip().lower()
            return {"ok": False, "audio_b64": "", "fmt": fmt, "provider": f"dashscope/{model_id}", "error": "empty text"}

        model_id = self._settings.qwen_tts_model_id.strip().lower()
        try:
            normalized_voice = (voice or "").strip()
            if model_id.startswith("cosyvoice"):
                if not normalized_voice or normalized_voice.lower() in {"default", "longxiaochun", "longwan", "longcheng", "longhua"}:
                    normalized_voice = self._settings.qwen_tts_voice_id
            else:
                if normalized_voice.lower() in {"longxiaochun", "longwan", "longcheng", "longhua"}:
                    normalized_voice = "Cherry"
                if not normalized_voice:
                    normalized_voice = "Cherry"

            language_type = "Chinese" if any("\u4e00" <= ch <= "\u9fff" for ch in text) else "English"

            if model_id.startswith("cosyvoice"):
                import dashscope
                from dashscope.audio.tts_v2 import SpeechSynthesizer
                from dashscope.audio.tts_v2.speech_synthesizer import AudioFormat
                from dashscope.audio.tts_v2.speech_synthesizer import ResultCallback

                dashscope.api_key = self._api_key
                dashscope.base_websocket_api_url = "wss://dashscope.aliyuncs.com/api-ws/v1/inference"
                if not normalized_voice:
                    normalized_voice = self._settings.qwen_tts_voice_id
                if fmt == "mp3":
                    audio_format = AudioFormat.MP3_24000HZ_MONO_256KBPS
                elif fmt == "wav":
                    audio_format = AudioFormat.WAV_24000HZ_MONO_16BIT
                else:
                    audio_format = AudioFormat.PCM_16000HZ_MONO_16BIT

                class _Cb(ResultCallback):
                    def __init__(self) -> None:
                        self.err = ""

                    def on_error(self, message) -> None:
                        self.err = str(message)

                cb = _Cb()
                synthesizer = SpeechSynthesizer(
                    model=model_id,
                    voice=normalized_voice,
                    format=audio_format,
                    speech_rate=speed,
                    callback=cb,
                    workspace=workspace,
                )
                try:
                    audio_bytes: bytes = synthesizer.call(text)
                except Exception as exc:
                    return {"ok": False, "audio_b64": "", "fmt": fmt, "provider": f"dashscope/{model_id}", "error": str(exc)}
                if not audio_bytes:
                    err = cb.err.strip()
                    if err:
                        return {"ok": False, "audio_b64": "", "fmt": fmt, "provider": f"dashscope/{model_id}", "error": err}
                    return {"ok": False, "audio_b64": "", "fmt": fmt, "provider": f"dashscope/{model_id}", "error": "CosyVoice returned empty audio (voice id may be invalid; create a voice via voice design/replication and pass its voice id)"}
                audio_b64 = base64.b64encode(audio_bytes).decode()
                return {
                    "ok": True,
                    "audio_b64": audio_b64,
                    "fmt": fmt,
                    "provider": f"dashscope/{model_id}",
                    "voice": normalized_voice,
                }

            import dashscope

            response = dashscope.MultiModalConversation.call(
                model=model_id,
                api_key=self._api_key,
                text=text,
                voice=normalized_voice,
                language_type=language_type,
                stream=False,
            )
            audio_url = ""
            if getattr(response, "output", None) is not None:
                try:
                    audio_url = str(((response.output["audio"] or {})["url"]) or "")
                except Exception:
                    audio_url = ""
            if not audio_url:
                return {"ok": False, "audio_b64": "", "fmt": fmt, "provider": f"dashscope/{model_id}", "error": "TTS returned empty audio url"}

            audio_bytes = httpx.get(audio_url, timeout=30).content
            actual_fmt = "wav" if ".wav" in audio_url.lower() else fmt
            audio_b64 = base64.b64encode(audio_bytes).decode()
            return {"ok": True, "audio_b64": audio_b64, "fmt": actual_fmt, "provider": f"dashscope/{model_id}", "voice": normalized_voice}
        except Exception as exc:
            logger.warning("TTS failed: %s", exc)
            return {"ok": False, "audio_b64": "", "fmt": fmt, "provider": f"dashscope/{model_id}", "error": str(exc)}
