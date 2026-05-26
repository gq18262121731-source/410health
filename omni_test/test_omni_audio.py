"""
Qwen3.5-Omni-Plus 多模态语音交互测试脚本
支持语音输入问题，获得语音输出的答案
"""

import os
import sys

# 设置 UTF-8 编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import json
import base64
import asyncio
from pathlib import Path
from typing import Optional
import httpx
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置
QWEN_API_BASE = os.getenv("QWEN_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
QWEN_API_KEY = os.getenv("QWEN_API_KEY")
QWEN_OMNI_MODEL = os.getenv("QWEN_OMNI_MODEL", "qwen3.5-omni-plus")

class QwenOmniAudioTester:
    """Qwen Omni 语音交互测试类"""
    
    def __init__(self):
        self.api_base = QWEN_API_BASE
        self.api_key = QWEN_API_KEY
        self.model = QWEN_OMNI_MODEL
        
        if not self.api_key:
            raise ValueError("QWEN_API_KEY 环境变量未设置")
        
        print(f"✓ 初始化成功")
        print(f"  API Base: {self.api_base}")
        print(f"  Model: {self.model}")
        print(f"  API Key: {self.api_key[:10]}***")
    
    def _encode_audio_to_base64(self, audio_path: str) -> str:
        """将音频文件编码为base64"""
        with open(audio_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    
    async def test_text_input(self, user_input: str) -> Optional[dict]:
        """测试文本输入，获取文本和音频输出"""
        print(f"\n📝 测试：文本输入 → 多模态输出")
        print(f"输入问题: {user_input}")
        
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
            # Omni模型特定参数
            "parameters": {
                "audio": {
                    "input": False,  # 不使用音频输入
                    "output": True   # 启用音频输出
                }
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                print(f"\n✓ API 调用成功")
                print(f"响应状态: {response.status_code}")
                
                # 打印完整响应
                print(f"\n响应内容:")
                print(json.dumps(result, indent=2, ensure_ascii=False))
                
                return result
        
        except httpx.HTTPStatusError as e:
            print(f"\n✗ HTTP 错误: {e.response.status_code}")
            print(f"错误信息: {e.response.text}")
            return None
        except Exception as e:
            print(f"\n✗ 错误: {str(e)}")
            return None
    
    async def test_audio_input(self, audio_path: str, question: Optional[str] = None) -> Optional[dict]:
        """测试音频输入，获取文本和音频输出"""
        if not os.path.exists(audio_path):
            print(f"✗ 音频文件不存在: {audio_path}")
            return None
        
        print(f"\n🎙️ 测试：音频输入 → 多模态输出")
        print(f"音频文件: {audio_path}")
        
        # 检测音频格式
        audio_format = Path(audio_path).suffix.lower().replace(".", "")
        if audio_format not in ["wav", "mp3", "m4a", "aac", "opus", "flac"]:
            print(f"⚠️  不支持的音频格式: {audio_format}")
            return None
        
        try:
            # 编码音频
            print(f"正在编码音频文件...")
            audio_base64 = self._encode_audio_to_base64(audio_path)
            file_size_mb = len(audio_base64) / (1024 * 1024)
            print(f"✓ 编码成功 (大小: {file_size_mb:.2f} MB)")
            
            url = f"{self.api_base}/chat/completions"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            
            # 构建消息
            messages = []
            
            # 添加音频内容
            if question:
                # 如果提供了问题，同时包含音频和文本
                print(f"用户问题: {question}")
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": question
                        },
                        {
                            "type": "audio",
                            "audio": f"data:audio/{audio_format};base64,{audio_base64}"
                        }
                    ]
                })
            else:
                # 仅音频
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "audio",
                            "audio": f"data:audio/{audio_format};base64,{audio_base64}"
                        }
                    ]
                })
            
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "parameters": {
                    "audio": {
                        "input": True,   # 启用音频输入
                        "output": True   # 启用音频输出
                    }
                }
            }
            
            print(f"正在调用 API...")
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                print(f"\n✓ API 调用成功")
                print(f"响应状态: {response.status_code}")
                
                # 打印响应
                print(f"\n响应内容:")
                print(json.dumps(result, indent=2, ensure_ascii=False))
                
                # 如果响应中包含音频，尝试提取
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0].get("message", {}).get("content", [])
                    if isinstance(content, list):
                        for item in content:
                            if item.get("type") == "audio" and "audio" in item:
                                audio_data = item["audio"]
                                if isinstance(audio_data, str) and audio_data.startswith("data:"):
                                    output_path = "qwen_output.wav"
                                    audio_base64_content = audio_data.split(",")[-1]
                                    with open(output_path, "wb") as f:
                                        f.write(base64.b64decode(audio_base64_content))
                                    print(f"\n✓ 音频响应已保存: {output_path}")
                
                return result
        
        except Exception as e:
            print(f"\n✗ 错误: {str(e)}")
            return None
    
    async def test_simple_conversation(self):
        """测试简单文本对话"""
        print("\n" + "="*60)
        print("测试 1: 简单文本对话")
        print("="*60)
        
        result = await self.test_text_input("你好，请介绍一下你自己。")
        return result is not None
    
    async def test_with_audio_file(self, audio_path: str):
        """测试带音频文件的对话"""
        print("\n" + "="*60)
        print(f"测试 2: 音频文件输入")
        print("="*60)
        
        result = await self.test_audio_input(audio_path)
        return result is not None


async def main():
    """主函数"""
    print("╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "Qwen3.5-Omni-Plus 多模态语音交互测试".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝")
    
    try:
        # 初始化测试机
        tester = QwenOmniAudioTester()
        
        # 测试 1: 文本输入
        success1 = await tester.test_simple_conversation()
        
        # 测试 2: 如果存在音频文件，测试音频输入
        audio_test_file = "test_audio.wav"
        if os.path.exists(audio_test_file):
            success2 = await tester.test_with_audio_file(audio_test_file)
        else:
            print(f"\n💡 提示: 未找到 {audio_test_file}")
            print(f"   如果需要测试音频输入，请提供音频文件")
            success2 = True
        
        # 总结
        print("\n" + "="*60)
        print("测试总结")
        print("="*60)
        if success1:
            print("✓ 文本输入测试: 通过")
        else:
            print("✗ 文本输入测试: 失败")
        
        if success2:
            print("✓ 音频输入测试: 通过 (或跳过)")
        else:
            print("✗ 音频输入测试: 失败")
        
    except Exception as e:
        print(f"\n✗ 初始化失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
