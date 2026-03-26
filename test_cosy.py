# test_cosy_fixed.py
import os
import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer
from dotenv import load_dotenv

load_dotenv()
# 不要把 key 写死在代码里
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
# dashscope.api_key = os.getenv("QWEN_API_KEY")

# 北京地域（中国内地）CosyVoice 的 WebSocket 接口
dashscope.base_websocket_api_url = "wss://dashscope.aliyuncs.com/api-ws/v1/inference"

def tts_to_file():
    # 方案 A：用 v2 + longxiaochun_v2
    # model = "cosyvoice-v2"
    # voice = "longxiaochun_v2"

    # 如果你想用 v3-flash，可以改成：
    model = "cosyvoice-v3-flash"
    voice = "longanyang"

    text = "你好，我是龙小春。这是通过新版 DashScope Python SDK 合成的语音。"

    try:
        synthesizer = SpeechSynthesizer(
            model=model,
            voice=voice,
            # 不传 format 时，官方文档说默认输出 22.05kHz 的 mp3
        )

        audio = synthesizer.call(text)

        with open("output.mp3", "wb") as f:
            f.write(audio)

        print("✅ 合成成功，已保存为 output.mp3")
        print("request_id:", synthesizer.get_last_request_id())
        print("首包延迟(ms):", synthesizer.get_first_package_delay())

    except Exception as e:
        print("❌ 合成失败：", e)

if __name__ == "__main__":
    tts_to_file()