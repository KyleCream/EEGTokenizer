"""
训练任务模块

支持多种训练任务：
1. classification - 分类任务
2. reconstruction - 重构任务
3. contrastive - 对比学习
4. probe - 探针任务（冻结部分模型）

每种任务定义自己的：
- 损失函数
- 前向传播逻辑
- 评估指标
"""

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from abc import ABC, abstractmethod
import logging
from typing import Dict, Any
from sklearn.metrics import accuracy_score

logger = logging.getLogger(__name__)


class BaseTask(ABC):
    """
    任务基类

    所有训练任务都应该继承这个基类
    """

    def __init__(self, model: nn.Module, config: Dict[str, Any], device: str):
        self.model = model
        self.config = config
        self.device = device

        # 初始化损失函数
        self.criterion = self._create_criterion()

        logger.info(f"{self.__class__.__name__} 初始化完成")

    @abstractmethod
    def _create_criterion(self) -> nn.Module:
        """创建损失函数"""
        pass

    @abstractmethod
    def train_step(self, batch: Dict[str, torch.Tensor]) -> Dict[str, float]:
        """
        单步训练

        Args:
            batch: 数据批次

        Returns:
            losses: 损失字典
        """
        pass

    @abstractmethod
    def validate_step(self, batch: Dict[str, torch.Tensor]) -> Dict[str, float]:
        """
        单步验证

        Args:
            batch: 数据批次

        Returns:
            metrics: 指标字典
        """
        pass

    def compute_metrics(self, outputs: torch.Tensor, labels: torch.Tensor) -> Dict[str, float]:
        """
        计算通用指标

        Args:
            outputs: 模型输出
            labels: 真实标签

        Returns:
            metrics: 指标字典
        """
        _, preds = torch.max(outputs, 1)
        acc = accuracy_score(labels.cpu().numpy(), preds.cpu().numpy())

        return {'accuracy': acc}


class ClassificationTask(BaseTask):
    """
    分类任务

    使用交叉熵损失
    """

    def _create_criterion(self) -> nn.Module:
        return nn.CrossEntropyLoss()

    def train_step(self, batch: Dict[str, torch.Tensor]) -> Dict[str, float]:
        """
        分类任务训练步骤

        Args:
            batch: {'data': Tensor, 'labels': Tensor}

        Returns:
            {'loss': float}
        """
        data = batch['data'].to(self.device)
        labels = batch['labels'].to(self.device)

        # 前向传播
        outputs = self.model(data)
        loss = self.criterion(outputs, labels)

        return {'loss': loss, 'outputs': outputs, 'labels': labels}

    def validate_step(self, batch: Dict[str, torch.Tensor]) -> Dict[str, float]:
        """
        分类任务验证步骤

        Args:
            batch: {'data': Tensor, 'labels': Tensor}

        Returns:
            {'loss': float, 'accuracy': float}
        """
        data = batch['data'].to(self.device)
        labels = batch['labels'].to(self.device)

        # 前向传播
        with torch.no_grad():
            outputs = self.model(data)
            loss = self.criterion(outputs, labels)

        # 计算指标
        metrics = self.compute_metrics(outputs, labels)
        metrics['loss'] = loss.item()

        return metrics


class ReconstructionTask(BaseTask):
    """
    重构任务

    使用 MSE 损失重构原始信号
    """

    def _create_criterion(self) -> nn.Module:
        return nn.MSELoss()

    def train_step(self, batch: Dict[str, torch.Tensor]) -> Dict[str, float]:
        """
        重构任务训练步骤

        Args:
            batch: {'data': Tensor}

        Returns:
            {'loss': float}
        """
        data = batch['data'].to(self.device)

        # 前向传播（模型应该返回重构的信号）
        reconstructed = self.model(data, task='reconstruction')
        loss = self.criterion(reconstructed, data)

        return {'loss': loss, 'outputs': reconstructed, 'labels': data}

    def validate_step(self, batch: Dict[str, torch.Tensor]) -> Dict[str, float]:
        """
        重构任务验证步骤

        Args:
            batch: {'data': Tensor}

        Returns:
            {'loss': float, 'mse': float, 'mae': float}
        """
        data = batch['data'].to(self.device)

        # 前向传播
        with torch.no_grad():
            reconstructed = self.model(data, task='reconstruction')
            mse_loss = self.criterion(reconstructed, data)

        # 计算 MAE
        mae = torch.abs(reconstructed - data).mean().item()

        return {
            'loss': mse_loss.item(),
            'mse': mse_loss.item(),
            'mae': mae
        }


class ProbeTask(BaseTask):
    """
    探针任务

    冻结 tokenizer，只训练探针（线性分类器）
    """

    def __init__(self, model: nn.Module, config: Dict[str, Any], device: str):
        super().__init__(model, config, device)

        # 冻结 tokenizer
        if hasattr(model, 'tokenizer'):
            for param in model.tokenizer.parameters():
                param.requires_grad = False
            logger.info("Tokenizer 已冻结（探针任务）")

    def _create_criterion(self) -> nn.Module:
        return nn.CrossEntropyLoss()

    def train_step(self, batch: Dict[str, torch.Tensor]) -> Dict[str, float]:
        """
        探针任务训练步骤

        Args:
            batch: {'data': Tensor, 'labels': Tensor}

        Returns:
            {'loss': float}
        """
        data = batch['data'].to(self.device)
        labels = batch['labels'].to(self.device)

        # 前向传播（只获取特征，不训练 tokenizer）
        features, _ = self.model(data, return_features=True)

        # 使用简单的线性分类器
        if not hasattr(self, 'probe_classifier'):
            self.probe_classifier = nn.Linear(features.shape[-1], labels.max().item() + 1).to(self.device)

        logits = self.probe_classifier(features.mean(dim=1))  # 全局平均池化
        loss = self.criterion(logits, labels)

        return {'loss': loss, 'outputs': logits, 'labels': labels}

    def validate_step(self, batch: Dict[str, torch.Tensor]) -> Dict[str, float]:
        """
        探针任务验证步骤

        Args:
            batch: {'data': Tensor, 'labels': Tensor}

        Returns:
            {'loss': float, 'accuracy': float}
        """
        data = batch['data'].to(self.device)
        labels = batch['labels'].to(self.device)

        # 前向传播（只获取特征）
        with torch.no_grad():
            features, _ = self.model(data, return_features=True)

            # 使用线性分类器
            if not hasattr(self, 'probe_classifier'):
                self.probe_classifier = nn.Linear(features.shape[-1], labels.max().item() + 1).to(self.device)

            logits = self.probe_classifier(features.mean(dim=1))
            loss = self.criterion(logits, labels)

        # 计算指标
        metrics = self.compute_metrics(logits, labels)
        metrics['loss'] = loss.item()

        return metrics


def create_task(model: nn.Module, config: Dict[str, Any], device: str) -> BaseTask:
    """
    工厂函数：创建任务

    Args:
        model: 模型
        config: 配置字典，必须包含 'task' 字段
        device: 设备

    Returns:
        task: 任务实例

    支持：
    - 'classification': 分类任务
    - 'reconstruction': 重构任务
    - 'probe': 探针任务
    """
    task_type = config.get('task', 'classification')

    task_map = {
        'classification': ClassificationTask,
        'reconstruction': ReconstructionTask,
        'probe': ProbeTask
    }

    task_class = task_map.get(task_type)
    if task_class is None:
        raise ValueError(f"Unknown task type: {task_type}. Supported: {list(task_map.keys())}")

    logger.info(f"创建任务: {task_type}")
    return task_class(model, config, device)
