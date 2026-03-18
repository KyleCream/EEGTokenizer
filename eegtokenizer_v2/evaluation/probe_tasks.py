"""
线性探针任务评估

冻结 tokenizer，训练线性探针

探针任务：
1. 节律分类（5 类：delta/theta/alpha/beta/gamma）
2. 运动想象分类（4 类）
3. 被试识别（识别是哪个被试）

目的：评估 tokenizer 表示质量

数据形状：(batch, channels, sample)
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
import numpy as np
import logging
from pathlib import Path
import json
from datetime import datetime
from typing import Dict, List
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, classification_report

logger = logging.getLogger(__name__)


class LinearProbe(nn.Module):
    """
    线性探针模型

    简单的多层感知机（MLP）
    """

    def __init__(self, input_dim: int, hidden_dim: int = 64, num_classes: int = 5):
        super().__init__()

        self.mlp = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim, num_classes)
        )

    def forward(self, x):
        return self.mlp(x)


class ProbeTrainer:
    """
    探针训练器

    训练线性探针，评估 tokenizer 表示质量
    """

    def __init__(
        self,
        probe_type: str = "rhythm",
        device: str = "cuda" if torch.cuda.is_available() else "cpu"
    ):
        self.probe_type = probe_type
        self.device = device

        logger.info(f"ProbeTrainer 初始化")
        logger.info(f"  probe_type: {probe_type}")

    def extract_features(
        self,
        model: nn.Module,
        data_loader: DataLoader
    ) -> np.ndarray:
        """
        提取特征（冻结 tokenizer）

        Returns:
            features: (n_samples, d_model)
        """
        model.eval()

        all_features = []
        all_labels = []

        with torch.no_grad():
            for data, labels in data_loader:
                data = data.to(self.device)

                # Tokenize
                if hasattr(model, 'tokenizer'):
                    features, _ = model.tokenizer(data)
                else:
                    logger.error("模型没有 tokenizer 属性")
                    return None

                # 全局平均池化
                pooled = features.mean(dim=1)  # (batch, d_model)

                all_features.append(pooled.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())

        return np.array(all_features), np.array(all_labels)

    def train_linear_probe(
        self,
        features: np.ndarray,
        labels: np.ndarray,
        save_dir: str = "./results/probe"
    ) -> Dict[str, float]:
        """
        训练线性探针

        Args:
            features: 特征, (n_samples, d_model)
            labels: 标签, (n_samples,)
            save_dir: 保存目录

        Returns:
            metrics: 指标字典
        """
        save_path = Path(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)

        # 训练 logistic 回归
        probe = LogisticRegression(max_iter=1000, random_state=42)
        probe.fit(features, labels)

        # 预测
        preds = probe.predict(features)
        acc = accuracy_score(labels, preds)
        f1 = f1_score(labels, preds, average='weighted')

        # 保存模型
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        model_file = save_path / f'linear_probe_{self.probe_type}_{timestamp}.pkl'

        import pickle
        with open(model_file, 'wb') as f:
            pickle.dump(probe, f)

        # 保存指标
        metrics = {
            'accuracy': acc,
            'f1': f1
        }

        metric_file = save_path / f'linear_probe_{self.probe_type}_{timestamp}.json'
        with open(metric_file, 'w') as f:
            json.dump(metrics, f, indent=2)

        logger.info(f"线性探针训练完成 ({self.probe_type})")
        logger.info(f"  Accuracy: {acc:.4f}")
        logger.info(f"  F1 Score: {f1:.4f}")
        logger.info(f"  模型保存: {model_file}")
        logger.info(f"  指标保存: {metric_file}")

        return metrics

    def evaluate(
        self,
        model: nn.Module,
        data_loader: DataLoader,
        save_dir: str = "./results/probe"
    ) -> Dict[str, Dict[str, float]]:
        """
        完整评估流程

        Returns:
            all_metrics: 所有探针任务的指标
        """
        model.eval()

        # 提取特征
        logger.info("提取特征...")
        features, labels = self.extract_features(model, data_loader)

        # 训练线性探针
        logger.info("训练线性探针...")
        metrics = self.train_linear_probe(features, labels, save_dir)

        return {
            self.probe_type: metrics
        }


class MultiProbeEvaluator:
    """
    多探针任务评估器

    同时运行多个探针任务，全面评估 tokenizer 表示质量
    """

    def __init__(
        self,
        device: str = "cuda" if torch.cuda.is_available() else "cpu"
    ):
        self.device = device
        logger.info(f"MultiProbeEvaluator 初始化，设备: {device}")

    def evaluate(
        self,
        model: nn.Module,
        data_loader: DataLoader,
        save_dir: str = "./results/probe"
    ) -> Dict[str, Dict[str, float]]:
        """
        评估多个探针任务

        Args:
            model: 模型
            data_loader: 数据加载器
            save_dir: 保存目录

        Returns:
            all_metrics: 所有探针任务的指标
        """
        all_metrics = {}

        # 探针任务 1：节律分类
        logger.info("=" * 60)
        logger.info("探针任务 1/3: 节律分类")
        logger.info("=" * 60)

        probe_trainer = ProbeTrainer("rhythm", self.device)
        rhythm_metrics = probe_trainer.evaluate(model, data_loader, save_dir)
        all_metrics['rhythm_classification'] = rhythm_metrics

        # 探针任务 2：运动想象分类
        logger.info("=" * 60)
        logger.info("探针任务 2/3: 运动想象分类")
        logger.info("=" * 60)

        probe_trainer = ProbeTrainer("motor_imagery", self.device)
        motor_metrics = probe_trainer.evaluate(model, data_loader, save_dir)
        all_metrics['motor_imagery'] = motor_metrics

        # 探针任务 3：被试识别
        logger.info("=" * 60)
        logger.info("探针任务 3/3: 被试识别")
        logger.info("=" * 60)

        # 注意：这个任务需要知道是哪个被试的数据
        # 简化版：假设数据加载器可以提供被试信息
        probe_trainer = ProbeTrainer("subject_id", self.device)
        subject_metrics = probe_trainer.evaluate(model, data_loader, save_dir)
        all_metrics['subject_identification'] = subject_metrics

        # 保存总指标
        timestamp = datetime.now(). datetime.now().strftime('%Y%m%d_%H%M%S')
        result_file = Path(save_dir) / f'probe_all_{timestamp}.json'

        with open(result_file, 'w') as f:
            json.dump(all_metrics, f, indent=2)

        logger.info("=" * 60)
        logger.info("多探针任务评估完成")
        logger.info(f"  节律分类: Accuracy={all_metrics['rhythm_classification']['accuracy']:.4f}")
        logger.info(f"  运动想象: Accuracy={all_metrics['motor_imagery']['accuracy']:.4f}")
        logger.info(f"  被试识别: Accuracy={all_metrics['subject_identification']['accuracy']:.4f}")
        logger.info("=" * 60)
        logger.info(f"  结果已保存: {result_file}")

        return all_metrics


def evaluate_probe_tasks(
    model: nn.Module,
    data_loader: DataLoader,
    device: str = "cuda",
    save_dir: str = "./results/probe"
) -> Dict[str, Dict[str, float]]:
    """
    评估探针任务（便捷函数）

    Args:
        model: 模型
        data_loader: 数据加载器
        device: 设备
        save_dir: 保存目录

    Returns:
        all_metrics: 所有探针任务的指标
    """
    evaluator = MultiProbeEvaluator(device)
    return evaluator.evaluate(model, data_loader, save_dir)


# ==================== 使用示例 ====================

if __name__ == "__main__":
    # 示例：评估模型
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from eegtokenizer_v2.models import EEGClassifier
    from eegtokenizer_v2.tokenizers import ADCTokenizer

    # 创建模型
    tokenizer = ADCTokenizer(
        window_length=250,
        step_length=125,
        num_bits=4,
        quant_type="scalar",
        agg_type="mean"
    )

    model = EEGClassifier(
        tokenizer=tokenizer,
        num_classes=4,
        nhead=8,
        num_layers=2,
        dropout=0.1
    )

    # 假设有数据加载器
    # data_loader = ...

    # 评估
    metrics = evaluate_probe_tasks(model, data_loader)
    print(metrics)
