"""
直接生成 PCM 测试音频 - 无需交互
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
    """生成简单的 PCM 音频（正弦波）"""
    
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
    print(f"  位置: {os.path.abspath(output_file)}")
    
    return output_file


if __name__ == "__main__":
    # 生成 2 秒的 440Hz 正弦波
    generate_pcm_audio(duration_seconds=2.0, frequency=440.0)
    
    # 生成更复杂的音频（多个频率）
    print(f"\n🎵 生成复杂音频（多频率）...")
    
    num_samples = int(16000 * 3)  # 3 秒
    audio_data = bytearray()
    amplitude = 32767
    
    for i in range(num_samples):
        # 混合多个频率
        freq1 = 440 * math.sin(2 * math.pi * 0.5 * i / 16000)  # 基频
        freq2 = 880 * math.cos(2 * math.pi * 0.3 * i / 16000)  # 谐波
        
        sample = amplitude * math.sin(2 * math.pi * (freq1 + freq2) * i / 16000)
        sample = int(sample)
        
        sample_bytes = struct.pack('<h', max(-32768, min(32767, sample)))
        audio_data.extend(sample_bytes)
    
    with open("complex_audio.pcm", "wb") as f:
        f.write(audio_data)
    
    file_size_kb = len(audio_data) / 1024
    print(f"✓ 已生成: complex_audio.pcm ({file_size_kb:.1f} KB)")
    print(f"  位置: {os.path.abspath('complex_audio.pcm')}")
    
    print("\n✅ 所有音频已生成")
    print("\n📝 接下来运行:")
    print("   python test_omni_pcm.py")
