# GitHub + Cron 轮询方案 - 完整指南

**日期：** 2026-03-18
**方案：** GitHub + Cron 轮询（30分钟间隔）

---

## 🎯 方案概述

由于 nit 无法修改 SSH 配置（需要管理员权限），我们采用 **GitHub + Cron 轮询方案**。

### 架构

```
云服务器
    ↓ git push
GitHub（Single Source of Truth）
    ↓ git pull（每 30 分钟）
nit 执行训练
    ↓ git push（结果）
GitHub
    ↓ git pull
云服务器查看结果
```

### 运行方式

**每次都运行训练**（不管有没有更新）

- ✅ **每次 Cron 触发都会运行训练**
- ✅ **持续尝试不同的配置**
- ✅ **自动重试（上次失败会自动重试）**
- ✅ **适合持续探索和实验**

---

## ✅ 优势

- ✅ **不需要 SSH 隧道**
- ✅ **不需要修改 SSH 配置**
- ✅ **不需要管理员权限**
- ✅ **代码有版本控制**
- ✅ **GitHub 是 Single Source of Truth**
- ✅ **实现简单**
- ✅ **每 30 分钟自动运行训练**

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

### 步骤 2：运行一键安装脚本

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
4. 安装 Cron 任务（30分钟间隔）
5. 询问是否立即测试运行

---

### 步骤 3：验证安装

```bash
# 在 nit 上

# 查看 Cron 任务
crontab -l
```

**应该看到：**
```
*/30 * * * * /home/zengkai/EEGTokenizer/eeg-auto-iteration/nit-server/scripts/github_pull_train.sh >> /home/zengkai/eeg-auto-logs/cron.log 2>&1
```

**说明：每 30 分钟运行一次（00分, 30分）**

---

## 🔄 工作原理

### 自动化流程

```
1. Cron 每 30 分钟触发一次（00分, 30分）
   ↓
2. github_pull_train.sh 运行
   ↓
3. 拉取最新代码（不管有没有更新）
   ↓
4. 激活 mamba_cuda121 环境
   ↓
5. 运行训练
   ↓
6. 推送结果回 GitHub
   ↓
7. 等待下一次触发（30分钟后）
```

### 运行时间

**每 30 分钟运行一次：**
- 00:00
- 00:30
- 01:00
- 01:30
- ...
- 23:30

---

## 📝 使用方法

### 在 nit 上手动触发训练

```bash
# 在 nit 上
cd ~/EEGTokenizer/eeg-auto-iteration/nit-server/scripts
./github_pull_train.sh
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

**默认：** 每 30 分钟检查一次

**运行时间：** 00分, 30分（每小时两次）

**修改间隔：**

```bash
# 在 nit 上
crontab -e

# 修改间隔（例如改为每 15 分钟）
# */30 * * * * ...
# 改为：
# */15 * * * * ...

# 保存退出
```

**常用间隔：**
- `*/5 * * * *` - 每 5 分钟
- `*/15 * * * *` - 每 15 分钟
- `*/30 * * * *` - 每 30 分钟（默认）
- `0 */1 * * *` - 每 1 小时
- `0 */2 * * *` - 每 2 小时
- `0 */6 * * *` - 每 6 小时

---

### Python 环境

**默认：** `mamba_cuda121` conda 环境

**Python 路径：** `/home/zengkai/conda/envs/mamba_cuda121/bin/python`

**修改配置：**

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

### 训练配置

**修改训练参数：**

```bash
# eegtokenizer_v2/configs/experiments.yaml

adc_4bit:
  model:
    tokenizer:
      num_bits: 4
      quant_type: "scalar"
      agg_type: "mean"
  
  data:
    subject_id: "A01"
    sessions: "train"
    win_sel: [0.0, 4.0]
  
  training:
    epochs: 100
    batch_size: 32
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

# 查看 Cron 日志（系统日志）
sudo grep CRON /var/log/syslog | tail -20
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

### 查看下次运行时间

```bash
# 在 nit 上

# 查看当前时间
date

# 计算下次运行时间
python3 -c "from datetime import datetime, timedelta; now=datetime.now(); next_run=(now.minute//30+1)*30; print(f'下次运行: {now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1 if now.minute>=30 else 0, minutes=30 if now.minute<30 else 0)}')"
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
tail -f ~/eeg-auto-logs/training_$(date +%Y%m%d).log
```

---

## 🎯 完整示例

### 示例 1：首次设置

```bash
# 在 nit 上

# 1. 克隆仓库
cd ~
git clone https://github.com/KyleCream/EEGTokenizer.git
cd ~/EEGTokenizer

# 2. 运行安装脚本
cd eeg-auto-iteration/nit-server/scripts
chmod +x install_cron.sh
./install_cron.sh

# 3. 确认安装
crontab -l

# 4. 查看下次运行时间
date
```

---

### 示例 2：手动触发训练

```bash
# 在 nit 上
cd ~/EEGTokenizer/eeg-auto-iteration/nit-server/scripts
./github_pull_train.sh
```

---

### 示例 3：查看训练结果

```bash
# 在 nit 上

# 1. 查看训练日志
tail -f ~/eeg-auto-logs/training_$(date +%Y%m%d).log

# 2. 查看检查点
ls -lh ~/EEGTokenizer/eegtokenizer_v2/checkpoints/

# 3. 查看结果
ls -lh ~/EEGTokenizer/eegtokenizer_v2/logs/
```

---

## ⚠️ 注意事项

### 1. 确保环境正确

```bash
# 在 nit 上

# 激活环境
conda activate mamba_cuda121

# 验证 Python
python --version
which python
# 应该输出：/home/zengkai/conda/envs/mamba_cuda121/bin/python

# 验证依赖
python -c "import torch; print(torch.__version__)"
python -c "import mne; print(mne.__version__)"
```

---

### 2. 确保数据文件正确

```bash
# 在 nit 上

# 检查数据文件
ls -lh ~/EEGTokenizer/data/BCI_IV_2a/A01T.gdf
ls -lh ~/EEGTokenizer/data/BCI_IV_2a/A01E.gdf

# 应该看到文件存在
```

---

### 3. 确保脚本有执行权限

```bash
# 在 nit 上

cd ~/EEGTokenizer/eeg-auto-iteration/nit-server/scripts

# 检查权限
ls -la *.sh

# 如果没有执行权限，添加：
chmod +x *.sh
```

---

### 4. 监控磁盘空间

```bash
# 在 nit 上

# 查看磁盘空间
df -h

# 查看日志目录大小
du -sh ~/eeg-auto-logs/

# 清理旧日志（保留最近7天）
find ~/eeg-auto-logs/ -name "*.log" -mtime +7 -delete
```

---

## 🎉 完成

现在你已经拥有一个完整的 **GitHub + Cron 自动回环系统**！

**特点：**
- ✅ 不需要 SSH 隧道
- ✅ 不需要管理员权限
- ✅ 代码有版本控制
- ✅ 每 30 分钟自动运行训练
- ✅ 持续探索和实验

**运行方式：**
- 自动：每 30 分钟运行一次
- 手动：随时可以手动触发

---

**Created by:** 小k 🔬
**Date:** 2026-03-18
**Status:** ✅ 已完成并推送到 GitHub
