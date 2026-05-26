"""
Qwen Omni API 权限诊断和修复工具
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

print("="*70)
print("Qwen Omni API 诊断工具".center(70))
print("="*70)

api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")

if not api_key:
    print("\n❌ API Key 未设置")
    sys.exit(1)

print(f"\n✓ API Key: {api_key[:20]}***")

# 检查模块
print("\n\n【1】检查 DashScope SDK")
print("-" * 70)

try:
    from dashscope.audio.qwen_omni import OmniRealtimeConversation, OmniRealtimeCallback, MultiModality
    import dashscope
    print(f"✓ DashScope 已安装")
    print(f"✓ 版本: {dashscope.__version__}")
except ImportError as e:
    print(f"❌ DashScope 导入失败: {e}")
    sys.exit(1)

dashscope.api_key = api_key

# 测试连接
print("\n\n【2】测试 WebSocket 连接")
print("-" * 70)

class DiagnosticCallback(OmniRealtimeCallback):
    def __init__(self):
        super().__init__()
        self.connected = False
        self.error_msg = None
    
    def on_open(self):
        self.connected = True
        print("✓ WebSocket 连接成功")
    
    def on_event(self, response):
        event_type = response.get("type", "")
        if "error" in event_type.lower():
            error = response.get("error", {})
            self.error_msg = error.get("message", "Unknown error")
            print(f"⚠️  错误事件: {self.error_msg}")
    
    def on_close(self, code, msg):
        print(f"连接关闭 (代码: {code}, 信息: {msg})")

callback = DiagnosticCallback()
conversation = None

try:
    conversation = OmniRealtimeConversation(
        model="qwen3.5-omni-plus-realtime",
        callback=callback,
        url="wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
    )
    
    print("✓ 对话实例创建")
    print("正在连接...")
    
    conversation.connect()
    
    import time
    time.sleep(1)
    
    if callback.connected:
        print("✓ 连接已建立")
    else:
        print("❌ 连接失败")
        print(f"错误: {callback.error_msg}")

except Exception as e:
    print(f"❌ 连接异常: {str(e)}")
    import traceback
    traceback.print_exc()

finally:
    if conversation:
        try:
            conversation.close()
            print("✓ 连接已关闭")
        except:
            pass

# 诊断结果
print("\n\n【3】诊断结果和建议")
print("-" * 70)

if callback.connected:
    print("✅ WebSocket 连接成功")
    print("\n可能的问题:")
    print("  1. 会话配置问题 - 某些模式或参数不支持")
    print("  2. 模型权限问题 - qwen3.5-omni-plus-realtime 未开通")
    print("  3. 音频格式问题 - 只支持 PCM 格式，不支持 MP3")
    print("  4. 账户配额问题 - 余额不足或超出限制")
else:
    print("❌ WebSocket 连接失败")
    print("\n建议:")
    print("  1. 检查 API Key 是否正确和有效")
    print("  2. 确认账户有足够余额")
    print("  3. 确认 qwen3.5-omni-plus-realtime 模型已开通")
    print("  4. 检查网络连接和防火墙")

print("\n\n【4】推荐操作")
print("-" * 70)

print("""
1. 登录 DashScope 控制面板:
   https://dashscope.aliyuncs.com
   
2. 检查:
   ✓ 账户状态和余额
   ✓ 模型开通情况
   ✓ API Key 有效性
   
3. 如果问题仍存在:
   - 使用诊断脚本: python test_omni_diagnose_models.py
   - 查看官方文档: https://help.aliyun.com/zh/model-studio/
   - 联系技术支持
""")

print("="*70)
print("诊断完成")
print("="*70)
