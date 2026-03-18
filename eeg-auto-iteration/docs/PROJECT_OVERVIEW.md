# 项目概览 - EEGTokenizer 自动回环迭代系统

## 🎯 项目目标

为 EEGTokenizer 项目实现**全自动化开发闭环**，让你能够在飞书上实时监控训练进度、查看错误日志、快速响应问题，并提供智能优化建议。

---

## 📊 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        飞书                                      │
│                    (控制中心 & 通知)                             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      云服务器 (VM-0-11)                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    OpenClaw                               │  │
│  │  ┌──────────────┐         ┌──────────────────────────┐  │  │
│  │  │  飞书 Session │◄────────┤  Notification Daemon     │  │  │
│  │  └──────────────┘         └──────────┬───────────────┘  │  │
│  │                                       │                  │  │
│  │  ┌─────────────────────────────────────▼──────────────┐ │  │
│  │  │          Flask Webhook Server (端口 5000)           │ │  │
│  │  └──────────────────────┬──────────────────────────────┘ │  │
│  └─────────────────────────┼─────────────────────────────────┘  │
│                            │                                      │
│  ┌─────────────────────────▼─────────────────────────────────┐  │
│  │              执行脚本 (scripts/)                            │  │
│  │  • run_training.sh      - 运行训练（带错误捕获）           │  │
│  │  • auto_iterate.sh      - 自动迭代模式                     │  │
│  │  • sync_code.sh         - 快速同步代码                     │  │
│  └──────────────────────┬────────────────────────────────────┘  │
└─────────────────────────┼────────────────────────────────────────┘
                          │
                  SSH 反向隧道 (端口 3022)
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    nit 服务器 (课题组服务器)                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              EEGTokenizer 代码                            │  │
│  │  • ~/EEGTokenizer/train.py                               │  │
│  │  • ~/EEGTokenizer/models/                                │  │
│  │  • ~/EEGTokenizer/data/                                  │  │
│  └──────────────────────┬───────────────────────────────────┘  │
│                         │                                       │
│  ┌──────────────────────▼───────────────────────────────────┐  │
│  │         隧道维护脚本 (maintain_tunnel.sh)                 │  │
│  │         • 持久连接云服务器                                │  │
│  │         • 自动重连                                        │  │
│  │         • 心跳保活                                        │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 完整工作流程

### 1. 开发阶段

```
你在任何地方
    │
    ├─ 修改代码 (本地或云服务器)
    │
    ├─ 推送到 GitHub
    │
    └─ 触发自动运行（可选）
```

### 2. 自动运行阶段

```
云服务器执行 run_training.sh
    │
    ├─ 检查 SSH 隧道
    │
    ├─ 从 GitHub 拉取最新代码（可选）
    │
    ├─ 通过 SSH 在 nit 上运行训练
    │
    ├─ 实时捕获输出
    │
    └─ 完成后发送通知
```

### 3. 错误处理阶段

```
训练失败
    │
    ├─ 捕获错误日志
    │
    ├─ 发送详细错误到飞书
    │
    ├─ 你收到通知 + 查看错误
    │
    ├─ 修复代码 + 推送到 GitHub
    │
    └─ 自动重试（如果使用 auto_iterate.sh）
```

### 4. 成功阶段

```
训练成功
    │
    ├─ 发送成功通知到飞书
    │
    ├─ 保存日志到云服务器
    │
    └─ 小k 分析结果 + 提供优化建议
```

---

## 📁 文件结构

### 云服务器 (VM-0-11)

```
/root/.openclaw/workspace/eeg-auto-iteration/
├── cloud-server/
│   ├── scripts/                    # 执行脚本
│   │   ├── run_training.sh         # ⭐ 运行训练（主要脚本）
│   │   ├── auto_iterate.sh         # 自动迭代模式
│   │   └── sync_code.sh            # 快速同步代码
│   ├── services/                   # 后台服务
│   │   ├── webhook_server.py       # Flask webhook 服务器
│   │   └── notification_daemon.py  # 通知守护进程
│   └── config/
│       └── config.sh               # 配置文件
├── logs/                           # 日志目录
│   ├── run_YYYYMMDD_HHMMSS.log     # 运行日志
│   ├── error_YYYYMMDD_HHMMSS.log   # 错误日志
│   └── notification_queue.jsonl    # 通知队列
├── docs/                           # 文档
│   ├── DEPLOYMENT.md               # 部署指南
│   ├── USAGE.md                    # 使用说明
│   └── TROUBLESHOOTING.md          # 故障排查
├── deploy.sh                       # ⭐ 一键部署脚本
└── README.md                       # 项目说明
```

### nit 服务器 (课题组服务器)

```
~/eeg-auto-iteration/
├── nit-server/
│   ├── scripts/                    # 执行脚本
│   │   ├── maintain_tunnel.sh      # 隧道维护脚本
│   │   └── tunnel_manager.sh       # 隧道管理脚本
│   └── config/
│       └── config.sh               # 配置文件
├── tunnel_logs/                    # 隧道日志
│   ├── tunnel_YYYYMMDD.log
│   └── auto_start.log
└── EEGTokenizer/                   # 代码目录
    ├── train.py
    ├── models/
    └── data/
```

---

## 🎯 核心功能

### 1. 远程执行

在云服务器上一键运行 nit 上的训练代码：

```bash
cd /root/.openclaw/workspace/eeg-auto-iteration/cloud-server/scripts
./run_training.sh "cd ~/EEGTokenizer && python train.py --epochs 100"
```

### 2. 自动同步

自动从 GitHub 拉取最新代码：

```bash
# 默认开启
./run_training.sh "cd ~/EEGTokenizer && python train.py"

# 跳过同步
AUTO_SYNC=false ./run_training.sh "cd ~/EEGTokenizer && python train.py"
```

### 3. 错误捕获

完整捕获训练输出和错误日志：

```
训练失败 → 自动捕获错误 → 发送到飞书 → 你看到详细错误
```

### 4. 飞书通知

实时通知训练状态：

- 🚀 **训练开始**：发送开始通知
- ✅ **训练成功**：发送成功通知 + 耗时统计
- ❌ **训练失败**：发送失败通知 + 详细错误日志

### 5. 自动迭代

失败后自动重试：

```bash
# 最多重试 3 次
./auto_iterate.sh "cd ~/EEGTokenizer && python train.py" 3

# 无限重试直到成功
./auto_iterate.sh "cd ~/EEGTokenizer && python train.py" 0
```

### 6. 智能建议

基于错误日志提供优化建议：

- **语法错误**：提示检查代码
- **导入错误**：提示安装依赖
- **CUDA 错误**：建议调整 batch size
- **内存错误**：建议优化数据加载

---

## 🚀 快速开始

### 第一次使用

1. **部署系统**
   ```bash
   # 在云服务器上
   cd /root/.openclaw/workspace/eeg-auto-iteration
   ./deploy.sh
   ```

2. **配置 nit 隧道**
   ```bash
   # 在 nit 上（用 atrust 或学校内网）
   # 按照部署指南配置隧道
   ```

3. **运行首次训练**
   ```bash
   cd /root/.openclaw/workspace/eeg-auto-iteration/cloud-server/scripts
   ./run_training.sh "cd ~/EEGTokenizer && python train.py --test"
   ```

### 日常使用

```bash
# 运行训练
./run_training.sh "cd ~/EEGTokenizer && python train.py"

# 自动迭代
./auto_iterate.sh "cd ~/EEGTokenizer && python train.py" 3

# 快速同步代码
./sync_code.sh ~/EEGTokenizer
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

⏱️ 耗时: 2h 15m 30s
```

### 训练失败（带详细错误）

```
❌ 🔬 EEGTokenizer 训练通知

📊 项目：EEGTokenizer
📈 状态：failed

🔴 退出码: 1

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 错误日志：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Traceback (most recent call last):
  File "train.py", line 42, in <module>
    model = EEGTokenizer(config)
TypeError: __init__() missing 1 required positional argument: 'dropout'
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 建议：检查模型初始化参数
```

---

## 🎁 特色功能

### 1. 全自动闭环

```
开发 → GitHub → 自动运行 → 错误通知 → 修复 → 自动重试 → 成功
```

### 2. 实时监控

- 飞书实时通知
- 本地完整日志
- 错误高亮显示

### 3. 智能建议

- 错误类型识别
- 针对性建议
- 优化方向推荐

### 4. 灵活控制

- 环境变量配置
- 跳过同步选项
- 自定义重试次数

---

## 📚 文档索引

| 文档 | 说明 |
|------|------|
| [README.md](../README.md) | 项目概述和快速开始 |
| [DEPLOYMENT.md](DEPLOYMENT.md) | 详细部署指南 |
| [USAGE.md](USAGE.md) | 完整使用教程 |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | 故障排查手册 |

---

## 🤝 支持

遇到问题？

1. 查看文档：`docs/` 目录
2. 查看日志：`logs/` 目录
3. 联系小k：飞书直接联系

---

**Created by:** 小k 🔬
**Date:** 2026-03-18
**Version:** 1.0.0
