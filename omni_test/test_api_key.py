# -*- coding: utf-8 -*-
"""
验证 API 密钥和可用模型
"""

import os
import sys
import asyncio
import httpx
from pathlib import Path
from dotenv import load_dotenv

# 设置 UTF-8 编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

load_dotenv()

QWEN_API_KEY = os.getenv("QWEN_API_KEY")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

async def test_models():
    """测试不同的模型和 API 端点"""
    
    print("="*60)
    print("API 密钥和模型诊断")
    print("="*60)
    
    # 检查密钥
    print(f"\n📋 密钥检查:")
    print(f"  QWEN_API_KEY: {QWEN_API_KEY[:15]}..." if QWEN_API_KEY else "  QWEN_API_KEY: [未设置]")
    print(f"  DASHSCOPE_API_KEY: {DASHSCOPE_API_KEY[:15]}..." if DASHSCOPE_API_KEY else "  DASHSCOPE_API_KEY: [未设置]")
    
    if not QWEN_API_KEY:
        print("\n✗ 错误: QWEN_API_KEY 未设置")
        return
    
    # 测试不同的 API 端点和模型
    test_configs = [
        {
            "name": "qwen3.5-flash (文本模型，兼容模式)",
            "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen3.5-flash",
            "messages": [{"role": "user", "content": "你好"}],
        },
        {
            "name": "qwen3.5-omni-plus (多模态模型，兼容模式)",
            "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen3.5-omni-plus",
            "messages": [{"role": "user", "content": "你好"}],
        },
        {
            "name": "qwen3.5-omni-plus-realtime (WebSocket 模型)",
            "api_base": "wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
            "model": "qwen3.5-omni-plus-realtime",
            "note": "WebSocket 模型（不使用 HTTP POST）",
        },
    ]
    
    print(f"\n🔍 测试各个模型:\n")
    
    for config in test_configs:
        print(f"测试: {config['name']}")
        
        if "note" in config:
            print(f"  备注: {config['note']}")
            continue
        
        api_base = config['api_base']
        model = config['model']
        url = f"{api_base}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {QWEN_API_KEY}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": model,
            "messages": config['messages'],
            "max_tokens": 100,
        }
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=payload, headers=headers)
                
                if response.status_code == 200:
                    print(f"  ✓ 成功 (200)")
                    result = response.json()
                    if "choices" in result and result["choices"]:
                        content = result["choices"][0].get("message", {}).get("content", "")
                        print(f"    响应: {content[:50]}...")
                else:
                    print(f"  ✗ 失败 ({response.status_code})")
                    try:
                        error = response.json()
                        if "error" in error:
                            print(f"    错误: {error['error'].get('message', error['error'])}")
                    except:
                        print(f"    响应: {response.text[:100]}")
        
        except Exception as e:
            print(f"  ✗ 异常: {str(e)[:100]}")
        
        print()
    
    # 显示建议
    print("\n💡 建议:")
    print("  1. 确保 API 密钥正确且有效")
    print("  2. 兼容模式 API 可能与标准 API 有差异")
    print("  3. 考虑使用 WebSocket realtime API (qwen3.5-omni-plus-realtime)")
    print("  4. 检查账户配额和服务限制")

if __name__ == "__main__":
    asyncio.run(test_models())
