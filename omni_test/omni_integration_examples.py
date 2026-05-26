"""
Qwen Omni 实时语音 - 集成示例
展示如何将实时语音交互集成到应用中
"""

import os
import json
import time
import base64
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

try:
    from dashscope.audio.qwen_omni import OmniRealtimeConversation, OmniRealtimeCallback
    import dashscope
except ImportError:
    print("需要安装: pip install dashscope")
    exit(1)

dashscope.api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")


class SimpleAudioTester:
    """简化版音频测试类 - 快速集成"""
    
    def __init__(self, instructions: str = None, voice: str = "Cherry"):
        self.instructions = instructions
        self.voice = voice
        self.conversation = None
        self.text_response = ""
        self.audio_response = None
        
        self._setup_callback()
    
    def _setup_callback(self):
        """设置回调处理器"""
        parent = self
        
        class SimpleCallback(OmniRealtimeCallback):
            def on_open(self):
                print("✓ 连接成功")
            
            def on_event(self, response):
                event_type = response.get("type", "")
                
                if event_type == "response.audio_transcript.delta":
                    parent.text_response += response.get("delta", "")
                    print(f"🤖 {response.get('delta', '')}", end="", flush=True)
                
                elif event_type == "response.audio.delta":
                    audio_data = response.get("delta", "")
                    if audio_data:
                        if parent.audio_response is None:
                            parent.audio_response = audio_data
                        else:
                            parent.audio_response += audio_data
                
                elif event_type == "response.audio_transcript.done":
                    print()
                
                elif event_type == "server.error":
                    error = response.get("error", {})
                    print(f"❌ {error.get('message', 'Error')}")
            
            def on_close(self, code, msg):
                pass
        
        self.current_callback = SimpleCallback()
    
    def start(self):
        """启动连接"""
        try:
            self.conversation = OmniRealtimeConversation(
                model="qwen3.5-omni-plus-realtime",
                callback=self.current_callback,
                url="wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
            )
            self.conversation.connect()
            time.sleep(0.5)
            
            # 配置会话
            session_config = {
                "event_id": f"session_{int(time.time() * 1000)}",
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "voice": self.voice,
                    "input_audio_format": "pcm",
                    "output_audio_format": "pcm",
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "silence_duration_ms": 800
                    }
                }
            }
            
            if self.instructions:
                session_config["session"]["instructions"] = self.instructions
            
            self.conversation.send_event(json.dumps(session_config))
            return True
        
        except Exception as e:
            print(f"❌ 启动失败: {str(e)}")
            return False
    
    def ask(self, text: str, wait_seconds: float = 3.0) -> str:
        """发送文本问题并等待响应"""
        self.text_response = ""
        self.audio_response = None
        
        try:
            # 发送文本
            text_event = {
                "event_id": f"event_{int(time.time() * 1000)}",
                "type": "input_text_buffer.append",
                "text": text
            }
            self.conversation.send_event(json.dumps(text_event))
            
            commit_event = {
                "event_id": f"event_{int(time.time() * 1000)}",
                "type": "input_text_buffer.commit"
            }
            self.conversation.send_event(json.dumps(commit_event))
            
            # 等待响应
            time.sleep(wait_seconds)
            
            return self.text_response.strip()
        
        except Exception as e:
            print(f"❌ 错误: {str(e)}")
            return ""
    
    def close(self):
        """关闭连接"""
        if self.conversation:
            self.conversation.close()


# ============================================================
# 使用示例
# ============================================================

def example_1_simple_qa():
    """示例 1: 简单问答"""
    print("\n" + "="*60)
    print("示例 1: 简单问答".center(60))
    print("="*60 + "\n")
    
    tester = SimpleAudioTester(
        instructions="你是一个旅游推荐师。请给出简洁、实用的建议。"
    )
    
    if not tester.start():
        return False
    
    try:
        response = tester.ask("推荐一个春天可以去的景点")
        print(f"\n✓ 完整回复:\n{response}")
        return True
    finally:
        tester.close()


def example_2_multi_turn():
    """示例 2: 多轮对话"""
    print("\n" + "="*60)
    print("示例 2: 多轮对话".center(60))
    print("="*60 + "\n")
    
    tester = SimpleAudioTester(
        instructions="你是一个友好的助手。请记住对话历史。"
    )
    
    if not tester.start():
        return False
    
    try:
        questions = [
            "我喜欢看电影，有什么推荐吗？",
            "有没有最近的热门电影？",
            "那部电影的评分怎样？"
        ]
        
        for i, question in enumerate(questions, 1):
            print(f"\n问题 {i}: {question}")
            response = tester.ask(question, wait_seconds=2.5)
            print(f"回答: {response}")
    finally:
        tester.close()
    
    return True


def example_3_with_voice_control():
    """示例 3: 指定输出语音"""
    print("\n" + "="*60)
    print("示例 3: 不同的输出语音".center(60))
    print("="*60 + "\n")
    
    voices = ["Cherry", "Daisy"]
    
    for voice in voices:
        print(f"\n🎙️ 语音角色: {voice}")
        print("-" * 40)
        
        tester = SimpleAudioTester(voice=voice)
        
        if not tester.start():
            continue
        
        try:
            response = tester.ask("用你最喜欢的语调说一句欢迎词", wait_seconds=2)
            print(f"\\n✓ {response}")
        finally:
            tester.close()
    
    return True


def example_4_streaming_response():
    """示例 4: 流式响应（边接收边处理）"""
    print("\n" + "="*60)
    print("示例 4: 流式响应处理".center(60))
    print("="*60 + "\n")
    
    tester = SimpleAudioTester()
    
    if not tester.start():
        return False
    
    try:
        print("📤 发送问题...")
        response = tester.ask("请用 5 条要点总结一下春节的庆祝方式", wait_seconds=3)
        
        # 处理流式响应
        if tester.audio_response:
            print(f"\n✓ 收到音频响应 ({len(tester.audio_response)} 字符)")
            # 这里可以实时播放或处理音频
        
        return True
    finally:
        tester.close()


def example_5_use_with_sleep_monitoring():
    """示例 5: 整合到睡眠监测系统"""
    print("\n" + "="*60)
    print("示例 5: 睡眠监测系统集成".center(60))
    print("="*60 + "\n")
    
    # 模拟睡眠数据
    sleep_data = {
        "user": "张三",
        "sleep_duration": 7.5,
        "sleep_quality": "一般",
        "issues": ["早醒", "入睡困难"]
    }
    
    prompt = f"""
    用户 {sleep_data['user']} 的睡眠数据:
    - 睡眠时长: {sleep_data['sleep_duration']} 小时
    - 睡眠质量: {sleep_data['sleep_quality']}
    - 问题: {', '.join(sleep_data['issues'])}
    
    请提供改善建议。
    """
    
    tester = SimpleAudioTester(
        instructions="你是一个睡眠健康顾问。基于用户的数据提供专业建议。",
        voice="Daisy"
    )
    
    if not tester.start():
        return False
    
    try:
        print(f"👤 用户: {sleep_data['user']}")
        print(f"📊 睡眠时长: {sleep_data['sleep_duration']}h")
        print(f"⭐ 质量: {sleep_data['sleep_quality']}")
        print()
        
        response = tester.ask(prompt, wait_seconds=3)
        
        print(f"\n🎯 建议:\n{response}")
        return True
    finally:
        tester.close()


# ============================================================
# 主函数
# ============================================================

if __name__ == "__main__":
    print("\n╔" + "="*58 + "╗")
    print("║" + "Qwen Omni 集成示例".center(60) + "║")
    print("╚" + "="*58 + "╝")
    
    print("\n选择要运行的示例:\n")
    print("  1. 简单问答")
    print("  2. 多轮对话")
    print("  3. 不同语音角色")
    print("  4. 流式响应")
    print("  5. 睡眠监测系统集成")
    print("  6. 运行所有示例")
    print("  0. 退出")
    
    choice = input("\n请选择 (0-6): ").strip()
    
    examples = {
        "1": example_1_simple_qa,
        "2": example_2_multi_turn,
        "3": example_3_with_voice_control,
        "4": example_4_streaming_response,
        "5": example_5_use_with_sleep_monitoring,
    }
    
    if choice == "6":
        for example_func in examples.values():
            try:
                example_func()
            except Exception as e:
                print(f"\n❌ 示例出错: {str(e)}")
            time.sleep(1)
    elif choice in examples:
        try:
            examples[choice]()
        except Exception as e:
            print(f"\n❌ 示例出错: {str(e)}")
    elif choice == "0":
        print("👋 再见!")
    else:
        print("❌ 无效选项")
