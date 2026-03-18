# EEGTokenizer v2.0 - 重构版本

**重构日期：** 2026-03-18
**作者：** 曾凯
**重构目标：** 模块化、可扩展、易维护、适配自动回环系统

---

## 🎯 重构核心思想

### 核心目标

根据老板的指示，重构的核心思想是：

1. **Tokenizer 作为独立模块**
   - 当前思路：ADC 风格量化
   - 以后有其他思路：直接作为独立脚本添加
   - **即插即用**：无需修改其他代码

2. **封装和模块化**
   - Tokenizer、Data、Model、Training 完全分离
   - 每个模块都有清晰的接口
   - 便于测试和维护

3. **完整的错误管理和日志**
   - 详细的日志记录
   - 异常捕获和处理
   - 便于后续分析结果

---

## 📁 新代码结构

```
eegtokenizer_v2/
├── __init__.py                 # 包初始化
├── train.py                   # ⭐ 统一训练入口
│
├── tokenizers/                # Tokenizer 模块（核心）
│   ├── __init__.py
│   ├── base.py                 # ⭐ 基类（所有 tokenizer 继承）
│   └── adc.py                 # ⭐ ADC 量化 tokenizer
│
├── data/                      # 数据模块
│   ├── __init__.py
│   └── loader.py              # ⭐ 数据加载器
│
├── models/                    # 模型模块
│   ├── __init__.py
│   └── classifier.py          # ⭐ 分类器 + 解码器
│
├── training/                  # 训练模块
│   ├── __init__.py
│   └── trainer.py             # ⭐ 训练器（包含日志、错误处理）
│
├── evaluation/                # 评估模块（预留）
│   └── __init__.py
│
├── utils/                     # 工具模块（预留）
│   └── __init__.py
│
└── configs/                   # 配置文件
    └── experiments.yaml       # ⭐ 实验配置（YAML）
```

---

## 🚀 快速开始

### 1. 训练 ADC 4bit 模型

```bash
cd /root/.openclaw/workspace/EEGTokenizer
python eegtokenizer_v2/train.py --config eegtokenizer_v2/configs/experiments.yaml::adc_4bit
```

### 2. 训练 ADC 8bit 模型

```bash
python eegtokenizer_v2/train.py --config eegtokenizer_v2/configs/experiments.yaml::adc_8bit
```

### 3. 训练 ADC 注意力聚合模型

```bash
python eegtokenizer_v2/train.py --config eegtokenizer_v2/configs/experiments.yaml::adc_attention
```

---

## 🎨 核心设计

### 1. Tokenizer 基类

**位置：** `eegtokenizer_v2/tokenizers/base.py`

**核心接口：**

```python
class BaseTokenizer(nn.Module):
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """
        输入: (batch, channels, timepoints)
        输出: (batch, n_patches, d_model), padding_mask
        """
        pass
```

**使用方法：**

```python
from eegtokenizer_v2.tokenizers import BaseTokenizer

class MyTokenizer(BaseTokenizer):
    def __init__(self, ...):
        super().__init__(d_model=64)
        # 你的代码

    def forward(self, x):
        # 你的逻辑
        return features, padding_mask
```

### 2. ADC Tokenizer（老板的新思路）

**位置：** `eegtokenizer_v2/tokenizers/adc.py`

**核心步骤：**

1. **时间分 patch**：固定长度分割
2. **量化**：ADC 风格量化（1/2/4/8/16bit）
3. **聚合**：mean/attention/gate

**配置参数：**

```python
tokenizer = ADCTokenizer(
    window_length=250,      # 250Hz × 0.25s = 62.5ms
    step_length=125,        # 50% 重叠
    num_bits=4,            # 4bit = 16 级
    quant_type="scalar",   # 标量量化
    agg_type="mean"        # 简单平均
)
```

**支持的配置组合：**

| quant_type | agg_type | 说明 |
|------------|----------|------|
| scalar | mean | 标量量化 + 平均聚合（最简单） |
| scalar | attention | 标量量化 + 注意力聚合 |
| vector | mean | 矢量量化 + 平均聚合 |
| product | mean | 乘积量化 + 平均聚合 |

### 3. 数据加载器

**位置：** `eegtokenizer_v2/data/loader.py`

**接口：**

```python
from eegtokenizer_v2.data import EEGDataLoader

loader = EEGDataLoader(
    data_dir="./data/BCI_IV_2a",
    subject_id="A01",
    data_mode="single"
)

train_loader, val_loader, test_loader = loader.load_single_subject(
    train_ratio=0.7,
    val_ratio=0.15,
    batch_size=32
)
```

### 4. 训练器

**位置：** `eegtokenizer_v2/training/trainer.py`

**功能：**

- ✅ 统一训练接口
- ✅ 完整的日志管理
- ✅ 错误处理
- ✅ 模型保存
- ✅ 训练历史记录

**使用方法：**

```python
from eegtokenizer_v2.training import Trainer

trainer = Trainer(model, config, device="cuda:0")
trainer.train(train_loader, val_loader)
```

### 5. 配置文件

**位置：** `eegtokenizer_v2/configs/experiments.yaml`

**格式：**

```yaml
adc_4bit:
  model:
    type: "ADC"
    tokenizer:
      window_length: 250
      step_length: 125
      num_bits: 4
      quant_type: "scalar"
      agg_type: "mean"
    # ...

  data:
    dataset: "BCI_IV_2a"
    # ...

  training:
    epochs: 100
    # ...
```

---

## 🔧 添加新的 Tokenizer

### 步骤 1：创建新的 tokenizer 文件

```bash
cd /root/.openclaw/workspace/EEGTokenizer/eegtokenizer_v2/tokenizers
touch my_tokenizer.py
```

### 步骤 2：继承基类

```python
import torch
import torch.nn as nn
from typing import Tuple
from .base import BaseTokenizer

class MyTokenizer(BaseTokenizer):
    """
    我的 Tokenizer

    核心思路：...
    """

    def __init__(self, d_model: int = 64, **kwargs):
        super().__init__(d_model)
        # 你的参数
        # ...

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """
        Tokenize EEG 信号

        Args:
            x: (batch, channels, timepoints)

        Returns:
            features: (batch, n_patches, d_model)
            padding_mask: (batch, n_patches)
        """
        # 你的逻辑
        return features, padding_mask
```

### 步骤 3：注册到 __init__.py

```python
# eegtokenizer_v2/tokenizers/__init__.py
from .base import BaseTokenizer
from .adc import ADCTokenizer
from .my_tokenizer import MyTokenizer  # 添加这一行

__all__ = ['BaseTokenizer', 'ADCTokenizer', 'MyTokenizer']
```

### 步骤 4：更新配置文件

```yaml
# eegtokenizer_v2/configs/experiments.yaml
my_experiment:
  model:
    type: "MyTokenizer"
    tokenizer:
      name: "MyTokenizer"
      # 你的参数
  # ...
```

### 步骤 5：运行训练

```bash
python eegtokenizer_v2/train.py --config eegtokenizer_v2/configs/experiments.yaml::my_experiment
```

---

## 📊 与旧代码的对比

| 特性 | 旧代码（Space_freq/） | 新代码（eegtokenizer_v2/） |
|------|---------------------|-------------------------|
| 模块化 | ❌ 单文件，600+ 行 | ✅ 清晰的模块划分 |
| 可扩展性 | ❌ 难以添加新 tokenizer | ✅ 继承基类即可 |
| 配置管理 | ❌ 硬编码超参数 | ✅ YAML 配置文件 |
| 日志管理 | ❌ 简单的 print | ✅ 完整的 logging |
| 错误处理 | ❌ 缺乏异常捕获 | ✅ 完整的 try-catch |
| 模型保存 | ⚠️ 基础保存 | ✅ 检查点 + 历史记录 |
| 文档 | ⚠️ 缺乏 API 文档 | ✅ 清晰的接口说明 |

---

## 🎯 核心优势

### 1. 即插即用的 Tokenizer

**旧代码：**
- 修改 `Space_freq/encode.py`
- 修改 `Space_freq/main.py`
- 修改数据加载逻辑
- 代码耦合严重

**新代码：**
- 创建 `eegtokenizer_v2/tokenizers/my_tokenizer.py`
- 继承 `BaseTokenizer`
- 在配置文件中指定
- **其他代码完全不用改**

### 2. 完整的日志和错误管理

**日志记录：**

```
2026-03-18 15:30:00 - root - INFO - ========================================
2026-03-18 15:30:00 - root - INFO - EEGTokenizer 训练开始
2026-03-18 15:30:00 - root - INFO - ========================================
2026-03-18 15:30:00 - root - INFO - 配置文件: adc_4bit
2026-03-18 15:30:00 - root - INFO - GPU: cuda:0
2026-03-18 15:30:00 - root - INFO - ========================================
2026-03-18 15:30:00 - root - INFO - 创建模型...
2026-03-18 15:30:00 - eegtokenizer_v2.tokenizers.adc - INFO - ADC Tokenizer 初始化完成
2026-03-18 15:30:00 - eegtokenizer_v2.tokenizers.adc - INFO -   window_length: 250, step_length: 125
2026-03-18 15:30:00 - eegtokenizer_v2.tokenizers.adc - INFO -   num_bits: 4 (16 级)
2026-03-18 15:30:00 - eegtokenizer_v2.tokenizers.adc - INFO -   quant_type: scalar, agg_type: mean
2026-03-18 15:30:00 - eegtokenizer_v2.tokenizers.adc - INFO -   d_model: 22
2026-03-18 15:30:00 - eegtokenizer_v2.models.classifier - INFO - EEGClassifier 初始化完成
2026-03-18 15:30:00 - eegtokenizer_v2.models.classifier - INFO -   num_classes: 4
2026-03-18 15:30:00 - eegtokenizer_v2.models.classifier - INFO -   nhead: 8, num_layers: 2
2026-03-18 15:30:00 - eegtokenizer_v2.models.classifier - INFO -   dropout: 0.1
2026-03-18 15:30:00 - root - INFO - 加载数据...
2026-03-18 15:30:00 - eegtokenizer_v2.data.loader - INFO - 单被试数据加载完成
2026-03-18 15:30:00 - eegtokenizer_v2.data.loader - INFO -   训练集: 140 样本
2026-03-18 15:30:00 - eegtokenizer_v2.data.loader - INFO -   验证集: 30 样本
2026-03-18 15:30:00 - eegtokenizer_v2.data.loader - INFO -   测试集: 30 样本
2026-03-18 15:30:00 - root - INFO - 开始训练，共 100 个 epoch
2026-03-18 15:30:15 - root - INFO - Epoch 0/100 - Train Loss: 1.2345, Acc: 0.4567 | Val Loss: 1.3456, Acc: 0.4321
2026-03-18 15:30:15 - root - INFO -   ✓ 保存最佳模型 (val_acc: 0.4321)
...
```

**错误处理：**

```python
try:
    # 训练逻辑
    ...
except Exception as e:
    logger.error(f"❌ 训练失败: {e}")
    logger.error(traceback.format_exc())
    sys.exit(1)
```

### 3. 适配自动回环系统

**统一训练入口：**

```bash
python eegtokenizer_v2/train.py --config xxx.yaml
```

**标准输出：**
- 训练日志保存到文件
- 模型检查点保存
- 训练历史记录（JSON）
- 错误详细记录

---

## 📝 下一步

### 立即可用

- ✅ ADC Tokenizer 已实现
- ✅ 数据加载器已实现
- ✅ 训练器已实现
- ✅ 配置文件已创建

### 待完善

- ⚠️ 数据加载器需要适配实际数据格式
- ⚠️ 需要添加单元测试
- ⚠️ 需要添加评估模块（重构质量）

### 后续优化

- 🔧 添加 STF Encoder（重构旧代码）
- 🔧 添加重构质量评估
- 🔧 添加探针任务评估
- 🔧 添加可视化工具

---

## 🎁 总结

### 重构成果

1. ✅ **模块化设计**：清晰的模块划分
2. ✅ **即插即用**：添加新 tokenizer 无需修改其他代码
3. ✅ **完整日志**：详细的训练日志和错误处理
4. ✅ **配置管理**：YAML 配置文件，易于管理实验
5. ✅ **适配回环系统**：统一训练入口，标准输出

### 核心思想落地

**老板的思路：**
> "当前我的思路是量化采样，那就把这个编码器作为一个独立的脚本，然后以后有其他思路可以直接做成单独脚本，即插即用。"

✅ **已完全实现！**

- `ADCTokenizer` 是独立的 tokenizer
- 添加新 tokenizer 只需继承 `BaseTokenizer`
- 配置文件中指定使用哪个 tokenizer
- **完全解耦，即插即用**

---

**Created by:** 小k 🔬
**Date:** 2026-03-18
**Version:** 2.0.0
