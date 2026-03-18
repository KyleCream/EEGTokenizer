# EEGTokenizer

**版本：** 2.0
**日期：** 2026-03-18
**作者：** KyleCream

---

## 📖 项目概述

EEGTokenizer 是一个用于 EEG 信号处理的深度学习框架，专注于设计更好的 tokenizer 并验证其性能。

### 核心目标

1. **Tokenizer 设计**：如何设计更好的 EEG tokenizer
2. **性能验证**：多维度评估 tokenizer 表示质量
3. **自动回环**：完整的自动化训练和迭代系统

---

## 🚀 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 训练模型

```bash
cd eegtokenizer_v2
python train.py --config configs/experiments.yaml::adc_4bit
```

### 评估模型

```bash
# 重构质量评估
python evaluate.py --config configs/experiments.yaml::adc_4bit --type reconstruction

# 线性探针评估
python evaluate.py --config configs/experiments.yaml::adc_4bit --type probe

# 全部评估
python evaluate.py --config configs/experiments.yaml::adc_4bit --type all
```

---

## 📁 项目结构

### EEGTokenizer v2（重构版）

```
eegtokenizer_v2/
├── README.md                              # 完整文档
├── train.py                              # 训练入口
├── evaluate.py                           # 评估入口
├── configs/
│   └── experiments.yaml                  # 实验配置
├── tokenizers/                           # Tokenizer 模块
│   ├── base.py                          # 基类
│   └── adc.py                           # ADC tokenizer
├── data/
│   └── loader.py                        # 数据加载器
├── models/
│   └── classifier.py                    # 分类器
├── training/
│   └── trainer.py                       # 训练器
└── evaluation/                           # 评估模块
    ├── reconstruction.py                 # 重构质量评估
    └── probe_tasks.py                    # 线性探针评估
```

### 自动回环迭代系统

```
eeg-auto-iteration/
├── README.md                              # 项目概述
├── deploy.sh                              # 一键部署脚本
├── cloud-server/                          # 云服务器端
│   ├── config/
│   │   └── config.sh                      # 配置文件
│   ├── scripts/                           # 自动化脚本
│   └── services/                          # 服务脚本
├── nit-server/                            # nit 服务器端
│   ├── config/
│   │   └── config.sh                      # 配置文件
│   └── scripts/                           # nit 脚本
└── docs/                                  # 文档
    ├── DEPLOYMENT.md                      # 部署指南
    ├── PROJECT_OVERVIEW.md                # 项目概述
    └── QUICK_REFERENCE.md                 # 快速参考
```

---

## 🔬 核心特性

### 1. 模块化架构

- **即插即用的 Tokenizer**：添加新 tokenizer 无需修改其他代码
- **配置驱动**：YAML 文件管理所有实验配置
- **标准接口**：所有 tokenizer 继承 `BaseTokenizer`

### 2. ADC Tokenizer

- **标量量化**：简单的标量量化
- **矢量量化**：VQ-VAE 风格
- **乘积量化**：Product Quantization
- **多种聚合方式**：mean / attention / gate

### 3. 完整的评估体系

- **重构质量评估**：MSE / MAE / SNR
- **线性探针任务**：节律分类 / 运动想象 / 被试识别
- **频域误差分析**：delta / theta / alpha / beta / gamma

### 4. 自动回环系统

- **SSH 隧道连接**：nit 主动连接云服务器
- **代码自动同步**：GitHub + rsync
- **远程训练执行**：智能环境适配
- **GPU 队列管理**：自动等待空闲资源
- **错误捕获与通知**：飞书实时通知

---

## 📊 实验配置

### ADC 4bit（基线）

```yaml
model:
  tokenizer:
    name: "ADCTokenizer"
    num_bits: 4
    quant_type: "scalar"
    agg_type: "mean"
```

### ADC 8bit

```yaml
model:
  tokenizer:
    num_bits: 8
```

### ADC 注意力聚合

```yaml
model:
  tokenizer:
    agg_type: "attention"
    n_head: 8
```

---

## 🎯 研究方向

### 当前方向：ADC 风格量化

**核心思想：**
1. **时间分割**：固定时间窗口分 patch
2. **量化**：标量/矢量/乘积量化
3. **聚合**：mean / attention / gate

**验证方法：**
1. **重构质量**（40%）：直接评估 tokenizer 编码质量
2. **线性探针**（30%）：评估表示质量
3. **可视化分析**（20%）：t-SNE / 码本利用率
4. **下游任务**（10%）：运动想象分类

---

## 🚀 部署指南

### 快速部署

```bash
# 云服务器端
./eeg-auto-iteration/deploy.sh --cloud

# nit 服务器端
./eeg-auto-iteration/deploy.sh --nit
```

**详细部署指南：** 参见 [eeg-auto-iteration/docs/DEPLOYMENT.md](eeg-auto-iteration/docs/DEPLOYMENT.md)

---

## 📈 性能指标

### 重构质量

| 量化精度 | MSE | MAE | SNR (dB) |
|---------|-----|-----|----------|
| 1bit    | TBD | TBD | TBD      |
| 2bit    | TBD | TBD | TBD      |
| 4bit    | TBD | TBD | TBD      |
| 8bit    | TBD | TBD | TBD      |

### 线性探针

| 探针任务 | 准确率 | F1 分数 |
|---------|--------|--------|
| 节律分类 | TBD    | TBD     |
| 运动想象 | TBD    | TBD     |
| 被试识别 | TBD    | TBD     |

---

## 🤝 贡献指南

### 添加新 Tokenizer

1. 继承 `BaseTokenizer`
2. 实现 `forward` 方法
3. 在配置文件中注册

**示例：**

```python
# eegtokenizer_v2/tokenizers/my_tokenizer.py
from .base import BaseTokenizer

class MyTokenizer(BaseTokenizer):
    def __init__(self, ...):
        super().__init__(d_model=...)
        # 你的初始化代码

    def forward(self, x):
        # 你的前向传播
        return features, padding_mask
```

```yaml
# configs/experiments.yaml
my_tokenizer:
  model:
    tokenizer:
      name: "MyTokenizer"
      # 你的参数
```

---

## 📝 更新日志

### v2.0 (2026-03-18)

- ✅ 完整重构：模块化架构
- ✅ 新增 ADC Tokenizer
- ✅ 完整的评估体系
- ✅ 自动回环迭代系统
- ✅ 配置驱动的实验管理

### v1.0 (2026-03-03)

- ✅ 初始版本
- ✅ 基础的 STF 编码器

---

## 📄 许可证

MIT License

---

## 👤 作者

**KyleCream** - [GitHub](https://github.com/KyleCream)

---

## 🙏 致谢

- BCI Competition IV 2a 数据集
- PyTorch 团队
- MNE-Python 团队

---

**Last Updated:** 2026-03-18
**Version:** 2.0
**Status:** 🚧 Active Development
