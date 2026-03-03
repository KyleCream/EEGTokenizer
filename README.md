# EEGTokenizer

EEG 信号的时空频 tokenizer，用于将 EEG 信号转换为适合 Transformer 等模型处理的序列表示。

## 核心思想

1. **时间分patch**：将 EEG 时间序列滑动窗口切分成多个 patches
2. **多分支节律卷积**：为 5 种 EEG 节律（delta/theta/alpha/beta/gamma）设计专属卷积核
3. **空洞卷积空间建模**：通过不同膨胀率的空洞卷积捕捉空间依赖
4. **相似patch合并**：可选的余弦相似度合并机制
5. **位置编码**：为序列添加位置信息

## 代码结构

```
Space_freq/
├── BCIdataloader.py    # BCI IV 2a 数据加载（独立脚本）
├── loaddata.py         # 通用 EEG 数据加载器（带归一化）
├── encode.py           # EEG tokenizer 编码器
├── MYmodel.py          # 分类模型（Transformer/CNN）
└── main.py             # 训练主函数
```

## 核心组件

### 1. EEGSTFEncoder（时空频编码器）

**输入：** `(batch, channels, timepoints)`

**输出：** `(batch, n_patches, d_model)` + padding mask

**关键参数：**
- `window_length`: 滑动窗口长度
- `step_length`: 滑动步长
- `patch_enabled`: 是否开启时间分patch
- `merge_enabled`: 是否合并相似patch
- `n_head`: 注意力头数（用于自动计算 d_model）

**处理流程：**
1. 时间维度分patch → `(batch, channels, window_length, n_patches)`
2. 5分支节律卷积提取时序特征 → `(batch, channels, 40, n_patches)`
3. 空洞卷积提取空间特征 → `(batch, n_patches, spatial_feat_dim)`
4. 投影到 d_model → `(batch, n_patches, d_model)`
5. 可选：相似patch合并
6. 位置编码

### 2. EEGClassifier（Transformer分类器）

```python
EEGClassifier(
    eeg_encoder=EEGSTFEncoder(...),
    num_classes=4,
    nhead=8,
    num_transformer_layers=2,
    use_residual=True  # 跨层残差连接
)
```

### 3. EEGClassifierCNN（CNN分类器）

CNN 版本，用于防过拟合场景。

## 数据加载

支持两种模式：

**单被试模式：**
```python
config = {
    'data': {
        'data_mode': 'single',
        'single_subject_id': 'A01',
        'single_train_ratio': 0.7,
        'single_val_ratio': 0.15
    }
}
```

**跨被试模式（留一法）：**
```python
config = {
    'data': {
        'data_mode': 'cross'
    }
}
```

**归一化支持：**
- `none`: 不归一化
- `z_score`: Z-score 归一化（基于训练集统计量）
- `sample_z_score`: 样本级归一化
- `min_max`: Min-Max 归一化

## 性能验证问题（核心方向）

> **关键问题：如何验证所提 tokenizer 的性能？**

当前仓库通过下游分类任务（BCI IV 2a 运动想象分类）来间接验证 tokenizer 效果。但这存在以下问题：

1. **耦合度高**：分类性能受分类器架构、训练策略等多种因素影响
2. **缺乏直接性**：没有直接评估 tokenizer 表示质量的指标
3. **可解释性弱**：难以判断性能提升来自 tokenizer 还是其他部分

**可能的探索方向：**
- 重构质量：tokenize → detokenize 的恢复误差
- 探针任务：在中间表示上做简单探针任务
- 可视化：t-SNE/UMAP 可视化 token 表示
- 对比学习：相似 EEG 片段的表示相似度
- 零样本/少样本迁移：tokenizer 在不同任务/数据集上的迁移能力

## 使用示例

```python
from loaddata import EEGDataLoader
from encode import EEGSTFEncoder
from MYmodel import EEGClassifier

# 1. 加载数据
config = {...}
loader = EEGDataLoader(config)
loader.load_single_subject("A01")
train_dataset, val_dataset, test_dataset = loader.train_test_split_single_subject("A01")

# 2. 初始化模型
encoder = EEGSTFEncoder(
    window_length=250,
    step_length=50,
    fs=250,
    max_freq=50,
    patch_enabled=True
)
model = EEGClassifier(encoder, num_classes=4)

# 3. 训练
# 详见 main.py
```

## 依赖

- PyTorch
- MNE
- scikit-learn
- NumPy
- SciPy
- Matplotlib

## 数据集

默认使用 **BCI IV 2a** 数据集（22 通道 EEG，4 类运动想象任务）。
