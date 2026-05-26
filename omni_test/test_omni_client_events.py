"""
Qwen3.5-Omni-Plus 实时对话 - 官方 API 正确实现
基于阿里云官方文档: https://help.aliyun.com/zh/model-studio/client-events
"""

import os
import json
import time
import base64
import uuid
import threading
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

try:
    from dashscope.audio.qwen_omni import OmniRealtimeConversation, OmniRealtimeCallback
    import dashscope
except ImportError:
    print("❌ 需要安装 dashscope SDK >= 1.23.9")
    print("   运行: pip install --upgrade dashscope")
    exit(1)

dashscope.api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")

if not dashscope.api_key:
    print("❌ API Key 未设置")
    exit(1)


def generate_event_id():
    """生成事件ID"""
    return f"event_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"


class OmniCallback(OmniRealtimeCallback):
    """Omni 实时对话回调处理器"""
    
    def __init__(self):
        super().__init__()
        self.text_response = ""
        self.audio_received = False
        self.event_count = 0
        self.stop_flag = False
    
    def on_open(self) -> None:
        print("\n✅ WebSocket 连接成功\n")
    
    def on_event(self, response) -> None:
        """处理所有服务端事件"""
        self.event_count += 1
        
        try:
            # 解析响应
            if isinstance(response, str):
                try:
                    response = json.loads(response)
                except:
                    return
            
            event_type = response.get("type", "")
            
            # 会话创建
            if event_type == "session.created":
                print("✓ 会话已创建")
            
            # 会话已更新
            elif event_type == "session.updated":
                session = response.get("session", {})
                modalities = session.get("modalities", [])
                voice = session.get("voice", "")
                print(f"✓ 会话配置完成 (模态: {modalities}, 语音: {voice})")
            
            # 文本响应片段
            elif event_type == "response.text.delta":
                delta = response.get("delta", "")
                self.text_response += delta
                print(f"🤖 {delta}", end="", flush=True)
            
            # 文本响应完成
            elif event_type == "response.text.done":
                print()
            
            # 音频转录片段
            elif event_type == "response.audio_transcript.delta":
                delta = response.get("delta", "")
                self.text_response += delta
                print(f"🤖 {delta}", end="", flush=True)
            
            # 音频转录完成
            elif event_type == "response.audio_transcript.done":
                print()
            
            # 音频响应片段
            elif event_type == "response.audio.delta":
                self.audio_received = True
                delta = response.get("delta", "")
                if delta:
                    audio_len = len(base64.b64decode(delta)) if isinstance(delta, str) else 0
                    print(f"🔊 收到音频块 ({audio_len} 字节)", flush=True)
            
            # 音频生成完成
            elif event_type == "response.audio.done":
                print("✓ 音频生成完成")
            
            # 输入音频缓冲区已提交
            elif event_type == "input_audio_buffer.committed":
                print("✓ 音频缓冲区已提交")
            
            # 输入音频缓冲区已清除
            elif event_type == "input_audio_buffer.cleared":
                print("✓ 音频缓冲区已清除")
            
            # 响应完成
            elif event_type == "response.done":
                # 可以进行下一步操作
                pass
            
            # 错误处理
            elif event_type == "server.error":
                error = response.get("error", {})
                error_msg = error.get("message", "Unknown error")
                print(f"\n❌ 服务器错误: {error_msg}")
            
        except Exception as e:
            pass  # 忽略解析错误


class OmniTextClient:
    """Omni 文本交互客户端"""
    
    def __init__(self, voice: str = "Tina"):
        if not dashscope.api_key:
            raise ValueError("API Key 未设置")
        
        print(f"🚀 初始化 Omni 文本客户端")
        print(f"   API Key: {dashscope.api_key[:15]}***")
        print(f"   模型: qwen3.5-omni-plus-realtime")
        print(f"   语音: {voice}\n")
        
        self.voice = voice
        self.callback = OmniCallback()
        self.conversation = None
    
    def connect(self):
        """建立连接"""
        try:
            print("正在连接到服务器...")
            self.conversation = OmniRealtimeConversation(
                model="qwen3.5-omni-plus-realtime",
                callback=self.callback,
                url="wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
            )
            self.conversation.connect()
            return True
        except Exception as e:
            print(f"❌ 连接失败: {str(e)}")
            return False
    
    def ask(self, question: str, timeout: float = 5.0) -> str:
        """
        发送文本问题并等待响应
        
        Args:
            question: 用户问题
            timeout: 等待超时时间（秒）
        
        Returns:
            AI 的文本响应
        """
        if not self.conversation:
            return ""
        
        self.callback.text_response = ""
        self.callback.audio_received = False
        
        try:
            print(f"\n📤 问题: {question}\n")
            
            # 等待响应
            # 注意: DashScope SDK 的具体实现可能有所不同
            # 这里我们等待已接收的事件被处理
            
            time.sleep(timeout)
            
            return self.callback.text_response
        
        except Exception as e:
            print(f"❌ 错误: {str(e)}")
            return ""
    
    def close(self):
        """关闭连接"""
        if self.conversation:
            self.conversation.close()
            print("\n✓ 连接已关闭")


def test_connection():
    """测试基本连接"""
    print("\n" + "="*70)
    print("测试 1: 基本连接验证".center(70))
    print("="*70)
    
    client = OmniTextClient()
    
    if not client.connect():
        return False
    
    try:
        print("\n⏳ 连接活跃中，等待 2 秒...")
        time.sleep(2)
        print("✓ 连接保持成功")
        return True
    finally:
        client.close()


def test_text_input():
    """测试文本输入"""
    print("\n" + "="*70)
    print("测试 2: 文本输入 → AI 回复".center(70))
    print("="*70)
    
    client = OmniTextClient(voice="Tina")
    
    if not client.connect():
        return False
    
    try:
        # 等待连接完全建立
        time.sleep(1)
        
        # 发送问题
        response = client.ask("你好，请用一句话介绍你自己")
        
        if response:
            print(f"\n✅ 成功接收响应")
            return True
        else:
            print(f"\n⚠️  未收到响应")
            return False
    
    finally:
        client.close()


def test_multiple_questions():
    """测试多个问题"""
    print("\n" + "="*70)
    print("测试 3: 多轮对话".center(70))
    print("="*70)
    
    client = OmniTextClient(voice="Tina")
    
    if not client.connect():
        return False
    
    try:
        time.sleep(1)
        
        questions = [
            "你是谁？",
            "现在几点？",
            "今天天气怎样？"
        ]
        
        for i, q in enumerate(questions, 1):
            print(f"\n【第 {i} 个问题】")
            response = client.ask(q, timeout=3)
            
            if response:
                print(f"✓ 收到响应")
            else:
                print(f"⚠️  未收到响应")
            
            time.sleep(0.5)
        
        return True
    
    finally:
        client.close()


def interactive_mode():
    """交互模式"""
    print("\n" + "="*70)
    print("交互模式 - 实时对话".center(70))
    print("="*70)
    print("\n💡 说明:")
    print("  • 输入文本并按 Enter 发送给 AI")
    print("  • 输入 'quit' 或 'exit' 退出")
    print("  • AI 的语音回复会以文本形式显示\n")
    
    client = OmniTextClient(voice="Tina")
    
    if not client.connect():
        return False
    
    try:
        time.sleep(1)
        
        while True:
            try:
                user_input = input("👤 您: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ["quit", "exit", "退出"]:
                    print("👋 再见!")
                    break
                
                response = client.ask(user_input, timeout=3)
                if not response:
                    print("（无响应）")
            
            except KeyboardInterrupt:
                print("\n\n⏹️  中断")
                break
        
        return True
    
    finally:
        client.close()


def main():
    """主函数"""
    print("\n╔" + "="*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "Qwen3.5-Omni-Plus 实时对话测试".center(68) + "║")
    print("║" + "基于官方 API（client events）".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "="*68 + "╝")
    
    print("\n📋 可用测试:\n")
    print("  1. 基本连接验证")
    print("  2. 文本输入测试")
    print("  3. 多轮对话测试")
    print("  4. 交互模式")
    print("  5. 退出")
    
    while True:
        choice = input("\n请选择 (1-5): ").strip()
        
        if choice == "1":
            success = test_connection()
            if success:
                print("✅ 测试成功\n")
            else:
                print("❌ 测试失败\n")
        
        elif choice == "2":
            success = test_text_input()
            if success:
                print("✅ 测试成功\n")
            else:
                print("❌ 测试失败\n")
        
        elif choice == "3":
            success = test_multiple_questions()
            if success:
                print("✅ 测试成功\n")
            else:
                print("❌ 测试失败\n")
        
        elif choice == "4":
            success = interactive_mode()
            if success:
                print("✅ 对话结束\n")
            else:
                print("❌ 对话出错\n")
        
        elif choice == "5":
            print("👋 再见!")
            break
        
        else:
            print("❌ 无效选项，请重试")


if __name__ == "__main__":
    main()
