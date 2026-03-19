"""
数据加载模块（修正版 v2）

根据 BCI IV 2a 数据集的标准加载方式重写

数据格式：
- 训练集：A01T.gdf, A02T.gdf, ...
- 测试集：A01E.gdf, A02E.gdf, ...
- 测试集标签：/home/zengkai/model_compare/data/BNCI2014_001/Data sets 2a_true_labels/A01E.mat

数据形状：
- X: (n_trials, n_channels, n_samples)
- Y: (n_trials,)
"""

import torch
from torch.utils.data import Dataset, DataLoader
import numpy as np
import mne
from scipy.io import loadmat
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class BCIDataset(Dataset):
    """
    BCI IV 2a 数据集（修正版 v2）

    使用 MNE 的 Epochs 接口，正确处理事件和标签

    Args:
        file_path: 数据文件路径
        subject: 被试 ID（1-9）
        win_sel: 时间窗口选择 (tmin, tmax)
        sessions: 要加载的会话 ('train' / 'test' / 'both')
    """

    def __init__(
        self,
        file_path: str,
        subject: int,
        win_sel: Tuple[float, float] = (0.0, 4.0),
        sessions: str = 'train',
        channels_to_remove: Optional[list] = None
    ):
        self.file_path = file_path
        self.subject = subject
        self.win_sel = win_sel
        self.sessions = sessions

        # 移除的通道（眼电）
        if channels_to_remove is None:
            self.channels_to_remove = ['EOG-left', 'EOG-central', 'EOG-right']
        else:
            self.channels_to_remove = channels_to_remove

        # 刺激代码
        # '769', '770', '771', '772' 对应 4 个类别
        # '768' 是 trial 开始（0 时刻）
        self.stimcodes_train = ('769', '770', '771', '772')

        # 加载数据
        self.data = self._load_data()

        logger.info(f"数据集加载完成")
        logger.info(f"  被试: {subject}")  # 直接显示原始字符串
        logger.info(f"  会话: {sessions}")
        logger.info(f"  形状: {self.data['X'].shape}")
        logger.info(f"  标签形状: {self.data['Y'].shape}")

    def _load_data(self):
        """加载数据"""
        data_subject = {}
        tmin, tmax = self.win_sel

        # ==================== 训练集数据 ====================
        if self.sessions in ['train', 'both']:
            # 使用原始 subject 字符串 (如 "A01")
            file_to_load = f"{self.file_path}/{self.subject}T.gdf"
            logger.info(f"加载训练集: {file_to_load}")

            raw_data = mne.io.read_raw_gdf(file_to_load, preload=True, verbose=False)
            fs = raw_data.info['sfreq']

            # 从注释中提取事件
            events, event_ids = mne.events_from_annotations(raw_data)

            # 只选择 4 个类别的刺激
            stims = [value for key, value in event_ids.items() if key in self.stimcodes_train]

            # 创建 Epochs
            epochs = mne.Epochs(
                raw_data,
                events,
                event_id=stims,
                tmin=tmin,
                tmax=tmax,
                event_repeated='drop',
                baseline=None,
                preload=True,
                proj=False,
                reject_by_annotation=False,
                verbose=False
            )

            # 移除眼电通道
            epochs = epochs.drop_channels(self.channels_to_remove)

            # 获取标签（转换为 0-3）
            class_return = epochs.events[:, -1] - min(epochs.events[:, -1])

            # 获取数据并转换为 μV
            data_return = epochs.get_data() * 1e6

            # 去均值（对每个 trial 的每个通道，计算所有时间点的均值）
            # 数据形状: (n_trials, n_channels, n_samples)
            # axis=1 是通道维度（n_channels）
            # 这意味着：对每个通道，计算所有时间点的均值，然后减去
            data_return = data_return - np.mean(data_return, axis=1, keepdims=True)

            # 重采样到 1000 个点
            if data_return.shape[2] != 1000:
                from scipy import signal
                logger.info(f"重采样: {data_return.shape[2]} → 1000 个采样点")
                data_return = signal.resample(data_return, 1000, axis=2)

            data_subject['train'] = {
                'X': data_return,
                'Y': class_return
            }

        # ==================== 测试集数据 ====================
        if self.sessions in ['test', 'both']:
            # 使用原始 subject 字符串 (如 "A01")
            file_to_load = f"{self.file_path}/{self.subject}E.gdf"
            logger.info(f"加载测试集: {file_to_load}")

            raw_data = mne.io.read_raw_gdf(file_to_load, preload=True, verbose=False)
            fs = raw_data.info['sfreq']

            # 加载真实标签（.mat 文件）
            labels_mat_path = f"{self.file_path}/Data sets 2a_true_labels/{self.subject}E.mat"
            logger.info(f"加载测试集标签: {labels_mat_path}")
            
            labels_mat = loadmat(labels_mat_path)
            class_all = labels_mat['classlabel'][:, 0]

            # 从注释中提取事件
            events, event_ids = mne.events_from_annotations(raw_data)

            # 找到 '783' 事件（trial 开始）
            index_type = [value for key, value in event_ids.items() if key in '783']
            events_index = np.where(events[:, 2] == np.array(index_type))[0]
            events = events[events_index, :]
            events[:, 2] = class_all

            # 获取所有类别
            stims = list(np.array(np.unique(class_all)))

            # 创建 Epochs
            epochs = mne.Epochs(
                raw_data,
                events,
                event_id=stims,
                tmin=tmin,
                tmax=tmax,
                event_repeated='drop',
                baseline=None,
                preload=True,
                proj=False,
                reject_by_annotation=False,
                verbose=False
            )

            # 移除眼电通道
            epochs = epochs.drop_channels(self.channels_to_remove)

            # 获取标签（转换为 0-3）
            class_return = epochs.events[:, -1] - min(epochs.events[:, -1])

            # 获取数据并转换为 μV
            data_return = epochs.get_data() * 1e6

            # 去均值（对每个 trial 的每个通道，计算所有时间点的均值）
            # 数据形状: (n_trials, n_channels, n_samples)
            # axis=1 是通道维度（n_channels）
            # 这意味着：对每个通道，计算所有时间点的均值，然后减去
            data_return = data_return - np.mean(data_return, axis=1, keepdims=True)

            # 重采样到 1000 个点
            if data_return.shape[2] != 1000:
                from scipy import signal
                logger.info(f"重采样: {data_return.shape[2]} → 1000 个采样点")
                data_return = signal.resample(data_return, 1000, axis=2)

            data_subject['test'] = {
                'X': data_return,
                'Y': class_return
            }

        # 添加元数据
        data_subject['fs'] = fs
        data_subject['win_sel'] = self.win_sel

        # 合并训练和测试集
        if self.sessions == 'both':
            X_train = data_subject['train']['X']
            Y_train = data_subject['train']['Y']
            X_test = data_subject['test']['X']
            Y_test = data_subject['test']['Y']

            X = np.concatenate([X_train, X_test], axis=0)
            Y = np.concatenate([Y_train, Y_test], axis=0)

            return {'X': X, 'Y': Y, 'fs': fs}
        elif self.sessions == 'train':
            return {'X': data_subject['train']['X'], 'Y': data_subject['train']['Y'], 'fs': fs}
        else:  # test
            return {'X': data_subject['test']['X'], 'Y': data_subject['test']['Y'], 'fs': fs}

    def __len__(self):
        return self.data['X'].shape[0]

    def __getitem__(self, idx) -> Tuple[torch.Tensor, int]:
        data = self.data['X'][idx]
        label = self.data['Y'][idx]
        return torch.tensor(data, dtype=torch.float32), int(label)


class EEGDataLoader:
    """
    EEG 数据加载器（修正版 v2）

    使用正确的 BCI IV 2a 数据加载方式

    数据路径（nit）：
- 训练集：/home/zengkai/model_compare/data/BNCI2014_001/A01T.gdf
- 测试集：/home/zengkai/model_compare/data/BNCI2014_001/A01E.gdf
- 测试集标签：/home/zengkai/model_compare/data/BNCI2014_001/Data sets 2a_true_labels/A01E.mat
    """

    def __init__(
        self,
        data_dir: str = None,
        subject_id: str = "A01",
        sessions: str = "train",
        win_sel: Tuple[float, float] = (-2.0, 5.0)  # 修改为 [-2, 5]
    ):
        # 如果未指定 data_dir，使用默认路径
        if data_dir is None:
            data_dir = "/home/zengkai/model_compare/data/BNCI2014_001"

        # 保存 data_dir
        self.data_dir = data_dir
        
        # 保存 subject_id (字符串形式,如 "A01")
        self.subject_id = subject_id
        self.sessions = sessions
        self.win_sel = win_sel

        logger.info(f"EEGDataLoader 初始化")
        logger.info(f"  data_dir: {data_dir}")
        logger.info(f"  subject_id: {subject_id}")
        logger.info(f"  sessions: {sessions}")
        logger.info(f"  win_sel: {win_sel}")

    def load_data(
        self,
        train_ratio: float = 0.8,
        batch_size: int = 32,
        num_workers: int = 0
    ) -> Tuple[DataLoader, DataLoader, DataLoader]:
        """
        加载数据

        正确的加载逻辑:
        1. 加载 A01T.gdf → 288 trials (训练数据)
        2. 加载 A01E.gdf → 288 trials (测试数据)
        3. 从 A01T 中划分训练集和验证集

        Returns:
            train_loader, val_loader, test_loader
        """
        # 1. 加载训练数据 (A01T.gdf)
        logger.info("加载训练数据 (A01T.gdf)...")
        train_val_dataset = BCIDataset(
            file_path=self.data_dir,
            subject=self.subject_id,
            win_sel=self.win_sel,
            sessions='train'  # 加载 A01T.gdf
        )
        
        # 2. 加载测试数据 (A01E.gdf)
        logger.info("加载测试数据 (A01E.gdf)...")
        test_dataset = BCIDataset(
            file_path=self.data_dir,
            subject=self.subject_id,
            win_sel=self.win_sel,
            sessions='test'  # 加载 A01E.gdf
        )

        # 3. 从训练数据中划分训练集和验证集
        total_train_size = len(train_val_dataset)
        train_size = int(total_train_size * train_ratio)
        val_size = total_train_size - train_size

        logger.info(f"数据集划分:")
        logger.info(f"  训练+验证集 (A01T): {total_train_size} 样本")
        logger.info(f"  测试集 (A01E): {len(test_dataset)} 样本")
        logger.info(f"  训练集: {train_size} ({train_ratio*100}%)")
        logger.info(f"  验证集: {val_size} ({(1-train_ratio)*100}%)")

        train_dataset, val_dataset = torch.utils.data.random_split(
            train_val_dataset,
            [train_size, val_size]
        )

        # 创建 DataLoader
        train_loader = DataLoader(
            train_dataset,
            batch_size=batch_size,
            shuffle=True,
            num_workers=num_workers
        )
        
        # 验证集和测试集使用较小的 batch_size
        val_batch_size = min(batch_size, len(val_dataset))
        test_batch_size = min(batch_size, len(test_dataset))
        
        val_loader = DataLoader(
            val_dataset,
            batch_size=val_batch_size,
            shuffle=False,
            num_workers=num_workers
        )
        test_loader = DataLoader(
            test_dataset,
            batch_size=test_batch_size,
            shuffle=False,
            num_workers=num_workers
        )

        logger.info(f"数据加载完成")
        logger.info(f"  训练集: {len(train_dataset)} 样本")
        logger.info(f"  验证集: {len(val_dataset)} 样本")
        logger.info(f"  测试集: {len(test_dataset)} 样本")

        return train_loader, val_loader, test_loader
