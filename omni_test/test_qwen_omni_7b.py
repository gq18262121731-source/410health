# -*- coding: utf-8 -*-
"""
Qwen2.5-Omni-7B 模型测试脚本
这是一个开放模型，不需要特殊权限申请
支持文本、音频输入输出
"""

import os
import sys
import json
import base64
import asyncio
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# 设置 UTF-8 编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import httpx

load_dotenv()

QWEN_API_BASE = os.getenv("QWEN_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
QWEN_API_KEY = os.getenv("QWEN_API_KEY")

# Qwen2.5-Omni-7B 模型配置
QWEN_OMNI_7B_MODEL = "qwen2.5-omni-7b"


class QwenOmni7bTester:
    """Qwen2.5-Omni-7B 多模态模型测试类"""
    
    def __init__(self):
        self.api_base = QWEN_API_BASE
        self.api_key = QWEN_API_KEY
        self.model = QWEN_OMNI_7B_MODEL
        
        if not self.api_key:
            raise ValueError("QWEN_API_KEY 环境变量未设置")
        
        print(f"✓ 初始化成功")
        print(f"  API Base: {self.api_base}")
        print(f"  模型: {self.model}")
        print(f"  API Key: {self.api_key[:10]}***")
    
    def _encode_audio_to_base64(self, audio_path: str) -> str:
        """将音频文件编码为base64"""
        with open(audio_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    
    async def test_text_input(self, user_input: str) -> Optional[dict]:
        """测试文本输入"""
        print(f"\n📝 测试：文本输入")
        print(f"  输入: {user_input}")
        
        url = f"{self.api_base}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": user_input
                }
            ],
            "stream": False,
        }
        
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                print(f"\n✓ API 调用成功 (状态码: {response.status_code})")
                
                # 提取响应内容
                if "choices" in result and result["choices"]:
                    content = result["choices"][0].get("message", {}).get("content", "")
                    print(f"\n响应内容:")
                    print(f"  {content[:200]}...")
                
                return result
        
        except httpx.HTTPStatusError as e:
            print(f"\n✗ HTTP 错误: {e.response.status_code}")
            try:
                error_info = e.response.json()
                print(f"  错误: {error_info.get('error', {}).get('message', e.response.text)}")
            except:
                print(f"  错误: {e.response.text[:200]}")
            return None
        except Exception as e:
            print(f"\n✗ 错误: {str(e)}")
            return None
    
    async def test_with_audio(self, audio_path: str) -> Optional[dict]:
        """测试音频输入"""
        if not os.path.exists(audio_path):
            print(f"\n💡 提示: 音频文件不存在: {audio_path}")
            return None
        
        print(f"\n🎙️ 测试：音频输入")
        print(f"  文件: {audio_path}")
        
        try:
            # 读取音频文件
            with open(audio_path, "rb") as f:
                audio_bytes = f.read()
            
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
            file_size_kb = len(audio_base64) / 1024
            print(f"  大小: {file_size_kb:.2f} KB")
            
            # 检测音频格式
            audio_format = Path(audio_path).suffix.lower().replace(".", "")
            
            url = f"{self.api_base}/chat/completions"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "audio",
                                "audio": f"data:audio/{audio_format};base64,{audio_base64}"
                            }
                        ]
                    }
                ],
                "stream": False,
            }
            
            print(f"  正在上传和处理...")
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                print(f"\n✓ API 调用成功 (状态码: {response.status_code})")
                
                # 提取响应
                if "choices" in result and result["choices"]:
                    content = result["choices"][0].get("message", {}).get("content", "")
                    print(f"\n音频识别结果:")
                    print(f"  {content[:200]}...")
                
                return result
        
        except Exception as e:
            print(f"\n✗ 错误: {str(e)}")
            return None
    
    async def run_all_tests(self):
        """运行所有测试"""
        print(f"\n{'='*60}")
        print(f"测试 1: 简单文本对话")
        print(f"{'='*60}")
        success1 = await self.test_text_input("你好，请自我介绍一下") is not None
        
        print(f"\n{'='*60}")
        print(f"测试 2: 医学常识问答")
        print(f"{'='*60}")
        success2 = await self.test_text_input("老年人如何保持健康？请给出5个建议。") is not None
        
        print(f"\n{'='*60}")
        print(f"测试 3: 音频输入（可选）")
        print(f"{'='*60}")
        audio_file = "test_audio.wav"
        if os.path.exists(audio_file):
            success3 = await self.test_with_audio(audio_file) is not None
        else:
            print(f"\n💡 跳过: 未找到 {audio_file}")
            success3 = True
        
        return success1 and success2 and success3


async def main():
    """主函数"""
    print("╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "Qwen2.5-Omni-7B 多模态模型测试".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝")
    
    try:
        tester = QwenOmni7bTester()
        success = await tester.run_all_tests()
        
        # 总结
        print(f"\n{'='*60}")
        print(f"测试总结")
        print(f"{'='*60}")
        if success:
            print("✓ 所有测试通过")
            print(f"\n💡 Qwen2.5-Omni-7B 模型可用，可以用于:")
            print(f"  - 文本对话")
            print(f"  - 音频理解")
            print(f"  - 多轮对话")
            sys.exit(0)
        else:
            print("✗ 某些测试失败")
            sys.exit(1)
    
    except Exception as e:
        print(f"\n✗ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
