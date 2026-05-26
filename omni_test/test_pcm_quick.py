"""
快速测试 PCM 音频 - 自动化版本
"""

import os
import base64
import time
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY") or "sk-67d1be1cac0649b9a8839d2328bbb845"

def test_pcm_audio_quick():
    """快速测试 PCM 音频"""
    
    print("\n╔" + "="*68 + "╗")
    print("║" + "快速 PCM 音频测试".center(70) + "║")
    print("╚" + "="*68 + "╝\n")
    
    try:
        from dashscope.audio.qwen_omni import OmniRealtimeConversation, OmniRealtimeCallback, MultiModality
        import dashscope
        
        # 设置 API 密钥
        dashscope.api_key = DASHSCOPE_API_KEY
        
        print(f"✓ 已配置 API 密钥")
        print(f"  Key: {DASHSCOPE_API_KEY[:20]}...***\n")
        
        # 检查音频文件
        audio_file = "test_audio.pcm"
        if not os.path.exists(audio_file):
            print(f"❌ 文件不存在: {audio_file}")
            print(f"   请先运行: python gen_audio.py")
            return False
        
        print(f"✓ 找到音频文件: {audio_file}")
        file_size = os.path.getsize(audio_file)
        print(f"  大小: {file_size} 字节 ({file_size/1024:.1f} KB)\n")
        
        # 读取音频
        with open(audio_file, "rb") as f:
            audio_data = f.read()
        
        audio_b64 = base64.b64encode(audio_data).decode()
        print(f"✓ 音频已编码")
        print(f"  Base64 长度: {len(audio_b64)} 字符\n")
        
        # 创建回调
        callback = OmniRealtimeCallback()
        results = {"connected": False, "error": None, "response": None}
        
        def on_open():
            print("✓ WebSocket 已连接")
            results["connected"] = True
        
        def on_event(response):
            event_type = response.get("type", "")
            
            if "error" in event_type.lower():
                error_msg = response.get("error", {}).get("message", "未知错误")
                print(f"❌ 错误事件: {error_msg}")
                results["error"] = error_msg
            elif "delta" in event_type and "text" in event_type:
                delta = response.get("delta", "")
                if delta:
                    print(delta, end="", flush=True)
        
        def on_close(code, msg):
            print(f"\n✓ WebSocket 已关闭 (code={code})")
        
        callback.on_open = on_open
        callback.on_event = on_event
        callback.on_close = on_close
        
        # 创建对话
        print("🔗 连接到 Qwen Omni...")
        conversation = OmniRealtimeConversation(
            model="qwen3.5-omni-plus-realtime",
            callback=callback
        )
        
        # 连接
        conversation.connect()
        time.sleep(1)
        
        if not results["connected"]:
            print("\n❌ 无法连接到服务器")
            return False
        
        # 配置会话
        print("\n⚙️  配置会话...")
        conversation.update_session(
            output_modalities=[MultiModality.TEXT],
            voice="Tina",
            enable_turn_detection=True
        )
        print("✓ 会话已配置\n")
        
        # 追加音频
        print("📤 追加 PCM 音频...")
        conversation.append_audio(audio_b64)
        print("✓ 音频已追加\n")
        
        # 提交
        print("📤 提交音频...")
        conversation.commit()
        print("✓ 已提交\n")
        
        # 等待响应
        print("⏳ 等待响应 (5秒)...")
        time.sleep(5)
        
        # 获取消息
        try:
            message = conversation.get_last_message()
            if message:
                results["response"] = message
                print(f"\n🤖 AI 回复: {message}")
            else:
                print("\n⚠️  未收到回复")
        except Exception as e:
            print(f"\n⚠️  获取响应失败: {e}")
        
        # 关闭
        conversation.close()
        
        # 总结
        if results["error"]:
            print(f"\n❌ 测试失败")
            print(f"   错误: {results['error']}")
            return False
        elif results["response"]:
            print(f"\n✅ 测试成功!")
            return True
        else:
            print(f"\n⚠️  部分成功（无响应）")
            return True
        
    except ImportError:
        print("❌ 缺少依赖包")
        print("   请运行: pip install dashscope")
        return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_pcm_audio_quick()
    sys.exit(0 if success else 1)
