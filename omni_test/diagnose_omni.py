"""
Qwen Omni 综合诊断工具
诊断 "Access denied" 问题并提供解决方案
"""

import os
import sys
import time
import base64
import struct
from dotenv import load_dotenv

load_dotenv()

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY") or "sk-67d1be1cac0649b9a8839d2328bbb845"


class Diagnostic:
    """综合诊断工具"""
    
    def __init__(self):
        self.results = {}
        self.issues = []
        self.suggestions = []
    
    def print_header(self, title):
        """打印小标题"""
        print(f"\n{'='*70}")
        print(f"  {title}")
        print(f"{'='*70}")
    
    def check_api_key(self):
        """检查 API 密钥"""
        self.print_header("1️⃣  API 密钥检查")
        
        if not DASHSCOPE_API_KEY:
            print("❌ API 密钥未设置")
            self.issues.append("API 密钥未找到")
            return False
        
        key_preview = DASHSCOPE_API_KEY[:20] + "...***"
        print(f"✓ API 密钥已配置: {key_preview}")
        self.results["api_key"] = True
        return True
    
    def check_dependencies(self):
        """检查依赖包"""
        self.print_header("2️⃣  依赖包检查")
        
        required = {
            "dashscope": "DashScope SDK",
            "dotenv": "Environment variables",
        }
        
        optional = {
            "librosa": "MP3 转换 (audiodub)",
            "pydub": "MP3 转换 (pydub)",
            "numpy": "数值计算",
        }
        
        missing_required = []
        missing_optional = []
        
        for module, desc in required.items():
            try:
                __import__(module)
                print(f"✓ {desc:30} ({module})")
            except ImportError:
                print(f"❌ {desc:30} ({module})")
                missing_required.append(module)
        
        print()
        
        for module, desc in optional.items():
            try:
                __import__(module)
                print(f"✓ {desc:30} ({module})")
            except ImportError:
                print(f"⚠️  {desc:30} ({module})")
                missing_optional.append(module)
        
        if missing_required:
            self.issues.append(f"缺少必需包: {', '.join(missing_required)}")
            self.suggestions.append(f"pip install dashscope python-dotenv")
            return False
        
        if missing_optional:
            print(f"\n💡 可选: pip install librosa pydub")
        
        self.results["dependencies"] = True
        return True
    
    def check_audio_files(self):
        """检查音频文件"""
        self.print_header("3️⃣  音频文件检查")
        
        pcm_files = {
            "test_audio.pcm": "生成的测试音频",
            "complex_audio.pcm": "复杂测试音频",
        }
        
        mp3_files = {
            "output.mp3": "原始 MP3 文件（需转换）",
        }
        
        found = {}
        
        for fname, desc in pcm_files.items():
            if os.path.exists(fname):
                size = os.path.getsize(fname)
                print(f"✓ {fname:25} ({size:>10} 字节) - {desc}")
                found[fname] = size
            else:
                print(f"⚠️  {fname:25} 未找到")
        
        for fname, desc in mp3_files.items():
            if os.path.exists(fname):
                size = os.path.getsize(fname)
                print(f"⚠️  {fname:25} ({size:>10} 字节) - {desc}")
                print(f"\n   ⚠️  提示: {fname} 是 MP3 格式，不支持")
                print(f"   💡 需要转换: python mp3_to_pcm.py {fname}")
                self.suggestions.append(f"转换 {fname}: python mp3_to_pcm.py {fname}")
        
        if not found:
            print("\n⚠️  未找到 PCM 音频文件")
            print("   需要生成: python gen_audio.py")
            self.suggestions.append("生成 PCM 音频: python gen_audio.py")
            return False
        
        self.results["audio_files"] = True
        return True
    
    def verify_pcm_format(self):
        """验证 PCM 格式"""
        self.print_header("4️⃣  PCM 格式验证")
        
        pcm_files = [f for f in os.listdir(".") if f.endswith(".pcm")]
        
        if not pcm_files:
            print("⚠️  没有 PCM 文件需要验证")
            return True
        
        for pcm_file in pcm_files:
            try:
                size = os.path.getsize(pcm_file)
                duration_s = size / 32000  # 16kHz, 16-bit, mono
                
                with open(pcm_file, "rb") as f:
                    sample1 = struct.unpack('<h', f.read(2))[0]
                    sample2 = struct.unpack('<h', f.read(2))[0]
                
                if -32768 <= sample1 <= 32767 and -32768 <= sample2 <= 32767:
                    print(f"✓ {pcm_file}")
                    print(f"  - 大小: {size} 字节 ({size/1024:.1f} KB)")
                    print(f"  - 时长: {duration_s:.2f} 秒")
                    print(f"  - 格式: PCM16, 16kHz, 单声道 ✓")
                else:
                    print(f"⚠️  {pcm_file} - 采样范围异常")
                    self.issues.append(f"{pcm_file} 格式可能有问题")
            
            except Exception as e:
                print(f"❌ {pcm_file} - 验证出错: {e}")
                self.issues.append(f"无法验证 {pcm_file}")
        
        self.results["pcm_format"] = True
        return True
    
    def test_connection(self):
        """测试 WebSocket 连接"""
        self.print_header("5️⃣  WebSocket 连接测试")
        
        try:
            from dashscope.audio.qwen_omni import OmniRealtimeConversation, OmniRealtimeCallback, MultiModality
            import dashscope
            
            dashscope.api_key = DASHSCOPE_API_KEY
            
            print("🔗 连接到 Qwen Omni...")
            
            callback = OmniRealtimeCallback()
            connected = [False]
            error = [None]
            
            def on_open():
                connected[0] = True
                print("✓ WebSocket 已连接")
            
            def on_event(response):
                resp_type = response.get("type", "")
                if "error" in resp_type.lower():
                    error[0] = response.get("error", {})
            
            def on_close(code, msg):
                print(f"✓ WebSocket 已关闭 (code={code})")
            
            callback.on_open = on_open
            callback.on_event = on_event
            callback.on_close = on_close
            
            conversation = OmniRealtimeConversation(
                model="qwen3.5-omni-plus-realtime",
                callback=callback
            )
            
            conversation.connect()
            time.sleep(1)
            
            if connected[0]:
                print("✓ 连接测试成功")
                conversation.close()
                self.results["connection"] = True
                return True
            else:
                print("❌ 无法连接")
                self.issues.append("无法建立 WebSocket 连接")
                return False
        
        except Exception as e:
            print(f"❌ 连接错误: {e}")
            self.issues.append(f"连接测试失败: {str(e)}")
            return False
    
    def test_audio_submit(self):
        """测试音频提交"""
        self.print_header("6️⃣  音频提交测试")
        
        # 查找 PCM 文件
        pcm_file = None
        for f in ["test_audio.pcm", "complex_audio.pcm"]:
            if os.path.exists(f):
                pcm_file = f
                break
        
        if not pcm_file:
            print("⚠️  没有 PCM 文件用于测试")
            print("   需要先运行: python gen_audio.py")
            self.suggestions.append("生成 PCM 音频: python gen_audio.py")
            return False
        
        try:
            from dashscope.audio.qwen_omni import OmniRealtimeConversation, OmniRealtimeCallback, MultiModality
            import dashscope
            
            dashscope.api_key = DASHSCOPE_API_KEY
            
            print(f"📤 测试从 {pcm_file} 提交音频...")
            
            # 读取音频
            with open(pcm_file, "rb") as f:
                audio_data = f.read()
            
            audio_b64 = base64.b64encode(audio_data).decode()
            print(f"✓ 音频已编码 ({len(audio_b64)} 字符)")
            
            # 连接和提交
            callback = OmniRealtimeCallback()
            results = {"success": False, "error": None}
            
            def on_event(response):
                resp_type = response.get("type", "")
                if "error" in resp_type.lower():
                    results["error"] = response.get("error", {}).get("message")
            
            def on_close(code, msg):
                pass
            
            callback.on_event = on_event
            callback.on_close = on_close
            
            conversation = OmniRealtimeConversation(
                model="qwen3.5-omni-plus-realtime",
                callback=callback
            )
            
            conversation.connect()
            time.sleep(1)
            
            print("⚙️  配置会话...")
            conversation.update_session(
                output_modalities=[MultiModality.TEXT],
                voice="Tina"
            )
            print("✓ 会话已配置")
            
            print("📤 追加音频...")
            conversation.append_audio(audio_b64)
            print("✓ 音频已追加")
            
            print("📤 提交音频...")
            conversation.commit()
            print("✓ 已提交")
            
            time.sleep(2)
            
            if results["error"]:
                print(f"\n❌ 服务器错误: {results['error']}")
                if "Access denied" in results["error"]:
                    self.issues.append("服务器拒绝音频提交")
                    self.suggestions.append("检查 API 密钥是否有音频权限")
                    self.suggestions.append("确认账户余额充足")
            else:
                print("\n✓ 音频提交成功（无明显错误）")
                results["success"] = True
            
            conversation.close()
            self.results["audio_submit"] = results["success"]
            return results["success"]
        
        except Exception as e:
            print(f"❌ 错误: {e}")
            self.issues.append(f"音频提交失败: {str(e)}")
            return False
    
    def generate_report(self):
        """生成诊断报告"""
        self.print_header("📋 诊断报告总结")
        
        passed = sum(1 for v in self.results.values() if v)
        total = len(self.results)
        
        print(f"\n✓ 通过检查: {passed}/{total}")
        
        if self.issues:
            print(f"\n⚠️  发现的问题:")
            for i, issue in enumerate(self.issues, 1):
                print(f"  {i}. {issue}")
        else:
            print(f"\n✅ 没有发现问题!")
        
        if self.suggestions:
            print(f"\n💡 建议：")
            for i, suggestion in enumerate(self.suggestions, 1):
                print(f"  {i}. {suggestion}")
        
        # 最终诊断
        print(f"\n{'='*70}")
        if passed == total and not self.issues:
            print("✅ 系统就绪！您可以运行:")
            print("   python test_pcm_quick.py")
        elif passed >= total - 1:
            print("⚠️  系统基本就绪，但有些问题需要解决:")
            for suggestion in self.suggestions:
                print(f"   - {suggestion}")
        else:
            print("❌ 有多个问题需要解决:")
            for suggestion in self.suggestions:
                print(f"   - {suggestion}")
        print(f"{'='*70}\n")
    
    def run_all(self):
        """运行所有诊断"""
        print("\n╔" + "="*68 + "╗")
        print("║" + "Qwen Omni 综合诊断工具".center(70) + "║")
        print("║" + "(Access Denied 问题排查)".center(70) + "║")
        print("╚" + "="*68 + "╝")
        
        self.check_api_key()
        self.check_dependencies()
        self.check_audio_files()
        self.verify_pcm_format()
        self.test_connection()
        self.test_audio_submit()
        self.generate_report()


def main():
    """主函数"""
    diagnostic = Diagnostic()
    diagnostic.run_all()


if __name__ == "__main__":
    main()
