#!/usr/bin/env python3
"""
设备绑定问题修复工具
"""
import sqlite3
import sys
from pathlib import Path


def get_db_path():
    """获取数据库路径"""
    # 尝试几个可能的路径
    paths = [
        Path("data/app.db"),
        Path("data/health_monitor.db"),
        Path(__file__).parent.parent / "data" / "app.db",
    ]
    
    for path in paths:
        if path.exists():
            return path
    
    return None


def list_devices(db_path):
    """列出所有设备"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT mac_address, device_name, user_id, bind_status, ingest_mode
            FROM devices
            ORDER BY mac_address
        """)
        
        devices = cursor.fetchall()
        return devices
    finally:
        conn.close()


def unbind_device(db_path, mac_address):
    """解绑设备"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查设备是否存在
        cursor.execute(
            "SELECT mac_address, user_id, bind_status FROM devices WHERE mac_address = ?",
            (mac_address,)
        )
        device = cursor.fetchone()
        
        if not device:
            return False, "设备不存在"
        
        # 解绑设备
        cursor.execute("""
            UPDATE devices 
            SET user_id = NULL, bind_status = 'unbound'
            WHERE mac_address = ?
        """, (mac_address,))
        
        conn.commit()
        return True, f"设备 {mac_address} 已解绑"
    except Exception as e:
        return False, f"解绑失败: {e}"
    finally:
        conn.close()


def main():
    print("="*70)
    print("设备绑定问题修复工具")
    print("="*70)
    
    # 查找数据库
    db_path = get_db_path()
    
    if not db_path:
        print("\n✗ 未找到数据库文件")
        print("  请确认后端已运行过至少一次")
        return 1
    
    print(f"\n数据库: {db_path}")
    
    # 列出所有设备
    print("\n[1/2] 查询设备列表...")
    try:
        devices = list_devices(db_path)
        
        if not devices:
            print("  未找到任何设备")
            return 0
        
        print(f"\n  找到 {len(devices)} 个设备：")
        print()
        print(f"  {'MAC地址':<20} {'设备名':<15} {'用户ID':<15} {'绑定状态':<10} {'模式':<10}")
        print("  " + "-"*75)
        
        for device in devices:
            mac, name, user_id, bind_status, mode = device
            user_display = user_id[:12] + "..." if user_id and len(user_id) > 15 else (user_id or "N/A")
            print(f"  {mac:<20} {name:<15} {user_display:<15} {bind_status:<10} {mode:<10}")
    
    except Exception as e:
        print(f"  ✗ 查询失败: {e}")
        return 1
    
    # 询问是否解绑
    print("\n[2/2] 解绑设备...")
    print("\n是否需要解绑某个设备？")
    print("  输入MAC地址解绑，或直接回车跳过")
    
    mac_input = input("\nMAC地址: ").strip()
    
    if not mac_input:
        print("\n跳过解绑")
        return 0
    
    # 规范化MAC地址
    mac_normalized = mac_input.upper().replace("-", ":").replace(" ", "")
    
    # 执行解绑
    success, message = unbind_device(db_path, mac_normalized)
    
    if success:
        print(f"\n✓ {message}")
        print("\n下一步：")
        print("  1. 在手机APP中刷新设备列表")
        print("  2. 重新绑定该设备")
    else:
        print(f"\n✗ {message}")
        return 1
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n操作已取消")
        sys.exit(1)
