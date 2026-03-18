# 环境适配问题 - 解决方案总结

**日期：** 2026-03-18
**问题：** nit 环境未知，代码可能不适配，GPU 资源管理

---

## 🎯 你的问题

### 问题 1：nit 环境未知

> "因为代码运行肯定是要用nit上的torch环境的"

**可能的环境：**
- 系统Python (`/usr/bin/python3`)
- 虚拟环境 (`~/EEGTokenizer/venv`)
- Conda环境 (`~/anaconda3/envs/base`)
- 其他...

### 问题 2：GPU资源管理

> "还有要在显卡空闲时才能运行，不然爆显存了咋办对吧"

**问题：**
- GPU可能被其他任务占用
- 直接运行会显存不足（OOM）
- 需要等待GPU空闲

---

## ✅ 完整解决方案

### 解决方案 1：环境自动检测（智能训练脚本）

**脚本：** `nit-server/scripts/smart_train.sh`

**功能：**
```
自动检测Python环境
    ↓
优先级：venv > conda > system
    ↓
自动激活环境
    ↓
验证PyTorch可用
    ↓
运行训练
```

**示例：**

```bash
# 在nit上
cd ~/eeg-auto-iteration/nit-server/scripts
./smart_train.sh "python train.py"

# 脚本会自动：
# 1. 检查 ~/EEGTokenizer/venv
# 2. 如果没有，检查 conda
# 3. 如果没有，使用系统python
# 4. 验证 torch + CUDA
# 5. 运行训练
```

**检测逻辑：**

```python
# 伪代码
if exists(~/EEGTokenizer/venv):
    activate venv
elif conda_available():
    activate conda
else:
    use system_python

verify_pytorch()  # 检查torch和cuda
run_training()
```

---

### 解决方案 2：GPU队列管理

**脚本：** `nit-server/scripts/gpu_queue.sh`

**功能：**
```
检查GPU状态
    ↓
GPU空闲？
    ↓ 是  → 立即运行
    ↓ 否
等待30秒
    ↓
重新检查（最多等2小时）
    ↓
超时则失败
```

**示例：**

```bash
# 在nit上
cd ~/eeg-auto-iteration/nit-server/scripts

# 正常模式：等待GPU空闲
./gpu_queue.sh "python train.py"

# 强制模式：忽略GPU占用
FORCE_RUN=true ./gpu_queue.sh "python train.py"

# 自定义等待时间
MAX_WAIT_TIME=3600 ./gpu_queue.sh "python train.py"
```

**工作流程：**

```
开始 → 检查GPU（显存 < 90%？）
                    ↓ 是
                  运行训练
                    ↓ 否
                  等待30秒
                    ↓
                  重新检查
                    ↓
                  （循环直到空闲或超时）
```

---

### 解决方案 3：环境检测报告

**脚本：** `nit-server/scripts/detect_environment.sh`

**功能：**
- 检测系统信息（OS、内存、CPU）
- 检测Python环境（版本、路径）
- 检测PyTorch信息（版本、CUDA支持）
- 检测GPU信息（型号、显存、驱动）
- 检测已安装的依赖包

**使用方法：**

```bash
# 在nit上运行
cd ~/eeg-auto-iteration/nit-server/scripts
./detect_environment.sh

# 会生成详细报告：~/nit_environment_report.txt
# 将报告发送给小k
```

**报告包含：**

```
========================================
🔍 nit 环境检测报告
========================================
检测时间: 2026-03-18 14:30:00
主机名: nit-server
用户: kaizeng

1️⃣ 系统信息
操作系统: Linux
内核版本: 5.4.0
CPU 核心数: 16
总内存: 64 GB

2️⃣ Python 环境
Python 版本: 3.9.7
Python 路径: /home/kaizeng/anaconda3/bin/python
虚拟环境: /home/kaizeng/anaconda3

3️⃣ PyTorch 环境
PyTorch 版本: 1.13.0
CUDA 可用: True
CUDA 版本: 11.7
GPU 数量: 1
GPU 0: NVIDIA RTX 3090
  显存: 24.00 GB

4️⃣ GPU 状态
NVIDIA GPU 信息:
GPU 0: NVIDIA RTX 3090
  显存: 1000 / 24576 MiB (4%)
  利用率: 0%

5️⃣ 常用依赖包
✓ numpy: 1.21.0
✓ pandas: 1.3.0
✓ torch: 1.13.0
✓ scipy: 1.7.0
✗ tensorflow: 未安装
```

---

## 🚀 完整使用流程

### 第1步：检测nit环境

```bash
# 在nit上（用atrust或学校内网登录）
ssh your_username@nit

# 运行环境检测
cd ~/eeg-auto-iteration/nit-server/scripts
./detect_environment.sh

# 将生成的报告发送给小k
cat ~/nit_environment_report.txt
```

### 第2步：测试智能训练脚本

```bash
# 在nit上测试
cd ~/eeg-auto-iteration/nit-server/scripts

# 测试1：检查环境
./smart_train.sh "python -c 'import torch; print(torch.__version__)'"

# 测试2：简单训练
./smart_train.sh "python train.py --test --epochs 1"
```

### 第3步：从云服务器运行

```bash
# 在云服务器上
cd /root/.openclaw/workspace/eeg-auto-iteration/cloud-server/scripts

# 使用智能训练脚本（自动环境检测 + GPU队列）
./run_training_smart.sh "python train.py --epochs 100"

# 优势：
# - 自动检测nit的Python环境
# - 自动等待GPU空闲
# - 完整的错误捕获和飞书通知
```

---

## 🎯 工作原理

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    云服务器 (VM-0-11)                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  ./run_training_smart.sh "python train.py"          │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       │                                      │
│  ┌────────────────────▼─────────────────────────────────┐  │
│  │  1. 通过SSH隧道连接到nit                              │  │
│  │  2. 同步代码（git pull）                              │  │
│  │  3. 调用智能训练脚本                                  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │
                  SSH隧道 (3022)
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    nit 服务器                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  smart_train.sh "python train.py"                    │  │
│  │  ┌────────────────────────────────────────────────┐  │  │
│  │  │ 1. 检测Python环境                              │  │  │
│  │  │    - 尝试激活 venv                            │  │  │
│  │  │    - 否则激活 conda                            │  │  │
│  │  │    - 否则使用系统python                        │  │  │
│  │  │ 2. 验证PyTorch                                 │  │  │
│  │  │ 3. 检查GPU状态                                 │  │  │
│  │  │ 4. GPU繁忙？                                   │  │  │
│  │  │    - 是 → 等待空闲                             │  │  │
│  │  │    - 否 → 立即运行                             │  │  │
│  │  └────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 对比

| 方案 | 环境适配 | GPU管理 | 错误处理 | 推荐度 |
|------|---------|---------|---------|--------|
| **手动运行** | ❌ 需要指定路径 | ❌ 需要手动检查 | ⚠️ | ⭐ |
| **智能训练脚本** | ✅ 自动检测 | ❌ 不等待 | ✅ | ⭐⭐⭐⭐ |
| **GPU队列** | ❌ 需要指定路径 | ✅ 自动等待 | ✅ | ⭐⭐⭐⭐ |
| **智能训练 + GPU队列** | ✅ 自动检测 | ✅ 自动等待 | ✅ | ⭐⭐⭐⭐⭐ |

---

## 🎁 总结

### 你的问题 → 解决方案

| 问题 | 解决方案 |
|------|---------|
| nit环境未知 | ✅ `smart_train.sh` 自动检测 |
| GPU可能被占用 | ✅ `gpu_queue.sh` 自动等待 |
| 代码不适配 | ✅ 自动适配Python环境 |
| 显存不足 | ✅ GPU空闲时才运行 |

### 核心优势

1. ✅ **无需手动配置**：自动检测Python环境
2. ✅ **避免OOM错误**：自动等待GPU空闲
3. ✅ **完整错误捕获**：详细的错误日志
4. ✅ **飞书实时通知**：训练状态实时推送

### 下一步

1. **在nit上运行环境检测**
   ```bash
   ./detect_environment.sh
   ```

2. **将报告发送给小k**

3. **开始使用智能训练**
   ```bash
   ./run_training_smart.sh "python train.py"
   ```

---

**Created by:** 小k 🔬
**Date:** 2026-03-18
