"""
Qwen3.5-Omni-Plus 实时对话 - 基于官方 API
基于用户提供的官方示例代码
"""

import os
import json
import time
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

try:
    from dashscope.audio.qwen_omni import OmniRealtimeConversation, OmniRealtimeCallback
    import dashscope
except ImportError:
    print("❌ 需要安装 dashscope SDK >= 1.23.9")
    print("   运行: pip install --upgrade dashscope")
    sys.exit(1)

# 设置 API Key
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")

if not dashscope.api_key:
    print("❌ DASHSCOPE_API_KEY 或 QWEN_API_KEY 环境变量未设置")
    sys.exit(1)

print(f"✓ API Key: {dashscope.api_key[:15]}***")


class VerboseCallback(OmniRealtimeCallback):
    """详细的回调处理"""
    
    def on_open(self) -> None:
        print("\n✅ WebSocket 连接已建立")
        print("💬 开始接收消息...\n")
    
    def on_event(self, response: dict) -> None:
        """接收和显示事件"""
        try:
            if not isinstance(response, dict):
                return
            
            event_type = response.get("type", "unknown")
            
            # 文本响应片段
            if event_type == "response.text.delta":
                text = response.get("delta", "")
                print(f"🤖 {text}", end="", flush=True)
            
            # 文本响应完成
            elif event_type == "response.text.done":
                print("\n")
            
            # 输入缓冲区更新
            elif event_type == "input_text_buffer.commit":
                content = response.get("input", {}).get("content", "")
                if content:
                    print(f"\n📤 已发送文本: {content}\n")
            
            # 会话创建
            elif event_type == "session.created":
                print("✓ 会话已创建")
            
            # 其他重要事件
            elif "error" in event_type.lower():
                print(f"\n❌ 错误: {json.dumps(response, indent=2, ensure_ascii=False)}")
            
            # 静默处理其他事件
            
        except Exception as e:
            print(f"\n⚠️  处理事件失败: {str(e)}")
    
    def on_close(self, close_status_code: int, close_msg: str) -> None:
        print(f"\n✓ 连接已关闭 (代码: {close_status_code}, 信息: {close_msg})")


def test_basic_connection():
    """基础连接测试"""
    print("\n" + "="*70)
    print("测试 1: 基础连接验证".center(70))
    print("="*70)
    
    callback = VerboseCallback()
    conversation = OmniRealtimeConversation(
        model="qwen3.5-omni-plus-realtime",
        callback=callback,
        url="wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
    )
    
    try:
        print("\n正在连接到服务器...")
        conversation.connect()
        
        print("✓ 连接成功，等待 3 秒...")
        time.sleep(3)
        
        print("✓ 关闭连接...")
        conversation.close()
        
        print("\n✅ 基础连接测试成功！")
        return True
    
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        return False


def test_with_input_stream():
    """使用输入流的测试"""
    print("\n" + "="*70)
    print("测试 2: 与文本输入交互").center(70))
    print("="*70)
    
    callback = VerboseCallback()
    conversation = OmniRealtimeConversation(
        model="qwen3.5-omni-plus-realtime",
        callback=callback,
        url="wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
    )
    
    try:
        print("\n正在连接...")
        conversation.connect()
        
        # 尝试发送文本
        # 注意: 具体的 API 方法需要根据实际 SDK 调整
        print("\n尝试发送文本输入...")
        
        # 可能的发送方法（需要根据实际 SDK 调整）:
        # 1. conversation.send_text("你好")
        # 2. conversation.write(b"你好")
        # 3. 通过某种输入队列
        
        # 这里添加实际的发送代码
        # conversation.send_text("你好，请自我介绍")
        
        print("⏳ 等待响应 (3 秒)...")
        time.sleep(3)
        
        conversation.close()
        print("\n✅ 测试完成")
        return True
    
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        if conversation:
            try:
                conversation.close()
            except:
                pass
        return False


def interactive_mode():
    """交互模式"""
    print("\n" + "="*70)
    print("交互模式 - 实时对话".center(70))
    print("="*70)
    print("\n💡 说明:")
    print("  • 输入文本并按 Enter 发送")
    print("  • 输入 'quit' 或 'exit' 退出")
    print("  • 输入 'help' 查看帮助\n")
    
    callback = VerboseCallback()
    conversation = OmniRealtimeConversation(
        model="qwen3.5-omni-plus-realtime",
        callback=callback,
        url="wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
    )
    
    try:
        print("正在连接...")
        conversation.connect()
        print("✓ 连接成功\n")
        
        while True:
            try:
                user_input = input("👤 您: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ["quit", "exit"]:
                    print("👋 再见!")
                    break
                
                if user_input.lower() == "help":
                    print("\n📖 帮助:")
                    print("  • 直接输入文本即可与 AI 对话")
                    print("  • 输入 'quit' 或 'exit' 退出")
                    print()
                    continue
                
                print()
                # 这里需要根据实际 SDK API 发送消息
                # 例如: conversation.send_text(user_input)
                # 或: conversation.input_text_buffer.append(user_input)
                
                time.sleep(2)
            
            except KeyboardInterrupt:
                print("\n\n⏹️  中断")
                break
        
        conversation.close()
        return True
    
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        if conversation:
            try:
                conversation.close()
            except:
                pass
        return False


def main():
    """主函数"""
    print("\n╔" + "="*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "Qwen3.5-Omni-Plus 实时对话（基于官方 API）".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "="*68 + "╝")
    
    print("\n📋 可用测试:\n")
    print("  1. 基础连接验证")
    print("  2. 输入/输出测试")
    print("  3. 交互模式")
    print("  4. 退出")
    
    while True:
        choice = input("\n请选择 (1-4): ").strip()
        
        if choice == "1":
            success = test_basic_connection()
            print()
        
        elif choice == "2":
            success = test_with_input_stream()
            print()
        
        elif choice == "3":
            success = interactive_mode()
            print()
        
        elif choice == "4":
            print("👋 再见!")
            break
        
        else:
            print("❌ 无效选项，请重试")


if __name__ == "__main__":
    main()
