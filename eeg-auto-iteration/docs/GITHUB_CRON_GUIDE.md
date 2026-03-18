# GitHub + Cron 轮询方案 - 完整指南

**日期：** 2026-03-18
**方案：** GitHub + Cron 轮询（标记文件控制）

---

## 🎯 方案概述

由于 nit 无法修改 SSH 配置（需要管理员权限），我们采用 **GitHub + Cron 轮询方案**。

### 架构

```
云服务器
    ↓ git push + 创建 .needs_training
GitHub（Single Source of Truth）
    ↓ git pull（每 30 分钟）
nit 检查 .needs_training
    ↓ 如果存在
nit 运行训练
    ↓ 删除 .needs_training
    ↓ git push（结果）
GitHub
```

### 运行方式

**标记文件控制：**
- ✅ 创建 `.needs_training` 文件 → 下次 Cron 运行时训练
- ✅ 训练完成后自动删除标记文件
- ✅ 灵活控制训练时机
- ✅ 避免不必要的训练

---

## ✅ 优势

- ✅ **不需要 SSH 隧道**
- ✅ **不需要修改 SSH 配置**
- ✅ **不需要管理员权限**
- ✅ **代码有版本控制**
- ✅ **GitHub 是 Single Source of Truth**
- ✅ **实现简单**
- ✅ **标记文件灵活控制**
- ✅ **训练失败自动保留标记（下次重试）**

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
3. 检查 .needs_training 文件是否存在
   ↓
4. 如果不存在：
   - 退出，等待下次检查
   ↓
5. 如果存在：
   - 拉取最新代码
   - 激活 mamba_cuda121 环境
   - 运行训练
   - 删除 .needs_training 文件
   - 推送结果回 GitHub
   ↓
6. 等待下一次触发
```

---

## 📝 使用方法

### 方法 1：在云服务器上触发训练（推荐）⭐⭐⭐⭐⭐

```bash
# 在云服务器上
cd ~/EEGTokenizer

# 创建标记文件并推送到 GitHub
touch .needs_training
git add .needs_training
git commit -m "触发训练"
git push origin main
```

**等待 30 分钟内，nit 会自动：**
1. Pull 代码
2. 检测到 `.needs_training` 文件
3. 运行训练
4. 删除标记文件
5. 推送结果

---

### 方法 2：在 nit 上手动触发（立即训练）

```bash
# 在 nit 上
cd ~/EEGTokenizer/eeg-auto-iteration/nit-server/scripts

# 创建标记文件
./trigger_training.sh

# 或立即运行训练
./github_pull_train.sh
```

---

### 方法 3：带参数触发训练

```bash
# 在云服务器上
cd ~/EEGTokenizer

# 创建标记文件并指定参数
echo "--config eegtokenizer_v2/configs/experiments.yaml::adc_8bit" > .needs_training
git add .needs_training
git commit -m "触发训练：ADC 8bit"
git push origin main
```

---

## 🔧 控制选项

### 触发训练

```bash
# 在云服务器上
cd ~/EEGTokenizer

# 触发默认训练
touch .needs_training
git add .needs_training
git commit -m "触发训练"
git push origin main
```

---

### 取消训练

```bash
# 在云服务器上
cd ~/EEGTokenizer

# 删除标记文件
rm .needs_training
git add .needs_training
git commit -m "取消训练"
git push origin main
```

---

### 检查训练状态

```bash
# 在 nit 上

# 检查标记文件是否存在
ls -la ~/EEGTokenizer/.needs_training

# 如果存在，说明等待训练
# 如果不存在，说明没有待训练任务
```

---

## 📊 监控和管理

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

## 🛠️ 故障排查

### 问题 1：创建了标记文件但没有训练

**检查：**

```bash
# 在 nit 上

# 1. 检查标记文件是否同步到 nit
cd ~/EEGTokenizer
git pull origin main
ls -la .needs_training

# 2. 查看 Cron 日志
tail -f ~/eeg-auto-logs/cron.log

# 3. 手动运行脚本
cd ~/EEGTokenizer/eeg-auto-iteration/nit-server/scripts
./github_pull_train.sh
```

---

### 问题 2：训练失败后没有重试

**检查：**

```bash
# 在 nit 上

# 1. 查看训练日志
tail -f ~/eeg-auto-logs/training_*.log

# 2. 检查标记文件是否还存在
ls -la ~/EEGTokenizer/.needs_training

# 如果标记文件存在，下次 Cron 会自动重试
```

---

### 问题 3：如何手动重试失败的训练

```bash
# 在 nit 上
cd ~/EEGTokenizer/eeg-auto-iteration/nit-server/scripts

# 立即运行训练（会检查标记文件）
./github_pull_train.sh
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
```

---

### 示例 2：触发训练

```bash
# 在云服务器上
cd ~/EEGTokenizer

# 创建标记文件
touch .needs_training

# 推送到 GitHub
git add .needs_training
git commit -m "触发训练"
git push origin main

# 等待 30 分钟内，nit 自动运行训练
```

---

### 示例 3：触发特定配置的训练

```bash
# 在云服务器上
cd ~/EEGTokenizer

# 创建标记文件并指定参数
echo "--config eegtokenizer_v2/configs/experiments.yaml::adc_attention" > .needs_training

# 推送到 GitHub
git add .needs_training
git commit -m "触发训练：ADC + Attention"
git push origin main
```

---

### 示例 4：取消训练

```bash
# 在云服务器上
cd ~/EEGTokenizer

# 删除标记文件
rm .needs_training

# 推送到 GitHub
git add .needs_training
git commit -m "取消训练"
git push origin main
```

---

### 示例 5：查看训练状态

```bash
# 在 nit 上

# 检查标记文件
ls -la ~/EEGTokenizer/.needs_training

# 查看日志
tail -f ~/eeg-auto-logs/training_*.log
```

---

## ⚠️ 注意事项

### 1. 标记文件会自动删除

**训练成功后：**
- ✅ 标记文件自动删除
- ✅ 结果推送到 GitHub

**训练失败后：**
- ⚠️ 标记文件保留
- ✅ 下次 Cron 会自动重试

---

### 2. 多次触发的效果

**如果在训练过程中再次触发：**
- ✅ 不会重复训练
- ✅ 标记文件保留到训练成功

**如果需要排队训练：**
- 可以创建多个标记文件
- 或在训练完成后再次触发

---

### 3. 确保环境正确

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

## 🎉 完成

现在你已经拥有一个完整的 **GitHub + Cron 自动回环系统（标记文件控制）**！

**特点：**
- ✅ 不需要 SSH 隧道
- ✅ 不需要管理员权限
- ✅ 代码有版本控制
- ✅ 标记文件灵活控制
- ✅ 每 30 分钟自动检查
- ✅ 训练失败自动重试

**使用方式：**
- **触发训练：** 创建 `.needs_training` 文件
- **取消训练：** 删除 `.needs_training` 文件
- **查看状态：** 检查 `.needs_training` 是否存在

---

**Created by:** 小k 🔬
**Date:** 2026-03-18
**Status:** ✅ 已完成并推送到 GitHub
