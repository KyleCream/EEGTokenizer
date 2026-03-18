# EEGTokenizer 自动回环迭代系统

**版本：** 1.0.0
**日期：** 2026-03-18
**作者：** 小k 🔬

---

## 🎯 项目目标

实现完整的**自动化开发闭环**，让你能够在飞书上全流程控制项目迭代，实时查看训练日志，并快速响应错误。

### 核心功能

- ✅ **远程执行**：在云服务器上一键运行 nit 上的训练代码
- ✅ **自动同步**：自动从 GitHub 拉取最新代码
- ✅ **环境自适应**：自动检测 Python 环境（venv/conda/system）
- ✅ **GPU 智能管理**：自动等待 GPU 空闲，避免显存不足
- ✅ **错误捕获**：完整捕获训练输出和错误日志
- ✅ **飞书通知**：训练开始/成功/失败实时通知
- ✅ **自动重试**：失败后自动重试（可选）
- ✅ **智能建议**：错误时提供修复建议

---

## 🏗️ 系统架构

```
┌─────────────────┐         SSH 反向隧道         ┌─────────────────┐
│   云服务器       │ ◄─────────────────────────► │    nit 服务器    │
│  (VM-0-11)      │                             │  (课题组服务器)   │
└────────┬────────┘                             └────────┬────────┘
         │                                                │
         │                                                │
    ┌────▼────┐                                     ┌────▼────┐
    │  Flask  │                                     │ EEGTokenizer │
    │ Webhook │                                     │ 训练代码  │
    └────┬────┘                                     └─────────┘
         │
         │
    ┌────▼────┐
    │ OpenClaw│
    │   →    │
    │  飞书   │
    └─────────┘
```

---

## 📁 项目结构

```
eeg-auto-iteration/
├── cloud-server/              # 云服务器文件
│   ├── scripts/               # 执行脚本
│   │   ├── run_training.sh    # 运行训练（带错误捕获）⭐
│   │   ├── auto_iterate.sh    # 自动迭代模式
│   │   └── sync_code.sh       # 快速同步代码
│   ├── services/              # 服务配置
│   │   ├── webhook.service    # Flask webhook 服务
│   │   └── notification-daemon.service  # 通知守护进程
│   └── config/                # 配置文件
│       └── config.sh          # 云服务器配置
│
├── nit-server/                # nit 服务器文件
│   ├── scripts/               # 执行脚本
│   │   ├── maintain_tunnel.sh # 隧道维护脚本
│   │   └── tunnel_manager.sh  # 隧道管理脚本
│   └── config/                # 配置文件
│       └── config.sh          # nit 配置
│
├── docs/                      # 文档
│   ├── DEPLOYMENT.md          # 部署指南
│   ├── USAGE.md               # 使用说明
│   └── TROUBLESHOOTING.md     # 故障排查
│
├── logs/                      # 日志目录
│   ├── run_*.log              # 运行日志
│   ├── error_*.log            # 错误日志
│   └── notification_queue.jsonl  # 通知队列
│
└── README.md                  # 本文档
```

---

## 🚀 快速开始

### 前置条件

1. **云服务器**：VM-0-11-opencloudos（已安装 OpenClaw）
2. **nit 服务器**：课题组服务器（在校园网内）
3. **GitHub 仓库**：https://github.com/KyleCream/EEGTokenizer
4. **SSH 访问**：云服务器和 nit 之间的 SSH 访问

---

## 📋 部署步骤

### 第 1 步：在 nit 上配置 SSH 反向隧道

#### 1.1 上传脚本到 nit

```bash
# 在云服务器上，打包 nit 脚本
cd /root/.openclaw/workspace/eeg-auto-iteration
tar -czf nit-package.tar.gz nit-server/

# 复制到 nit（用 atrust 或在学校内网登录）
scp nit-package.tar.gz your_username@nit:~/

# 在 nit 上解压
ssh your_username@nit
cd ~
tar -xzf nit-package.tar.gz
mv nit-server eeg-auto-iteration
```

#### 1.2 配置 nit

```bash
# 在 nit 上
cd ~/eeg-auto-iteration/nit-server

# 编辑配置文件
vim config/config.sh

# 修改以下配置：
# CLOUD_SERVER="root@<你的云服务器公网IP>"
# REMOTE_USER="your_username"
# TUNNEL_PORT=3022
```

#### 1.3 在云服务器上添加 nit 的公钥

```bash
# 在 nit 上获取公钥
cat ~/.ssh/id_rsa.pub

# 复制公钥，然后在云服务器上添加
ssh root@云服务器
nano ~/.ssh/authorized_keys

# 粘贴 nit 的公钥
```

#### 1.4 启动隧道

```bash
# 在 nit 上
cd ~/eeg-auto-iteration/nit-server/scripts
./tunnel_manager.sh start

# 检查状态
./tunnel_manager.sh status

# 应该看到：
# 状态: 运行中
# PID: xxxxx
# SSH 隧道: 已建立
```

#### 1.5 设置开机自启（可选）

```bash
# 在 nit 上
crontab -e

# 添加以下内容
@reboot sleep 30 && /home/your_username/eeg-auto-iteration/nit-server/scripts/tunnel_manager.sh start
```

---

### 第 2 步：在云服务器上部署

#### 2.1 安装依赖

```bash
# 安装 Flask
pip3 install flask

# 安装 jq（用于 JSON 处理）
yum install -y jq  # 或 apt-get install jq
```

#### 2.2 配置云服务器

```bash
cd /root/.openclaw/workspace/eeg-auto-iteration/cloud-server

# 编辑配置文件
vim config/config.sh

# 修改以下配置（如果需要）：
# NIT_SSH_PORT=3022
# REPO_URL="https://github.com/KyleCream/EEGTokenizer.git"
# AUTO_SYNC=true
```

#### 2.3 启动服务

```bash
# 复制服务文件到 systemd
sudo cp services/*.service /etc/systemd/system/

# 重载 systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start webhook
sudo systemctl start notification-daemon

# 设置开机自启
sudo systemctl enable webhook
sudo systemctl enable notification-daemon

# 检查状态
sudo systemctl status webhook
sudo systemctl status notification-daemon
```

#### 2.4 测试隧道

```bash
# 在云服务器上测试连接到 nit
ssh -p 3022 localhost "hostname && whoami"

# 应该返回 nit 的主机名和用户名
```

---

## 🎯 使用方法

### 场景 1：日常开发训练

```bash
# 在云服务器上
cd /root/.openclaw/workspace/eeg-auto-iteration/cloud-server/scripts

# 运行训练（自动同步 + 错误捕获）
./run_training.sh "cd ~/EEGTokenizer && python train.py --epochs 100"

# 你会收到飞书通知：
# ✅ 训练开始
# ✅ 训练成功/失败（带详细日志）
```

### 场景 2：快速迭代测试

```bash
# 1. 修改代码
vim ~/EEGTokenizer/train.py

# 2. 快速同步到 nit（跳过 GitHub）
./sync_code.sh ~/EEGTokenizer

# 3. 运行测试（跳过自动同步）
AUTO_SYNC=false ./run_training.sh "cd ~/EEGTokenizer && python test.py"
```

### 场景 3：自动修复 bug

```bash
# 启动自动迭代模式（最多重试 3 次）
./auto_iterate.sh "cd ~/EEGTokenizer && python train.py" 3

# 同时在另一个终端修复代码：
# 1. 看到飞书错误通知
# 2. 修复代码
# 3. 推送到 GitHub
# 4. 等待自动重试成功...
```

---

## 📊 飞书通知示例

### 训练开始

```
🚀 🔬 EEGTokenizer 训练通知

📊 项目：EEGTokenizer
📈 状态：started
⏰ 时间：2026-03-18 11:30:00

📝 开始运行训练

🆔 运行 ID: 20260318_113000
🖥️ 主机: nit-server
💻 命令: cd ~/EEGTokenizer && python train.py
```

### 训练成功

```
✅ 🔬 EEGTokenizer 训练通知

📊 项目：EEGTokenizer
📈 状态：success
⏰ 时间：2026-03-18 13:45:00

📝 训练成功完成！

🆔 运行 ID: 20260318_113000
⏱️ 耗时: 2h 15m 30s
📄 日志: /root/.openclaw/workspace/eeg-auto-iteration/logs/run_20260318_113000.log
```

### 训练失败

```
❌ 🔬 EEGTokenizer 训练通知

📊 项目：EEGTokenizer
📈 状态：failed
⏰ 时间：2026-03-18 11:31:00

📝 训练失败，请检查错误日志

🆔 运行 ID: 20260318_113000
🔴 退出码: 1
⏱️ 耗时: 15s

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 错误日志：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Traceback (most recent call last):
  File "train.py", line 42, in <module>
    model = EEGTokenizer(config)
TypeError: __init__() missing 1 required positional argument: 'dropout'
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 建议检查：
1. 查看完整日志：/root/.openclaw/workspace/eeg-auto-iteration/logs/
2. 修复代码后重新运行
3. 使用 AUTO_SYNC=false 跳过同步（如果代码已是最新）
```

---

## 🔧 高级配置

### 环境变量

```bash
# 自定义隧道端口
NIT_SSH_PORT=3022 ./run_training.sh "command"

# 跳过代码自动同步
AUTO_SYNC=false ./run_training.sh "command"

# 自定义 webhook 地址
WEBHOOK_URL=http://localhost:5000/webhook/eegtokenizer ./run_training.sh "command"

# 自定义项目名称
PROJECT_NAME="MyProject" ./run_training.sh "command"
```

### 日志查看

```bash
# 查看最新运行日志
ls -lt /root/.openclaw/workspace/eeg-auto-iteration/logs/run_*.log | head -1 | xargs tail

# 查看最新错误日志
ls -lt /root/.openclaw/workspace/eeg-auto-iteration/logs/error_*.log | head -1 | xargs cat

# 实时监控日志
tail -f /root/.openclaw/workspace/eeg-auto-iteration/logs/run_*.log
```

---

## 🎁 特色功能

### 1. 智能错误分析

系统会自动分析错误类型并提供针对性建议：

- **语法错误**：提示检查 Python 语法
- **导入错误**：提示安装缺失的包
- **运行时错误**：提供具体的修复建议
- **CUDA 错误**：建议调整 batch size 或清理 GPU 缓存

### 2. 自动代码同步

- **GitHub 模式**：自动从 GitHub 拉取最新代码（推荐）
- **rsync 模式**：快速同步本地代码到 nit（开发测试）
- **手动模式**：跳过同步，直接运行

### 3. 迭代优化建议

基于训练结果，小k 会：
- 分析错误日志
- 识别性能瓶颈
- 提供优化建议
- 推荐下一步行动

---

## 📚 相关文档

- **[部署指南](docs/DEPLOYMENT.md)** - 详细的部署步骤
- **[使用说明](docs/USAGE.md)** - 完整的使用教程
- **[故障排查](docs/TROUBLESHOOTING.md)** - 常见问题解决

---

## 🤝 贡献

欢迎提出建议和改进！

---

## 📝 更新日志

### v1.0.0 (2026-03-18)
- ✅ 初始版本
- ✅ SSH 反向隧道
- ✅ 自动代码同步
- ✅ 错误捕获和通知
- ✅ 自动迭代模式
- ✅ 飞书集成

---

**Created by:** 小k 🔬
**Email:** kaizeng_kyle@163.com
**GitHub:** https://github.com/KyleCream
