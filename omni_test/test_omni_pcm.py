"""
Qwen Omni SDK 测试 - PCM 音频版本
使用生成的 PCM 音频而不是 MP3
"""

import os
import base64
import time
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# DashScope API 密钥
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")

# 如果环境变量中没有，使用提供的 API 密钥（仅用于演示）
if not DASHSCOPE_API_KEY:
    DASHSCOPE_API_KEY = "sk-67d1be1cac0649b9a8839d2328bbb845"


class OmniClientPCM:
    """Qwen Omni 客户端 - PCM 音频专用"""
    
    def __init__(self, api_key=None, voice="Tina", model="qwen3.5-omni-plus-realtime"):
        from dashscope.audio.qwen_omni import OmniRealtimeConversation, OmniRealtimeCallback, MultiModality
        import dashscope
        
        self.api_key = api_key or DASHSCOPE_API_KEY
        self.voice = voice
        self.model = model
        self.MultiModality = MultiModality
        
        # 设置 API 密钥
        dashscope.api_key = self.api_key
        
        # 创建回调处理器
        self.callback = self._create_callback()
        
        # 初始化对话
        self.conversation = OmniRealtimeConversation(
            model=self.model,
            callback=self.callback
        )
        
        self.last_message = None
        self.error_message = None
        
        print(f"✓ OmniClientPCM 已初始化")
        print(f"  API Key: {self.api_key[:20]}...***")
        print(f"  Voice: {self.voice}")
        print(f"  Model: {self.model}")
    
    def _create_callback(self):
        """创建事件回调处理器"""
        from dashscope.audio.qwen_omni import OmniRealtimeCallback
        
        callback = OmniRealtimeCallback()
        
        def on_open():
            print("✓ WebSocket 已连接")
        
        def on_event(response):
            response_type = response.get("type", "")
            
            # 处理错误事件
            if "error" in response_type.lower():
                self.error_message = response.get("error", {})
                print(f"❌ 错误事件: {self.error_message}")
            
            # 处理文本增量
            elif "delta" in response_type and "text" in response_type:
                delta = response.get("delta", "")
                if delta:
                    print(delta, end="", flush=True)
                    if not self.last_message:
                        self.last_message = ""
                    self.last_message += delta
            
            # 处理其他事件
            elif response_type:
                print(f"\n[事件] {response_type}")
        
        def on_close(code, msg):
            print(f"\n✓ WebSocket 已关闭 (code={code})")
        
        callback.on_open = on_open
        callback.on_event = on_event
        callback.on_close = on_close
        
        return callback
    
    def connect(self):
        """连接到 Qwen Omni"""
        print("\n🔗 连接到 Qwen Omni...")
        try:
            self.conversation.connect()
            print("✓ 连接成功")
            return True
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return False
    
    def configure(self, enable_audio_output=False):
        """配置会话"""
        print("\n⚙️  配置会话...")
        try:
            modalities = [self.MultiModality.TEXT]
            if enable_audio_output:
                modalities.append(self.MultiModality.AUDIO)
            
            self.conversation.update_session(
                output_modalities=modalities,
                voice=self.voice,
                enable_turn_detection=True,
                turn_detection_threshold=0.6
            )
            print(f"✓ 会话已配置")
            print(f"  输出模态: {[str(m) for m in modalities]}")
            print(f"  语音角色: {self.voice}")
            return True
        except Exception as e:
            print(f"❌ 配置失败: {e}")
            return False
    
    def append_pcm_audio(self, audio_file):
        """追加 PCM 音频"""
        print(f"\n📤 追加 PCM 音频: {audio_file}")
        try:
            # 读取音频文件
            with open(audio_file, "rb") as f:
                audio_data = f.read()
            
            print(f"  音频大小: {len(audio_data)} 字节")
            
            # Base64 编码
            audio_b64 = base64.b64encode(audio_data).decode()
            print(f"  Base64 长度: {len(audio_b64)} 字符")
            
            # 追加到会话
            print(f"  追加到会话...")
            self.conversation.append_audio(audio_b64)
            print(f"✓ 音频已追加")
            return True
        except FileNotFoundError:
            print(f"❌ 文件不存在: {audio_file}")
            return False
        except Exception as e:
            print(f"❌ 追加音频失败: {e}")
            return False
    
    def commit(self):
        """提交音频"""
        print(f"\n📤 提交音频...")
        try:
            self.conversation.commit()
            print(f"✓ 已提交")
            return True
        except Exception as e:
            print(f"❌ 提交失败: {e}")
            return False
    
    def get_response(self, wait_time=3):
        """获取响应"""
        print(f"\n⏳ 等待响应 ({wait_time}s)...")
        time.sleep(wait_time)
        
        try:
            message = self.conversation.get_last_message()
            if message:
                print(f"\n🤖 AI 回复: {message}")
                return message
            else:
                print(f"⚠️  未收到回复")
                return None
        except Exception as e:
            print(f"❌ 获取响应失败: {e}")
            return None
    
    def close(self):
        """关闭连接"""
        print(f"\n🔌 关闭连接...")
        try:
            self.conversation.close()
            print(f"✓ 已关闭")
            return True
        except Exception as e:
            print(f"⚠️  关闭时出错: {e}")
            return False


def test_pcm_audio():
    """测试 PCM 音频"""
    
    print("\n" + "="*70)
    print("测试 PCM 音频".center(70))
    print("="*70)
    
    client = OmniClientPCM(voice="Tina")
    
    try:
        # 1. 连接
        if not client.connect():
            return
        
        # 2. 配置
        if not client.configure(enable_audio_output=False):
            return
        
        # 3. 使用 test_audio.pcm（如果存在）
        audio_file = "test_audio.pcm"
        if not os.path.exists(audio_file):
            print(f"\n⚠️  文件不存在: {audio_file}")
            print(f"   请先运行: python generate_test_audio.py")
            return
        
        # 4. 追加音频
        if not client.append_pcm_audio(audio_file):
            return
        
        # 5. 提交
        if not client.commit():
            return
        
        # 6. 获取响应
        response = client.get_response(wait_time=3)
        
        if response:
            print("\n✅ 测试成功!")
        else:
            print("\n⚠️  无法获取响应")
    
    finally:
        client.close()


def test_text_input():
    """测试文本输入"""
    
    print("\n" + "="*70)
    print("测试文本输入".center(70))
    print("="*70)
    
    client = OmniClientPCM(voice="Daisy")
    
    try:
        # 1. 连接
        if not client.connect():
            return
        
        # 2. 配置
        if not client.configure(enable_audio_output=False):
            return
        
        # 3. 获取用户输入
        print("\n💬 请输入问题:")
        user_input = input("> ").strip()
        
        if not user_input:
            print("❌ 输入为空")
            return
        
        print(f"\n📤 发送: {user_input}")
        
        # 4. 通过文本交互（使用 append_audio 的替代方案）
        # 注意：SDK 可能不支持直接的文本追加，这里需要通过其他方式
        
        print("\n⚠️  注意: SDK 可能不支持直接的文本输入")
        print("   建议使用 REST API 或转换文本为语音")
        
    finally:
        client.close()


def test_basic_connection():
    """测试基本连接"""
    
    print("\n" + "="*70)
    print("测试基本连接".center(70))
    print("="*70)
    
    try:
        from dashscope.audio.qwen_omni import OmniRealtimeConversation, OmniRealtimeCallback
        import dashscope
        
        dashscope.api_key = DASHSCOPE_API_KEY
        
        print(f"\n🔗 连接到 Qwen Omni...")
        print(f"   Model: qwen3.5-omni-plus-realtime")
        
        callback = OmniRealtimeCallback()
        
        connected = [False]
        closed = [False]
        
        def on_open():
            connected[0] = True
            print(f"✓ 连接成功")
        
        def on_close(code, msg):
            closed[0] = True
            print(f"✓ 连接已关闭")
        
        callback.on_open = on_open
        callback.on_close = on_close
        
        conversation = OmniRealtimeConversation(
            model="qwen3.5-omni-plus-realtime",
            callback=callback
        )
        
        conversation.connect()
        time.sleep(1)
        
        if connected[0]:
            print("✅ 连接测试成功!")
            conversation.close()
            return True
        else:
            print("❌ 无法建立连接")
            return False
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主菜单"""
    
    print("\n╔" + "="*68 + "╗")
    print("║" + "Qwen Omni SDK 测试 - PCM 音频版本".center(70) + "║")
    print("╚" + "="*68 + "╝")
    
    print("\n📋 选择测试:\n")
    print("  1. 基本连接测试")
    print("  2. PCM 音频测试")
    print("  3. 文本输入测试")
    print("  4. 完整流程测试")
    print("  5. 退出")
    
    while True:
        choice = input("\n请选择 (1-5): ").strip()
        
        if choice == "1":
            test_basic_connection()
        elif choice == "2":
            test_pcm_audio()
        elif choice == "3":
            test_text_input()
        elif choice == "4":
            test_basic_connection()
            test_pcm_audio()
        elif choice == "5":
            print("\n👋 再见!")
            break
        else:
            print("❌ 无效选项")
        
        print("\n" + "-"*70)


if __name__ == "__main__":
    main()
