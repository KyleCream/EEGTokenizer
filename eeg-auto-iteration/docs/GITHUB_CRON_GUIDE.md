# GitHub + Cron 轮询方案 - 完整指南

**日期：** 2026-03-18
**方案：** GitHub + Cron 轮询（不需要 SSH 隧道）

---

## 🎯 方案概述

由于 nit 无法修改 SSH 配置（需要管理员权限），我们采用 **GitHub + Cron 轮询方案**。

### 架构

```
云服务器
    ↓ git push
GitHub（Single Source of Truth）
    ↓ git pull（每 5 分钟）
nit 执行训练
    ↓ git push（结果）
GitHub
    ↓ git pull
云服务器查看结果
```

---

## ✅ 优势

- ✅ **不需要 SSH 隧道**
- ✅ **不需要修改 SSH 配置**
- ✅ **不需要管理员权限**
- ✅ **代码有版本控制**
- ✅ **GitHub 是 Single Source of Truth**
- ✅ **实现简单**

---

## 📋 部署步骤

### 步骤 1：在 nit 上克隆仓库

```bash
# 在 nit 上
cd ~
git clone https://github.com/KyleCream/EEGTokenizer.git
cd ~/EEGTokenizer
```

---

### 步骤 2：修改配置文件

```bash
# 在 nit 上
cd ~/EEGTokenizer/eeg-auto-iteration/nit-server

# 编辑配置文件
nano config/config.sh
```

**必须修改的配置：**

```bash
# GitHub 仓库 URL
GITHUB_REPO="https://github.com/KyleCream/EEGTokenizer.git"

# 本地项目路径
PROJECT_DIR="$HOME/EEGTokenizer"

# Conda 环境名称
CONDA_ENV_NAME="mamba_cuda121"

# Python 解释器路径
PYTHON_PATH="$HOME/conda/envs/$CONDA_ENV_NAME/bin/python"

# 激活 Conda 环境的脚本
CONDA_INIT="$HOME/conda/etc/profile.d/conda.sh"
```

**保存退出（`Ctrl+O`，`Enter`，`Ctrl+X`）**

---

### 步骤 3：运行安装脚本

```bash
# 在 nit 上
cd ~/EEGTokenizer/eeg-auto-iteration/nit-server/scripts
chmod +x install_cron.sh
./install_cron.sh
```

**安装脚本会自动：**
1. 检查配置
2. 克隆 GitHub 仓库
3. 设置脚本权限
4. 安装 Cron 任务
5. 测试运行

---

### 步骤 4：验证安装

```bash
# 在 nit 上

# 查看 Cron 任务
crontab -l

# 应该看到类似这样的输出：
# */5 * * * * /home/zengkai/EEGTokenizer/eeg-auto-iteration/nit-server/scripts/github_pull_train.sh >> /home/zengkai/eeg-auto-logs/cron.log 2>&1
```

---

### 步骤 5：测试首次运行

```bash
# 在云服务器上
cd ~/EEGTokenizer

# 修改配置（触发更新）
vim eegtokenizer_v2/configs/experiments.yaml

# 提交并推送
git add .
git commit -m "测试 GitHub + Cron 方案"
git push origin main
```

**等待 5 分钟，nit 会自动：**
1. 检查 GitHub 更新
2. Pull 最新代码
3. 运行训练
4. 推送结果回 GitHub

---

## 📝 使用方法

### 在云服务器上触发训练

```bash
# 在云服务器上
cd ~/EEGTokenizer

# 修改代码或配置
vim eegtokenizer_v2/configs/experiments.yaml

# 提交并推送
git add .
git commit -m "添加新的训练任务"
git push origin main
```

---

### 在 nit 上查看日志

```bash
# 在 nit 上

# 查看 Cron 日志
tail -f ~/eeg-auto-logs/cron.log

# 查看训练日志
tail -f ~/eeg-auto-logs/training_*.log
```

---

### 在云服务器上查看结果

```bash
# 在云服务器上
cd ~/EEGTokenizer

# 拉取结果
git pull origin main

# 查看训练日志
ls -lh eegtokenizer_v2/logs/
tail -f eegtokenizer_v2/logs/training_*.log

# 查看检查点
ls -lh eegtokenizer_v2/checkpoints/
```

---

## 🔧 配置说明

### Cron 轮询间隔

**默认：每 5 分钟检查一次**

修改配置文件中的 `CHECK_INTERVAL`：

```bash
# nit-server/config/config.sh

# 检查间隔（分钟）
CHECK_INTERVAL=5  # 可以改为 1, 2, 3, 5, 10, 15, 30
```

---

### Python 环境

**默认：** `mamba_cuda121` conda 环境

**Python 路径：** `/home/zengkai/conda/envs/mamba_cuda121/bin/python`

**如果使用其他环境，修改配置：**

```bash
# nit-server/config/config.sh

# Conda 环境名称
CONDA_ENV_NAME="your_env_name"

# Python 解释器路径
PYTHON_PATH="$HOME/conda/envs/$CONDA_ENV_NAME/bin/python"

# 激活 Conda 环境的脚本
CONDA_INIT="$HOME/conda/etc/profile.d/conda.sh"
```

---

### 数据集配置

**默认配置：**

```bash
# 数据目录
DATA_DIR="./data/BCI_IV_2a"

# 被试 ID
SUBJECT_ID="A01"

# 时间窗口（秒）
WIN_TMIN=0.0
WIN_TMAX=4.0
```

**修改训练配置：**

```bash
# eegtokenizer_v2/configs/experiments.yaml

data:
  dataset: "BCI_IV_2a"
  data_dir: "./data/BCI_IV_2a"
  subject_id: "A01"
  sessions: "train"  # 'train' / 'test' / 'both'
  win_sel: [0.0, 4.0]  # 时间窗口，单位秒
```

---

## 🛠️ 故障排查

### 问题 1：Cron 任务没有运行

**检查：**

```bash
# 在 nit 上

# 查看 Cron 日志
tail -f ~/eeg-auto-logs/cron.log

# 查看 Cron 服务状态
sudo systemctl status cron

# 查看 Cron 任务
crontab -l
```

---

### 问题 2：训练失败

**检查：**

```bash
# 在 nit 上

# 查看训练日志
tail -f ~/eeg-auto-logs/training_*.log

# 检查 Python 环境
conda activate mamba_cuda121
python --version
which python

# 手动运行训练
cd ~/EEGTokenizer
python eegtokenizer_v2/train.py --config eegtokenizer_v2/configs/experiments.yaml::adc_4bit
```

---

### 问题 3：数据加载失败

**检查：**

```bash
# 在 nit 上

# 检查数据文件
ls -lh ~/EEGTokenizer/data/BCI_IV_2a/A01T.gdf
ls -lh ~/EEGTokenizer/data/BCI_IV_2a/A01E.gdf

# 测试数据加载
conda activate mamba_cuda121
cd ~/EEGTokenizer
python -c "
from eegtokenizer_v2.data.loader import load_BNCI2014_001
data = load_BNCI2014_001('./data/BCI_IV_2a', 1, (0.0, 4.0), 'train')
print('数据形状:', data['X'].shape)
print('标签形状:', data['Y'].shape)
"
```

---

## 📊 监控和管理

### 查看 Cron 任务

```bash
# 在 nit 上
crontab -l
```

---

### 删除 Cron 任务

```bash
# 在 nit 上
crontab -e
# 删除对应行，保存退出
```

---

### 手动触发训练

```bash
# 在 nit 上
cd ~/EEGTokenizer/eeg-auto-iteration/nit-server/scripts
./github_pull_train.sh
```

---

### 查看训练进度

```bash
# 在 nit 上
tail -f ~/eeg-auto-logs/training_*.log
```

---

## 🎉 完成

现在你已经拥有一个完整的 **GitHub + Cron 自动回环系统**！

**特点：**
- ✅ 不需要 SSH 隧道
- ✅ 不需要管理员权限
- ✅ 代码有版本控制
- ✅ 自动轮询和训练

**开始使用：**
1. 在云服务器上修改代码
2. `git push` 到 GitHub
3. 等待 5 分钟
4. nit 自动运行训练

---

**Created by:** 小k 🔬
**Date:** 2026-03-18
**Status:** ✅ 已完成并推送到 GitHub
