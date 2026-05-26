<!-- v0.2.0 -->

<div align="center">
  <img src="./docs/fig/logo.png" width="50%" alt="FlowLine" />

  中文 | [English](./docs/readme_en.md)
</div>

# FlowLine Monitor - 多机GPU监控系统

FlowLine Monitor 是一个基于 **主从架构（Master-Slave）** 的多机GPU信息监控Web工具，可实时显示多台服务器的GPU状态和系统信息。

## 核心特性

* **主从架构**：支持一台主机管理多台从机的GPU监控
* **实时监控**：实时显示GPU使用率、显存、温度、功耗等信息
* **进程列表**：显示每个GPU上运行的进程详情
* **系统信息**：显示每台从机的CPU型号、使用率、温度、内存使用量、Swap使用量
* **分区展示**：每台从机独立分区显示，便于监控管理
* **自动刷新**：支持自动定时刷新和手动刷新

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         主机 (Master)                            │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────────┐ │
│  │  Web前端    │ ←→ │  Master API  │ ←→ │  从机信息收集器     │ │
│  │  (port 8000)│    │  (port 5000) │    │                     │ │
│  └─────────────┘    └──────────────┘    └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ↑
                              │ HTTP 请求
                              ↓
    ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
    │   从机 1       │  │   从机 2       │  │   从机 3       │
    │ 192.168.217.180│  │192.168.217.190│  │192.168.217.200│
    │   (port 5001) │  │   (port 5001) │  │   (port 5001) │
    │  ┌─────────┐  │  │  ┌─────────┐  │  │  ┌─────────┐  │
    │  │Slave API│  │  │  │Slave API│  │  │  │Slave API│  │
    │  └─────────┘  │  │  └─────────┘  │  │  └─────────┘  │
    └───────────────┘  └───────────────┘  └───────────────┘
```

## 🚀 快速开始

### 环境要求

* Python 3.8+
* NVIDIA GPU（从机需要）
* NVIDIA驱动和CUDA（从机需要）

### 安装依赖

在所有机器（主机和从机）上安装依赖：

```bash
pip install -r requirements.txt
```

或从源代码安装：

```bash
pip install -e .
```

---

## 📋 从机配置指南

从机运行在拥有GPU的服务器上，负责收集并报告GPU和系统信息。

### 步骤1：配置从机

编辑配置文件 `config/slave.json`：

```json
{
    "mode": "slave",
    "master_ip": "192.168.217.190",
    "master_port": 5000,
    "slave_host": "0.0.0.0",
    "slave_port": 5001,
    "report_interval": 3
}
```

**配置项说明：**

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `master_ip` | 主机IP地址 | 192.168.217.190 |
| `master_port` | 主机端口 | 5000 |
| `slave_host` | 从机绑定地址 | 0.0.0.0 |
| `slave_port` | 从机服务端口 | 5001 |
| `report_interval` | 信息上报间隔(秒) | 3 |

### 步骤2：启动从机服务

```bash
# 使用默认配置
python -m flowline.slave

# 指定配置文件
python -m flowline.slave --config config/slave.json

# 指定端口
python -m flowline.slave --port 5001
```

### 步骤3：验证从机运行

在浏览器中访问从机API：

```
http://<从机IP>:5001/api/info
```

应返回类似如下的JSON数据：

```json
{
  "timestamp": 1706000000.0,
  "system": {
    "hostname": "gpu-server-1",
    "cpu_model": "Intel(R) Xeon(R) CPU E5-2680 v4",
    "cpu_cores": 28,
    "cpu_usage": 12.5,
    "cpu_temperature": {"package": 55.2},
    "memory": {"total": 128.0, "used": 45.2, "percent": 35.3},
    "swap": {"total": 16.0, "used": 2.1, "percent": 13.1}
  },
  "gpus": [
    {
      "id": 0,
      "name": "NVIDIA GeForce RTX 3090",
      "memory": {"total": 24576, "used": 8192, "free": 16384},
      "utilization": 45,
      "temperature": 65,
      "power": {"current": 180.5, "max": 350.0},
      "processes": [...]
    }
  ]
}
```

### 步骤4：设置开机自启（可选）

创建systemd服务文件 `/etc/systemd/system/flowline-slave.service`：

```ini
[Unit]
Description=FlowLine GPU Monitor Slave
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/FlowPipeLine
ExecStart=/usr/bin/python -m flowline.slave --config config/slave.json
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable flowline-slave
sudo systemctl start flowline-slave
```

---

## 🖥️ 主机配置指南

主机运行Web前端和API服务，汇总所有从机的GPU信息。

### 步骤1：配置主机

编辑配置文件 `config/master.json`：

```json
{
    "mode": "master",
    "master_host": "0.0.0.0",
    "master_port": 5000,
    "web_port": 8000,
    "slaves": [
        {"name": "GPU服务器1", "ip": "192.168.217.180"},
        {"name": "GPU服务器2", "ip": "192.168.217.190"},
        {"name": "GPU服务器3", "ip": "192.168.217.200"}
    ],
    "slave_port": 5001,
    "refresh_interval": 5
}
```

**配置项说明：**

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `master_host` | 主机绑定地址 | 0.0.0.0 |
| `master_port` | API服务端口 | 5000 |
| `web_port` | Web前端端口 | 8000 |
| `slaves` | 从机列表配置 | - |
| `slaves[].name` | 从机显示名称 | - |
| `slaves[].ip` | 从机IP地址 | - |
| `slave_port` | 从机默认端口 | 5001 |
| `refresh_interval` | 刷新间隔(秒) | 5 |

### 步骤2：启动主机API服务

```bash
# 使用默认配置
python -m flowline.master

# 指定配置文件
python -m flowline.master --config config/master.json

# 指定端口
python -m flowline.master --port 5000
```

### 步骤3：启动Web前端服务

在另一个终端中：

```bash
cd web
python -m http.server 8000
```

### 步骤4：访问Web界面

打开浏览器访问：

```
http://<主机IP>:8000/monitor
```

即可看到所有从机的GPU监控信息。

### 步骤5：设置开机自启（可选）

**主机API服务** `/etc/systemd/system/flowline-master.service`：

```ini
[Unit]
Description=FlowLine GPU Monitor Master API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/FlowPipeLine
ExecStart=/usr/bin/python -m flowline.master --config config/master.json
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Web前端服务** `/etc/systemd/system/flowline-web.service`：

```ini
[Unit]
Description=FlowLine GPU Monitor Web Frontend
After=flowline-master.service

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/FlowPipeLine/web
ExecStart=/usr/bin/python -m http.server 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable flowline-master flowline-web
sudo systemctl start flowline-master flowline-web
```

---

## 📡 API接口说明

### 主机API (Master)

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/slaves` | GET | 获取所有从机信息 |
| `/api/slaves/<ip>` | GET | 获取指定从机信息 |
| `/api/slaves/<ip>/refresh` | POST | 刷新指定从机数据 |
| `/api/refresh` | POST | 刷新所有从机数据 |
| `/api/health` | GET | 健康检查 |
| `/api/system/uptime` | GET | 获取服务运行时间 |

### 从机API (Slave)

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/info` | GET | 获取GPU和系统信息 |
| `/api/health` | GET | 健康检查 |

---

## 🔧 故障排查

### 从机显示离线

1. 检查从机服务是否运行：`systemctl status flowline-slave`
2. 检查防火墙是否开放端口：`sudo ufw allow 5001`
3. 检查网络连通性：`ping <从机IP>`
4. 直接访问从机API：`curl http://<从机IP>:5001/api/health`

### GPU信息为空

1. 确认NVIDIA驱动已安装：`nvidia-smi`
2. 确认pynvml可用：`python -c "import pynvml; pynvml.nvmlInit()"`
3. 检查从机日志：`journalctl -u flowline-slave -f`

### Web页面无法加载

1. 检查主机API服务状态
2. 检查浏览器控制台错误
3. 确认跨域设置正确

---

## 📁 项目结构

```
FlowPipeLine/
├── config/                 # 配置文件
│   ├── master.json        # 主机配置
│   └── slave.json         # 从机配置
├── flowline/              # 核心模块
│   ├── master.py          # 主机服务
│   ├── slave.py           # 从机服务
│   ├── core/              # 核心功能
│   ├── api/               # API模块
│   └── utils/             # 工具函数
├── web/                   # Web前端
│   └── monitor/           # 监控页面
│       ├── index.html
│       ├── monitor.css
│       └── monitor.js
├── requirements.txt       # 依赖列表
└── readme.md             # 本文档
```

---

## 💐 贡献

欢迎大家为本项目贡献代码、修正bug或完善文档！

* 如有建议或问题，请提交Issue
* 欢迎提交Pull Request

> [!TIP]
> 若对您有帮助，请给这个项目点上 **Star**!

**感谢所有贡献者！**

[![贡献者](https://contrib.rocks/image?repo=Parallelopiped/FlowPipeLine)](https://github.com/Parallelopiped/FlowPipeLine/graphs/contributors)
