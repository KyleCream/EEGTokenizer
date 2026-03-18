# nit 环境适配完整指南

**版本：** 1.0.0
**日期：** 2026-03-18

---

## 🎯 目标

让训练脚本**自动适配 nit 的环境**，无需手动指定 Python 路径或 CUDA 设备。

---

## 📋 问题分析

### 问题 1：nit 环境未知

**你可能的环境：**

| 环境 | Python 位置 | 包管理 | 常见场景 |
|------|------------|--------|---------|
| **系统 Python** | `/usr/bin/python3` | pip | 轻量级、简单项目 |
| **虚拟环境 (venv)** | `~/project/venv/bin/python` | pip | 隔离环境、推荐 |
| **Conda** | `~/anaconda3/bin/python` | conda | 数据科学、ML 项目 |
| **Docker** | `/opt/conda/bin/python` | pip/conda | 容器化部署 |

### 问题 2：GPU 资源管理

**问题：**
- 训练需要 GPU
- GPU 可能被其他任务占用
- 直接运行会显存不足（OOM）

**解决：**
- ✅ 检测 GPU 状态
- ✅ 等待 GPU 空闲
- ✅ 空闲时自动运行

---

## 🚀 解决方案

### 方案 1：环境自动检测（智能训练脚本）

**脚本：** `smart_train.sh`

**功能：**

1. ✅ **自动检测并激活 Python 环境**
   - 优先使用虚拟环境（`venv`）
   - 其次使用 Conda 环境
   - 最后使用系统 Python

2. ✅ **检查 PyTorch 和 CUDA**
   - 验证 PyTorch 是否安装
   - 检查 CUDA 是否可用
   - 显示 GPU 信息

3. ✅ **智能启动训练**
   - 自动进入项目目录
   - 使用正确的 Python 解释器
   - 设置正确的 CUDA 设备

**使用方法：**

```bash
# 在 nit 上直接运行
cd ~/eeg-auto-iteration/nit-server/scripts
./smart_train.sh "python train.py --epochs 100"

# 或从云服务器运行
cd /root/.openclaw/workspace/eeg-auto-iteration/cloud-server/scripts
./run_training_smart.sh "python train.py --epochs 100"
```

**检测逻辑：**

```bash
# 1. 检查虚拟环境
if [ -f ~/EEGTokenizer/venv/bin/activate ]; then
    source ~/EEGTokenizer/venv/bin/activate
    echo "✓ 使用虚拟环境"

# 2. 检查 Conda
elif command -v conda &> /dev/null; then
    conda activate base  # 或你的环境名
    echo "✓ 使用 Conda 环境"

# 3. 使用系统 Python
else
    echo "✓ 使用系统 Python"
fi

# 4. 验证 PyTorch
python -c "import torch; print('CUDA:', torch.cuda.is_available())"
```

---

### 方案 2：GPU 队列管理

**脚本：** `gpu_queue.sh`

**功能：**

1. ✅ **实时监控 GPU 状态**
   - 检查 GPU 内存使用率
   - 检查 GPU 利用率
   - 检查活跃进程

2. ✅ **智能等待**
   - GPU 繁忙时等待
   - GPU 空闲时立即运行
   - 支持超时和强制运行

3. ✅ **灵活配置**
   - 可设置内存阈值
   - 可设置等待时间
   - 可强制运行（忽略占用）

**使用方法：**

```bash
# 在 nit 上运行
cd ~/eeg-auto-iteration/nit-server/scripts

# 正常模式（等待 GPU 空闲）
./gpu_queue.sh "python train.py"

# 强制模式（忽略 GPU 占用）
FORCE_RUN=true ./gpu_queue.sh "python train.py"

# 自定义等待时间（1小时）
MAX_WAIT_TIME=3600 ./gpu_queue.sh "python train.py"
```

**配置说明：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `GPU_MEMORY_THRESHOLD` | 90 | GPU 内存使用率阈值（%） |
| `MAX_WAIT_TIME` | 7200 | 最大等待时间（秒，2小时） |
| `CHECK_INTERVAL` | 30 | 检查间隔（秒） |
| `FORCE_RUN` | false | 是否强制运行 |

**工作流程：**

```
开始 → 检查 GPU → 空闲？
                    ↓ 是
                  运行训练 → 完成
                    ↓ 否
                  等待 30 秒 → 超时？
                              ↓ 是
                            失败
                              ↓ 否
                          重新检查
```

---

## 📝 完整部署流程

### 第 1 步：在 nit 上检测环境

```bash
# 在 nit 上运行（用 atrust 或学校内网登录）
cd ~/eeg-auto-iteration/nit-server/scripts
chmod +x detect_environment.sh
./detect_environment.sh

# 会生成详细的环境报告
# 将报告发送给小k
```

**报告包含：**

- ✅ 系统信息（OS、内存、CPU）
- ✅ Python 环境（版本、路径）
- ✅ PyTorch 信息（版本、CUDA 支持）
- ✅ GPU 信息（型号、显存、驱动）
- ✅ 已安装的依赖包
- ✅ Git 配置
- ✅ SSH 公钥

### 第 2 步：上传智能脚本到 nit

```bash
# 在云服务器上打包
cd /root/.openclaw/workspace/eeg-auto-iteration
tar -czf nit-scripts-package.tar.gz nit-server/scripts/

# 复制到 nit
scp nit-scripts-package.tar.gz your_username@nit:~/

# 在 nit 上解压
ssh your_username@nit
cd ~
tar -xzf nit-scripts-package.tar.gz
```

### 第 3 步：测试智能训练脚本

```bash
# 在 nit 上测试
cd ~/eeg-auto-iteration/nit-server/scripts

# 测试 1：检查环境
./smart_train.sh "python -c 'import torch; print(torch.__version__)'"

# 测试 2：简单训练
./smart_train.sh "python train.py --test --epochs 1"

# 测试 3：GPU 队列
./gpu_queue.sh "python train.py --test"
```

### 第 4 步：从云服务器运行

```bash
# 在云服务器上
cd /root/.openclaw/workspace/eeg-auto-iteration/cloud-server/scripts

# 使用智能训练脚本
./run_training_smart.sh "python train.py --epochs 100"

# 优势：
# - 自动检测 nit 的 Python 环境
# - 自动等待 GPU 空闲
# - 自动捕获错误和日志
```

---

## 🔧 环境适配示例

### 示例 1：虚拟环境

**nit 环境：**
```bash
# 项目目录：~/EEGTokenizer
# 虚拟环境：~/EEGTokenizer/venv
# Python：3.10
# PyTorch：2.0.0 + CUDA 11.8
```

**智能脚本会自动：**
```bash
cd ~/EEGTokenizer
source venv/bin/activate
python train.py  # 使用 venv 中的 python
```

### 示例 2：Conda 环境

**nit 环境：**
```bash
# Conda 环境：base
# Python：3.9
# PyTorch：1.13.0 + CUDA 11.7
```

**智能脚本会自动：**
```bash
conda activate base
python train.py  # 使用 conda 环境中的 python
```

### 示例 3：系统 Python

**nit 环境：**
```bash
# Python：/usr/bin/python3
# PyTorch：全局安装
```

**智能脚本会自动：**
```bash
cd ~/EEGTokenizer
python3 train.py  # 使用系统 python
```

---

## 🎯 最佳实践

### 1. 使用智能训练脚本（推荐）

```bash
# 从云服务器运行
./run_training_smart.sh "python train.py"

# 优势：
# - 自动适配环境
# - 自动等待 GPU
# - 完整错误捕获
```

### 2. GPU 忙碌时等待

```bash
# 正常模式：最多等待 2 小时
./run_training_smart.sh "python train.py"

# 自定义等待时间
MAX_WAIT_TIME=3600 ./run_training_smart.sh "python train.py"

# 强制运行（谨慎！）
FORCE_RUN=true ./run_training_smart.sh "python train.py"
```

### 3. 多任务管理

```bash
# 任务 1：等待 GPU
./run_training_smart.sh "python train.py --model modelA" &

# 任务 2：等待 GPU（会排队）
./run_training_smart.sh "python train.py --model modelB" &

# 查看任务
jobs
```

---

## 📊 对比

| 方案 | 环境检测 | GPU 管理 | 错误处理 | 推荐度 |
|------|---------|---------|---------|--------|
| **手动运行** | ❌ | ❌ | ⚠️ | ⭐ |
| **智能训练脚本** | ✅ | ❌ | ✅ | ⭐⭐⭐⭐ |
| **GPU 队列** | ❌ | ✅ | ✅ | ⭐⭐⭐⭐ |
| **智能训练 + GPU 队列** | ✅ | ✅ | ✅ | ⭐⭐⭐⭐⭐ |

---

## 🎁 总结

### 核心优势

1. ✅ **环境自适应**：自动检测虚拟环境、Conda、系统 Python
2. ✅ **GPU 智能管理**：自动等待 GPU 空闲
3. ✅ **完整错误捕获**：详细的错误日志和飞书通知
4. ✅ **无需手动配置**：自动适配 nit 的环境

### 下一步

1. **在 nit 上运行环境检测**
   ```bash
   ./detect_environment.sh
   ```

2. **将报告发送给小k**
   - 包含 Python 环境
   - 包含 GPU 信息
   - 包含已安装的包

3. **测试智能训练脚本**
   ```bash
   ./smart_train.sh "python train.py --test"
   ```

4. **开始使用**
   ```bash
   ./run_training_smart.sh "python train.py --epochs 100"
   ```

---

**Created by:** 小k 🔬
**Date:** 2026-03-18
**Version:** 1.0.0
