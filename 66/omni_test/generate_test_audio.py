"""
生成 PCM 测试音频
用于测试 Qwen Omni SDK 的音频功能
"""

import os
import struct
import math

def generate_pcm_audio(
    duration_seconds: float = 2.0,
    sample_rate: int = 16000,
    frequency: float = 440.0,
    output_file: str = "test_audio.pcm"
) -> str:
    """
    生成简单的 PCM 音频（正弦波）
    
    Args:
        duration_seconds: 音频时长（秒）
        sample_rate: 采样率（Hz）
        frequency: 频率（Hz，440Hz 是 A4 音调）
        output_file: 输出文件名
    
    Returns:
        输出文件路径
    """
    
    print(f"🎵 生成 PCM 测试音频...")
    print(f"   时长: {duration_seconds}s")
    print(f"   采样率: {sample_rate} Hz")
    print(f"   频率: {frequency} Hz")
    
    # 计算采样数
    num_samples = int(sample_rate * duration_seconds)
    
    # 生成音频数据
    audio_data = bytearray()
    amplitude = 32767  # 16-bit 最大值
    
    for i in range(num_samples):
        # 生成正弦波
        sample = amplitude * math.sin(2 * math.pi * frequency * i / sample_rate)
        sample = int(sample)
        
        # 转换为 16-bit PCM (小端字节序)
        sample_bytes = struct.pack('<h', max(-32768, min(32767, sample)))
        audio_data.extend(sample_bytes)
    
    # 写入文件
    with open(output_file, "wb") as f:
        f.write(audio_data)
    
    file_size_kb = len(audio_data) / 1024
    print(f"✓ 已生成: {output_file} ({file_size_kb:.1f} KB)")
    
    return output_file


def generate_pcm_silence(
    duration_seconds: float = 1.0,
    sample_rate: int = 16000,
    output_file: str = "silence.pcm"
) -> str:
    """
    生成静音 PCM 音频
    """
    
    print(f"🔇 生成静音音频...")
    print(f"   时长: {duration_seconds}s")
    
    num_samples = int(sample_rate * duration_seconds)
    
    # 直接生成零字节
    audio_data = b'\x00' * (num_samples * 2)  # 2 字节每样本 (16-bit)
    
    with open(output_file, "wb") as f:
        f.write(audio_data)
    
    file_size_kb = len(audio_data) / 1024
    print(f"✓ 已生成: {output_file} ({file_size_kb:.1f} KB)")
    
    return output_file


def test_pcm_audio():
    """测试使用生成的 PCM 音频"""
    
    import base64
    
    print("\n" + "="*70)
    print("测试生成的 PCM 音频".center(70))
    print("="*70 + "\n")
    
    # 生成音频
    audio_file = generate_pcm_audio(duration_seconds=2.0, frequency=440.0)
    
    # 读取并编码
    print(f"\n📚 读取音频文件...")
    with open(audio_file, "rb") as f:
        audio_data = f.read()
    
    audio_b64 = base64.b64encode(audio_data).decode()
    
    print(f"✓ 音频大小: {len(audio_data)} 字节")
    print(f"✓ Base64 长度: {len(audio_b64)} 字符")
    
    # 尝试连接并发送
    print(f"\n🚀 测试发送到 Qwen Omni...")
    
    try:
        from dashscope.audio.qwen_omni import OmniRealtimeConversation, OmniRealtimeCallback, MultiModality
        import dashscope
        import time
        
        dashscope.api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")
        
        class TestCallback(OmniRealtimeCallback):
            def on_open(self):
                print("✓ 连接成功")
            
            def on_event(self, response):
                event_type = response.get("type", "")
                if "error" in event_type.lower():
                    print(f"❌ 错误: {response.get('error', {}).get('message')}")
                elif "text" in event_type and "delta" in event_type:
                    delta = response.get("delta", "")
                    print(f"🤖 {delta}", end="", flush=True)
            
            def on_close(self, code, msg):
                print(f"\n✓ 连接关闭")
        
        callback = TestCallback()
        conversation = OmniRealtimeConversation(
            model="qwen3.5-omni-plus-realtime",
            callback=callback
        )
        
        conversation.connect()
        print("✓ WebSocket 已连接\n")
        
        conversation.update_session(
            output_modalities=[MultiModality.TEXT],
            voice="Tina"
        )
        print("✓ 会话已配置\n")
        
        # 追加音频
        print("📤 追加音频...")
        conversation.append_audio(audio_b64)
        print("✓ 音频已追加")
        
        # 提交
        print("📤 提交音频...")
        conversation.commit()
        print("✓ 已提交\n")
        
        # 等待响应
        print("⏳ 等待响应...")
        time.sleep(3)
        
        # 获取消息
        message = conversation.get_last_message()
        if message:
            print(f"\n✅ AI 回复: {message}")
            return True
        else:
            print(f"\n⚠️  未收到回复")
            return False
        
    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        try:
            conversation.close()
        except:
            pass


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    print("\n╔" + "="*68 + "╗")
    print("║" + "PCM 测试音频生成器".center(70) + "║")
    print("╚" + "="*68 + "╝")
    
    print("\n📋 选择操作:\n")
    print("  1. 生成简单测试音频")
    print("  2. 生成静音音频")
    print("  3. 测试生成的音频")
    print("  4. 全部执行")
    print("  5. 退出")
    
    choice = input("\n请选择 (1-5): ").strip()
    
    if choice == "1":
        generate_pcm_audio()
    elif choice == "2":
        generate_pcm_silence()
    elif choice == "3":
        test_pcm_audio()
    elif choice == "4":
        generate_pcm_audio()
        generate_pcm_silence()
        test_pcm_audio()
    elif choice == "5":
        print("👋 再见!")
    else:
        print("❌ 无效选项")
