# -*- coding: utf-8 -*-
"""
Qwen Omni Realtime WebSocket API 测试
用于语音和音频交互的完整实现
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

import websockets

load_dotenv()

QWEN_API_KEY = os.getenv("QWEN_API_KEY")
QWEN_OMNI_REALTIME_MODEL = "qwen3.5-omni-plus-realtime"
QWEN_REALTIME_WS_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"


class QwenOmniRealtimeClient:
    """Qwen Omni Realtime WebSocket 客户端"""
    
    def __init__(self):
        self.api_key = QWEN_API_KEY
        self.model = QWEN_OMNI_REALTIME_MODEL
        self.ws_url = QWEN_REALTIME_WS_URL
        
        if not self.api_key:
            raise ValueError("QWEN_API_KEY 环境变量未设置")
        
        print(f"✓ 初始化成功")
        print(f"  模型: {self.model}")
        print(f"  WebSocket URL: {self.ws_url}")
        print(f"  API Key: {self.api_key[:10]}***")
    
    async def connect(self) -> Optional[websockets.WebSocketClientProtocol]:
        """建立 WebSocket 连接"""
        try:
            print(f"\n📡 正在连接到 Qwen Omni Realtime...")
            
            # 在 URL 中添加 API 密钥作为查询参数
            # 根据 DashScope 文档，使用 X-DashScope-OssResourceUrl 或 Authorization header
            # WebSocket 连接使用 subprotocol 传递认证
            
            ws = await websockets.connect(
                self.ws_url,
                subprotocols=[f"https.{self.api_key}"]
            )
            print(f"✓ WebSocket 连接成功")
            
            # 建立连接后等待
            await asyncio.sleep(0.2)
            
            return ws
        
        except Exception as e:
            print(f"✗ 连接失败: {str(e)}")
            # 如果 subprotocol 方式失败，尝试其他方式
            try:
                print(f"\n尝试替代认证方式...")
                # 直接连接，连接后发送认证消息
                ws = await websockets.connect(self.ws_url)
                print(f"✓ WebSocket 连接成功（直接连接）")
                
                # 发送认证信息
                await asyncio.sleep(0.2)
                auth_msg = {
                    "type": "authentication",
                    "api_key": self.api_key
                }
                await ws.send(json.dumps(auth_msg))
                print(f"✓ 认证消息已发送")
                
                return ws
            except Exception as e2:
                print(f"✗ 替代认证方式也失败: {str(e2)}")
                return None
    
    async def test_text_input(self, ws):
        """测试文本输入"""
        print(f"\n{'='*60}")
        print(f"测试 1: 文本输入 → 实时响应")
        print(f"{'='*60}")
        
        user_input = "你好，请自我介绍一下"
        
        message = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_input
                    }
                ]
            }
        }
        
        try:
            print(f"\n📝 发送: {user_input}")
            await ws.send(json.dumps(message))
            
            # 请求响应
            commit_message = {
                "type": "response.create",
                "response": {
                    "modalities": ["text", "audio"],  # 同时请求文本和音频
                    "instructions": "请用户友好的方式回答"
                }
            }
            await ws.send(json.dumps(commit_message))
            
            # 接收响应
            full_response = ""
            audio_delta_count = 0
            
            print(f"\n📥 接收响应:")
            
            while True:
                try:
                    response_data = await asyncio.wait_for(ws.recv(), timeout=30)
                    response = json.loads(response_data)
                    
                    event_type = response.get("type", "")
                    
                    # 处理文本内容
                    if event_type == "response.content_block.delta":
                        delta = response.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            full_response += text
                            print(text, end="", flush=True)
                        elif delta.get("type") == "audio_delta":
                            audio_delta_count += 1
                            # 如果需要保存音频
                            # audio_data = delta.get("audio")
                    
                    # 处理响应完成
                    elif event_type == "response.done":
                        print(f"\n\n✓ 响应完成")
                        print(f"  文本: {full_response[:100]}...")
                        print(f"  音频数据块: {audio_delta_count}")
                        break
                    
                    # 处理错误
                    elif event_type == "error":
                        print(f"\n✗ 错误: {response}")
                        return False
                
                except asyncio.TimeoutError:
                    print(f"\n⏱️  响应超时")
                    return False
            
            return True
        
        except Exception as e:
            print(f"\n✗ 错误: {str(e)}")
            return False
    
    async def test_audio_input(self, ws, audio_path: str):
        """测试音频输入"""
        if not os.path.exists(audio_path):
            print(f"\n💡 提示: 音频文件不存在: {audio_path}")
            return False
        
        print(f"\n{'='*60}")
        print(f"测试 2: 音频输入 → 实时响应")
        print(f"{'='*60}")
        
        try:
            # 读取音频文件
            print(f"\n🎙️  加载音频: {audio_path}")
            with open(audio_path, "rb") as f:
                audio_bytes = f.read()
            
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
            file_size_kb = len(audio_base64) / 1024
            print(f"✓ 音频加载成功 (大小: {file_size_kb:.2f} KB)")
            
            # 检测音频格式
            audio_format = Path(audio_path).suffix.lower().replace(".", "")
            
            # 创建消息
            message = {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "audio",
                            "audio": f"data:audio/{audio_format};base64,{audio_base64}"
                        }
                    ]
                }
            }
            
            print(f"\n📡 发送音频到服务器...")
            await ws.send(json.dumps(message))
            
            # 请求响应
            commit_message = {
                "type": "response.create",
                "response": {
                    "modalities": ["text", "audio"],
                    "instructions": "请用友好的语音回答用户的语音问题"
                }
            }
            await ws.send(json.dumps(commit_message))
            
            # 接收响应
            full_response = ""
            audio_delta_count = 0
            
            print(f"\n📥 接收响应:")
            
            while True:
                try:
                    response_data = await asyncio.wait_for(ws.recv(), timeout=30)
                    response = json.loads(response_data)
                    
                    event_type = response.get("type", "")
                    
                    if event_type == "response.content_block.delta":
                        delta = response.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            full_response += text
                            print(text, end="", flush=True)
                        elif delta.get("type") == "audio_delta":
                            audio_delta_count += 1
                    
                    elif event_type == "response.done":
                        print(f"\n\n✓ 响应完成")
                        print(f"  文本: {full_response[:100]}...")
                        print(f"  音频数据块: {audio_delta_count}")
                        break
                    
                    elif event_type == "error":
                        print(f"\n✗ 错误: {response}")
                        return False
                
                except asyncio.TimeoutError:
                    print(f"\n⏱️  响应超时")
                    return False
            
            return True
        
        except Exception as e:
            print(f"\n✗ 错误: {str(e)}")
            return False
    
    async def run_tests(self):
        """运行所有测试"""
        ws = await self.connect()
        if not ws:
            return False
        
        try:
            # 测试 1: 文本输入
            success1 = await self.test_text_input(ws)
            
            # 测试 2: 音频输入（如果有文件）
            audio_file = "test_audio.wav"
            if os.path.exists(audio_file):
                success2 = await self.test_audio_input(ws, audio_file)
            else:
                print(f"\n💡 跳过音频测试: 未找到 {audio_file}")
                success2 = True
            
            return success1 and success2
        
        finally:
            await ws.close()
            print(f"\n✓ WebSocket 连接已关闭")


async def main():
    """主函数"""
    print("╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "Qwen Omni Realtime WebSocket 测试".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝")
    
    try:
        client = QwenOmniRealtimeClient()
        success = await client.run_tests()
        
        # 总结
        print(f"\n{'='*60}")
        print(f"测试总结")
        print(f"{'='*60}")
        if success:
            print("✓ 所有测试通过")
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
