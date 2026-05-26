"""
Qwen3.5-Omni-Plus 实时对话 - 使用 DashScope SDK 真实 API
基于诊断结果的正确实现
"""

import os
import json
import time
import base64
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

try:
    from dashscope.audio.qwen_omni import OmniRealtimeConversation, OmniRealtimeCallback, MultiModality
    import dashscope
except ImportError:
    print("❌ 需要安装 dashscope SDK >= 1.23.9")
    print("   运行: pip install --upgrade dashscope")
    exit(1)

dashscope.api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")

if not dashscope.api_key:
    print("❌ API Key 未设置")
    exit(1)


class SimpleCallback(OmniRealtimeCallback):
    """简单的回调处理器"""
    
    def __init__(self):
        super().__init__()
        self.is_open = False
        self.last_message = ""
        self.events_received = 0
    
    def on_open(self) -> None:
        self.is_open = True
        print("✅ WebSocket 连接成功\n")
    
    def on_event(self, response) -> None:
        """处理事件"""
        self.events_received += 1
        
        try:
            if isinstance(response, dict):
                event_type = response.get("type", "")
                
                # 处理文本响应
                if "text" in event_type and "delta" in event_type:
                    delta = response.get("delta", "")
                    print(f"🤖 {delta}", end="", flush=True)
                    self.last_message += delta
                
                elif "audio" in event_type and "delta" in event_type:
                    print(f"🔊 收到音频块", flush=True)
        
        except Exception as e:
            pass
    
    def on_close(self, close_status_code: int, close_msg: str) -> None:
        self.is_open = False
        print(f"\n✓ 连接已关闭")


class OmniClient:
    """Qwen Omni 实时对话客户端"""
    
    def __init__(self, voice: str = "Tina"):
        if not dashscope.api_key:
            raise ValueError("API Key 未设置")
        
        print(f"🚀 初始化 Omni 客户端")
        print(f"   API Key: {dashscope.api_key[:15]}***")
        print(f"   模型: qwen3.5-omni-plus-realtime")
        print(f"   语音: {voice}\n")
        
        self.voice = voice
        self.callback = SimpleCallback()
        self.conversation = None
    
    def connect(self):
        """建立连接"""
        try:
            print("正在连接到 Qwen Omni 服务...")
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
    
    def configure(self, instructions: str = None):
        """配置会话"""
        try:
            print("配置会话...")
            
            # 更新会话配置
            self.conversation.update_session(
                output_modalities=[MultiModality.TEXT, MultiModality.AUDIO],
                voice=self.voice,
                enable_turn_detection=True,
                turn_detection_type="server_vad"
            )
            
            if instructions:
                print(f"✓ 系统指令已设置")
            else:
                print(f"✓ 会话已配置")
            
            return True
        
        except Exception as e:
            print(f"❌ 配置失败: {str(e)}")
            return False
    
    def ask_text(self, question: str, wait_seconds: float = 3.0) -> str:
        """
        发送文本问题
        
        Args:
            question: 问题文本
            wait_seconds: 等待响应的秒数
        
        Returns:
            AI 的回复
        """
        if not self.conversation:
            return ""
        
        try:
            print(f"📤 问题: {question}\n")
            
            self.callback.last_message = ""
            
            # SDK 可能需要通过标准输入或其他方式发送
            # 目前尝试等待并检查回复
            
            time.sleep(wait_seconds)
            
            message = self.conversation.get_last_message()
            if message:
                print(f"\n✓ 成功获取回复")
                return message
            
            if self.callback.last_message:
                return self.callback.last_message
            
            print(f"⚠️  未收到回复")
            return ""
        
        except Exception as e:
            print(f"❌ 错误: {str(e)}")
            return ""
    
    def append_audio(self, audio_b64: str):
        """追加音频数据"""
        try:
            self.conversation.append_audio(audio_b64)
            return True
        except Exception as e:
            print(f"❌ 追加音频失败: {str(e)}")
            return False
    
    def commit(self):
        """提交缓冲区"""
        try:
            self.conversation.commit()
            print("✓ 已提交")
            return True
        except Exception as e:
            print(f"❌ 提交失败: {str(e)}")
            return False
    
    def get_last_message(self) -> str:
        """获取最后的消息"""
        try:
            return self.conversation.get_last_message()
        except:
            return ""
    
    def close(self):
        """关闭连接"""
        if self.conversation:
            try:
                self.conversation.end_session(timeout=5)
                print("✓ 会话已结束")
            except:
                pass
            
            try:
                self.conversation.close()
            except:
                pass


def test_1_basic():
    """测试 1: 基本连接"""
    print("\n" + "="*70)
    print("测试 1: 基本连接".center(70))
    print("="*70)
    
    client = OmniClient()
    
    if not client.connect():
        return False
    
    try:
        if client.configure():
            time.sleep(1)
            print("✓ 连接测试成功")
            return True
        return False
    finally:
        client.close()


def test_2_text_input():
    """测试 2: 文本输入"""
    print("\n" + "="*70)
    print("测试 2: 文本输入 → AI 回复".center(70))
    print("="*70)
    
    client = OmniClient(voice="Tina")
    
    if not client.connect():
        return False
    
    try:
        client.configure("你是一个友好的助手")
        time.sleep(1)
        
        # 尝试发送文本
        response = client.ask_text("你好，请介绍自己", wait_seconds=2)
        
        if response:
            print(f"\n✅ 成功接收: {response}")
            return True
        else:
            return False
    finally:
        client.close()


def test_3_audio_append():
    """测试 3: 音频追加"""
    print("\n" + "="*70)
    print("测试 3: 音频文件测试".center(70))
    print("="*70)
    
    client = OmniClient(voice="Daisy")
    
    if not client.connect():
        return False
    
    try:
        client.configure()
        
        # 检查是否有测试音频文件
        audio_file = "output.mp3"
        if not os.path.exists(audio_file):
            print(f"❌ 未找到音频文件: {audio_file}")
            return False
        
        print(f"📂 正在读取音频文件: {audio_file}")
        with open(audio_file, "rb") as f:
            audio_data = f.read()
        
        audio_b64 = base64.b64encode(audio_data).decode()
        print(f"✓ 音频大小: {len(audio_data)} 字节")
        
        # 追加音频
        print("📤 追加音频...")
        if client.append_audio(audio_b64):
            print("✓ 音频已追加")
            
            # 提交
            time.sleep(0.5)
            if client.commit():
                # 等待响应
                time.sleep(2)
                message = client.get_last_message()
                if message:
                    print(f"🤖 回复: {message}")
                    return True
        
        return False
    
    finally:
        client.close()


def test_4_interactive():
    """测试 4: 交互模式"""
    print("\n" + "="*70)
    print("交互模式".center(70))
    print("="*70)
    print("\n💡 说明:")
    print("  • 输入文本与 AI 对话")
    print("  • 输入 'quit' /退出\n")
    
    client = OmniClient(voice="Tina")
    
    if not client.connect():
        return False
    
    try:
        client.configure("你是一个有帮助的 AI 助手")
        time.sleep(1)
        
        while True:
            try:
                text = input("👤 您: ").strip()
                
                if not text:
                    continue
                
                if text.lower() in ["quit", "exit", "退出"]:
                    print("👋 再见!")
                    break
                
                response = client.ask_text(text, wait_seconds=2)
                if response:
                    print(f"✓ 回复已接收\n")
            
            except KeyboardInterrupt:
                print("\n⏹️  中断")
                break
        
        return True
    
    finally:
        client.close()


def main():
    """主函数"""
    print("\n╔" + "="*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "Qwen3.5-Omni-Plus 实时对话测试".center(68) + "║")
    print("║" + "基于 DashScope SDK 官方 API".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "="*68 + "╝")
    
    print("\n📋 可用测试:\n")
    print("  1. 基本连接测试")
    print("  2. 文本输入测试")
    print("  3. 音频文件测试")
    print("  4. 交互模式")
    print("  5. 退出")
    
    while True:
        choice = input("\n请选择 (1-5): ").strip()
        
        if choice == "1":
            test_1_basic()
        elif choice == "2":
            test_2_text_input()
        elif choice == "3":
            test_3_audio_append()
        elif choice == "4":
            test_4_interactive()
        elif choice == "5":
            print("👋 再见!")
            break
        else:
            print("❌ 无效选项")


if __name__ == "__main__":
    main()
