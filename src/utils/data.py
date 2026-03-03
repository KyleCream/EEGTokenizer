import numpy as np
import torch
from torch.utils.data import TensorDataset, DataLoader
from typing import Tuple, Optional


class UnifiedEEGDataLoader:
    """
    统一的 EEG 数据加载接口（简化版）
    
    用于快速实验，生成模拟数据或加载简单数据
    """
    
    def __init__(
        self,
        batch_size: int = 32,
        channels: int = 22,
        timepoints: int = 1000,
        num_classes: int = 4,
        num_samples: int = 1000  # 模拟数据样本数
    ):
        self.batch_size = batch_size
        self.channels = channels
        self.timepoints = timepoints
        self.num_classes = num_classes
        self.num_samples = num_samples
    
    def generate_mock_data(
        self,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
        seed: int = 42
    ) -> Tuple[DataLoader, DataLoader, DataLoader]:
        """
        生成模拟 EEG 数据（用于快速测试）
        
        返回: (train_loader, val_loader, test_loader)
        """
        np.random.seed(seed)
        torch.manual_seed(seed)
        
        # 生成模拟数据：带点节律信号的噪声
        t = np.linspace(0, 4, self.timepoints)  # 4秒数据
        
        X = np.random.randn(self.num_samples, self.channels, self.timepoints) * 10
        y = np.random.randint(0, self.num_classes, self.num_samples)
        
        # 加一点简单的节律（不同类别不同频率）
        freq_map = {0: 8, 1: 10, 2: 12, 3: 15}  # alpha/mu 频段
        for i in range(self.num_samples):
            freq = freq_map[y[i]]
            X[i, :, :] += 5 * np.sin(2 * np.pi * freq * t)[np.newaxis, :]
        
        # 划分数据集
        indices = np.arange(self.num_samples)
        np.random.shuffle(indices)
        
        train_size = int(train_ratio * self.num_samples)
        val_size = int(val_ratio * self.num_samples)
        
        train_indices = indices[:train_size]
        val_indices = indices[train_size:train_size+val_size]
        test_indices = indices[train_size+val_size:]
        
        # 构建数据集
        def make_loader(indices):
            X_sub = torch.tensor(X[indices], dtype=torch.float32)
            y_sub = torch.tensor(y[indices], dtype=torch.long)
            dataset = TensorDataset(X_sub, y_sub)
            return DataLoader(dataset, batch_size=self.batch_size, shuffle=(len(indices) == train_size))
        
        return make_loader(train_indices), make_loader(val_indices), make_loader(test_indices)
