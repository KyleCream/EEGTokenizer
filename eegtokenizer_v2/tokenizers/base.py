"""
Tokenizer 基类

定义所有 tokenizer 的统一接口
"""

import torch
import torch.nn as nn
from abc import ABC, abstractmethod
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class BaseTokenizer(nn.Module):
    """
    Tokenizer 基类

    所有 tokenizer 都应该继承这个类，实现 encode() 方法

    输入: (batch, channels, timepoints)
    输出: (batch, n_patches, d_model), padding_mask
    """

    def __init__(self, d_model: int = 64):
        """
        Args:
            d_model: 输出特征维度
        """
        super().__init__()
        self.d_model = d_model

    @abstractmethod
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """
        Tokenize EEG 信号

        Args:
            x: EEG 信号, shape (batch, channels, timepoints)

        Returns:
            features: token 特征, shape (batch, n_patches, d_model)
            padding_mask: padding mask, shape (batch, n_patches) 或 None
        """
        pass

    def get_num_patches(self, timepoints: int, window_length: int, step_length: int) -> int:
        """
        计算 patch 数量

        Args:
            timepoints: 时间点数
            window_length: 窗口长度
            step_length: 步长

        Returns:
            n_patches: patch 数量
        """
        n_patches = (timepoints - window_length) // step_length + 1
        return max(1, n_patches)

    def log_info(self):
        """记录 tokenizer 信息"""
        logger.info(f"Tokenizer: {self.__class__.__name__}")
        logger.info(f"  d_model: {self.d_model}")
