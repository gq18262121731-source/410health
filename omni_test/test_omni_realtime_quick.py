"""
快速测试 - Qwen3.5-Omni-Plus 实时语音（DashScope SDK）
最小依赖，快速验证连接
"""

import os
import json
import time
from dotenv import load_dotenv

load_dotenv()

print("╔" + "="*60 + "╗")
print("║" + "Qwen Omni 快速连接测试".center(62) + "║")
print("╚" + "="*60 + "╝\n")

# 检查环境变量
api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")

print("1️⃣  环境检查")
print("-" * 60)

if api_key:
    print(f"✓ API Key: {api_key[:15]}***")
else:
    print("✗ API Key 未设置")
    exit(1)

print("\n2️⃣  检查 DashScope SDK")
print("-" * 60)

try:
    from dashscope.audio.qwen_omni import OmniRealtimeConversation, OmniRealtimeCallback
    import dashscope
    print("✓ dashscope 库已安装")
except ImportError:
    print("✗ dashscope 库未安装")
    print("\n📦 安装命令:")
    print("   pip install dashscope")
    exit(1)

print("\n3️⃣  测试连接")
print("-" * 60)

dashscope.api_key = api_key

class SimpleCallback(OmniRealtimeCallback):
    def on_open(self):
        print("✓ WebSocket 连接成功")
    
    def on_event(self, response: dict):
        event_type = response.get("type", "")
        if event_type == "response.audio_transcript.delta":
            print(f"🤖 {response.get('delta', '')}", end="", flush=True)
        elif event_type == "response.audio_transcript.done":
            print()
        elif event_type == "server.error":
            print(f"❌ {response.get('error', {}).get('message', 'Error')}")
    
    def on_close(self, code, msg):
        print(f"\n✗ 连接关闭 (code={code}, msg={msg})")

try:
    callback = SimpleCallback()
    conversation = OmniRealtimeConversation(
        model="qwen3.5-omni-plus-realtime",
        callback=callback,
        url="wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
    )
    
    print("正在连接...")
    conversation.connect()
    
    print("✓ 连接建立")
    
    # 配置会话
    print("\n4️⃣  发送文本测试")
    print("-" * 60)
    
    session_config = {
        "event_id": "event_test_001",
        "type": "session.update",
        "session": {
            "modalities": ["text", "audio"],
            "voice": "Cherry",
            "input_audio_format": "pcm",
            "output_audio_format": "pcm",
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.5,
                "silence_duration_ms": 800
            }
        }
    }
    
    conversation.send_event(json.dumps(session_config))
    time.sleep(0.5)
    
    # 发送文本
    text_event = {
        "event_id": "event_test_002",
        "type": "input_text_buffer.append",
        "text": "你好，请自我介绍一下"
    }
    conversation.send_event(json.dumps(text_event))
    
    commit_event = {
        "event_id": "event_test_003",
        "type": "input_text_buffer.commit"
    }
    conversation.send_event(json.dumps(commit_event))
    
    print("📤 已发送文本")
    print("⏳ 等待响应...")
    
    time.sleep(3)
    
    conversation.close()
    
    print("\n✅ 连接测试成功！")
    print("\n✨ 下一步:")
    print("   运行: python test_omni_realtime.py")
    print("   开始完整的语音交互测试")

except Exception as e:
    print(f"\n❌ 测试失败: {str(e)}")
    print("\n⚠️  可能的原因:")
    print("   1. DashScope SDK 版本过低（需要 >= 1.23.9）")
    print("   2. API Key 无效或过期")
    print("   3. 账户没有权限使用此模型")
    print("   4. 网络连接问题")
    exit(1)
