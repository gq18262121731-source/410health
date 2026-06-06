"""
DashScope SDK 诊断 - 检查 OmniRealtimeConversation 的实际 API
"""

import os
from dotenv import load_dotenv

load_dotenv()

try:
    from dashscope.audio.qwen_omni import OmniRealtimeConversation, OmniRealtimeCallback
    import dashscope
    import inspect
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    exit(1)

dashscope.api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")

print("="*70)
print("DashScope SDK API 诊断".center(70))
print("="*70)

print("\n📦 检查导入的模块:\n")
print(f"dashscope 模块: {dashscope}")
print(f"OmniRealtimeConversation: {OmniRealtimeConversation}")
print(f"OmniRealtimeCallback: {OmniRealtimeCallback}")

print("\n\n🔍 OmniRealtimeConversation 类的方法和属性:\n")

# 获取类的所有成员
members = inspect.getmembers(OmniRealtimeConversation)

print("【公开方法】")
for name, obj in members:
    if not name.startswith('_') and callable(obj):
        try:
            sig = inspect.signature(obj)
            print(f"  • {name}{sig}")
        except:
            print(f"  • {name} (签名获取失败)")

print("\n【公开属性】")
for name, obj in members:
    if not name.startswith('_') and not callable(obj):
        print(f"  • {name}: {type(obj).__name__}")

print("\n【特殊方法】")
special_methods = [m[0] for m in members if m[0].startswith('__') and m[0].endswith('__')]
if special_methods:
    for method in special_methods[:10]:  # 只显示前10个
        print(f"  • {method}")
    if len(special_methods) > 10:
        print(f"  ... 和其他 {len(special_methods)-10} 个特殊方法")

print("\n\n📝 类的完整签名:\n")
try:
    sig = inspect.signature(OmniRealtimeConversation.__init__)
    print(f"OmniRealtimeConversation.__init__{sig}")
except Exception as e:
    print(f"❌ 无法获取签名: {e}")

print("\n\n📚 类的文档:\n")
if OmniRealtimeConversation.__doc__:
    print(OmniRealtimeConversation.__doc__)
else:
    print("（无文档）")

print("\n\n🧪 测试连接:\n")

try:
    # 创建简单回调
    class TestCallback(OmniRealtimeCallback):
        def on_open(self):
            print("✓ 连接已建立")
        def on_event(self, response):
            print(f"✓ 收到事件: {type(response).__name__}")
        def on_close(self, code, msg):
            print(f"✓ 连接已关闭")
    
    callback = TestCallback()
    conversation = OmniRealtimeConversation(
        model="qwen3.5-omni-plus-realtime",
        callback=callback,
        url="wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
    )
    
    print("✓ OmniRealtimeConversation 实例创建成功\n")
    print("【实例方法】")
    
    instance_methods = [m for m in dir(conversation) if not m.startswith('_') and callable(getattr(conversation, m))]
    for method in instance_methods:
        attr = getattr(conversation, method)
        try:
            sig = inspect.signature(attr)
            print(f"  • {method}{sig}")
        except:
            print(f"  • {method}() [签名获取失败]")
    
    print("\n正在尝试连接...")
    conversation.connect()
    print("✓ 连接成功")
    
    import time
    time.sleep(1)
    
    # 尝试找到合适的发送方法
    print("\n【尝试找到发送机制】")
    
    send_methods = [m for m in dir(conversation) if 'send' in m.lower() or 'write' in m.lower() or 'input' in m.lower()]
    print(f"包含 'send'/'write'/'input' 的方法: {send_methods}")
    
    # 检查是否有特定的属性
    print("\n【检查特定属性】")
    special_attrs = ['input_stream', 'stdin', 'input', 'output', '_stdin', '_input', 'thread']
    for attr in special_attrs:
        if hasattr(conversation, attr):
            val = getattr(conversation, attr)
            print(f"  • {attr}: {type(val).__name__} = {val}")
    
    conversation.close()
    
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("诊断完成")
print("="*70)
