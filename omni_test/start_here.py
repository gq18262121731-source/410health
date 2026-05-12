#!/usr/bin/env python3
"""
Qwen Omni PCM 音频 - 交互式入门指南
简化了菜单驱动的用户体验
"""

import os
import subprocess
import sys
from pathlib import Path


def print_banner(title):
    """打印横幅"""
    print("\n" + "="*70)
    print(f"  {title}".center(70))
    print("="*70 + "\n")


def print_step(number, title, description=""):
    """打印步骤"""
    print(f"{number}️⃣  {title}")
    if description:
        lines = description.split("\n")
        for line in lines:
            print(f"    {line}")


def check_file_exists(filename):
    """检查文件是否存在"""
    return os.path.exists(filename)


def run_script(script_name, description=""):
    """运行 Python 脚本"""
    print(f"\n🚀 运行 {script_name}...")
    if description:
        print(f"   {description}")
    print()
    
    try:
        result = subprocess.run([sys.executable, script_name], check=False)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def main():
    """主菜单"""
    
    print_banner("Qwen Omni PCM 音频 - 交互式入门指南")
    
    print("""
╭─────────────────────────────────────────────────────────────╮
│                                                               │
│  欢迎！快速消除您的 "Access denied" 错误              │
│                                                               │
│  问题：之前使用了 MP3 格式（不支持）                    │
│  解决：改用 PCM 格式（完全支持）✅                     │
│                                                               │
╰─────────────────────────────────────────────────────────────╯
    """)
    
    while True:
        print("\n📋 请选择一个选项:\n")
        
        print("  🚀 快速开始")
        print("    1. 一键设置（推荐首次运行）")
        print("    2. 仅生成测试音频")
        print("    3. 仅运行诊断检查")
        print("    4. 仅运行快速测试")
        
        print("\n  🔧 工具")
        print("    5. 完整交互式菜单测试")
        print("    6. MP3 转 PCM 转换器")
        print("    7. 系统诊断工具（详细版）")
        
        print("\n  📖 文档")
        print("    8. 打开快速参考卡 (QUICK_REFERENCE.md)")
        print("    9. 打开完整指南 (PCM_AUDIO_GUIDE.md)")
        print("   10. 打开问题分析 (FIX_ACCESS_DENIED.md)")
        print("   11. 打开方案总结 (SOLUTION_SUMMARY.md)")
        
        print("\n  📚 学习")
        print("   12. 显示快速开始教程")
        print("   13. 显示 API 快速查阅")
        print("   14. 显示故障排查指南")
        
        print("\n  退出")
        print("   15. 关闭程序")
        
        choice = input("\n请输入选项 (1-15): ").strip()
        
        # 快速开始
        if choice == "1":
            print_banner("一键设置 - 快速开始")
            
            print("这将:")
            print("  1. 生成 PCM 测试音频")
            print("  2. 运行系统诊断")
            print("  3. 执行快速测试")
            print()
            
            confirm = input("继续? (y/n): ").strip().lower()
            if confirm == "y":
                success = True
                
                print("\n📝 步骤 1: 生成 PCM 音频...")
                success = run_script("gen_audio.py") and success
                
                print("\n📝 步骤 2: 系统诊断...")
                success = run_script("diagnose_omni.py") and success
                
                print("\n📝 步骤 3: 快速测试...")
                success = run_script("test_pcm_quick.py") and success
                
                if success:
                    print_banner("✅ 一键设置完成！")
                    print("现在您可以:")
                    print("  • 使用 test_pcm_quick.py 进行快速测试")
                    print("  • 使用 test_omni_pcm.py 进行完整交互")
                    print("  • 在应用中集成音频处理")
                else:
                    print_banner("⚠️  设置部分失败")
                    print("请检查错误消息并查看文档")
        
        elif choice == "2":
            run_script("gen_audio.py", "生成 PCM 测试音频文件")
        
        elif choice == "3":
            run_script("diagnose_omni.py", "全面诊断系统和连接")
        
        elif choice == "4":
            run_script("test_pcm_quick.py", "快速自动化测试")
        
        elif choice == "5":
            run_script("test_omni_pcm.py", "完整交互式菜单")
        
        elif choice == "6":
            run_script("mp3_to_pcm.py", "转换现有的 MP3 文件到 PCM 格式")
        
        elif choice == "7":
            run_script("diagnose_omni.py", "详细诊断报告")
        
        # 文档
        elif choice == "8":
            open_file("QUICK_REFERENCE.md")
        
        elif choice == "9":
            open_file("PCM_AUDIO_GUIDE.md")
        
        elif choice == "10":
            open_file("FIX_ACCESS_DENIED.md")
        
        elif choice == "11":
            open_file("SOLUTION_SUMMARY.md")
        
        # 学习资源
        elif choice == "12":
            show_quickstart()
        
        elif choice == "13":
            show_api_reference()
        
        elif choice == "14":
            show_troubleshooting()
        
        # 退出
        elif choice == "15":
            print("\n👋 再见！\n")
            break
        
        else:
            print("\n❌ 无效选项，请重试")
        
        input("\n按 Enter 继续...")


def open_file(filename):
    """打开文件在默认编辑器"""
    print(f"\n📖 打开 {filename}...\n")
    
    if not os.path.exists(filename):
        print(f"❌ 文件不存在: {filename}")
        return
    
    if sys.platform == "win32":
        os.startfile(filename)
    elif sys.platform == "darwin":
        subprocess.run(["open", filename])
    else:
        subprocess.run(["xdg-open", filename])
    
    print(f"✓ {filename} 已打开")


def show_quickstart():
    """显示快速开始教程"""
    
    print_banner("⚡ 快速开始教程")
    
    tutorial = """
这是解决您的 "Access denied" 问题的 3 步指南。

【步骤 1】生成 PCM 音频文件
━━━━━━━━━━━━━━━━━━━━━━━━━
python gen_audio.py

会生成两个文件:
  • test_audio.pcm (2 秒, 440Hz 正弦波)
  • complex_audio.pcm (3 秒, 复杂音频)

【步骤 2】验证系统就绪
━━━━━━━━━━━━━━━━━━━━━━━━━
python diagnose_omni.py

检查:
  ✓ API 密钥配置
  ✓ 依赖包安装
  ✓ 音频文件存在
  ✓ PCM 格式有效
  ✓ WebSocket 连接
  ✓ 音频提交功能

【步骤 3】快速测试
━━━━━━━━━━━━━━━━━━━━━━━━━
python test_pcm_quick.py

完整的端到端测试:
  ✓ 连接到 Qwen Omni
  ✓ 配置会话
  ✓ 追加 PCM 音频
  ✓ 提交和等待响应
  ✓ 获取 AI 回复

【完成！】
━━━━━━━━━━━━━━━━━━━━━━━━━
现在您可以:
  • 集成到应用中
  • 从 MP3 转换音频
  • 自定义配置和语音选项

【核心代码示例】
━━━━━━━━━━━━━━━━━━━━━━━━━
from dashscope.audio.qwen_omni import OmniRealtimeConversation, MultiModality
import base64

conversation = OmniRealtimeConversation(
    model="qwen3.5-omni-plus-realtime",
    callback=your_callback
)

conversation.connect()
conversation.update_session(
    output_modalities=[MultiModality.TEXT],
    voice="Tina"
)

with open("test_audio.pcm", "rb") as f:
    audio_b64 = base64.b64encode(f.read()).decode()

conversation.append_audio(audio_b64)
conversation.commit()

import time
time.sleep(3)
message = conversation.get_last_message()
conversation.close()

【关键点】
━━━━━━━━━━━━━━━━━━━━━━━━━
✓ 必须使用 PCM 格式 (不能用 MP3)
✓ 采样率必须是 16000 Hz
✓ 比特深度必须是 16-bit
✓ 追加后必须调用 commit()
✓ 需要等待 2-3 秒以获得响应
✓ 关闭前必须调用 close()

【更多信息】
━━━━━━━━━━━━━━━━━━━━━━━━━
查看完整指南:
  • QUICK_REFERENCE.md    - 快速参考卡
  • PCM_AUDIO_GUIDE.md    - 详细使用指南
  • FIX_ACCESS_DENIED.md  - 问题原因分析
    """
    
    print(tutorial)


def show_api_reference():
    """显示 API 快速参考"""
    
    print_banner("API 快速参考")
    
    reference = """
【初始化】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from dashscope.audio.qwen_omni import OmniRealtimeConversation, MultiModality
import dashscope

dashscope.api_key = "your-api-key"

conversation = OmniRealtimeConversation(
    model="qwen3.5-omni-plus-realtime",
    callback=your_callback
)

【主要方法】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
conversation.connect()
  → 建立 WebSocket 连接到服务器

conversation.update_session(
    output_modalities=[MultiModality.TEXT],  # 或 AUDIO
    voice="Tina",                             # Tina, Daisy, Alfie, Chelsie
    enable_turn_detection=True,
    turn_detection_threshold=0.6
)
  → 配置会话参数

conversation.append_audio(audio_b64)
  → 追加 Base64 编码的 PCM 音频

conversation.commit()
  → 提交已追加的音频到服务器

message = conversation.get_last_message()
  → 获取最后一条 AI 消息

conversation.close()
  → 关闭连接并清理资源

【回调类】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from dashscope.audio.qwen_omni import OmniRealtimeCallback

class MyCallback(OmniRealtimeCallback):
    def on_open(self):
        # WebSocket 连接已建立
        print("Connected")
    
    def on_event(self, response):
        # 收到服务器事件
        event_type = response.get("type")
        if "error" in event_type:
            print("Error:", response.get("error"))
        elif "delta" in event_type and "text" in event_type:
            print(response.get("delta"), end="")
    
    def on_close(self, code, msg):
        # WebSocket 已关闭
        print(f"Closed: {code}")

【数据格式】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
音频编码:
  import base64
  audio_b64 = base64.b64encode(pcm_data).decode()

PCM 文件生成:
  import struct, math
  
  audio = bytearray()
  for i in range(32000):  # 2秒 @ 16kHz
      sample = int(32767 * math.sin(2*pi*440*i/16000))
      audio.extend(struct.pack('<h', sample))

【错误处理】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
try:
    conversation.connect()
except Exception as e:
    print(f"Connection error: {e}")

# 在 on_event 中检查错误
if "error" in response.get("type", ""):
    error_msg = response.get("error", {}).get("message")
    print(f"Server error: {error_msg}")

【常见参数】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
voice 选项:
  "Tina"      - 默认，清晰女声
  "Daisy"     - 温柔女声
  "Alfie"     - 男声
  "Chelsie"   - 自然女声

output_modalities:
  MultiModality.TEXT   - 文本输出
  MultiModality.AUDIO  - 音频输出

turn_detection_threshold: 0.0 - 1.0
  值越高，越容易结束用户发言

【完整示例】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
import base64, time
from dashscope.audio.qwen_omni import (
    OmniRealtimeConversation,
    OmniRealtimeCallback,
    MultiModality
)

class SimpleCallback(OmniRealtimeCallback):
    def on_open(self):
        print("✓ Connected")
    
    def on_event(self, response):
        if "delta" in response.get("type", ""):
            print(response.get("delta", ""), end="")

# 初始化
callback = SimpleCallback()
conversation = OmniRealtimeConversation(
    model="qwen3.5-omni-plus-realtime",
    callback=callback
)

# 连接和配置
conversation.connect()
conversation.update_session(
    output_modalities=[MultiModality.TEXT],
    voice="Tina"
)

# 读取音频
with open("test_audio.pcm", "rb") as f:
    audio_b64 = base64.b64encode(f.read()).decode()

# 提交
conversation.append_audio(audio_b64)
conversation.commit()

# 等待响应
time.sleep(3)
message = conversation.get_last_message()

# 清理
conversation.close()
    """
    
    print(reference)


def show_troubleshooting():
    """显示故障排查指南"""
    
    print_banner("故障排查指南")
    
    troubleshooting = """
【错误：Access denied】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
症状:
  websocket closed due to fin=1 opcode=8 data=b'\\x03\\xefAccess denied.'

原因:
  ❌ 使用了 MP3 格式而不是 PCM
  ❌ API 密钥无音频权限
  ❌ 账户余额不足

解决方案:
  1. 使用 PCM 格式:
     python gen_audio.py
     python test_pcm_quick.py
  
  2. 如果有 MP3 文件，转换它:
     python mp3_to_pcm.py your_file.mp3
  
  3. 检查 API 密钥和账户


【错误：Connection refused】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
症状:
  Failed to establish connection to Qwen Omni

原因:
  ❌ 网络连接问题
  ❌ 防火墙阻止
  ❌ 代理配置问题

解决方案:
  1. 检查网络连接:
     ping dashscope.aliyuncs.com
  
  2. 检查防火墙:
     确保 443 端口未被阻止
  
  3. 运行诊断:
     python diagnose_omni.py


【错误：ModuleNotFoundError: dashscope】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
症状:
  No module named 'dashscope'

解决方案:
  pip install dashscope>=1.23.9


【错误：No audio files found】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
症状:
  No PCM files found

解决方案:
  1. 生成测试音频:
     python gen_audio.py
  
  2. 检查文件:
     ls -la *.pcm


【无响应】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
症状:
  追加音频后没有响应

原因:
  ❌ 等待时间不足
  ❌ 没有调用 commit()
  ❌ API 密钥问题

解决方案:
  1. 增加等待时间:
     time.sleep(5)  # 增加到 5 秒
  
  2. 确认调用了 commit():
     conversation.commit()  # 必须调用
  
  3. 验证 API 密钥:
     python diagnose_omni.py


【诊断步骤】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 运行综合诊断:
   python diagnose_omni.py
   
2. 检查输出结果:
   ✓ 通过检查: 绿色
   ⚠️ 警告: 黄色
   ❌ 失败: 红色
   
3. 跟随诊断建议
   
4. 如果仍有问题:
   a) 查看 FIX_ACCESS_DENIED.md
   b) 查看 PCM_AUDIO_GUIDE.md 故障排查部分
   c) 检查 DashScope 官方文档


【常见问题】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Q: 我可以使用 MP3 吗?
A: 不可以，必须使用 PCM16 格式

Q: 支持其他音频格式吗?
A: 仅验证了 PCM16，其他格式不推荐

Q: 音频质量要求是什么?
A: 16kHz, 16-bit, 单声道的 PCM

Q: 我该如何将现有音频转换为 PCM?
A: 使用 mp3_to_pcm.py: python mp3_to_pcm.py file.mp3

Q: 测试失败怎么办?
A: 查看 diagnose_omni.py 的输出，按建议操作


【获取帮助】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 快速参考卡:
   QUICK_REFERENCE.md
   
2. 完整使用指南:
   PCM_AUDIO_GUIDE.md
   
3. 问题原因分析:
   FIX_ACCESS_DENIED.md
   
4. API 参考:
   SDK_API_REFERENCE.md
   
5. 运行诊断工具:
   python diagnose_omni.py
    """
    
    print(troubleshooting)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 已取消\n")
    except Exception as e:
        print(f"\n❌ 错误: {e}\n")
        import traceback
        traceback.print_exc()
