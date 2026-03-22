# Windows 本地部署与启动指南

这份文档面向第一次在 Windows 上跑通本项目的同学，重点说明本机环境准备、依赖安装、Redis 启动、后端启动、前端启动和常见问题处理。

如果你只是想快速了解项目结构和整体功能，请优先看 `README.md`；如果你现在的目标是把项目在自己电脑上跑起来，请按本文步骤执行。

## 1. 推荐运行方式

当前仓库推荐使用下面这套本地开发组合：

- Docker Desktop：用于启动 Redis
- Python 本地环境：用于运行后端
- Node.js 本地环境：用于运行前端
- ChromaDB：默认使用 `pip` 安装后的本地持久化模式，不强制使用 Docker 容器

这套方式的优点是依赖更少、排错更直接，也更适合日常联调。

## 2. 环境准备

### 2.1 Windows 和 WSL 2

建议先将系统更新到 Windows 10 22H2 或更新版本。这样更容易兼容 Docker Desktop 和 WSL 2。

然后用管理员身份打开 PowerShell，安装 WSL：

```powershell
wsl --install
```

安装完成后重启电脑，再检查 WSL 是否可用：

```powershell
wsl --version
```

如果能够看到版本号，说明 WSL 已经安装成功。

### 2.2 安装 Docker Desktop

Docker Desktop 官方下载地址：

https://docs.docker.com/desktop/setup/install/windows-install/

安装时建议保持 `Use WSL 2 instead of Hyper-V` 勾选。安装完成后启动 Docker Desktop，确认左下角显示 Engine running。

如果你所在网络访问 Docker Hub 不稳定，可以在 Docker Desktop 的 `Settings -> Docker Engine` 中配置镜像源。例如：

```json
{
  "builder": {
    "gc": {
      "defaultKeepStorage": "20GB",
      "enabled": true
    }
  },
  "experimental": false,
  "registry-mirrors": [
    "https://docker.m.daocloud.io"
  ]
}
```

如果你平时通过本地代理上网，例如 `http://127.0.0.1:7890`，更推荐在 Docker Desktop 的 `Settings -> Resources -> Proxies` 中配置 `HTTP Proxy` 和 `HTTPS Proxy`，通常会比公共镜像源更稳定。

### 2.3 Python 和 Node.js

项目的 Python 版本要求见 `pyproject.toml`，当前为 `>=3.10`。推荐使用 conda 创建一个独立环境，避免污染已有环境。

示例：

```powershell
conda create -n helth python=3.11 -y
conda activate helth
```

前端使用 Vite，建议本机准备 Node.js 18 或更高版本。

## 3. 安装项目依赖

### 3.1 初始化环境变量

先在项目根目录复制一份本地环境文件：

```powershell
Copy-Item .env.example .env
```

这样做的原因是：`.env.example` 用于提供示例配置，真正的本地配置应写在 `.env` 中，便于你按需修改且不影响示例文件。

### 3.2 切换到真实串口采集模式

如果你当前不是只想跑前后端演示，而是要把 T10 手环通过蓝牙采集器真正接进系统，建议把 `.env` 切到真实串口模式。

推荐至少修改下面这些配置：

```env
DATA_MODE=serial
USE_MOCK_DATA=false
SERIAL_ENABLED=true
SERIAL_BAUDRATE=115200
SERIAL_PACKET_TYPE=5
SERIAL_MAC_FILTER=535708000000
SERIAL_AUTO_CONFIGURE=true
```

如果你已经知道采集器对应的串口号，例如 `COM3`，可以再补上：

```env
SERIAL_PORT=COM3
```

如果你暂时还不知道串口号，也可以先留空：

```env
SERIAL_PORT=
```

此时系统会优先尝试自动识别候选串口。

这些配置项的含义如下：

- `DATA_MODE=serial`：切换到真实串口采集模式
- `USE_MOCK_DATA=false`：关闭模拟数据，避免真实数据与演示数据混在一起
- `SERIAL_ENABLED=true`：启用串口采集线程
- `SERIAL_BAUDRATE=115200`：采集器串口波特率，按 T10 协议文档配置
- `SERIAL_PACKET_TYPE=5`：默认优先采集回应包
- `SERIAL_MAC_FILTER=535708000000`：保留给支持前缀过滤的采集器使用
- `SERIAL_APPLY_MAC_FILTER=false`：当前这块采集器在 `TYPE=5` 下加过滤会无输出，因此默认关闭
- `SERIAL_APPLY_PACKET_TYPE=true`：启动时主动切到 `AT+TYPE=5`
- `SERIAL_FALLBACK_DEVICE_MAC=`：当前采集器会在串口行前缀里带真实 MAC，因此默认不再强制兜底
- `SERIAL_ENABLE_BROADCAST_SOS_OVERLAY=true`：主跑 `TYPE=5` 的同时，周期性切到 `TYPE=4` 补抓 SOS
- `SERIAL_RESPONSE_CYCLE_SECONDS=8`：回应包模式持续时长
- `SERIAL_BROADCAST_CYCLE_SECONDS=2`：广播包模式持续时长
- `SERIAL_AUTO_CONFIGURE=true`：启动后自动下发采集器初始化指令

当 `SERIAL_AUTO_CONFIGURE=true` 时，系统启动后会自动尝试执行以下采集器初始化流程：

```text
AT+SCANSTOP
AT+UUID=NO
AT+TYPE=5
AT+SCANSTART
```

如果开启 `SERIAL_ENABLE_BROADCAST_SOS_OVERLAY=true`，系统会在运行期自动按下面的节奏切换：

```text
AT+TYPE=5  持续 8 秒，优先拿完整健康数据
AT+TYPE=4  持续 2 秒，补抓广播包里的 SOS
```

广播包进来后，系统会保留最近一次回应包里的电量、步数、血压、环境温度、表面温度，只用广播包补 `sos_flag` 和实时心率/体温。

如果你后续要切回演示模式，可把 `.env` 改回：

```env
DATA_MODE=mock
USE_MOCK_DATA=true
SERIAL_ENABLED=false
```

### 3.3 安装 Python 依赖

默认请安装 `requirements.txt`：

```powershell
python -m pip install -r requirements.txt
```

这里的 `requirements.txt` 是完整开发依赖，适合本地开发、调试和联调使用。

项目里还有一个 `requirements-runtime.txt`，它是精简运行依赖，只适合“尽快把服务跑起来”的场景，不建议把它当作默认安装入口。


## 4. 启动基础服务

### 4.1 启动 Redis

当前本地开发最少需要先把 Redis 启动起来。进入 `docker` 目录后执行：

```powershell
cd docker
docker compose up -d redis
```

如果看到容器 `ai-health-iot-redis` 运行成功，就说明 Redis 已经就绪。

也可以进一步检查：

```powershell
docker ps
```

### 4.2 关于 PostgreSQL、Ollama 和 ChromaDB

这些服务在仓库里都有预留，但不是你第一次本地跑通时的硬性前置条件。

- PostgreSQL：当前默认配置下项目可先使用 SQLite，本地联调时不是必须
- Ollama：如果你要体验本地大模型能力，再额外启动即可
- ChromaDB：推荐直接使用本地 `pip` 安装模式，不强制用 Docker

如果你后续确实需要这些服务，再单独补启会更稳。

## 5. 启动后端

回到项目根目录后，启动 FastAPI 后端：

```powershell
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

如果你不需要热重载，也可以去掉 `--reload`。在 OneDrive 目录下开发时，不开热重载有时会更稳定。

后端启动成功后，可以用下面的命令做一次健康检查：

```powershell
curl http://127.0.0.1:8000/healthz
```

如果接口正常返回，说明后端已经启动成功。

## 6. 启动前端

新开一个终端，进入前端目录：

```powershell
cd frontend\vue-dashboard
npm install
npm run dev
```

前端是标准的 Vite 开发服务。启动成功后，终端通常会给出一个本地访问地址，例如：

```text
http://127.0.0.1:5173/
```

这时用浏览器打开该地址即可。

### 6.1 登录与角色页面

新版前端已按角色分成“社区端”和“子女端”，启动后先进入登录页。默认演示账号和密码由后端接口生成，密码统一为：

```text
123456
```

你可以在页面下拉框里直接选择账号：

- `community_admin`：社区端账号，可查看全社区总览与关系台账
- `family01` / `family02` ...：子女端账号，只能查看该账号绑定老人

如果你不确定当前有哪些可用账号，可通过接口查看：

```powershell
curl http://127.0.0.1:8000/api/v1/auth/mock-accounts
```

## 7. 推荐启动顺序

如果你想按最稳妥的顺序执行，建议按下面的步骤来：

1. 复制 `.env.example` 为 `.env`
2. 激活 Python 环境
3. 安装 `requirements.txt`
4. 启动 Redis：`docker compose up -d redis`
5. 启动后端：`uvicorn backend.main:app ...`
6. 启动前端：`npm run dev`
7. 验证后端健康检查和前端页面是否正常打开

## 8. 常见问题

### 8.1 `docker-compose.yml` 提示 `version is obsolete`

如果你看到类似下面的警告：

```text
the attribute `version` is obsolete, it will be ignored
```

这是新版 Docker Compose 的兼容性提示，不会阻止容器启动。可以暂时忽略。

### 8.2 Docker 拉取镜像失败

如果 Redis、PostgreSQL、Ollama 或 ChromaDB 拉取镜像失败，通常是网络、镜像源或代理问题，而不是项目代码问题。

优先排查这几项：

- Docker Desktop 是否已经启动
- 是否需要在 Docker Desktop 中配置代理
- `Docker Engine` 中的镜像源 JSON 是否格式正确
- 当前镜像源是否可用

如果只是 ChromaDB 容器拉取失败，可以先跳过，因为本项目默认不强制依赖 Docker 版 ChromaDB。

### 8.3 PowerShell 报脚本执行策略错误

如果你看到类似下面的提示：

```text
无法加载文件 ... profile.ps1，因为在此系统上禁止运行脚本
```

这通常表示 PowerShell 的执行策略较严格。它会影响某些 `.ps1` 脚本直接运行，但不一定影响你手动执行 `python`、`npm`、`docker` 等命令。

如果你当前只是想先把项目跑起来，可以优先使用本文中的直接命令，而不是依赖 `scripts/*.ps1`。

### 8.4 不知道该装哪个 requirements 文件

默认安装：

```powershell
python -m pip install -r requirements.txt
```

原因很简单：

- `requirements.txt`：完整开发依赖，适合本地开发与联调
- `requirements-runtime.txt`：精简运行依赖，只适合快速试跑

如果你没有特别明确的精简需求，就以 `requirements.txt` 为准。

### 8.5 前端能打开，但接口报错

这种情况通常说明前端已经正常启动，但后端没有启动、端口不对，或者 Redis 没起来。

建议按下面顺序检查：

1. 后端终端是否仍在运行
2. `http://127.0.0.1:8000/healthz` 是否可访问
3. Redis 容器是否在运行
4. `.env` 中的配置是否被错误修改

## 9. 最小可用命令清单

如果你只想快速抄一份最短命令流程，可以直接用下面这组：

```powershell
conda create -n helth python=3.11 -y
conda activate helth
Copy-Item .env.example .env
python -m pip install -r requirements.txt
cd docker
docker compose up -d redis
cd ..
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

然后新开一个终端执行：

```powershell
cd frontend\vue-dashboard
npm install
npm run dev
```
