"""
Qwen3.5-Omni-Plus 实时语音交互 - 使用 DashScope SDK
支持实时双向语音交互（语音输入 → 语音输出）
"""

import os
import json
import time
import base64
import threading
import queue
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

try:
    from dashscope.audio.qwen_omni import OmniRealtimeConversation, OmniRealtimeCallback
    import dashscope
except ImportError:
    print("❌ 需要安装 dashscope-python SDK")
    print("   运行命令: pip install dashscope")
    exit(1)

load_dotenv()

# 配置
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")

class AudioBuffer:
    """音频缓冲区，用于存储接收到的音频数据"""
    def __init__(self):
        self.audio_data = bytearray()
        self.lock = threading.Lock()
    
    def append(self, data: bytes):
        """添加音频数据"""
        with self.lock:
            self.audio_data.extend(data)
    
    def get_all(self) -> bytes:
        """获取所有音频数据"""
        with self.lock:
            result = bytes(self.audio_data)
            self.audio_data.clear()
            return result


class QwenOmniRealtimeCallback(OmniRealtimeCallback):
    """Qwen Omni 实时对话回调处理器"""
    
    def __init__(self, audio_buffer: AudioBuffer = None):
        super().__init__()
        self.audio_buffer = audio_buffer or AudioBuffer()
        self.text_buffer = ""
        self.is_connected = False
        self.responses = []
        self.lock = threading.Lock()
        self.input_method = None  # 'text' 或 'audio'
    
    def on_open(self) -> None:
        """连接开启时调用"""
        self.is_connected = True
        print("✅ WebSocket 连接成功")
        print("💬 准备进行实时对话...\n")
    
    def on_event(self, response) -> None:
        """接收服务器事件"""
        try:
            # response 可能是字符串或字典
            if isinstance(response, str):
                response = json.loads(response)
            
            event_type = response.get("type", "unknown")
            
            # 处理文本响应
            if event_type == "response.text.delta":
                text = response.get("delta", "")
                self.text_buffer += text
                print(f"🤖 {text}", end="", flush=True)
            
            elif event_type == "response.text.done":
                print()  # 换行
                with self.lock:
                    self.responses.append({
                        "type": "text",
                        "content": self.text_buffer
                    })
                self.text_buffer = ""
            
            # 处理音频转录响应
            elif event_type == "response.audio_transcript.delta":
                text = response.get("delta", "")
                self.text_buffer += text
                print(f"🤖 {text}", end="", flush=True)
            
            elif event_type == "response.audio_transcript.done":
                print()  # 换行
                with self.lock:
                    self.responses.append({
                        "type": "text",
                        "content": self.text_buffer
                    })
                self.text_buffer = ""
            
            # 处理音频响应
            elif event_type == "response.audio.delta":
                audio_data = response.get("delta", "")
                if audio_data:
                    try:
                        # Base64 解码
                        audio_bytes = base64.b64decode(audio_data)
                        self.audio_buffer.append(audio_bytes)
                        print(f"🔊 接收音频数据 ({len(audio_bytes)} 字节)", flush=True)
                    except Exception as e:
                        print(f"⚠️  音频解码失败: {str(e)}")
            
            elif event_type == "response.audio.done":
                print("🎵 音频响应完成")
                with self.lock:
                    self.responses.append({
                        "type": "audio",
                        "received": True
                    })
            
            # 处理错误
            elif event_type == "server.error":
                error = response.get("error", {})
                print(f"❌ 服务器错误: {error.get('message', 'Unknown error')}")
            
            else:
                # 其他事件类型
                if event_type not in ["session.created", "response.done", "session.updated"]:
                    pass  # 静默处理其他事件
        
        except Exception as e:
            print(f"⚠️  处理事件失败: {str(e)}")
    
    def on_close(self, close_status_code: int, close_msg: str) -> None:
        """连接关闭时调用"""
        self.is_connected = False
        print(f"\n❌ 连接关闭 (代码: {close_status_code}, 信息: {close_msg})")


class QwenOmniRealtimeClient:
    """Qwen Omni 实时对话客户端"""
    
    def __init__(self, voice: str = "Cherry"):
        """
        初始化客户端
        
        Args:
            voice: 输出语音角色 ("Cherry", "Daisy", "Alfie" 等)
        """
        if not dashscope.api_key:
            raise ValueError("❌ DASHSCOPE_API_KEY 或 QWEN_API_KEY 环境变量未设置")
        
        print("🚀 初始化 Qwen Omni 实时对话客户端...")
        print(f"   API Key: {dashscope.api_key[:15]}***")
        print(f"   模型: qwen3.5-omni-plus-realtime")
        print(f"   语音: {voice}\n")
        
        self.voice = voice
        self.audio_buffer = AudioBuffer()
        self.callback = QwenOmniRealtimeCallback(self.audio_buffer)
        self.conversation = None
    
    def connect(self):
        """连接到服务器"""
        try:
            self.conversation = OmniRealtimeConversation(
                model="qwen3.5-omni-plus-realtime",
                callback=self.callback,
                url="wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
            )
            self.conversation.connect()
            print("✓ 连接建立\n")
            return True
        except Exception as e:
            print(f"❌ 连接失败: {str(e)}")
            return False
    
    def configure_session(self, instructions: str = None, modalities: list = None):
        """配置会话参数"""
        if not self.conversation:
            print("❌ 未连接到服务器")
            return False
        
        try:
            # 默认模式：文本 + 音频
            if modalities is None:
                modalities = ["text", "audio"]
            
            session_config = {
                "event_id": f"event_{int(time.time() * 1000)}",
                "type": "session.update",
                "session": {
                    "modalities": modalities,
                    "voice": self.voice,
                    "input_audio_format": "pcm",
                    "output_audio_format": "pcm",
                }
            }
            
            # 添加系统指令
            if instructions:
                session_config["session"]["instructions"] = instructions
            
            # 启用服务端 VAD（语音活动检测）
            session_config["session"]["turn_detection"] = {
                "type": "server_vad",
                "threshold": 0.5,
                "silence_duration_ms": 800
            }
            
            self.conversation.send_event(json.dumps(session_config))
            print("✓ 会话配置已发送\n")
            return True
        
        except Exception as e:
            print(f"❌ 配置失败: {str(e)}")
            return False
    
    def send_text_input(self, text: str):
        """发送文本输入"""
        if not self.conversation:
            print("❌ 未连接到服务器")
            return False
        
        try:
            request = {
                "event_id": f"event_{int(time.time() * 1000)}",
                "type": "input_text_buffer.append",
                "text": text
            }
            
            self.conversation.send_event(json.dumps(request))
            
            # 提交
            commit_event = {
                "event_id": f"event_{int(time.time() * 1000)}",
                "type": "input_text_buffer.commit"
            }
            self.conversation.send_event(json.dumps(commit_event))
            
            print(f"📤 发送文本: {text}\n")
            return True
        
        except Exception as e:
            print(f"❌ 发送失败: {str(e)}")
            return False
    
    def send_audio_input(self, audio_data: bytes, is_final: bool = True):
        """
        发送音频输入
        
        Args:
            audio_data: 音频数据（PCM 格式）
            is_final: 是否为最后一段
        """
        if not self.conversation:
            print("❌ 未连接到服务器")
            return False
        
        try:
            # Base64 编码
            audio_base64 = base64.b64encode(audio_data).decode("utf-8")
            
            request = {
                "event_id": f"event_{int(time.time() * 1000)}",
                "type": "input_audio_buffer.append",
                "audio": audio_base64
            }
            
            self.conversation.send_event(json.dumps(request))
            
            # 如果是最后一段，提交缓冲区
            if is_final:
                commit_event = {
                    "event_id": f"event_{int(time.time() * 1000)}",
                    "type": "input_audio_buffer.commit"
                }
                self.conversation.send_event(json.dumps(commit_event))
                print(f"📤 音频已提交 ({len(audio_data)} 字节)\n")
            
            return True
        
        except Exception as e:
            print(f"❌ 发送失败: {str(e)}")
            return False
    
    def save_output_audio(self, filename: str = None) -> str:
        """保存输出音频到文件"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"qwen_output_{timestamp}.wav"
        
        audio_data = self.audio_buffer.get_all()
        
        if not audio_data:
            print("⚠️  没有音频数据可保存")
            return None
        
        try:
            # 写入 PCM 数据（简化版，仅用于测试）
            with open(filename, "wb") as f:
                f.write(audio_data)
            
            print(f"✓ 音频已保存: {filename} ({len(audio_data)} 字节)")
            return filename
        
        except Exception as e:
            print(f"❌ 保存失败: {str(e)}")
            return None
    
    def close(self):
        """关闭连接"""
        if self.conversation:
            self.conversation.close()
            print("✓ 连接已关闭")


def test_text_to_speech():
    """测试：文本 → 语音"""
    print("\n" + "="*70)
    print("测试 1: 文本输入 → 语音输出".center(70))
    print("="*70)
    
    client = QwenOmniRealtimeClient(voice="Cherry")
    
    if not client.connect():
        return False
    
    try:
        # 配置会话
        instructions = "你是一个友好的旅游咨询顾问。请用简洁、热情的语气回答用户的旅游相关问题。"
        client.configure_session(
            instructions=instructions,
            modalities=["text", "audio"]
        )
        
        # 发送文本问题
        time.sleep(1)
        client.send_text_input("请介绍一下黄山旅游的最佳季节和注意事项。")
        
        # 等待响应
        print("⏳ 等待服务器响应...")
        time.sleep(5)
        
        # 保存输出音频
        output_file = client.save_output_audio("test_output_1.wav")
        
        return True
    
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        return False
    
    finally:
        client.close()


def test_audio_to_speech(audio_file: str):
    """测试：语音 → 语音"""
    print("\n" + "="*70)
    print("测试 2: 语音输入 → 语音输出".center(70))
    print("="*70)
    
    if not os.path.exists(audio_file):
        print(f"❌ 音频文件不存在: {audio_file}")
        return False
    
    client = QwenOmniRealtimeClient(voice="Daisy")
    
    if not client.connect():
        return False
    
    try:
        # 配置会话
        instructions = "你是一个热心的健康咨询师。请根据用户的语音问题，提供专业的健康建议。"
        client.configure_session(
            instructions=instructions,
            modalities=["text", "audio"]
        )
        
        # 读取和发送音频
        print(f"📂 读取音频文件: {audio_file}")
        with open(audio_file, "rb") as f:
            audio_data = f.read()
        
        time.sleep(1)
        print(f"📤 发送音频（{len(audio_data)} 字节）...")
        client.send_audio_input(audio_data, is_final=True)
        
        # 等待响应
        print("⏳ 等待服务器响应...")
        time.sleep(5)
        
        # 保存输出音频
        output_file = client.save_output_audio("test_output_2.wav")
        
        return True
    
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        return False
    
    finally:
        client.close()


def interactive_mode():
    """交互模式：实时对话"""
    print("\n" + "="*70)
    print("交互模式: 实时对话".center(70))
    print("="*70)
    print("💡 提示:")
    print("   - 输入文本并按 Enter 发送")
    print("   - 输入 'exit' 或 'quit' 退出")
    print("   - 输入 'save' 保存输出音频\n")
    
    client = QwenOmniRealtimeClient(voice="Cherry")
    
    if not client.connect():
        return False
    
    try:
        # 配置会话
        instructions = "你是一个有帮助的 AI 助手。请用友好和专业的语气回答用户的问题。"
        client.configure_session(
            instructions=instructions,
            modalities=["text", "audio"]
        )
        
        time.sleep(1)
        
        while True:
            try:
                user_input = input("👤 您: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ["exit", "quit"]:
                    print("\n👋 再见!")
                    break
                
                if user_input.lower() == "save":
                    client.save_output_audio()
                    continue
                
                client.send_text_input(user_input)
                
                # 等待响应
                time.sleep(3)
            
            except KeyboardInterrupt:
                print("\n\n⏹️  已停止")
                break
        
        return True
    
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        return False
    
    finally:
        client.close()


def main():
    """主函数"""
    print("╔" + "="*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "Qwen3.5-Omni-Plus 实时语音交互测试 (WebSocket)".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "="*68 + "╝\n")
    
    print("📋 可用测试:\n")
    print("  1. 文本输入 → 语音输出 (快速测试)")
    print("  2. 语音输入 → 语音输出 (需要音频文件)")
    print("  3. 交互模式 (实时对话)")
    print("  4. 退出\n")
    
    while True:
        choice = input("请选择 (1-4): ").strip()
        
        if choice == "1":
            success = test_text_to_speech()
            print(f"\n✓ 测试完成\n" if success else "\n✗ 测试失败\n")
        
        elif choice == "2":
            audio_file = input("请输入音频文件路径 (例如: test_audio.wav): ").strip()
            success = test_audio_to_speech(audio_file)
            print(f"\n✓ 测试完成\n" if success else "\n✗ 测试失败\n")
        
        elif choice == "3":
            success = interactive_mode()
            print(f"\n✓ 对话结束\n" if success else "\n✗ 对话失败\n")
        
        elif choice == "4":
            print("👋 再见!")
            break
        
        else:
            print("❌ 无效选项，请重试\n")


if __name__ == "__main__":
    main()
