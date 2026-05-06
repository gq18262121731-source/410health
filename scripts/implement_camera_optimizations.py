#!/usr/bin/env python3
"""
摄像头性能优化实施脚本
自动应用网络和缓存优化
"""
import sys
from pathlib import Path

def add_camera_optimizations_to_env():
    """添加摄像头优化配置到.env"""
    env_path = Path(".env")
    
    if not env_path.exists():
        print("✗ .env文件不存在")
        return False
    
    # 读取现有配置
    content = env_path.read_text(encoding="utf-8")
    
    # 检查是否已添加
    if "CAMERA_CONNECTION_POOL_SIZE" in content:
        print("⚠ 优化配置已存在，跳过")
        return True
    
    # 添加优化配置
    optimizations = """
# ========================================
# 摄像头性能优化配置
# ========================================

# 网络优化
CAMERA_CONNECTION_POOL_SIZE=10
CAMERA_KEEP_ALIVE_TIMEOUT=30
CAMERA_MAX_RETRIES=2
CAMERA_RETRY_BACKOFF=0.1

# 缓存优化
CAMERA_FRAME_CACHE_SIZE=10
CAMERA_FRAME_CACHE_TTL=2.0
CAMERA_PREFETCH_ENABLED=true

# 自适应优化
CAMERA_ADAPTIVE_FPS=true
CAMERA_ADAPTIVE_RESOLUTION=false
CAMERA_MIN_FPS=2
CAMERA_MAX_FPS=15

# 编解码优化
CAMERA_HWACCEL=auto
CAMERA_JPEG_ENCODER=turbo

# 传输优化
CAMERA_TRANSPORT=http
CAMERA_BUFFER_SIZE=3

# 性能监控
CAMERA_PERFORMANCE_MONITORING=true
"""
    
    # 追加到文件末尾
    with env_path.open("a", encoding="utf-8") as f:
        f.write(optimizations)
    
    print("✓ 已添加摄像头优化配置到.env")
    return True

def create_optimized_camera_service():
    """创建优化版本的摄像头服务"""
    code = '''"""
摄像头服务优化版本
包含连接池、缓存、并发请求等优化
"""
from __future__ import annotations

import asyncio
import time
from typing import Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from cachetools import TTLCache

from backend.config import Settings
from backend.services.camera_service import CameraService as BaseCameraService


class OptimizedCameraService(BaseCameraService):
    """优化版摄像头服务"""
    
    _session: requests.Session | None = None
    _frame_cache: TTLCache | None = None
    _prefetch_task: asyncio.Task | None = None
    
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._init_session()
        self._init_cache()
    
    def _init_session(self):
        """初始化HTTP会话（连接池）"""
        if self._session is None:
            self._session = requests.Session()
            
            # 配置连接池
            pool_size = getattr(self._settings, 'camera_connection_pool_size', 10)
            adapter = HTTPAdapter(
                pool_connections=pool_size,
                pool_maxsize=pool_size * 2,
                max_retries=Retry(
                    total=getattr(self._settings, 'camera_max_retries', 2),
                    backoff_factor=getattr(self._settings, 'camera_retry_backoff', 0.1),
                    status_forcelist=[500, 502, 503, 504]
                ),
                pool_block=False
            )
            
            self._session.mount('http://', adapter)
            self._session.mount('https://', adapter)
            
            # 保持连接
            timeout = getattr(self._settings, 'camera_keep_alive_timeout', 30)
            self._session.headers.update({
                'Connection': 'keep-alive',
                'Keep-Alive': f'timeout={timeout}, max=100'
            })
    
    def _init_cache(self):
        """初始化帧缓存"""
        if self._frame_cache is None:
            cache_size = getattr(self._settings, 'camera_frame_cache_size', 10)
            cache_ttl = getattr(self._settings, 'camera_frame_cache_ttl', 2.0)
            self._frame_cache = TTLCache(maxsize=cache_size, ttl=cache_ttl)
    
    def capture_jpeg(self) -> tuple[bytes, dict[str, str]]:
        """优化的JPEG抓取（使用缓存）"""
        # 尝试从缓存获取
        cache_key = "latest_frame"
        if self._frame_cache and cache_key in self._frame_cache:
            cached_frame, cached_headers = self._frame_cache[cache_key]
            cached_headers['X-Cache'] = 'HIT'
            return cached_frame, cached_headers
        
        # 缓存未命中，抓取新帧
        frame, headers = super().capture_jpeg()
        
        # 缓存结果
        if self._frame_cache:
            self._frame_cache[cache_key] = (frame, headers)
        
        headers['X-Cache'] = 'MISS'
        return frame, headers
    
    async def start_prefetch(self):
        """启动后台预取"""
        if not getattr(self._settings, 'camera_prefetch_enabled', False):
            return
        
        if self._prefetch_task and not self._prefetch_task.done():
            return
        
        self._prefetch_task = asyncio.create_task(self._prefetch_loop())
    
    async def stop_prefetch(self):
        """停止后台预取"""
        if self._prefetch_task:
            self._prefetch_task.cancel()
            try:
                await self._prefetch_task
            except asyncio.CancelledError:
                pass
    
    async def _prefetch_loop(self):
        """后台预取循环"""
        while True:
            try:
                # 在后台抓取帧
                await asyncio.to_thread(self.capture_jpeg)
            except Exception:
                pass
            
            # 根据FPS调整间隔
            fps = max(1.0, min(self._settings.camera_stream_fps, 15.0))
            await asyncio.sleep(1.0 / fps)


# 替换原始服务
CameraService = OptimizedCameraService
'''
    
    output_path = Path("backend/services/camera_service_optimized.py")
    output_path.write_text(code, encoding="utf-8")
    print(f"✓ 已创建优化版摄像头服务: {output_path}")

def show_next_steps():
    """显示下一步操作"""
    print("\n" + "="*60)
    print("优化配置已添加！")
    print("="*60)
    
    print("\n下一步操作：")
    print("1. 重启后端服务")
    print("   python run.py")
    
    print("\n2. 验证优化效果")
    print("   curl http://localhost:8000/api/v1/camera/stream-status")
    
    print("\n3. 查看性能指标")
    print("   - 查看FPS是否提升")
    print("   - 查看延迟是否降低")
    print("   - 查看缓存命中率")
    
    print("\n4. 进一步优化（可选）")
    print("   - 实施WebSocket传输")
    print("   - 启用硬件编解码")
    print("   - 配置自适应帧率")
    
    print("\n详细文档：")
    print("   docs/摄像头全面性能优化方案.md")
    print()

def main():
    print("="*60)
    print("摄像头性能优化实施工具")
    print("="*60)
    print()
    
    try:
        # 1. 添加配置
        print("[1/3] 添加优化配置...")
        if not add_camera_optimizations_to_env():
            return 1
        
        # 2. 创建优化服务
        print("\n[2/3] 创建优化版服务...")
        create_optimized_camera_service()
        
        # 3. 显示下一步
        print("\n[3/3] 完成")
        show_next_steps()
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n操作已取消")
        return 1
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
