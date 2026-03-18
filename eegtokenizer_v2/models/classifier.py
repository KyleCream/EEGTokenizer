"""
模型模块

包含分类器和解码器
"""

import torch
import torch.nn as nn
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class EEGClassifier(nn.Module):
    """
    EEG 分类器

    Args:
        tokenizer: tokenizer 实例
        num_classes: 类别数
        nhead: 注意力头数
        num_layers: Transformer 层数
        dropout: dropout 率
    """

    def __init__(
        self,
        tokenizer: nn.Module,
        num_classes: int = 4,
        nhead: int = 8,
        num_layers: int = 2,
        dropout: float = 0.1
    ):
        super().__init__()

        self.tokenizer = tokenizer
        self.num_classes = num_classes

        # Transformer 编码器
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=tokenizer.d_model,
            nhead=nhead,
            dim_feedforward=tokenizer.d_model * 4,
            dropout=dropout,
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        # 分类头
        self.classifier = nn.Linear(tokenizer.d_model, num_classes)

        logger.info(f"EEGClassifier 初始化完成")
        logger.info(f"  num_classes: {num_classes}")
        logger.info(f"  nhead: {nhead}, num_layers: {num_layers}")
        logger.info(f"  dropout: {dropout}")

    def forward(self, x: torch.Tensor, return_features: bool = False):
        """
        前向传播

        Args:
            x: EEG 信号, shape (batch, channels, timepoints)
            return_features: 是否返回中间特征

        Returns:
            logits: 分类 logits, shape (batch, num_classes)
            features (可选): token 特征, shape (batch, n_patches, d_model)
        """
        # Tokenize
        features, padding_mask = self.tokenizer(x)

        # Transformer
        # 注意：Transformer 需要 (batch, seq, feature) 格式
        features = self.transformer(features, src_key_padding_mask=padding_mask)

        # 全局平均池化
        pooled = features.mean(dim=1)  # (batch, d_model)

        # 分类
        logits = self.classifier(pooled)

        if return_features:
            return logits, features
        else:
            return logits


class SimpleClassifier(nn.Module):
    """
    简单分类器（用于防过拟合）

    Args:
        tokenizer: tokenizer 实例
        num_classes: 类别数
        hidden_dim: 隐藏层维度
        dropout: dropout 率
    """

    def __init__(
        self,
        tokenizer: nn.Module,
        num_classes: int = 4,
        hidden_dim: int = 128,
        dropout: float = 0.3
    ):
        super().__init__()

        self.tokenizer = tokenizer
        self.num_classes = num_classes

        # 全局平均池化
        self.pool = nn.AdaptiveAvgPool1d(1)

        # MLP
        self.mlp = nn.Sequential(
            nn.Linear(tokenizer.d_model, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, num_classes)
        )

        logger.info(f"SimpleClassifier 初始化完成")
        logger.info(f"  num_classes: {num_classes}")
        logger.info(f"  hidden_dim: {hidden_dim}")

    def forward(self, x: torch.Tensor):
        """
        前向传播

        Args:
            x: EEG 信号, shape (batch, channels, timepoints)

        Returns:
            logits: 分类 logits, shape (batch, num_classes)
        """
        # Tokenize
        features, _ = self.tokenizer(x)

        # 全局平均池化
        # features: (batch, n_patches, d_model)
        pooled = features.mean(dim=1)  # (batch, d_model)

        # MLP
        logits = self.mlp(pooled)

        return logits


class EEGDecoder(nn.Module):
    """
    EEG 解码器（用于重构评估）

    Args:
        d_model: 输入特征维度
        channels: EEG 通道数
        window_length: 窗口长度
        step_length: 步长
    """

    def __init__(
        self,
        d_model: int,
        channels: int = 22,
        window_length: int = 250,
        step_length: int = 125
    ):
        super().__init__()

        self.d_model = d_model
        self.channels = channels
        self.window_length = window_length
        self.step_length = step_length

        # 反投影
        self.projection = nn.Linear(d_model, channels)

        # 反量化（简单版本：直接输出，不量化）
        # 在实际应用中，可以学习一个更复杂的解码器

        logger.info(f"EEGDecoder 初始化完成")

    def forward(self, features: torch.Tensor, original_length: int) -> torch.Tensor:
        """
        解码 token 为 EEG 信号

        Args:
            features: token 特征, shape (batch, n_patches, d_model)
            original_length: 原始信号长度

        Returns:
            reconstructed: 重构的 EEG 信号, shape (batch, channels, original_length)
        """
        batch_size, n_patches, _ = features.shape

        # 投影回 channels
        patches = self.projection(features)  # (batch, n_patches, channels)

        # 计算重构长度
        reconstructed_length = (n_patches - 1) * self.step_length + self.window_length

        # 创建输出 tensor
        reconstructed = torch.zeros(batch_size, self.channels, reconstructed_length, device=features.device)

        # 填充 patches
        for i in range(n_patches):
            start = i * self.step_length
            end = start + self.window_length

            if end <= reconstructed_length:
                reconstructed[:, :, start:end] = patches[:, i, :]

        return reconstructed
