import os
import numpy as np
import re
from scipy.signal import butter, filtfilt
from scipy.signal import resample
from scipy.io import loadmat
import torch
import mne
from torch.utils.data import TensorDataset, DataLoader

# 数据预处理函数（保持不变）
def butter_lowpass(cutoff, fs, order=4):
    nyquist = 0.5 * fs
    normal_cutoff = cutoff / nyquist
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return b, a

def lowpass_filter(data, cutoff, fs, order=4):
    b, a = butter_lowpass(cutoff, fs, order)
    return filtfilt(b, a, data, axis=0)

# 通用EEG数据加载类（支持单被试和跨被试，新增归一化逻辑）
class EEGDataLoader:
    def __init__(self, config):
        # 原始数据配置
        self.sample_rate = config['data']['sample_rate']
        self.cutoff_frequency = config['data']['cutoff_frequency']
        self.data_path = config['data']['data_path']
        self.target_length = config['data']['target_length']
        self.channels = config['data']['channels']
        self.augment_data = config['data'].get('augment_data', False)  # 可选参数
        
        # 归一化配置（新增核心配置）
        self.norm_config = config.get('norm', {})
        self.norm_type = self.norm_config.get('norm_type', 'none')  # none/z_score/sample_z_score/min_max
        self.norm_axis = self.norm_config.get('norm_axis', (0, 2))  # z_score：(样本数, 时间步)，对应每个通道计算统计量
        self.min_max_range = self.norm_config.get('min_max_range', (-1, 1))  # min-max范围
        self.eps = self.norm_config.get('eps', 1e-8)  # 防止除以0
        
        # 存储归一化统计量（训练集的mean/std/min/max，避免测试集泄露）
        self.norm_stats = None

        # 存储所有被试的数据：key=被试ID（如A01），value=(data, labels)
        self.subject_data = {}
        # 所有被试ID列表
        self.all_subjects = []

    def _extract_subject_id(self, filename):
        """从文件名中提取被试ID（如A01T.mat -> A01）"""
        match = re.match(r'(A\d{2})[TE]\.mat', filename)
        if match:
            return match.group(1)
        return None

    # def _load_single_subject_data(self, subject_id):
    #     """【内部方法】加载单个被试的所有数据（T.mat和E.mat），返回数据和标签"""
    #     subject_all_data = []
    #     subject_all_labels = []

    #     # 遍历文件，加载该被试的T.mat和E.mat
    #     for filename in os.listdir(self.data_path):
    #         if filename.startswith(subject_id) and (filename.endswith('T.mat') or filename.endswith('E.mat')):
    #             mat_path = os.path.join(self.data_path, filename)
    #             mat_data = loadmat(mat_path)

    #             # 处理mat文件中的数据（与原逻辑一致）
    #             struct_count = mat_data['data'].shape[1]
    #             for i in range(struct_count):
    #                 trials = mat_data['data'][0, i]['trial'][0, 0].astype(int)
    #                 n_trials = len(trials)
    #                 if n_trials == 0:
    #                     continue
    #                 # 截取指定通道
    #                 X = mat_data['data'][0, i]['X'][0, 0][:, :self.channels]
    #                 Y = mat_data['data'][0, i]['y'][0, 0].ravel()

    #                 # 处理每个试次
    #                 for j in range(n_trials - 1):
    #                     start_idx = int(trials[j].item())
    #                     end_idx = int(trials[j + 1].item())
    #                     trial_data = X[start_idx:end_idx, :]
    #                     # 低通滤波
    #                     trial_data = lowpass_filter(trial_data, self.cutoff_frequency, self.sample_rate)
    #                     # 重采样到目标长度
    #                     trial_resampled_data = resample(trial_data, self.target_length, axis=0)
    #                     subject_all_data.append(trial_resampled_data)
    #                     subject_all_labels.append(Y[j])

    #                 # 处理最后一个试次
    #                 trial_data = X[int(trials[-1].item()):, :]
    #                 trial_data = lowpass_filter(trial_data, self.cutoff_frequency, self.sample_rate)
    #                 trial_resampled_data = resample(trial_data, self.target_length, axis=0)
    #                 subject_all_data.append(trial_resampled_data)
    #                 subject_all_labels.append(Y[-1])

    #     # 转换为numpy数组并预处理
    #     subject_all_data = np.array(subject_all_data)
    #     subject_all_labels = np.array(subject_all_labels)

    #     # 标签归一化（确保从0开始）
    #     if len(subject_all_labels) > 0 and subject_all_labels.min() > 0:
    #         subject_all_labels = subject_all_labels - 1

    #     # 转置：(样本数, target_length, channels) -> (样本数, channels, target_length)
    #     subject_all_data = np.transpose(subject_all_data, (0, 2, 1))

    #     print(f"Loaded subject {subject_id}: {len(subject_all_data)} samples, shape {subject_all_data.shape}")
    #     return subject_all_data, subject_all_labels
    def _butter_lowpass_filter(self, data, cutoff, fs, order=4):
        """低通滤波（复用你原有的滤波逻辑，改为零相位滤波）"""
        nyq = 0.5 * fs
        normal_cutoff = cutoff / nyq
        b, a = butter(order, normal_cutoff, btype='low', analog=False)
        # 对时间维度（axis=2）滤波，保持维度：(n_trials, n_channels, n_times)
        filtered_data = filtfilt(b, a, data, axis=2)
        return filtered_data

    def _load_single_subject_data(self, subject_id):
        """
        【内部方法】加载单个被试的所有数据（合并训练集T.gdf和测试集E.gdf）
        :param subject_id: 被试ID，支持字符串（如"A01"）或整数（如1）
        :return: subject_all_data (np.array)、subject_all_labels (np.array)
        """
        # 初始化存储列表（合并训练+测试集）
        subject_all_data = []
        subject_all_labels = []

        # 处理被试ID格式：统一为"A0X"（如1→"A01"，"A01"→"A01"）
        if isinstance(subject_id, int):
            subject_str = f"A0{subject_id}"
            subject_num = str(subject_id)
        else:
            subject_str = subject_id
            subject_num = subject_id.replace("A0", "")  # 提取数字部分（如"A01"→"1"）

        # BCI IV 2a核心配置（整合自MNE脚本）
        stimcodes = ('769', '770', '771', '772')  # 四类MI事件码
        channels_to_remove = ['EOG-left', 'EOG-central', 'EOG-right']  # 移除EOG伪迹通道
        win_sel = (0, 3)  # 截取提示后0-3秒的运动想象期（可根据需要改为配置项）
        true_label_path = os.path.join(self.data_path, "Data sets 2a_true_labels")  # 测试集标签路径

        # ====================== 1. 加载训练集（T.gdf）======================
        train_file = os.path.join(self.data_path, f"{subject_str}T.gdf")
        if os.path.exists(train_file):
            # 读取GDF文件（MNE核心逻辑）
            raw_data = mne.io.read_raw_gdf(train_file, preload=True, verbose=False)
            # 提取事件标注（对应TRIG通道）
            events, event_ids = mne.events_from_annotations(raw_data, verbose=False)
            # 筛选目标事件（仅保留769-772的四类MI）
            stims = [v for k, v in event_ids.items() if k in stimcodes]
            # 截取时间窗口的Epochs（按事件切分数据）
            epochs = mne.Epochs(
                raw_data, events, event_id=stims,
                tmin=win_sel[0], tmax=win_sel[1],
                event_repeated='drop', baseline=None, preload=True, verbose=False
            )
            # 移除EOG通道，保留指定数量的EEG通道
            epochs = epochs.drop_channels(channels_to_remove)
            if epochs.info['nchan'] > self.channels:
                epochs = epochs.pick_channels(epochs.ch_names[:self.channels])  # 截取前self.channels个通道

            # 获取训练集数据和标签
            train_data = epochs.get_data() * 1e6  # 单位转换：V→μV
            train_labels = epochs.events[:, -1] - min(epochs.events[:, -1])  # 标签归一化到0开始

            # 处理训练集数据（适配你的配置项）
            for trial in train_data:
                # 重采样到目标长度（时间维度，axis=1）
                trial_resampled = resample(trial, self.target_length, axis=1)
                subject_all_data.append(trial_resampled)
            subject_all_labels.extend(train_labels.tolist())

        # ====================== 2. 加载测试集（E.gdf）======================
        test_file = os.path.join(self.data_path, f"{subject_str}E.gdf")
        if os.path.exists(test_file):
            # 读取测试集GDF文件
            raw_data_test = mne.io.read_raw_gdf(test_file, preload=True, verbose=False)
            # 读取测试集真实标签（mat文件）
            label_file = os.path.join(true_label_path, f"{subject_str}E.mat")
            if os.path.exists(label_file):
                labels_mat = loadmat(label_file)
                test_labels_all = labels_mat['classlabel'][:, 0]  # 真实标签

                # 处理测试集事件（783是测试集trial结束事件码）
                events_test, event_ids_test = mne.events_from_annotations(raw_data_test, verbose=False)
                index_type = [v for k, v in event_ids_test.items() if k == '783']
                if index_type:
                    events_index = np.where(events_test[:, 2] == index_type[0])[0]
                    events_test = events_test[events_index, :]
                    events_test[:, 2] = test_labels_all  # 替换为真实标签

                    # 截取测试集Epochs
                    stims_test = list(np.unique(test_labels_all))
                    epochs_test = mne.Epochs(
                        raw_data_test, events_test, event_id=stims_test,
                        tmin=win_sel[0], tmax=win_sel[1],
                        event_repeated='drop', baseline=None, preload=True, verbose=False
                    )
                    # 移除EOG通道，保留指定数量的EEG通道
                    epochs_test = epochs_test.drop_channels(channels_to_remove)
                    if epochs_test.info['nchan'] > self.channels:
                        epochs_test = epochs_test.pick_channels(epochs_test.ch_names[:self.channels])

                    # 获取测试集数据和标签
                    test_data = epochs_test.get_data() * 1e6  # 单位转换：V→μV
                    test_labels = epochs_test.events[:, -1] - min(epochs_test.events[:, -1])  # 标签归一化到0开始

                    # 处理测试集数据（适配你的配置项）
                    for trial in test_data:
                        # 重采样到目标长度（时间维度，axis=1）
                        trial_resampled = resample(trial, self.target_length, axis=1)
                        subject_all_data.append(trial_resampled)
                    subject_all_labels.extend(test_labels.tolist())

        # ====================== 3. 数据后处理（适配你的原有逻辑）======================
        # 转换为numpy数组
        subject_all_data = np.array(subject_all_data)  # 形状：(n_samples, n_channels, target_length)
        subject_all_labels = np.array(subject_all_labels)  # 形状：(n_samples,)

        # 低通滤波（应用你的cutoff_frequency配置）
        subject_all_data = self._butter_lowpass_filter(subject_all_data, self.cutoff_frequency, self.sample_rate)

        # （可选）若你需要调整维度顺序，可取消注释（根据你的模型输入需求）
        # subject_all_data = np.transpose(subject_all_data, (0, 2, 1))  # (n_samples, target_length, n_channels)

        print(f"Loaded subject {subject_str}: {len(subject_all_data)} samples, shape {subject_all_data.shape}")
        return subject_all_data, subject_all_labels

    # -------------------------- 新增：归一化核心方法 --------------------------
    def _compute_norm_stats(self, train_data):
        """【内部方法】计算训练集的归一化统计量（mean/std/min/max），存储到self.norm_stats"""
        if self.norm_type == 'z_score':
            # 计算指定轴的均值和标准差（如(0,2)：样本数+时间步，每个通道一个mean/std）
            mean = np.mean(train_data, axis=self.norm_axis, keepdims=True)
            std = np.std(train_data, axis=self.norm_axis, keepdims=True)
            self.norm_stats = {'mean': mean, 'std': std}
        elif self.norm_type == 'min_max':
            # 计算指定轴的最小值和最大值
            min_val = np.min(train_data, axis=self.norm_axis, keepdims=True)
            max_val = np.max(train_data, axis=self.norm_axis, keepdims=True)
            self.norm_stats = {'min': min_val, 'max': max_val}
        else:
            # sample_z_score/none不需要训练集统计量
            self.norm_stats = None

    def _apply_normalization(self, data, is_train=False):
        """【内部方法】应用归一化，is_train=True时计算统计量（仅训练集）"""
        if self.norm_type == 'none':
            return data  # 不做归一化
        elif self.norm_type == 'z_score':
            if is_train:
                self._compute_norm_stats(data)
            # 用训练集的mean/std归一化
            mean = self.norm_stats['mean']
            std = self.norm_stats['std']
            data = (data - mean) / (std + self.eps)  # eps防止除以0
        elif self.norm_type == 'sample_z_score':
            # 样本级归一化：每个样本自己的mean/std（轴：(1,2)即通道+时间步，或根据需求调整）
            # 轴说明：data.shape=(n_samples, channels, seqlen)，(1,2)表示每个样本的所有通道和时间步计算统计量
            sample_axis = self.norm_config.get('sample_axis', (1, 2))
            mean = np.mean(data, axis=sample_axis, keepdims=True)
            std = np.std(data, axis=sample_axis, keepdims=True)
            data = (data - mean) / (std + self.eps)
        elif self.norm_type == 'min_max':
            if is_train:
                self._compute_norm_stats(data)
            # 用训练集的min/max缩放到指定范围
            min_val = self.norm_stats['min']
            max_val = self.norm_stats['max']
            # 先缩放到[0,1]，再缩放到[min_max_range[0], min_max_range[1]]
            data = (data - min_val) / (max_val - min_val + self.eps)
            data = data * (self.min_max_range[1] - self.min_max_range[0]) + self.min_max_range[0]
        return data

    # -------------------------- 原有方法：加载数据（无修改） --------------------------
    def load_all_subjects(self):
        """【跨被试模式】加载所有被试的数据到self.subject_data"""
        print(f"\nLoading all subjects from {self.data_path}...")
        # 获取所有唯一的被试ID
        subject_ids = set()
        for filename in os.listdir(self.data_path):
            sub_id = self._extract_subject_id(filename)
            if sub_id:
                subject_ids.add(sub_id)
        # 排序（如A01, A02, ..., A09）
        self.all_subjects = sorted(list(subject_ids))

        # 加载每个被试的数据
        for sub_id in self.all_subjects:
            self.subject_data[sub_id] = self._load_single_subject_data(sub_id)

        print(f"Loaded all {len(self.all_subjects)} subjects: {self.all_subjects}")

    def load_single_subject(self, subject_id):
        """【单被试模式】加载指定单个被试的数据到self.subject_data"""
        print(f"\nLoading single subject {subject_id} from {self.data_path}...")
        # 验证被试ID是否存在
        has_subject = any(filename.startswith(subject_id) for filename in os.listdir(self.data_path))
        if not has_subject:
            raise ValueError(f"Subject {subject_id} not found in data path {self.data_path}!")
        
        # 加载该被试数据并存储
        self.subject_data[subject_id] = self._load_single_subject_data(subject_id)
        self.all_subjects = [subject_id]  # 更新被试列表为仅当前被试
        return self.subject_data[subject_id]

    # -------------------------- 修改：划分数据时加入归一化 --------------------------
    def leave_one_out_split(self, test_subject, val_ratio=0.2, seed=42):
        """【跨被试模式】留一法划分数据：指定被试为测试集，其余为训练集，训练集划分验证集"""
        assert test_subject in self.all_subjects, f"Test subject {test_subject} not found!"
        np.random.seed(seed)

        # 1. 测试集：指定被试的数据
        test_data, test_labels = self.subject_data[test_subject]

        # 2. 训练集：所有其他被试的数据合并
        train_data_list = []
        train_labels_list = []
        for sub_id in self.all_subjects:
            if sub_id != test_subject:
                data, labels = self.subject_data[sub_id]
                train_data_list.append(data)
                train_labels_list.append(labels)
        train_data = np.concatenate(train_data_list, axis=0)
        train_labels = np.concatenate(train_labels_list, axis=0)

        print(f"\nLeave-one-out split (test subject: {test_subject}):")
        print(f"Train set: {len(train_data)} samples, shape {train_data.shape}")
        print(f"Test set: {len(test_data)} samples, shape {test_data.shape}")

        # 3. 从训练集中划分验证集
        train_size = len(train_data)
        val_size = int(val_ratio * train_size)
        # 随机打乱训练集索引
        indices = np.arange(train_size)
        np.random.shuffle(indices)
        # 划分验证集和训练集
        val_indices = indices[:val_size]
        train_indices = indices[val_size:]

        # 提取划分后的数据
        train_data_split = train_data[train_indices]
        val_data_split = train_data[val_indices]
        train_labels_split = train_labels[train_indices]
        val_labels_split = train_labels[val_indices]

        # -------------------------- 新增：应用归一化 --------------------------
        # 训练集：is_train=True（计算统计量）
        train_data_norm = self._apply_normalization(train_data_split, is_train=True)
        # 验证集/测试集：is_train=False（复用训练集统计量）
        val_data_norm = self._apply_normalization(val_data_split, is_train=False)
        test_data_norm = self._apply_normalization(test_data, is_train=False)

        # 构建PyTorch数据集（使用归一化后的数据）
        train_dataset = TensorDataset(
            torch.tensor(train_data_norm, dtype=torch.float32),
            torch.tensor(train_labels_split, dtype=torch.long)
        )
        val_dataset = TensorDataset(
            torch.tensor(val_data_norm, dtype=torch.float32),
            torch.tensor(val_labels_split, dtype=torch.long)
        )
        test_dataset = TensorDataset(
            torch.tensor(test_data_norm, dtype=torch.float32),
            torch.tensor(test_labels, dtype=torch.long)
        )

        print(f"Train set (after split): {len(train_dataset)} samples")
        print(f"Validation set: {len(val_dataset)} samples")
        print(f"Test set: {len(test_dataset)} samples")

        return train_dataset, val_dataset, test_dataset

    def train_test_split_single_subject(self, subject_id, train_ratio=0.7, val_ratio=0.15, seed=42):
        """【单被试模式】在单个被试内部按比例划分训练、验证、测试集"""
        assert subject_id in self.subject_data, f"Subject {subject_id} not loaded! Call load_single_subject first."
        assert train_ratio + val_ratio < 1.0, "train_ratio + val_ratio must be less than 1.0 (remaining is test_ratio)"
        np.random.seed(seed)

        # 获取该被试的所有数据和标签
        data, labels = self.subject_data[subject_id]
        total_size = len(data)

        # 计算各集大小
        train_size = int(train_ratio * total_size)
        val_size = int(val_ratio * total_size)
        test_size = total_size - train_size - val_size

        # 随机打乱索引
        indices = np.arange(total_size)
        np.random.shuffle(indices)

        # 划分索引
        train_indices = indices[:train_size]
        val_indices = indices[train_size:train_size+val_size]
        test_indices = indices[train_size+val_size:]

        # 提取划分后的数据
        train_data_split = data[train_indices]
        val_data_split = data[val_indices]
        test_data_split = data[test_indices]
        train_labels_split = labels[train_indices]
        val_labels_split = labels[val_indices]
        test_labels_split = labels[test_indices]

        # -------------------------- 新增：应用归一化 --------------------------
        # 训练集：is_train=True（计算统计量）
        train_data_norm = self._apply_normalization(train_data_split, is_train=True)
        # 验证集/测试集：is_train=False（复用训练集统计量）
        val_data_norm = self._apply_normalization(val_data_split, is_train=False)
        test_data_norm = self._apply_normalization(test_data_split, is_train=False)

        # 构建PyTorch数据集（使用归一化后的数据）
        train_dataset = TensorDataset(
            torch.tensor(train_data_norm, dtype=torch.float32),
            torch.tensor(train_labels_split, dtype=torch.long)
        )
        val_dataset = TensorDataset(
            torch.tensor(val_data_norm, dtype=torch.float32),
            torch.tensor(val_labels_split, dtype=torch.long)
        )
        test_dataset = TensorDataset(
            torch.tensor(test_data_norm, dtype=torch.float32),
            torch.tensor(test_labels_split, dtype=torch.long)
        )

        print(f"\nSingle subject split (subject: {subject_id}):")
        print(f"Train set: {len(train_dataset)} samples ({train_ratio*100:.1f}%)")
        print(f"Validation set: {len(val_dataset)} samples ({val_ratio*100:.1f}%)")
        print(f"Test set: {len(test_dataset)} samples ({(1-train_ratio-val_ratio)*100:.1f}%)")

        return train_dataset, val_dataset, test_dataset

    def get_data_loaders(self, train_dataset, val_dataset, test_dataset, batch_size=32):
        """获取DataLoader（返回的批次数据shape：(batch_size, channels, target_length)）"""
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
        test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)
        return train_loader, val_loader, test_loader

# -------------------------- 测试代码（更新配置，加入归一化） --------------------------
if __name__ == "__main__":
    # 配置示例（新增归一化配置，根据需求调整）
    config = {
        'data': {
            'sample_rate': 250,  # 采样率
            'cutoff_frequency': 50,  # 低通滤波截止频率
            'data_path': '/home/zengkai/model_compare/data/BNCI2014_001',  # 你的数据路径
            'target_length': 1000,  # 重采样后的时间步长度
            'channels': 22,  # 保留的EEG通道数
            'augment_data': False
        },
        # 新增：归一化配置（核心）
        'norm': {
            'norm_type': 'z_score',  # 可选：none/z_score/sample_z_score/min_max
            'norm_axis': (0, 2),  # z_score：(样本数, 时间步)，每个通道单独计算mean/std
            'sample_axis': (1, 2),  # sample_z_score：每个样本的(通道, 时间步)计算mean/std
            'min_max_range': (-1, 1),  # min_max归一化的目标范围
            'eps': 1e-8  # 防止除以0
        }
    }

    # ==================== 测试1：单被试模式 ====================
    print("="*50 + " 单被试模式 " + "="*50)
    loader = EEGDataLoader(config)
    # 加载单个被试（如A01）
    loader.load_single_subject("A01")
    # 单被试内部划分数据集（自动应用归一化）
    train_dataset, val_dataset, test_dataset = loader.train_test_split_single_subject("A01", train_ratio=0.7, val_ratio=0.15)
    # 获取DataLoader
    train_loader, val_loader, test_loader = loader.get_data_loaders(train_dataset, val_dataset, test_dataset, batch_size=32)
    # 验证批次数据形状
    for batch_data, batch_labels in train_loader:
        print(f"\nBatch data shape (single subject): {batch_data.shape}")  # 输出：(32, channels, target_length)
        print(f"Batch labels shape (single subject): {batch_labels.shape}")
        # 验证归一化效果：查看数据的均值和标准差（z_score后应接近0和1）
        print(f"Batch data mean: {batch_data.mean().item():.4f}, std: {batch_data.std().item():.4f}")
        break

    # ==================== 测试2：跨被试模式 ====================
    print("\n" + "="*50 + " 跨被试模式 " + "="*50)
    loader = EEGDataLoader(config)
    # 加载所有被试数据
    loader.load_all_subjects()
    # 遍历每个被试作为测试集，进行跨被试实验
    for test_sub in loader.all_subjects[:1]:  # 测试时只取第一个被试，可注释掉[:1]遍历所有
        # 留一法划分数据（自动应用归一化）
        train_dataset, val_dataset, test_dataset = loader.leave_one_out_split(test_sub, val_ratio=0)
        # 获取DataLoader
        train_loader, val_loader, test_loader = loader.get_data_loaders(train_dataset, val_dataset, test_dataset, batch_size=32)
        # 验证批次数据形状
        for batch_data, batch_labels in train_loader:
            print(f"\nBatch data shape (cross subject): {batch_data.shape}")
            print(f"Batch labels shape (cross subject): {batch_labels.shape}")
            print(f"Batch data mean: {batch_data.mean().item():.4f}, std: {batch_data.std().item():.4f}")
            break