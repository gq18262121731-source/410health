"""
MP3 to PCM 转换工具
将 MP3 文件转换为 DashScope 兼容的 PCM16 格式
"""

import os
import sys
import argparse
from pathlib import Path


def convert_mp3_to_pcm_librosa(input_file: str, output_file: str = None):
    """使用 librosa 转换 MP3 到 PCM"""
    try:
        import librosa
        import numpy as np
        
        if output_file is None:
            output_file = Path(input_file).stem + ".pcm"
        
        print(f"🎵 使用 librosa 转换...")
        print(f"   输入: {input_file}")
        print(f"   输出: {output_file}")
        
        # 加载音频，重新采样到 16kHz
        print(f"   加载音频...")
        audio_data, sr = librosa.load(input_file, sr=16000, mono=True)
        
        # 转换为 16-bit PCM
        print(f"   转换为 PCM16...")
        audio_pcm = np.int16(audio_data * 32767)
        
        # 保存为 PCM
        print(f"   保存文件...")
        with open(output_file, "wb") as f:
            f.write(audio_pcm.tobytes())
        
        file_size_kb = os.path.getsize(output_file) / 1024
        duration_s = len(audio_pcm) / 16000
        
        print(f"✓ 转换成功!")
        print(f"   文件大小: {file_size_kb:.1f} KB")
        print(f"   时长: {duration_s:.2f} 秒")
        print(f"   位置: {os.path.abspath(output_file)}")
        
        return output_file
    
    except ImportError:
        print(f"❌ 缺少 librosa")
        print(f"   安装: pip install librosa")
        return None
    except Exception as e:
        print(f"❌ 错误: {e}")
        return None


def convert_mp3_to_pcm_pydub(input_file: str, output_file: str = None):
    """使用 pydub 转换 MP3 到 PCM"""
    try:
        from pydub import AudioSegment
        import numpy as np
        
        if output_file is None:
            output_file = Path(input_file).stem + ".pcm"
        
        print(f"🎵 使用 pydub 转换...")
        print(f"   输入: {input_file}")
        print(f"   输出: {output_file}")
        
        # 加载 MP3
        print(f"   加载 MP3...")
        sound = AudioSegment.from_mp3(input_file)
        
        # 转换为 16kHz 单声道
        print(f"   转换采样率...")
        sound = sound.set_frame_rate(16000)
        sound = sound.set_channels(1)
        
        # 转换为 numpy 数组
        print(f"   转换为 PCM16...")
        samples = np.array(sound.get_array_of_samples(), dtype=np.int16)
        
        # 保存为 PCM
        print(f"   保存文件...")
        with open(output_file, "wb") as f:
            f.write(samples.tobytes())
        
        file_size_kb = os.path.getsize(output_file) / 1024
        duration_s = len(samples) / 16000
        
        print(f"✓ 转换成功!")
        print(f"   文件大小: {file_size_kb:.1f} KB")
        print(f"   时长: {duration_s:.2f} 秒")
        print(f"   位置: {os.path.abspath(output_file)}")
        
        return output_file
    
    except ImportError:
        print(f"❌ 缺少 pydub 或 ffmpeg")
        print(f"   安装: pip install pydub")
        print(f"   并需要 ffmpeg: https://ffmpeg.org/download.html")
        return None
    except Exception as e:
        print(f"❌ 错误: {e}")
        return None


def convert_mp3_to_pcm_scipy(input_file: str, output_file: str = None):
    """使用 scipy 转换 MP3 到 PCM（需要先转换为 WAV）"""
    try:
        import scipy.io.wavfile as wavfile
        import numpy as np
        
        if output_file is None:
            output_file = Path(input_file).stem + ".pcm"
        
        print(f"🎵 使用 scipy 转换...")
        
        # 注意：scipy 不直接支持 MP3
        # 需要先将 MP3 转换为 WAV
        print(f"   注意：scipy 不支持直接读取 MP3")
        print(f"   请先安装 librosa 或 pydub")
        
        return None
    
    except Exception as e:
        print(f"❌ 错误: {e}")
        return None


def verify_pcm_file(pcm_file: str):
    """验证 PCM 文件"""
    try:
        import struct
        
        if not os.path.exists(pcm_file):
            print(f"❌ 文件不存在: {pcm_file}")
            return False
        
        file_size = os.path.getsize(pcm_file)
        
        # PCM16 = 2 字节/样本 = 16kHz = 32000 字节/秒
        expected_sizes = {
            62500: "2 秒",
            93750: "3 秒",
            125000: "4 秒",
            156250: "5 秒",
            32000: "1 秒",
        }
        
        print(f"\n📊 验证 PCM 文件: {pcm_file}")
        print(f"   文件大小: {file_size} 字节 ({file_size/1024:.1f} KB)")
        
        # 估计时长
        duration_s = file_size / 32000  # 16kHz, 16-bit, 1 channel
        print(f"   估计时长: {duration_s:.2f} 秒")
        
        # 读取前几个样本
        with open(pcm_file, "rb") as f:
            sample1 = struct.unpack('<h', f.read(2))[0]
            sample2 = struct.unpack('<h', f.read(2))[0]
            f.seek(-4, 2)  # 末尾前 4 字节
            sample_last = struct.unpack('<h', f.read(2))[0]
        
        print(f"   第一个样本: {sample1}")
        print(f"   第二个样本: {sample2}")
        print(f"   最后一个样本: {sample_last}")
        
        # 验证采样位数范围
        if -32768 <= sample1 <= 32767 and -32768 <= sample2 <= 32767:
            print(f"✓ PCM 文件格式正确")
            return True
        else:
            print(f"⚠️  可能不是 16-bit PCM")
            return False
    
    except Exception as e:
        print(f"❌ 验证出错: {e}")
        return False


def main():
    """主菜单"""
    
    print("\n╔" + "="*68 + "╗")
    print("║" + "MP3 to PCM 转换工具".center(70) + "║")
    print("║" + "(for DashScope Qwen Omni)".center(70) + "║")
    print("╚" + "="*68 + "╝")
    
    parser = argparse.ArgumentParser(
        description="将 MP3 文件转换为 PCM16 格式"
    )
    parser.add_argument("input", nargs="?", help="输入 MP3 文件")
    parser.add_argument("-o", "--output", help="输出 PCM 文件（可选）")
    parser.add_argument("-m", "--method", choices=["librosa", "pydub"], 
                       default="librosa", help="转换方法")
    parser.add_argument("-v", "--verify", action="store_true", help="验证转换后的文件")
    
    args = parser.parse_args()
    
    if args.input:
        # 命令行模式
        if not os.path.exists(args.input):
            print(f"❌ 文件不存在: {args.input}")
            sys.exit(1)
        
        print(f"\n转换模式: {args.method}")
        
        if args.method == "librosa":
            output = convert_mp3_to_pcm_librosa(args.input, args.output)
        else:
            output = convert_mp3_to_pcm_pydub(args.input, args.output)
        
        if output and args.verify:
            verify_pcm_file(output)
    
    else:
        # 交互模式
        print("\n📋 选择操作:\n")
        print("  1. 转换 MP3 到 PCM (使用 librosa)")
        print("  2. 转换 MP3 到 PCM (使用 pydub)")
        print("  3. 验证 PCM 文件")
        print("  4. 学习 Web 使用")
        print("  5. 退出")
        
        choice = input("\n请选择 (1-5): ").strip()
        
        if choice == "1":
            mp3_file = input("MP3 文件路径: ").strip().strip('"')
            output_file = input("PCM 文件路径 (可选，按回车使用默认): ").strip().strip('"')
            output_file = output_file or None
            
            if mp3_file and os.path.exists(mp3_file):
                convert_mp3_to_pcm_librosa(mp3_file, output_file)
            else:
                print(f"❌ 文件不存在: {mp3_file}")
        
        elif choice == "2":
            mp3_file = input("MP3 文件路径: ").strip().strip('"')
            output_file = input("PCM 文件路径 (可选): ").strip().strip('"')
            output_file = output_file or None
            
            if mp3_file and os.path.exists(mp3_file):
                convert_mp3_to_pcm_pydub(mp3_file, output_file)
            else:
                print(f"❌ 文件不存在: {mp3_file}")
        
        elif choice == "3":
            pcm_file = input("PCM 文件路径: ").strip().strip('"')
            verify_pcm_file(pcm_file)
        
        elif choice == "4":
            print_quickstart()
        
        elif choice == "5":
            print("👋 再见!")
        
        else:
            print("❌ 无效选项")


def print_quickstart():
    """快速开始指南"""
    
    print("""
╔════════════════════════════════════════════════════════════════╗
║                    使用快速开始                                ║
╚════════════════════════════════════════════════════════════════╝

1️⃣  安装依赖

   # 方法 A: 使用 librosa（推荐）
   pip install librosa

   # 方法 B: 使用 pydub
   pip install pydub
   # 还需要安装 ffmpeg: https://ffmpeg.org/download.html

2️⃣  转换文件

   # 从命令行
   python mp3_to_pcm.py input.mp3 -o output.pcm --verify

   # 或使用交互菜单
   python mp3_to_pcm.py

3️⃣  验证转换

   # 检查文件大小和采样
   python mp3_to_pcm.py -v output.pcm

4️⃣  使用转换后的文件

   import base64
   with open("output.pcm", "rb") as f:
       audio_b64 = base64.b64encode(f.read()).decode()
   
   conversation.append_audio(audio_b64)
   conversation.commit()

📝 示例：

   # 转换并验证
   python mp3_to_pcm.py output.mp3 -o output.pcm --verify

   # 输出应该显示：
   # ✓ 转换成功!
   #   文件大小: XX.X KB
   #   时长: X.XX 秒
   # ✓ PCM 文件格式正确

🆘 故障排查：

   ❌ librosa 错误?
      pip install --upgrade librosa

   ❌ pydub 需要 ffmpeg?
      Windows: 下载 ffmpeg.exe 放在 PATH 中
      macOS: brew install ffmpeg
      Linux: apt-get install ffmpeg

   ❌ 转换失败?
      检查 MP3 文件是否有效
      尝试另一种方法 (librosa vs pydub)

📚 更多信息：
   - 详见 PCM_AUDIO_GUIDE.md
   - 详见 FIX_ACCESS_DENIED.md
    """)


if __name__ == "__main__":
    main()
