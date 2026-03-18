"""
数据加载模块

封装 BCI IV 2a 数据集的加载逻辑
"""

import torch
from torch.utils.data import Dataset, DataLoader
import numpy as np
import mne
from typing import Tuple, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class BCIDataset(Dataset):
    """
    BCI IV 2a 数据集

    Args:
        data_path: 数据路径（.fif 文件）
        window_length: 窗口长度
        step_length: 步长
        normalization: 归一化方式（"z_score"/"min_max"/"none"）
    """

    def __init__(
        self,
        data_path: str,
        labels_path: str,
        window_length: int = 1000,
        step_length: int = 500,
        normalization: str = "z_score"
    ):
        self.data_path = data_path
        self.labels_path = labels_path
        self.window_length = window_length
        self.step_length = step_length
        self.normalization = normalization

        # 加载数据
        self.raw_data = mne.io.read_raw_fif(data_path, preload=True)
        self.data = self.raw_data.get_data()  # (channels, timepoints)

        # 加载标签
        self.labels = np.load(labels_path)

        # 归一化
        if normalization == "z_score":
            mean = np.mean(self.data, axis=1, keepdims=True)
            std = np.std(self.data, axis=1, keepdims=True)
            self.data = (self.data - mean) / (std + 1e-8)
        elif normalization == "min_max":
            min_val = np.min(self.data, axis=1, keepdims=True)
            max_val = np.max(self.data, axis=1, keepdims=True)
            self.data = (self.data - min_val) / (max_val - min_val + 1e-8)

        # 分段
        self.segments = self._create_segments()

        logger.info(f"数据集加载完成: {len(self.segments)} 个样本")

    def _create_segments(self) -> list:
        """创建样本片段"""
        segments = []

        for i in range(0, self.data.shape[1] - self.window_length + 1, self.step_length):
            segment_data = self.data[:, i:i + self.window_length]

            # 标签：取该段的主要标签
            segment_labels = self.labels[i:i + self.window_length]
            segment_label = np.bincount(segment_labels.astype(int)).argmax()

            segments.append((segment_data, segment_label))

        return segments

    def __len__(self):
        return len(self.segments)

    def __getitem__(self, idx) -> Tuple[torch.Tensor, int]:
        data, label = self.segments[idx]
        return torch.tensor(data, dtype=torch.float32), int(label)


class EEGDataLoader:
    """
    EEG 数据加载器（统一接口）

    支持单被试和跨被试模式
    """

    def __init__(self, data_dir: str, subject_id: str = "A01", data_mode: str = "single"):
        self.data_dir = data_dir
        self.subject_id = subject_id
        self.data_mode = data_mode

        logger.info(f"EEGDataLoader 初始化")
        logger.info(f"  data_dir: {data_dir}")
        logger.info(f"  subject_id: {subject_id}")
        logger.info(f"  data_mode: {data_mode}")

    def load_single_subject(
        self,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
        batch_size: int = 32,
        num_workers: int = 0
    ) -> Tuple[DataLoader, DataLoader, DataLoader]:
        """
        加载单被试数据

        Returns:
            train_loader, val_loader, test_loader
        """
        data_path = f"{self.data_dir}/{self.subject_id}.fif"
        labels_path = f"{self.data_dir}/{self.subject_id}_labels.npy"

        # 创建数据集
        full_dataset = BCIDataset(data_path, labels_path)

        # 划分训练/验证/测试集
        total_size = len(full_dataset)
        train_size = int(total_size * train_ratio)
        val_size = int(total_size * val_ratio)

        train_dataset, val_dataset, test_dataset = torch.utils.data.random_split(
            full_dataset,
            [train_size, val_size, total_size - train_size - val_size]
        )

        # 创建 DataLoader
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=num_workers)
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=num_workers)
        test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, num_workers=num_workers)

        logger.info(f"单被试数据加载完成")
        logger.info(f"  训练集: {len(train_dataset)} 样本")
        logger.info(f"  验证集: {len(val_dataset)} 样本")
        logger.info(f"  测试集: {len(test_dataset)} 样本")

        return train_loader, val_loader, test_loader
