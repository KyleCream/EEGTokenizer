# EEGTokenizer 项目周报 - 2026年3月4日

**项目仓库：** https://github.com/KyleCream/EEGTokenizer  
**报告人：** 小k  
**报告时间：** 2026-03-04  
**报告周期：** 2026年3月3日 - 2026年3月4日

---

## 一、项目概述

EEGTokenizer 项目旨在探索更好的 EEG 信号 tokenization 方法，并建立可靠的性能验证框架。

**核心问题：**
1. 如何设计更好的 EEG tokenizer？
2. 如何验证 tokenizer 的好坏？

---

## 二、本周完成的工作

### 2.1 项目基础架构

#### 文档和规划
- ✅ `README.md` - 项目概述、核心组件、性能验证问题
- ✅ `RESEARCH_DIRECTIONS.md` - 研究方向罗列，按 P0/P1/P2 优先级

#### 目录结构重构
```
EEGTokenizer/
├── Space_freq/              # 现有代码（保留作为基线）
├── src/
│   ├── tokenizers/
│   │   ├── stf_encoder.py   # EEGSTFEncoder（重构自 Space_freq/encode.py）
│   │   └── adc_quantizer.py # ADC 风格量化 tokenizer（新）
│   ├── evaluation/
│   │   ├── reconstruction.py # 重构质量评估
│   │   └── probe_tasks.py    # 探针任务评估
│   └── utils/
│       └── data.py          # 统一数据加载接口
├── experiments/
│   └── quick_start.py       # 快速上手实验
├── README.md
├── RESEARCH_DIRECTIONS.md
└── requirements.txt
```

### 2.2 Tokenizer 实现

#### ADCQuantizer（ADC 风格量化 Tokenizer）
**核心思想：**
- 固定时间分割成 patch
- 类似硬件 ADC 的思路，直接数字量化成码字
- 探索不同精确度（1/2/4/8/16bit）的性能表现
- 码字聚合（mean/attention/gate/聚类）

**主要特性：**
- 可配置时间窗口（`window_length`）和步长（`step_length`）
- 支持多种量化类型（`scalar`/`vector`/`product`）
- 支持多种聚合方式（`mean`/`attention`/`gate`）
- 完整的 tokenize + detokenize 流程
- 可配置 EEG 信号范围和通道数

#### EEGSTFEncoder（空间-频率编码器）
- 重构自 Space_freq/encode.py
- 作为基线方法保留

### 2.3 评估框架

#### ReconstructionEvaluator（重构质量评估）
**评估指标：**
- MSE（均方误差）
- MAE（平均绝对误差）
- SNR（信噪比）
- R²（决定系数）

**适用场景：**
- 验证 tokenizer 是否能保留信号信息
- 比较不同 tokenizer 的重构质量

#### ProbeTaskEvaluator（探针任务评估）
- 框架已搭建，后续完善具体任务

### 2.4 Kaggle 链路打通（本周新增）

#### 目录结构
```
kaggle/
├── README.md                    # 说明文档
├── runner.ipynb                 # Kaggle Notebook 入口（完整版）
├── runner_simple.ipynb          # 简化版（先不 push 结果）
├── run_experiment.py            # 实验运行脚本
├── push_results.py              # 结果推送脚本
└── results/                     # 结果目录
```

#### 工作流设计
```
GitHub (Single Source of Truth)
    ↓ pull
Kaggle Notebook 运行实验
    ↓ push 结果
GitHub (kaggle/results/)
```

#### 关键特性
- `run_experiment.py` - 从模拟改成真实版本，调用真实的 `ADCQuantizer`、`ReconstructionEvaluator`、`ProbeTaskEvaluator`
- 支持真实 EEG 数据加载，保留模拟数据作为备用
- 输出完整评估指标和可视化图表
- 输出 SUMMARY.md 文本格式总结报告

#### 关键问题解决
| 问题 | 解决方案 |
|------|----------|
| Kaggle Notebook git 需要交互式输入 yes | 添加 git config 避免交互 |
| GitHub Token push 返回 403 | 用 HTTPS + Token 替代 SSH |
| GitHub 检测到 Token 是 secret，不让 push | Token 不提交到代码库，由用户在 Notebook 中填写 |

---

## 三、技术要点

### 3.1 ADCQuantizer 设计
- 固定窗口分割：`(batch, channels, time) → (batch, n_patches, channels, window_length)`
- 量化：标量/矢量/乘积量化
- 聚合：mean/attention/gate 方式聚合 patch 内码字
- 输出：`(batch, n_patches, d_model)` + padding mask

### 3.2 评估指标
- **重构质量**：MSE/MAE（越小越好），SNR/R²（越大越好）
- **探针任务**：后续将实现睡眠分期、运动想象等任务

### 3.3 Kaggle 集成
- GitHub 是 Single Source of Truth
- Kaggle Notebook 用于运行实验（利用免费 GPU）
- 结果自动推回 GitHub

---

## 四、当前状态

### 已完成
- ✅ 项目基础架构和文档
- ✅ ADCQuantizer 实现（tokenize + detokenize）
- ✅ ReconstructionEvaluator 实现
- ✅ ProbeTaskEvaluator 框架
- ✅ Kaggle 链路打通（目录结构 + 脚本）
- ✅ `run_experiment.py` 从模拟改成真实版本

### 进行中
- ⏳ 等待老板在 Kaggle 上测试运行
- ⏳ 探针任务评估具体实现

### 待开始
- ⏳ 系统对比不同 tokenizer 性能
- ⏳ 超参数优化
- ⏳ 多样性和新颖性保证

---

## 五、下周计划

1. 根据 Kaggle 测试结果迭代改进
2. 完善 ProbeTaskEvaluator 具体实现
3. 系统对比不同 tokenizer（STF vs ADCQuantizer）
4. 超参数优化实验
5. 继续探索研究方向（P0 优先级）

---

## 六、仓库链接

- GitHub：https://github.com/KyleCream/EEGTokenizer
- 当前 Commit：02534f7（Kaggle 真实版本）
