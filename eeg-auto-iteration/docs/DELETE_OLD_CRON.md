# 删除旧的 Cron 任务

## 在 nit 上操作

### 步骤 1：查看当前的 Cron 任务

```bash
# 在 nit 上
crontab -l
```

**可能会看到类似这样的输出：**
```
*/5 * * * * /home/zengkai/EEGTokenizer/eeg-auto-iteration/nit-server/scripts/github_pull_train.sh >> /home/zengkai/eeg-auto-logs/cron.log 2>&1
```

---

### 步骤 2：编辑 Cron 任务

```bash
# 在 nit 上
crontab -e
```

**这会打开一个编辑器（通常是 nano 或 vim）**

---

### 步骤 3：删除旧的 Cron 任务

**在编辑器中：**
1. 找到这一行：`*/5 * * * * ...`
2. 删除这一行
3. 保存退出（nano: `Ctrl+O`, `Enter`, `Ctrl+X`）

---

### 步骤 4：验证删除成功

```bash
# 在 nit 上
crontab -l
```

**应该看到：**
- 空的（没有任务）
- 或只有其他任务

---

## 快速删除方法（一行命令）

```bash
# 在 nit 上

# 方法 1：删除所有 Cron 任务（如果有其他任务，请谨慎使用）
crontab -r

# 方法 2：只删除 github_pull_train 相关的任务
crontab -l | grep -v "github_pull_train" | crontab -
```

---

## 删除后重新安装新版本

```bash
# 在 nit 上
cd ~/EEGTokenizer/eeg-auto-iteration/nit-server/scripts

# 重新运行安装脚本（会自动安装30分钟版本）
./install_cron.sh
```

---

## 验证

```bash
# 在 nit 上

# 查看 Cron 任务
crontab -l

# 应该看到：
# */30 * * * * /home/zengkai/EEGTokenizer/eeg-auto-iteration/nit-server/scripts/github_pull_train.sh >> /home/zengkai/eeg-auto-logs/cron.log 2>&1
```

---

## 总结

**删除旧 Cron 任务的三种方法：**

### 方法 1：编辑 crontab（推荐）
```bash
crontab -e
# 删除对应行，保存退出
```

### 方法 2：一行命令删除所有任务
```bash
crontab -r
# 然后重新运行 install_cron.sh
```

### 方法 3：一行命令只删除特定任务
```bash
crontab -l | grep -v "github_pull_train" | crontab -
# 然后重新运行 install_cron.sh
```

---

**推荐使用方法 1**（编辑 crontab），因为最安全！
