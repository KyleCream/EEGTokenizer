# 快速参考卡 - EEGTokenizer 自动回环系统

## 🚀 常用命令

### 在云服务器上

```bash
# === 运行训练 ===
cd /root/.openclaw/workspace/eeg-auto-iteration/cloud-server/scripts

# 单次运行（带错误捕获）
./run_training.sh "cd ~/EEGTokenizer && python train.py"

# 自动迭代（最多重试 3 次）
./auto_iterate.sh "cd ~/EEGTokenizer && python train.py" 3

# 快速同步代码
./sync_code.sh ~/EEGTokenizer

# === 服务管理 ===
# 查看 webhook 状态
sudo systemctl status eeg-webhook

# 重启 webhook
sudo systemctl restart eeg-webhook

# 查看通知守护进程状态
sudo systemctl status eeg-notification

# === 日志查看 ===
# 查看最新运行日志
ls -lt /root/.openclaw/workspace/eeg-auto-iteration/logs/run_*.log | head -1 | xargs tail

# 查看最新错误日志
ls -lt /root/.openclaw/workspace/eeg-auto-iteration/logs/error_*.log | head -1 | xargs cat

# === 测试隧道 ===
# 测试连接到 nit
ssh -p 3022 localhost "hostname && whoami"
```

### 在 nit 上

```bash
# === 隧道管理 ===
cd ~/eeg-auto-iteration/nit-server/scripts

# 启动隧道
./tunnel_manager.sh start

# 停止隧道
./tunnel_manager.sh stop

# 重启隧道
./tunnel_manager.sh restart

# 查看状态
./tunnel_manager.sh status

# 查看日志
./tunnel_manager.sh log

# === 日志查看 ===
# 查看隧道日志
tail -f ~/tunnel_logs/tunnel_*.log
```

---

## 🎯 常见场景

### 场景 1：日常开发训练

```bash
# 1. 修改代码
vim ~/EEGTokenizer/train.py

# 2. 提交到 GitHub
cd ~/EEGTokenizer
git add . && git commit -m "feat: 新功能" && git push

# 3. 运行训练（自动拉取最新代码）
cd /root/.openclaw/workspace/eeg-auto-iteration/cloud-server/scripts
./run_training.sh "cd ~/EEGTokenizer && python train.py"
```

### 场景 2：快速测试调试

```bash
# 1. 修改代码
vim ~/EEGTokenizer/test.py

# 2. 快速同步到 nit（跳过 GitHub）
cd /root/.openclaw/workspace/eeg-auto-iteration/cloud-server/scripts
./sync_code.sh ~/EEGTokenizer

# 3. 运行测试（跳过同步）
AUTO_SYNC=false ./run_training.sh "cd ~/EEGTokenizer && python test.py"
```

### 场景 3：修复 bug

```bash
# 启动自动迭代（最多重试 5 次）
cd /root/.openclaw/workspace/eeg-auto-iteration/cloud-server/scripts
./auto_iterate.sh "cd ~/EEGTokenizer && python train.py" 5

# 同时在另一个终端：
# 1. 等待飞书错误通知
# 2. 修复代码
# 3. 推送到 GitHub
# 4. 等待自动重试成功
```

---

## 🔧 环境变量

```bash
# 自定义隧道端口
NIT_SSH_PORT=3022 ./run_training.sh "command"

# 跳过代码自动同步
AUTO_SYNC=false ./run_training.sh "command"

# 自定义项目名称
PROJECT_NAME="MyProject" ./run_training.sh "command"
```

---

## 📊 文件位置

### 云服务器

| 类型 | 路径 |
|------|------|
| 执行脚本 | `/root/.openclaw/workspace/eeg-auto-iteration/cloud-server/scripts/` |
| 日志文件 | `/root/.openclaw/workspace/eeg-auto-iteration/logs/` |
| 配置文件 | `/root/.openclaw/workspace/eeg-auto-iteration/cloud-server/config/config.sh` |
| 文档 | `/root/.openclaw/workspace/eeg-auto-iteration/docs/` |

### nit

| 类型 | 路径 |
|------|------|
| 隧道脚本 | `~/eeg-auto-iteration/nit-server/scripts/` |
| 隧道日志 | `~/tunnel_logs/` |
| 配置文件 | `~/eeg-auto-iteration/nit-server/config/config.sh` |
| 代码目录 | `~/EEGTokenizer/` |

---

## ⚡ 快速诊断

### 隧道连接失败？

```bash
# 1. 检查 nit 上的隧道状态
ssh -p 3022 localhost "hostname"

# 2. 如果失败，在 nit 上检查
~/eeg-auto-iteration/nit-server/scripts/tunnel_manager.sh status

# 3. 查看隧道日志
tail -f ~/tunnel_logs/tunnel_*.log

# 4. 重启隧道
~/eeg-auto-iteration/nit-server/scripts/tunnel_manager.sh restart
```

### Webhook 无通知？

```bash
# 1. 检查服务状态
sudo systemctl status eeg-webhook
sudo systemctl status eeg-notification

# 2. 查看 webhook 日志
journalctl -u eeg-webhook -n 50

# 3. 测试 webhook
curl -X POST http://localhost:5000/webhook/eegtokenizer \
  -H "Content-Type: application/json" \
  -d '{"event": "test", "status": "test", "project": "EEGTokenizer"}'

# 4. 重启服务
sudo systemctl restart eeg-webhook eeg-notification
```

### 训练失败？

```bash
# 1. 查看错误日志
ls -lt /root/.openclaw/workspace/eeg-auto-iteration/logs/error_*.log | head -1 | xargs cat

# 2. 查看完整运行日志
ls -lt /root/.openclaw/workspace/eeg-auto-iteration/logs/run_*.log | head -1 | xargs tail

# 3. 修复代码后重新运行
./run_training.sh "cd ~/EEGTokenizer && python train.py"
```

---

## 📞 获取帮助

| 问题类型 | 解决方案 |
|---------|---------|
| 部署问题 | 查看 `docs/DEPLOYMENT.md` |
| 使用问题 | 查看 `docs/USAGE.md` |
| 隧道问题 | 查看 `docs/TROUBLESHOOTING.md` |
| 其他问题 | 联系小k（飞书）|

---

## 🎯 下一步

1. ✅ 完成首次部署
2. ✅ 运行测试训练
3. ✅ 查看飞书通知
4. ✅ 尝试自动迭代
5. ✅ 开始日常使用

---

**提示：** 将此文件加入书签，方便快速查找命令！
