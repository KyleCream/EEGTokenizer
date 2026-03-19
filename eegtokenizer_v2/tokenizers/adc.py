"""
ADC 风格量化 Tokenizer

老板的新思路：固定时间分割 → ADC 风格量化 → 码字聚合

核心思想：
1. 固定时间分割成 patch
2. 类似硬件 ADC 的标量量化
3. 支持不同精度（1/2/4/8/16bit）
4. 多种码字聚合方式
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional
import logging

from .base import BaseTokenizer

logger = logging.getLogger(__name__)


class ADCTokenizer(BaseTokenizer):
    """
    ADC 风格量化 Tokenizer

    核心步骤：
    1. 时间分 patch（固定长度）
    2. 量化（标量量化/矢量量化）
    3. 聚合（mean/attention/gate）

    Args:
        window_length: 每个 patch 的时间长度（采样点数）
        step_length: 滑动步长（采样点数）
        num_bits: 量化精度（bit）
        quant_type: 量化类型（"scalar"/"vector"/"product"）
        agg_type: 聚合方式（"mean"/"attention"/"gate"）
        d_model: 输出特征维度
        channels: EEG 通道数
        value_range: EEG 信号范围（min, max）
        n_head: 注意力头数（仅用于 agg_type="attention"）
    """

    def __init__(
        self,
        window_length: int = 250,      # 250Hz × 0.25s = 62.5ms
        step_length: int = 125,        # 50% 重叠
        num_bits: int = 4,              # 4bit = 16 级
        quant_type: str = "scalar",     # 标量量化
        agg_type: str = "mean",         # 简单平均
        d_model: Optional[int] = None,
        channels: int = 22,
        value_range: tuple = (-100, 100),  # μV
        n_head: int = 8,
        **kwargs
    ):
        # 初始化基类
        if d_model is None:
            d_model = self._compute_d_model(channels, quant_type, n_head)
        super().__init__(d_model)

        # 保存参数
        self.window_length = window_length
        self.step_length = step_length
        self.num_bits = num_bits
        self.quant_type = quant_type
        self.agg_type = agg_type
        self.channels = channels
        self.value_range = value_range
        self.n_head = n_head

        # 计算量化级别
        self.quant_levels = 2 ** num_bits

        # 初始化量化器
        self.quantizer = self._create_quantizer()

        # 初始化聚合器
        self.aggregator = self._create_aggregator()

        logger.info(f"ADC Tokenizer 初始化完成")
        logger.info(f"  window_length: {window_length}, step_length: {step_length}")
        logger.info(f"  num_bits: {num_bits} ({self.quant_levels} 级)")
        logger.info(f"  quant_type: {quant_type}, agg_type: {agg_type}")
        logger.info(f"  d_model: {self.d_model}")

    def _compute_d_model(self, channels: int, quant_type: str, n_head: int) -> int:
        """自动计算合适的 d_model"""
        if quant_type == "scalar":
            base_dim = channels
        elif quant_type == "vector":
            base_dim = channels * 4
        elif quant_type == "product":
            base_dim = channels * 2
        else:
            raise ValueError(f"Unknown quant_type: {quant_type}")

        # 确保 d_model 能被 n_head 整除
        d_model = base_dim
        while d_model % n_head != 0:
            d_model += 1

        return d_model

    def _create_quantizer(self) -> nn.Module:
        """创建量化器"""
        if self.quant_type == "scalar":
            return ScalarQuantizer(
                self.num_bits,
                self.value_range
            )
        elif self.quant_type == "vector":
            return VectorQuantizer(
                self.num_bits,
                self.channels
            )
        elif self.quant_type == "product":
            return ProductQuantizer(
                self.num_bits,
                self.channels
            )
        else:
            raise ValueError(f"Unknown quant_type: {self.quant_type}")

    def _create_aggregator(self) -> nn.Module:
        """创建聚合器"""
        if self.agg_type == "mean":
            return MeanAggregator(self.d_model)
        elif self.agg_type == "attention":
            return AttentionAggregator(self.d_model, self.n_head)
        elif self.agg_type == "gate":
            return GateAggregator(self.d_model)
        else:
            raise ValueError(f"Unknown agg_type: {self.agg_type}")

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """
        Tokenize EEG 信号

        Args:
            x: EEG 信号, shape (batch, channels, timepoints)

        Returns:
            features: token 特征, shape (batch, n_patches, d_model)
            padding_mask: padding mask, shape (batch, n_patches)
        """
        batch_size, channels, timepoints = x.shape

        # 1. 时间分 patch
        patches = self._split_patches(x)  # (batch, channels, window_length, n_patches)

        # 2. 量化
        quantized = self.quantizer(patches)  # (batch, channels, window_length, n_patches)

        # 3. 聚合（时间维度）
        aggregated = self.aggregator(quantized)  # (batch, n_patches, channels)

        # 4. 投影到 d_model
        features = self._project_to_d_model(aggregated)  # (batch, n_patches, d_model)

        # 5. 计算 padding mask
        padding_mask = self._compute_padding_mask(batch_size, features.size(1))

        return features, padding_mask

    def _split_patches(self, x: torch.Tensor) -> torch.Tensor:
        """
        时间分 patch

        Args:
            x: (batch, channels, timepoints)

        Returns:
            patches: (batch, channels, n_patches, window_length)
        """
        batch_size, channels, timepoints = x.shape

        # unfold: 滑动窗口
        # unfold(2, window_length, step_length)
        # dim=2 是时间维度
        patches = x.unfold(2, self.window_length, self.step_length)
        # 输出: (batch, channels, n_patches, window_length)

        return patches  # 不需要 permute!

    def _project_to_d_model(self, aggregated: torch.Tensor) -> torch.Tensor:
        """
        投影到 d_model

        Args:
            aggregated: (batch, n_patches, channels)

        Returns:
            features: (batch, n_patches, d_model)
        """
        batch_size, n_patches, channels = aggregated.shape

        # 投影层
        if not hasattr(self, 'projection'):
            self.projection = nn.Linear(channels, self.d_model).to(aggregated.device)

        features = self.projection(aggregated)
        return features

    def _compute_padding_mask(self, batch_size: int, n_patches: int) -> torch.Tensor:
        """
        计算 padding mask

        Args:
            batch_size: batch 大小
            n_patches: patch 数量

        Returns:
            mask: (batch, n_patches), True 表示有效
        """
        # 目前所有 patch 都是有效的，所以 mask 全为 True
        mask = torch.ones(batch_size, n_patches, dtype=torch.bool)
        return mask.to(self.projection.weight.device) if hasattr(self, 'projection') else torch.ones(batch_size, n_patches, dtype=torch.bool)


# ==================== 量化器 ====================

class ScalarQuantizer(nn.Module):
    """标量量化器"""

    def __init__(self, num_bits: int, value_range: tuple):
        super().__init__()
        self.num_bits = num_bits
        self.min_val, self.max_val = value_range
        self.quant_levels = 2 ** num_bits

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        标量量化

        Args:
            x: (batch, channels, window_length, n_patches)

        Returns:
            quantized: 量化后的值
        """
        # 归一化到 [0, 1]
        x_norm = (x - self.min_val) / (self.max_val - self.min_val)
        x_norm = torch.clamp(x_norm, 0, 1)

        # 量化到 [0, quant_levels-1]
        x_quant = torch.round(x_norm * (self.quant_levels - 1))

        # 反归一化
        x_quant = x_quant / (self.quant_levels - 1) * (self.max_val - self.min_val) + self.min_val

        return x_quant


class VectorQuantizer(nn.Module):
    """矢量量化器（VQ-VAE 风格）"""

    def __init__(self, num_bits: int, channels: int):
        super().__init__()
        self.num_bits = num_bits
        self.channels = channels
        self.codebook_size = 2 ** num_bits

        # 学习 codebook
        self.codebook = nn.Parameter(
            torch.randn(self.codebook_size, channels)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        矢量量化

        Args:
            x: (batch, channels, window_length, n_patches)

        Returns:
            quantized: 量化后的值
        """
        batch, channels, window, n_patches = x.shape

        # Reshape: (batch * n_patches, channels * window)
        x_flat = x.permute(0, 3, 1, 2).contiguous()
        x_flat = x_flat.view(batch * n_patches, -1)

        # 计算与 codebook 的距离
        distances = torch.cdist(x_flat, self.codebook)  # (batch * n_patches, codebook_size)

        # 找到最近的 codebook entry
        indices = torch.argmin(distances, dim=1)  # (batch * n_patches,)
        quantized_flat = self.codebook[indices]  # (batch * n_patches, channels * window)

        # Reshape 回原形状
        quantized = quantized_flat.view(batch, n_patches, channels, window)
        quantized = quantized.permute(0, 2, 3, 1)  # (batch, channels, window, n_patches)

        return quantized


class ProductQuantizer(nn.Module):
    """乘积量化器（PQ）"""

    def __init__(self, num_bits: int, channels: int):
        super().__init__()
        self.num_bits = num_bits
        self.channels = channels

        # 将通道分成子空间
        self.nsubq = 4  # 子空间数量
        self.sub_channels = channels // self.nsubq

        # 每个子空间的 codebook
        self.sub_bits = num_bits // 2
        self.codebook_size = 2 ** self.sub_bits

        self.codebooks = nn.Parameter(
            torch.randn(self.nsubq, self.codebook_size, self.sub_channels)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        乘积量化

        Args:
            x: (batch, channels, window_length, n_patches)

        Returns:
            quantized: 量化后的值
        """
        batch, channels, window, n_patches = x.shape

        # 分割成子空间
        x_sub = x.view(batch, self.nsubq, self.sub_channels, window, n_patches)

        quantized_sub = []
        for i in range(self.nsubq):
            # (batch, window, n_patches, sub_channels)
            x_sub_i = x_sub[:, i].permute(0, 2, 3, 1).contiguous()
            x_sub_flat = x_sub_i.view(batch * n_patches * window, -1)

            # 量化
            distances = torch.cdist(x_sub_flat, self.codebooks[i])
            indices = torch.argmin(distances, dim=1)
            quantized_flat = self.codebooks[i][indices]

            # Reshape 回
            quantized_i = quantized_flat.view(batch, n_patches, window, self.sub_channels)
            quantized_sub.append(quantized_i)

        # 合并子空间
        quantized = torch.cat(quantized_sub, dim=3)  # (batch, n_patches, window, channels)

        # 转置回原形状
        quantized = quantized.permute(0, 3, 2, 1)  # (batch, channels, window, n_patches)

        return quantized


# ==================== 聚合器 ====================

class MeanAggregator(nn.Module):
    """简单平均聚合器"""

    def __init__(self, d_model: int):
        super().__init__()
        self.d_model = d_model

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        时间维度平均

        Args:
            x: (batch, channels, n_patches, window_length)

        Returns:
            aggregated: (batch, n_patches, channels)
        """
        # 对时间维度求平均 (dim=3)
        return x.mean(dim=3).permute(0, 2, 1)  # (batch, n_patches, channels)


class AttentionAggregator(nn.Module):
    """注意力聚合器"""

    def __init__(self, d_model: int, n_head: int):
        super().__init__()
        self.d_model = d_model
        self.n_head = n_head

        # 多头注意力
        self.attention = nn.MultiheadAttention(d_model, n_head, batch_first=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        注意力聚合

        Args:
            x: (batch, channels, window_length, n_patches)

        Returns:
            aggregated: (batch, n_patches, channels)
        """
        batch, channels, window, n_patches = x.shape

        # Reshape: (batch * n_patches, window, channels)
        x_flat = x.permute(0, 3, 2, 1).contiguous()
        x_flat = x_flat.view(batch * n_patches, window, channels)

        # 注意力
        attn_out, _ = self.attention(x_flat, x_flat, x_flat)

        # Reshape 回
        attn_out = attn_out.view(batch, n_patches, window, channels)

        # 对时间维度求平均
        return attn_out.mean(dim=2)


class GateAggregator(nn.Module):
    """门控聚合器（LSTM 风格）"""

    def __init__(self, d_model: int):
        super().__init__()
        self.d_model = d_model

        # LSTM
        self.lstm = nn.LSTM(channels, d_model // 2, batch_first=True)
        self.fc = nn.Linear(d_model // 2, channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        门控聚合

        Args:
            x: (batch, channels, window_length, n_patches)

        Returns:
            aggregated: (batch, n_patches, channels)
        """
        batch, channels, window, n_patches = x.shape

        # Reshape: (batch * n_patches, window, channels)
        x_flat = x.permute(0, 3, 2, 1).contiguous()

        # LSTM
        lstm_out, _ = self.lstm(x_flat)

        # 投影回 channels
        out = self.fc(lstm_out)

        # Reshape 回
        out = out.view(batch, n_patches, channels)

        return out
