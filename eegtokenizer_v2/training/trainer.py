"""
训练器模块（重构版）

统一的训练接口，支持：
1. 多种训练任务（分类、重构、探针）
2. 完整的日志管理
3. 错误处理
4. 模型保存
5. 自动推送到 GitHub
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader
import logging
from pathlib import Path
import json
from datetime import datetime
import traceback
import subprocess
import os
from typing import Dict, Any

from .tasks import create_task

logger = logging.getLogger(__name__)


class Trainer:
    """
    统一训练器（支持多种任务）

    Args:
        model: 模型实例
        config: 配置字典
        device: 设备（cuda/cpu）
    """

    def __init__(self, model: nn.Module, config: Dict[str, Any], device: str = "cuda"):
        self.model = model.to(device)
        self.config = config
        self.device = device

        # 创建保存目录
        self.save_dir = Path(config.get('save_dir', './checkpoints'))
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # 创建任务
        self.task = create_task(model, config.get('training', {}), device)

        # 初始化优化器
        self.optimizer = self._create_optimizer()

        # 初始化学习率调度器
        self.scheduler = self._create_scheduler()

        # 训练状态
        self.current_epoch = 0
        self.best_metric = 0.0  # 根据任务类型可能是准确率或重构质量
        self.training_history = []

        logger.info(f"Trainer 初始化完成")
        logger.info(f"  device: {device}")
        logger.info(f"  task: {config.get('training', {}).get('task', 'classification')}")
        logger.info(f"  save_dir: {self.save_dir}")

    def _create_optimizer(self) -> optim.Optimizer:
        """创建优化器"""
        optimizer_config = self.config.get('training', {}).get('optimizer', {})
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
        scheduler_config = self.config.get('training', {}).get('scheduler', {})
        scheduler_name = scheduler_config.get('name', 'CosineAnnealingLR')

        if scheduler_name == 'CosineAnnealingLR':
            T_max = scheduler_config.get('T_max', 50)
            return CosineAnnealingLR(self.optimizer, T_max=T_max)
        else:
            return None

    def train_epoch(self, train_loader: DataLoader) -> Dict[str, float]:
        """
        训练一个 epoch

        Args:
            train_loader: 训练数据加载器

        Returns:
            metrics: 指标字典
        """
        self.model.train()
        total_loss = 0.0
        num_batches = 0

        for batch_idx, batch in enumerate(train_loader):
            try:
                # 转换数据格式（如果是元组）
                if isinstance(batch, (tuple, list)):
                    data, labels = batch
                    batch = {'data': data, 'labels': labels}

                # 执行训练步骤
                result = self.task.train_step(batch)
                loss = result['loss']

                # 反向传播
                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()

                # 记录
                total_loss += loss.item()
                num_batches += 1

            except Exception as e:
                logger.error(f"训练批次 {batch_idx} 失败: {e}")
                logger.error(traceback.format_exc())
                continue

        # 计算平均损失
        avg_loss = total_loss / max(num_batches, 1)

        return {'loss': avg_loss}

    def validate(self, val_loader: DataLoader) -> Dict[str, float]:
        """
        验证

        Args:
            val_loader: 验证数据加载器

        Returns:
            metrics: 指标字典
        """
        self.model.eval()
        all_metrics = []
        total_loss = 0.0
        num_batches = 0

        with torch.no_grad():
            for batch_idx, batch in enumerate(val_loader):
                try:
                    # 转换数据格式
                    if isinstance(batch, (tuple, list)):
                        data, labels = batch
                        batch = {'data': data, 'labels': labels}

                    # 执行验证步骤
                    metrics = self.task.validate_step(batch)
                    all_metrics.append(metrics)
                    total_loss += metrics.get('loss', 0.0)
                    num_batches += 1

                except Exception as e:
                    logger.error(f"验证批次 {batch_idx} 失败: {e}")
                    logger.error(traceback.format_exc())
                    continue

        # 汇总指标
        avg_metrics = {}
        if all_metrics:
            for key in all_metrics[0].keys():
                values = [m[key] for m in all_metrics if key in m]
                if values:
                    avg_metrics[key] = sum(values) / len(values)

        return avg_metrics

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

            # 训练一个 epoch
            train_metrics = self.train_epoch(train_loader)

            # 验证
            val_metrics = self.validate(val_loader)

            # 学习率调度
            if self.scheduler:
                self.scheduler.step()

            # 记录日志
            logger.info(
                f"Epoch {epoch}/{epochs} - "
                f"Train Loss: {train_metrics['loss']:.4f} | "
                f"Val Loss: {val_metrics.get('loss', 0):.4f}"
            )

            # 如果有准确率，也打印
            if 'accuracy' in val_metrics:
                logger.info(f"  Val Acc: {val_metrics['accuracy']:.4f}")

            # 保存最佳模型
            main_metric = val_metrics.get('accuracy', val_metrics.get('loss', 0))
            is_better = main_metric > self.best_metric if 'accuracy' in val_metrics else main_metric < self.best_metric

            if is_better:
                self.best_metric = main_metric
                self._save_checkpoint('best_model.pt')
                logger.info(f"  ✓ 保存最佳模型 ({main_metric:.4f})")

            # 保存训练历史
            epoch_history = {
                'epoch': epoch,
                'train_loss': train_metrics['loss'],
                'val_metrics': val_metrics
            }
            self.training_history.append(epoch_history)

        # 保存训练历史
        self._save_training_history()

        logger.info("训练完成！")

    def _save_checkpoint(self, filename: str):
        """保存模型检查点"""
        checkpoint_path = self.save_dir / filename
        torch.save({
            'epoch': self.current_epoch,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'best_metric': self.best_metric
        }, checkpoint_path)

    def _save_training_history(self):
        """保存训练历史"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        history_path = self.save_dir / f'training_history_{timestamp}.json'

        with open(history_path, 'w') as f:
            json.dump(self.training_history, f, indent=2)

        logger.info(f"训练历史已保存: {history_path}")

    def push_to_github(self, project_root: Path):
        """
        自动推送训练结果到 GitHub

        Args:
            project_root: 项目根目录
        """
        logger.info("自动推送训练结果到 GitHub...")

        try:
            # 切换到项目根目录
            original_dir = os.getcwd()
            os.chdir(project_root)

            # 只添加日志目录
            subprocess.run(
                ['git', 'add', 'eegtokenizer_v2/logs/'],
                check=True,
                capture_output=True
            )

            # 检查是否有变更
            result = subprocess.run(
                ['git', 'diff', '--cached', '--quiet'],
                capture_output=True
            )

            if result.returncode != 0:
                # 有变更，提交并推送
                task_name = self.config.get('training', {}).get('task', 'unknown')
                commit_msg = f"训练日志: {task_name}_metric_{self.best_metric:.4f}"
                subprocess.run(
                    ['git', 'commit', '-m', commit_msg],
                    check=True,
                    capture_output=True
                )

                # 推送（最多重试3次）
                for retry in range(3):
                    result = subprocess.run(
                        ['git', 'push', 'origin', 'main'],
                        capture_output=True
                    )
                    if result.returncode == 0:
                        logger.info("✓ 训练结果已推送到 GitHub")
                        break
                    else:
                        if retry < 2:
                            logger.warning(f"推送失败，10秒后重试 ({retry + 1}/3)...")
                            import time
                            time.sleep(10)
                        else:
                            logger.error("❌ 推送失败，请手动推送: git push origin main")
            else:
                logger.info("没有需要推送的变更")

            # 恢复目录
            os.chdir(original_dir)

        except Exception as e:
            logger.warning(f"自动推送失败: {e}")
            logger.warning("请手动推送: git push origin main")
