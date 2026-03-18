"""
训练器模块

统一的训练接口，包含：
1. 完整的日志管理
2. 错误处理
3. 模型保存
4. 评估指标
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torch.optim.lr_scheduler import CosineAnnealingLR
import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import logging
from pathlib import Path
import json
from datetime import datetime
import traceback

logger = logging.getLogger(__name__)


class Trainer:
    """
    统一训练器

    Args:
        model: 模型实例
        config: 配置字典
        device: 设备（cuda/cpu）
    """

    def __init__(self, model: nn.Module, config: dict, device: str = "cuda"):
        self.model = model.to(device)
        self.config = config
        self.device = device

        # 创建保存目录
        self.save_dir = Path(config.get('save_dir', './checkpoints'))
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # 初始化优化器
        self.optimizer = self._create_optimizer()

        # 初始化学习率调度器
        self.scheduler = self._create_scheduler()

        # 初始化损失函数
        self.criterion = nn.CrossEntropyLoss()

        # 训练状态
        self.current_epoch = 0
        self.best_val_acc = 0.0
        self.training_history = []

        logger.info(f"Trainer 初始化完成")
        logger.info(f"  device: {device}")
        logger.info(f"  save_dir: {self.save_dir}")

    def _create_optimizer(self) -> optim.Optimizer:
        """创建优化器"""
        optimizer_config = self.config.get('optimizer', {})
        optimizer_name = optimizer_config.get('name', 'Adam')
        lr = optimizer_config.get('lr', 0.001)

        if optimizer_name == 'Adam':
            return optim.Adam(self.model.parameters(), lr=lr)
        elif optimizer_name == 'AdamW':
            return optim.AdamW(self.model.parameters(), lr=lr)
        elif optimizer_name == 'SGD':
            momentum = optimizer_config.get('momentum', 0.9)
            return optim.SGD(self.model.parameters(), lr=lr, momentum=momentum)
        else:
            raise ValueError(f"Unknown optimizer: {optimizer_name}")

    def _create_scheduler(self) -> optim.lr_scheduler._LRScheduler:
        """创建学习率调度器"""
        scheduler_config = self.config.get('scheduler', {})
        scheduler_name = scheduler_config.get('name', 'CosineAnnealingLR')

        if scheduler_name == 'CosineAnnealingLR':
            T_max = scheduler_config.get('T_max', 50)
            return CosineAnnealingLR(self.optimizer, T_max=T_max)
        else:
            return None

    def train_epoch(self, train_loader: DataLoader) -> dict:
        """
        训练一个 epoch

        Returns:
            metrics: 指标字典
        """
        self.model.train()
        total_loss = 0.0
        all_preds = []
        all_labels = []

        for batch_idx, (data, labels) in enumerate(train_loader):
            try:
                data = data.to(self.device)
                labels = labels.to(self.device)

                # 前向传播
                self.optimizer.zero_grad()
                outputs = self.model(data)
                loss = self.criterion(outputs, labels)

                # 反向传播
                loss.backward()
                self.optimizer.step()

                # 记录
                total_loss += loss.item() * data.size(0)
                _, preds = torch.max(outputs, 1)
                all_preds.extend(preds.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())

            except Exception as e:
                logger.error(f"训练批次 {batch_idx} 失败: {e}")
                logger.error(traceback.format_exc())
                continue

        # 计算指标
        avg_loss = total_loss / len(train_loader.dataset)
        acc = accuracy_score(all_labels, all_preds)
        precision = precision_score(all_labels, all_preds, average='weighted', zero_division=0)
        recall = recall_score(all_labels, all_preds, average='weighted', zero_division=0)
        f1 = f1_score(all_labels, all_preds, average='weighted', zero_division=0)

        return {
            'loss': avg_loss,
            'accuracy': acc,
            'precision': precision,
            'recall': recall,
            'f1': f1
        }

    def validate(self, val_loader: DataLoader) -> dict:
        """
        验证

        Returns:
            metrics: 指标字典
        """
        self.model.eval()
        total_loss = 0.0
        all_preds = []
        all_labels = []

        with torch.no_grad():
            for batch_idx, (data, labels) in enumerate(val_loader):
                try:
                    data = data.to(self.device)
                    labels = labels.to(self.device)

                    outputs = self.model(data)
                    loss = self.criterion(outputs, labels)

                    total_loss += loss.item() * data.size(0)
                    _, preds = torch.max(outputs, 1)
                    all_preds.extend(preds.cpu().numpy())
                    all_labels.extend(labels.cpu().numpy())

                except Exception as e:
                    logger.error(f"验证批次 {batch_idx} 失败: {e}")
                    logger.error(traceback.format_exc())
                    continue

        # 计算指标
        avg_loss = total_loss / len(val_loader.dataset)
        acc = accuracy_score(all_labels, all_preds)
        precision = precision_score(all_labels, all_preds, average='weighted', zero_division=0)
        recall = recall_score(all_labels, all_preds, average='weighted', zero_division=0)
        f1 = f1_score(all_labels, all_preds, average='weighted', zero_division=0)

        return {
            'loss': avg_loss,
            'accuracy': acc,
            'precision': precision,
            'recall': recall,
            'f1': f1
        }

    def train(self, train_loader: DataLoader, val_loader: DataLoader):
        """
        完整训练流程

        Args:
            train_loader: 训练数据加载器
            val_loader: 验证数据加载器
        """
        epochs = self.config.get('training', {}).get('epochs', 100)

        logger.info(f"开始训练，共 {epochs} 个 epoch")

        for epoch in range(epochs):
            self.current_epoch = epoch

            # 训练
            train_metrics = self.train_epoch(train_loader)

            # 验证
            val_metrics = self.validate(val_loader)

            # 学习率调度
            if self.scheduler is not None:
                self.scheduler.step()

            # 记录历史
            self.training_history.append({
                'epoch': epoch,
                'train': train_metrics,
                'val': val_metrics
            })

            # 日志
            logger.info(
                f"Epoch {epoch}/{epochs} - "
                f"Train Loss: {train_metrics['loss']:.4f}, Acc: {train_metrics['accuracy']:.4f} | "
                f"Val Loss: {val_metrics['loss']:.4f}, Acc: {val_metrics['accuracy']:.4f}"
            )

            # 保存最佳模型
            if val_metrics['accuracy'] > self.best_val_acc:
                self.best_val_acc = val_metrics['accuracy']
                self.save_checkpoint('best_model.pth')
                logger.info(f"  ✓ 保存最佳模型 (val_acc: {self.best_val_acc:.4f})")

            # 定期保存
            if (epoch + 1) % 10 == 0:
                self.save_checkpoint(f'checkpoint_epoch_{epoch+1}.pth')

        # 保存训练历史
        self.save_training_history()

        logger.info(f"训练完成！最佳验证准确率: {self.best_val_acc:.4f}")

    def save_checkpoint(self, filename: str):
        """保存检查点"""
        checkpoint_path = self.save_dir / filename

        torch.save({
            'epoch': self.current_epoch,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'best_val_acc': self.best_val_acc,
            'config': self.config
        }, checkpoint_path)

        logger.info(f"检查点已保存: {checkpoint_path}")

    def save_training_history(self):
        """保存训练历史"""
        history_path = self.save_dir / 'training_history.json'

        with open(history_path, 'w') as f:
            json.dump(self.training_history, f, indent=2)

        logger.info(f"训练历史已保存: {history_path}")
