"""
快速测试脚本 - Qwen3.5-Omni-Plus 语音建议
依赖较少，用于快速验证 API 连接
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

QWEN_API_BASE = os.getenv("QWEN_API_BASE")
QWEN_API_KEY = os.getenv("QWEN_API_KEY")
QWEN_OMNI_MODEL = os.getenv("QWEN_OMNI_MODEL")

def test_basic_connection():
    """测试基础连接"""
    print("="*60)
    print("Qwen3.5-Omni-Plus 基础连接测试")
    print("="*60)
    
    print(f"\n✓ 环境配置:")
    print(f"  • API Base: {QWEN_API_BASE}")
    print(f"  • Model: {QWEN_OMNI_MODEL}")
    print(f"  • API Key: {QWEN_API_KEY[:15]}***{'*'*20}")
    
    if not QWEN_API_KEY:
        print("\n✗ 错误: QWEN_API_KEY 未设置")
        return False
    
    print(f"\n正在测试连接...")
    
    try:
        import requests
        
        url = f"{QWEN_API_BASE}/chat/completions"
        headers = {
            "Authorization": f"Bearer {QWEN_API_KEY}",
            "Content-Type": "application/json",
        }
        
        # 简单的文本请求
        payload = {
            "model": QWEN_OMNI_MODEL,
            "messages": [{
                "role": "user",
                "content": "你好，这是一个测试。请简短回复。"
            }]
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        print(f"✓ 响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if "choices" in result:
                message = result["choices"][0]["message"]["content"]
                print(f"✓ 模型响应: {message}")
                print("\n✓ 连接测试成功！")
                return True
            else:
                print(f"✗ 意外的响应格式: {json.dumps(result, indent=2)}")
                return False
        else:
            print(f"✗ API 错误:")
            print(response.text)
            return False
    
    except ImportError:
        print("✗ 需要安装 requests 库:")
        print("   pip install requests")
        return False
    except Exception as e:
        print(f"✗ 错误: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_basic_connection()
    exit(0 if success else 1)
