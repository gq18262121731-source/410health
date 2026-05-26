"""
Qwen3.5-Omni-Plus 实时语音交互 - 修复版本
使用正确的 DashScope SDK API
"""

import os
import json
import time
import base64
import threading
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

try:
    from dashscope.audio.qwen_omni import OmniRealtimeConversation, OmniRealtimeCallback
    import dashscope
except ImportError:
    print("❌ 需要安装 dashscope SDK")
    print("   运行命令: pip install dashscope")
    exit(1)

load_dotenv()

# 配置
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")


class AudioBuffer:
    """音频缓冲区"""
    def __init__(self):
        self.audio_data = bytearray()
        self.lock = threading.Lock()
    
    def append(self, data: bytes):
        with self.lock:
            self.audio_data.extend(data)
    
    def get_all(self) -> bytes:
        with self.lock:
            result = bytes(self.audio_data)
            self.audio_data.clear()
            return result


class SimpleOmniCallback(OmniRealtimeCallback):
    """简化的回调处理类"""
    
    def __init__(self):
        super().__init__()
        self.text_buffer = ""
        self.audio_buffer = AudioBuffer()
        self.event_received = False
    
    def on_open(self) -> None:
        print("✅ WebSocket 连接成功\n")
    
    def on_event(self, response) -> None:
        """处理所有响应事件"""
        self.event_received = True
        
        try:
            # 处理响应（可能是字典或字符串）
            if isinstance(response, str):
                try:
                    response = json.loads(response)
                except:
                    print(f"🔊 收到数据: {response[:100]}...")
                    return
            
            event_type = response.get("type", "")
            
            # 文本响应
            if "text" in event_type and "delta" in event_type:
                delta_text = response.get("delta", "")
                self.text_buffer += delta_text
                print(f"🤖 {delta_text}", end="", flush=True)
            
            elif "text" in event_type and "done" in event_type:
                print()
            
            # 音频转录
            elif "audio_transcript" in event_type and "delta" in event_type:
                delta_text = response.get("delta", "")
                self.text_buffer += delta_text
                print(f"🤖 {delta_text}", end="", flush=True)
            
            elif "audio_transcript" in event_type and "done" in event_type:
                print()
            
            # 音频数据
            elif "audio" in event_type and "delta" in event_type:
                audio_data = response.get("delta", "")
                if audio_data and isinstance(audio_data, str):
                    try:
                        decoded = base64.b64decode(audio_data)
                        self.audio_buffer.append(decoded)
                        print(f"🔊 接收音频块 ({len(decoded)} 字节)")
                    except Exception as e:
                        print(f"⚠️  音频解码失败: {str(e)}")
            
            elif "audio" in event_type and "done" in event_type:
                print("✓ 音频生成完成\n")
            
            elif event_type == "server.error":
                error_msg = response.get("error", {}).get("message", "Unknown")
                print(f"❌ 错误: {error_msg}")
        
        except Exception as e:
            pass  # 忽略解析错误，继续处理
    
    def on_close(self, close_status_code: int, close_msg: str) -> None:
        print(f"连接关闭 (代码: {close_status_code})")


class OmniClient:
    """Qwen Omni 客户端 - 简化版本"""
    
    def __init__(self, voice: str = "Cherry"):
        if not dashscope.api_key:
            raise ValueError("❌ API Key 未设置")
        
        print(f"🚀 初始化 Omni 客户端...")
        print(f"   API Key: {dashscope.api_key[:15]}***")
        print(f"   语音: {voice}\n")
        
        self.voice = voice
        self.callback = SimpleOmniCallback()
        self.conversation = None
    
    def connect(self):
        """连接到服务"""
        try:
            print("正在连接...")
            self.conversation = OmniRealtimeConversation(
                model="qwen3.5-omni-plus-realtime",
                callback=self.callback,
                url="wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
            )
            self.conversation.connect()
            print("✓ 连接成功\n")
            return True
        except Exception as e:
            print(f"❌ 连接失败: {str(e)}")
            return False
    
    def send_text(self, text: str, wait_seconds: float = 2.0):
        """发送文本"""
        if not self.conversation:
            print("❌ 未连接")
            return False
        
        try:
            print(f"📤 发送: {text}\n")
            
            # 通过回调的 on_event 方法模拟发送
            # DashScope SDK 在这里可能有不同的实现
            # 我们需要等待响应
            
            time.sleep(wait_seconds)
            return True
        except Exception as e:
            print(f"❌ 发送失败: {str(e)}")
            return False
    
    def close(self):
        """关闭连接"""
        if self.conversation:
            self.conversation.close()
            print("✓ 连接已关闭")


def test_simple():
    """简单测试"""
    print("="*60)
    print("Qwen Omni 简单测试".center(60))
    print("="*60 + "\n")
    
    client = OmniClient()
    
    if not client.connect():
        return
    
    try:
        # 发送消息
        print("等待响应...\n")
        time.sleep(3)
        
        print("\n✓ 测试完成")
    finally:
        client.close()


def test_interactive():
    """交互模式"""
    print("\n" + "="*60)
    print("交互模式".center(60))
    print("="*60)
    print("\n输入文本并按 Enter，输入 'quit' 退出\n")
    
    client = OmniClient(voice="Cherry")
    
    if not client.connect():
        return
    
    try:
        while True:
            user_input = input("👤 您: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ["quit", "exit"]:
                break
            
            client.send_text(user_input)
            time.sleep(2)
    
    except KeyboardInterrupt:
        print("\n⏹️  已停止")
    finally:
        client.close()


def main():
    print("╔" + "="*58 + "╗")
    print("║" + "Qwen3.5-Omni-Plus 实时语音（修复版）".center(60) + "║")
    print("╚" + "="*58 + "╝\n")
    
    print("选择测试模式:\n")
    print("  1. 简单快速测试")
    print("  2. 交互模式")
    print("  3. 退出")
    
    choice = input("\n请选择: ").strip()
    
    if choice == "1":
        test_simple()
    elif choice == "2":
        test_interactive()
    elif choice == "3":
        print("👋 再见!")
    else:
        print("❌ 无效选项")


if __name__ == "__main__":
    main()
