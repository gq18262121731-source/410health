"""
Qwen API 诊断工具
帮助排查连接和权限问题
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

def diagnose():
    print("╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "Qwen API 诊断工具".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝\n")
    
    # 检查环境变量
    print("1️⃣  检查环境变量")
    print("-" * 60)
    
    api_key = os.getenv("QWEN_API_KEY")
    api_base = os.getenv("QWEN_API_BASE")
    model = os.getenv("QWEN_OMNI_MODEL")
    
    if api_key:
        print(f"✓ QWEN_API_KEY: {api_key[:20]}...{api_key[-5:]}")
    else:
        print("✗ QWEN_API_KEY: 未设置")
    
    if api_base:
        print(f"✓ QWEN_API_BASE: {api_base}")
    else:
        print("✗ QWEN_API_BASE: 未设置")
    
    if model:
        print(f"✓ QWEN_OMNI_MODEL: {model}")
    else:
        print("✗ QWEN_OMNI_MODEL: 未设置")
    
    print()
    
    # 检查 API 密钥格式
    print("2️⃣  检查 API 密钥格式")
    print("-" * 60)
    
    if api_key:
        if api_key.startswith("sk-"):
            print("✓ API 密钥格式正确 (sk- 开头)")
        else:
            print("✗ API 密钥格式可能错误 (应以 sk- 开头)")
        
        if len(api_key) > 20:
            print(f"✓ API 密钥长度合理 ({len(api_key)} 字符)")
        else:
            print(f"✗ API 密钥长度过短 ({len(api_key)} 字符)")
    else:
        print("✗ 无法检查：API 密钥未设置")
    
    print()
    
    # 测试网络连接
    print("3️⃣  测试网络连接")
    print("-" * 60)
    
    try:
        response = requests.get("https://dashscope.aliyuncs.com", timeout=10)
        print(f"✓ 可以访问 DashScope (状态码: {response.status_code})")
    except requests.exceptions.ConnectionError:
        print("✗ 无法连接到 DashScope，检查网络和防火墙")
    except Exception as e:
        print(f"⚠️  连接测试出错: {str(e)}")
    
    print()
    
    # 测试 API 调用
    print("4️⃣  测试 API 调用")
    print("-" * 60)
    
    if not api_key or not api_base or not model:
        print("⚠️  环境变量不完整，跳过 API 测试")
    else:
        try:
            url = f"{api_base}/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": "test"
                }]
            }
            
            print(f"请求 URL: {url}")
            print(f"请求模型: {model}")
            print("正在发送请求...")
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            print(f"\n响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                print("✓ API 调用成功！")
                result = response.json()
                if "choices" in result:
                    print(f"✓ 模型正确响应")
                    print(f"  内容预览: {result['choices'][0]['message']['content'][:50]}...")
            
            elif response.status_code == 401:
                print("✗ 401 Unauthorized - API 密钥无效或过期")
                print("  解决方案:")
                print("  1. 检查 API 密钥是否正确复制")
                print("  2. 检查 API 密钥是否过期")
                print("  3. 在 DashScope 控制面板重新生成 API 密钥")
            
            elif response.status_code == 403:
                print("✗ 403 Forbidden - 访问被拒绝")
                error_msg = response.json()
                print(f"  错误信息: {error_msg.get('error', {}).get('message', '未知错误')}")
                print("\n  可能原因:")
                print("  1. 账户没有权限使用此模型")
                print("  2. 账户配额已用完")
                print("  3. 模型名称错误或不可用")
                print("  4. 区域或环境不匹配")
                print("\n  解决方案:")
                print("  1. 登录 DashScope 控制面板检查账户状态")
                print("  2. 确认有足够的余额/配额")
                print("  3. 检查 qwen3.5-omni-plus 是否已开通")
                print("  4. 查看错误链接获取更多信息")
            
            elif response.status_code == 429:
                print("✗ 429 Too Many Requests - 请求过于频繁")
                print("  解决方案: 等待一段时间后重试")
            
            else:
                print(f"✗ 其他错误 ({response.status_code})")
            
            # 打印完整错误响应
            try:
                error_detail = response.json()
                print(f"\n详细错误信息:")
                print(json.dumps(error_detail, indent=2, ensure_ascii=False))
            except:
                print(f"\n响应内容:\n{response.text}")
        
        except requests.exceptions.Timeout:
            print("✗ 请求超时 - 服务器响应太慢")
        except requests.exceptions.ConnectionError:
            print("✗ 连接错误 - 无法连接到服务器")
        except Exception as e:
            print(f"✗ 错误: {str(e)}")
    
    print()
    
    # 建议
    print("5️⃣  下一步建议")
    print("-" * 60)
    print("""
1. 访问 https://dashscope.aliyuncs.com 登录您的账户
2. 检查账户状态和配额余额
3. 确认 qwen3.5-omni-plus 模型已开通
4. 生成新的 API 密钥并更新 .env 文件
5. 如问题持续，联系阿里云支持

常见模型列表:
  • qwen4          - 通用大模型
  • qwen3.5-flash  - 快速版本
  • qwen3.5-omni   - 标准 Omni 版本
  • qwen3.5-omni-plus - 增强 Omni 版本（语音+文本）
""")

if __name__ == "__main__":
    diagnose()
