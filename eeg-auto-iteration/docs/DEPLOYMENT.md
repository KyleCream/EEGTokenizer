# 部署指南 - EEGTokenizer 自动回环迭代系统

**版本：** 1.0.0
**日期：** 2026-03-18

---

## 📋 部署前准备

### 服务器信息

| 服务器 | 角色 | IP/地址 | 备注 |
|--------|------|---------|------|
| VM-0-11-opencloudos | 云服务器 | <公网IP> | 已安装 OpenClaw |
| nit | 课题组服务器 | 校园网内 | 需要通过 atrust 访问 |

### 前置条件

#### 云服务器（VM-0-11）

- ✅ Python 3.11+
- ✅ OpenClaw 已安装
- ✅ SSH 服务运行中
- ✅ 有 root 权限

#### nit 服务器

- ✅ Python 3.x
- ✅ Git 已安装
- ✅ SSH 服务运行中
- ✅ 可以访问 GitHub
- ⚠️ **不需要 root 权限**

---

## 🚀 部署步骤

### 第一部分：在 nit 上部署（使用 atrust 或学校内网）

#### 步骤 1：登录 nit

```bash
# 使用 atrust 连接到校园网，或在学校内网
ssh your_username@nit
```

#### 步骤 2：上传脚本

**方法 A：使用 scp（推荐）**

```bash
# 在云服务器上打包
cd /root/.openclaw/workspace/eeg-auto-iteration
tar -czf nit-package.tar.gz nit-server/

# 复制到 nit
scp nit-package.tar.gz your_username@nit:~/

# 在 nit 上解压
ssh your_username@nit
cd ~
tar -xzf nit-package.tar.gz
mkdir -p eeg-auto-iteration
mv nit-server eeg-auto-iteration/
```

**方法 B：手动创建**

```bash
# 在 nit 上创建目录
mkdir -p ~/eeg-auto-iteration/nit-server/{scripts,config}

# 复制脚本内容（从项目文件中）
nano ~/eeg-auto-iteration/nit-server/scripts/maintain_tunnel.sh
nano ~/eeg-auto-iteration/nit-server/scripts/tunnel_manager.sh
nano ~/eeg-auto-iteration/nit-server/config/config.sh
```

#### 步骤 3：配置 nit

```bash
cd ~/eeg-auto-iteration/nit-server

# 编辑配置文件
vim config/config.sh
```

**必须修改的配置：**

```bash
# 云服务器信息
CLOUD_SERVER="root@<你的云服务器公网IP>"  # 必须修改！
CLOUD_SSH_PORT=22                         # 通常为 22

# 隧道配置
TUNNEL_PORT=3022                          # 建议保持 3022

# 本地配置
REMOTE_USER="your_username"               # 必须修改为 nit 上的用户名
```

#### 步骤 4：在云服务器上添加 nit 的公钥

```bash
# 在 nit 上获取公钥
cat ~/.ssh/id_rsa.pub

# 如果没有 SSH 密钥，先创建
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"

# 复制公钥输出
```

```bash
# 在云服务器上添加公钥
ssh root@云服务器
nano ~/.ssh/authorized_keys

# 粘贴 nit 的公钥
# 保存退出
```

#### 步骤 5：启动隧道

```bash
# 在 nit 上
cd ~/eeg-auto-iteration/nit-server/scripts
chmod +x *.sh

# 启动隧道
./tunnel_manager.sh start

# 检查状态
./tunnel_manager.sh status

# 应该看到：
# 状态: 运行中
# PID: xxxxx
# SSH 隧道: 已建立
```

#### 步骤 6：设置开机自启（可选但推荐）

```bash
# 在 nit 上
crontab -e

# 添加以下内容（等待30秒确保网络就绪）
@reboot sleep 30 && /home/your_username/eeg-auto-iteration/nit-server/scripts/tunnel_manager.sh start

# 保存退出
```

---

### 第二部分：在云服务器上部署

#### 步骤 1：安装依赖

```bash
# 在云服务器上
yum install -y python3-pip jq git

# 安装 Flask
pip3 install flask
```

#### 步骤 2：配置云服务器

```bash
cd /root/.openclaw/workspace/eeg-auto-iteration/cloud-server

# 编辑配置文件
vim config/config.sh
```

**可选配置（通常使用默认值）：**

```bash
# nit 隧道端口（默认 3022）
NIT_SSH_PORT=3022

# 代码仓库
REPO_URL="https://github.com/KyleCream/EEGTokenizer.git"
REPO_DIR="~/EEGTokenizer"
REPO_BRANCH="main"

# Webhook
WEBHOOK_URL="http://localhost:5000/webhook/eegtokenizer"
WEBHOOK_PORT=5000

# 日志
LOG_DIR="/root/.openclaw/workspace/eeg-auto-iteration/logs"

# 训练配置
PROJECT_NAME="EEGTokenizer"
AUTO_SYNC=true  # 是否自动从 GitHub 同步代码
```

#### 步骤 3：测试隧道连接

```bash
# 在云服务器上测试
ssh -p 3022 localhost "hostname && whoami"

# 应该返回：
# nit
# your_username
```

**如果测试失败：**

1. 检查 nit 上的隧道是否运行：
   ```bash
   # 在 nit 上
   ~/eeg-auto-iteration/nit-server/scripts/tunnel_manager.sh status
   ```

2. 检查云服务器的公钥是否正确添加：
   ```bash
   # 在云服务器上
   cat ~/.ssh/authorized_keys
   ```

3. 查看隧道日志：
   ```bash
   # 在 nit 上
   tail -f ~/tunnel_logs/tunnel_*.log
   ```

#### 步骤 4：部署 webhook 服务

```bash
# 在云服务器上
cd /root/.openclaw/workspace/eeg-auto-iteration

# 创建 webhook 服务器（从之前的文件复制）
cp /root/.openclaw/workspace/ssh-webhook-integration/webhook_server.py \
   /root/.openclaw/workspace/eeg-auto-iteration/cloud-server/services/

cp /root/.openclaw/workspace/ssh-webhook-integration/notification_daemon.py \
   /root/.openclaw/workspace/eeg-auto-iteration/cloud-server/services/

# 创建 systemd 服务文件
cat > /etc/systemd/system/eeg-webhook.service << 'EOF'
[Unit]
Description=EEGTokenizer Webhook Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/.openclaw/workspace/eeg-auto-iteration
Environment="WEBHOOK_PORT=5000"
ExecStart=/usr/bin/python3 /root/.openclaw/workspace/eeg-auto-iteration/cloud-server/services/webhook_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/eeg-notification.service << 'EOF'
[Unit]
Description=EEGTokenizer Notification Daemon
After=network.target eeg-webhook.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/.openclaw/workspace/eeg-auto-iteration
ExecStart=/usr/bin/python3 /root/.openclaw/workspace/eeg-auto-iteration/cloud-server/services/notification_daemon.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 重载并启动服务
sudo systemctl daemon-reload
sudo systemctl start eeg-webhook eeg-notification
sudo systemctl enable eeg-webhook eeg-notification

# 检查状态
sudo systemctl status eeg-webhook
sudo systemctl status eeg-notification
```

#### 步骤 5：测试 webhook

```bash
# 测试 webhook 接收
curl -X POST http://localhost:5000/webhook/eegtokenizer \
  -H "Content-Type: application/json" \
  -d '{
    "event": "test",
    "status": "testing",
    "project": "EEGTokenizer",
    "message": "这是一条测试消息"
  }'

# 应该返回：
# {"status": "success", "notification_sent": true}
```

---

## ✅ 验证部署

### 测试清单

- [ ] **nit 隧道运行正常**
  ```bash
  # 在 nit 上
  ~/eeg-auto-iteration/nit-server/scripts/tunnel_manager.sh status
  ```

- [ ] **云服务器可以连接到 nit**
  ```bash
  # 在云服务器上
  ssh -p 3022 localhost "hostname"
  ```

- [ ] **Webhook 服务运行正常**
  ```bash
  # 在云服务器上
  sudo systemctl status eeg-webhook
  ```

- [ ] **通知守护进程运行正常**
  ```bash
  # 在云服务器上
  sudo systemctl status eeg-notification
  ```

- [ ] **飞书通知正常发送**
  ```bash
  # 测试发送通知（应该收到飞书消息）
  curl -X POST http://localhost:5000/webhook/eegtokenizer \
    -H "Content-Type: application/json" \
    -d '{"event": "test", "status": "test", "project": "EEGTokenizer", "message": "测试"}'
  ```

---

## 🔧 故障排查

### 问题 1：隧道连接失败

**症状：**
```bash
ssh -p 3022 localhost "hostname"
# ssh: connect to host localhost port 3022: Connection refused
```

**解决方案：**

1. 检查 nit 上的隧道服务：
   ```bash
   # 在 nit 上
   ~/eeg-auto-iteration/nit-server/scripts/tunnel_manager.sh status
   ```

2. 查看隧道日志：
   ```bash
   # 在 nit 上
   tail -f ~/tunnel_logs/tunnel_*.log
   ```

3. 重启隧道：
   ```bash
   # 在 nit 上
   ~/eeg-auto-iteration/nit-server/scripts/tunnel_manager.sh restart
   ```

### 问题 2：SSH 公钥认证失败

**症状：**
```bash
Permission denied (publickey).
```

**解决方案：**

1. 确认 nit 的公钥已添加到云服务器：
   ```bash
   # 在云服务器上
   cat ~/.ssh/authorized_keys
   ```

2. 重新添加公钥：
   ```bash
   # 在 nit 上
   cat ~/.ssh/id_rsa.pub

   # 在云服务器上
   nano ~/.ssh/authorized_keys
   # 粘贴公钥
   ```

### 问题 3：Webhook 服务无法启动

**症状：**
```bash
sudo systemctl status eeg-webhook
# Failed to start
```

**解决方案：**

1. 检查端口占用：
   ```bash
   netstat -tuln | grep 5000
   ```

2. 查看 Webhook 日志：
   ```bash
   journalctl -u eeg-webhook -n 50
   ```

3. 手动运行测试：
   ```bash
   cd /root/.openclaw/workspace/eeg-auto-iteration
   python3 cloud-server/services/webhook_server.py
   ```

---

## 📊 部署完成后

### 下一步行动

1. ✅ **运行首次训练测试**
   ```bash
   cd /root/.openclaw/workspace/eeg-auto-iteration/cloud-server/scripts
   ./run_training.sh "cd ~/EEGTokenizer && python train.py --test"
   ```

2. ✅ **查看飞书通知**
   - 确认能收到训练开始通知
   - 确认能收到训练完成通知

3. ✅ **查看日志文件**
   ```bash
   ls -lh /root/.openclaw/workspace/eeg-auto-iteration/logs/
   ```

---

## 🎉 部署完成！

现在你已经拥有一个完整的自动回环迭代系统！

**开始使用：**
```bash
cd /root/.openclaw/workspace/eeg-auto-iteration/cloud-server/scripts

# 运行训练
./run_training.sh "cd ~/EEGTokenizer && python train.py"

# 自动迭代
./auto_iterate.sh "cd ~/EEGTokenizer && python train.py" 3
```

**详细使用说明：** 参见 [使用说明](USAGE.md)

---

**Created by:** 小k 🔬
**Date:** 2026-03-18
