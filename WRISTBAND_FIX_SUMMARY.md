# 手环数据问题修复总结

## ✅ 已完成

### 1. 配置已修复
`.env`文件已更新：
```env
DATA_MODE=serial          ✓ 已修改
SERIAL_ENABLED=true       ✓ 已修改
USE_MOCK_DATA=false       ✓ 已修改
SERIAL_PORT=COM3          ✓ 已配置
```

## 📋 下一步操作

### 步骤1：安装pyserial（必须）

在conda环境中运行：
```bash
pip install pyserial
```

### 步骤2：重启后端服务

```bash
# 如果后端正在运行，先停止（Ctrl+C）
# 然后重新启动
python run.py
```

### 步骤3：验证数据采集

启动后端后，查看日志应该看到：
```
Serial collector connected on COM3
Sample ingested
```

### 步骤4：监控数据（可选）

运行监控脚本查看实时数据：
```bash
python scripts/monitor_wristband_data.py
```

## 🔍 如果还有问题

### 问题1：找不到串口设备

**症状**：后端日志显示"No compatible collector serial port was detected"

**解决**：
1. 检查USB接收器是否插入
2. 在设备管理器中查看COM口
3. 安装CH340或CP210x驱动

### 问题2：串口连接失败

**症状**：后端日志显示"Serial collector unavailable on COM3"

**解决**：
1. 确认COM口号正确（设备管理器中查看）
2. 检查串口是否被其他程序占用
3. 重新插拔USB接收器

### 问题3：收到数据但手机端不显示

**症状**：后端日志显示数据采集成功，但手机APP无数据

**解决**：
1. 确认手机和电脑在同一WiFi
2. 在手机APP中下拉刷新
3. 检查设备状态是否显示"在线"
4. 重启手机APP

## 📊 预期结果

修复后应该看到：

### 后端日志
```
Serial collector connected on COM3
Sample ingested: device_mac=53:57:08:XX:XX:XX
```

### 监控脚本输出
```
✓ 手环名称 [53:57:08:XX:XX:XX]
  状态: ONLINE | 模式: SERIAL
  心率: 75 bpm | 体温: 36.5°C | 血氧: 98%
```

### 手机APP
- 设备状态：在线
- 数据实时更新
- 最后更新时间：几秒前

## 🛠️ 诊断工具

### 快速诊断
```bash
python scripts/quick_diagnose.py
```

### 实时监控
```bash
python scripts/monitor_wristband_data.py
```

## 📚 参考文档

- **快速修复**：`docs/WRISTBAND_QUICK_FIX.md`
- **完整排查**：`docs/WRISTBAND_DATA_TROUBLESHOOTING.md`

## ⚡ 快速命令

```bash
# 1. 安装依赖
pip install pyserial

# 2. 诊断
python scripts/quick_diagnose.py

# 3. 启动后端
python run.py

# 4. 监控数据（新终端）
python scripts/monitor_wristband_data.py
```

## 💡 提示

- 确保手环已开机并佩戴
- 手环与接收器距离不要超过5米
- 如果数据不稳定，检查USB连接是否松动
- 使用主板直连的USB口，不要用USB Hub
