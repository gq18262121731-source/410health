#!/usr/bin/env python3
"""
推理加速优化检查脚本
"""
import sys
import torch

def check_gpu():
    """检查GPU可用性"""
    print("\n[1/3] 检查GPU...")
    print("-" * 60)
    if torch.cuda.is_available():
        print(f"✓ GPU可用: {torch.cuda.get_device_name(0)}")
        print(f"  CUDA版本: {torch.version.cuda}")
        memory_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"  显存: {memory_gb:.1f} GB")
        return True
    else:
        print("✗ GPU不可用")
        print("  原因：未检测到NVIDIA GPU或未安装CUDA")
        return False

def check_pytorch_version():
    """检查PyTorch版本"""
    print("\n[2/3] 检查PyTorch版本...")
    print("-" * 60)
    print(f"PyTorch版本: {torch.__version__}")
    
    if "+cu" in torch.__version__:
        print("✓ 已安装CUDA版本（支持GPU加速）")
        return "cuda"
    elif "+cpu" in torch.__version__:
        print("⚠ 当前是CPU版本")
        print("  建议：安装CUDA版本以获得10-50倍速度提升")
        print("  命令：pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118")
        return "cpu"
    else:
        print("⚠ 无法确定PyTorch类型")
        return "unknown"

def recommend_config():
    """推荐配置"""
    print("\n[3/3] 推荐优化配置...")
    print("-" * 60)
    
    has_gpu = check_gpu()
    pytorch_type = check_pytorch_version()
    
    print("\n" + "=" * 60)
    print("推荐配置（复制到.env文件）")
    print("=" * 60)
    
    if has_gpu and pytorch_type == "cuda":
        print("\n# ✓ GPU加速配置（最佳性能）")
        print("MODEL_DEVICE=auto")
        print("FALL_DETECTION_PROCESS_EVERY_OVERRIDE=1  # 处理每帧")
        print("FALL_DETECTION_SPEED_PROFILE=accuracy  # 最高精度")
        print("\n预期效果：速度提升30-50倍，画面完全流畅")
    else:
        print("\n# CPU优化配置（立即生效）")
        print("MODEL_DEVICE=cpu")
        print("FALL_DETECTION_PROCESS_EVERY_OVERRIDE=3  # 每3帧处理1帧")
        print("FALL_DETECTION_SPEED_PROFILE=fast  # 快速模式")
        print("CAMERA_STREAM_WIDTH=640  # 降低分辨率")
        print("FALL_DETECTION_FRAME_WIDTH=1280")
        print("FALL_DETECTION_FRAME_HEIGHT=720")
        print("\n预期效果：速度提升5-8倍，画面基本流畅")
        
        if not has_gpu:
            print("\n# 如果要启用GPU加速：")
            print("# 1. 确保有NVIDIA GPU")
            print("# 2. 安装CUDA版PyTorch:")
            print("#    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118")
            print("# 3. 修改配置: MODEL_DEVICE=auto")

def benchmark_inference():
    """简单的推理性能测试"""
    print("\n" + "=" * 60)
    print("推理性能测试")
    print("=" * 60)
    
    import time
    
    # 创建测试张量
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\n测试设备: {device}")
    
    # 模拟推理
    x = torch.randn(1, 3, 224, 224, device=device)
    model = torch.nn.Sequential(
        torch.nn.Conv2d(3, 64, 3, padding=1),
        torch.nn.ReLU(),
        torch.nn.MaxPool2d(2),
        torch.nn.Conv2d(64, 128, 3, padding=1),
        torch.nn.ReLU(),
        torch.nn.AdaptiveAvgPool2d(1),
        torch.nn.Flatten(),
        torch.nn.Linear(128, 10)
    ).to(device)
    
    # 预热
    with torch.no_grad():
        for _ in range(10):
            _ = model(x)
    
    # 测试
    iterations = 100
    start = time.time()
    with torch.no_grad():
        for _ in range(iterations):
            _ = model(x)
    
    if device.type == "cuda":
        torch.cuda.synchronize()
    
    elapsed = time.time() - start
    fps = iterations / elapsed
    
    print(f"\n测试结果：")
    print(f"  迭代次数: {iterations}")
    print(f"  总时间: {elapsed:.2f}秒")
    print(f"  平均FPS: {fps:.1f}")
    print(f"  平均延迟: {1000/fps:.1f}ms")
    
    if fps < 10:
        print("\n⚠ 性能较低，建议：")
        print("  1. 降低处理频率（FALL_DETECTION_PROCESS_EVERY_OVERRIDE=3）")
        print("  2. 降低输入分辨率")
        if device.type == "cpu":
            print("  3. 使用GPU加速（速度提升10-50倍）")
    elif fps < 30:
        print("\n✓ 性能中等，可以满足基本需求")
    else:
        print("\n✓ 性能优秀，可以实时处理")

if __name__ == "__main__":
    print("=" * 60)
    print("推理加速优化检查工具")
    print("=" * 60)
    
    try:
        recommend_config()
        
        # 询问是否运行性能测试
        print("\n" + "=" * 60)
        response = input("是否运行推理性能测试？(y/n): ").strip().lower()
        if response == 'y':
            benchmark_inference()
        
        print("\n" + "=" * 60)
        print("检查完成！")
        print("=" * 60)
        print("\n下一步：")
        print("1. 根据推荐配置修改.env文件")
        print("2. 重启后端服务")
        print("3. 检查摄像头画面是否流畅")
        
    except KeyboardInterrupt:
        print("\n\n操作已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        sys.exit(1)
