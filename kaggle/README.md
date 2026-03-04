# Kaggle 实验运行目录

此目录用于 Kaggle 与 GitHub 的联动实验。

## 目录结构

```
kaggle/
├── README.md                    # 本说明文件
├── runner.ipynb                 # Kaggle Notebook 入口（由老板在 Kaggle 上创建）
├── run_experiment.py           # 实验运行脚本（在 Kaggle 上执行）
├── push_results.py             # 结果推送脚本（推送结果回 GitHub）
└── results/                    # 实验结果目录（由 Kaggle 生成）
    ├── exp_001/               # 第一次实验结果
    │   ├── metrics.json        # 评估指标
    │   ├── plots/             # 可视化图表
    │   ├── logs/              # 运行日志
    │   └── config.json        # 实验配置
    ├── exp_002/               # 第二次实验结果
    └── ...
```

## 工作流

```
1. 小k 写代码 → push 到 GitHub
         ↓
2. Kaggle Notebook 自动 pull GitHub 最新代码
         ↓
3. Kaggle 运行实验（用提前上传好的数据集）
         ↓
4. Kaggle 保存结果 → commit & push 回 GitHub（kaggle/results/）
         ↓
5. 小k pull 结果 → 分析 → 迭代改进
```

## Kaggle Notebook 配置

老板在 Kaggle 上需要配置：

1. **提前上传数据集** 到 Kaggle Dataset
2. **Notebook 中配置 GitHub API Key** 用于 push 结果
3. **Notebook 设置为定期运行** 或手动触发

## 实验配置

每次实验的配置在 `run_experiment.py` 中定义，包括：
- Tokenizer 类型和参数
- 评估任务
- 数据集路径
- 输出目录

## 结果格式

每个实验结果目录包含：
- `metrics.json` - 量化指标（MSE, MAE, SNR 等）
- `plots/` - 可视化图表（PNG/SVG）
- `logs/` - 训练/评估日志
- `config.json` - 本次实验的完整配置
