import torch
import torch.nn as nn
import torch.nn.functional as F

class EEGEncoder(nn.Module):
    def __init__(
        self,
        window_length: int,
        step_length: int,
        fs: int = 250,
        max_freq: int = 50,
        merge_threshold: float = 0.9,
        merge_enabled: bool = False,
        d_model: int = None,
        n_head: int = 8,
        rhythm_mode: str = "conv",
        n_rhythm_filters: int = 16,
        # 新增时域特征相关参数
        time_feature_enabled: bool = False,  # 是否开启时域特征提取
        time_conv_channels: list = None,     # 时域卷积通道数
        time_conv_kernels: list = None,      # 时域卷积核大小
        time_conv_paddings: list = None       # 时域池化核大小
    ):
        super(EEGEncoder, self).__init__()
        self.window_length = window_length
        self.step_length = step_length
        self.fs = fs
        self.max_freq = max_freq
        self.merge_threshold = merge_threshold
        self.merge_enabled = merge_enabled
        self.d_model = d_model
        self.n_head = n_head
        self.rhythm_mode = rhythm_mode
        self.n_rhythm_filters = n_rhythm_filters
        # 时域特征参数初始化
        self.time_feature_enabled = time_feature_enabled
        
        # 校验rhythm_mode的合法性
        assert self.rhythm_mode in ["agg", "conv"], "rhythm_mode must be 'agg' or 'conv'"
        # 提前校验n_head为正整数
        assert isinstance(n_head, int) and n_head > 0, "n_head must be a positive integer"

        # EEG节律频段
        self.rhythms = {
            'delta': (1, 4),
            'theta': (4, 8),
            'alpha': (8, 13),
            'beta': (13, 30),
            'gamma': (30, 50)
        }
        self.n_rhythms = len(self.rhythms)

        # 1. 确定原始节律特征维度
        self.raw_rhythm_dim = self.n_rhythms if self.rhythm_mode == "agg" else self.n_rhythm_filters
        # 2. 初始化时域卷积层（如果开启）
        self.time_feat_dim = 0  # 时域特征维度，后续会赋值
        if self.time_feature_enabled:
            # ========== 适配图片中的Temporal Encoder架构参数 ==========
            # 输出通道：对应图片的Output channels {8,8,8}
            self.time_conv_channels = time_conv_channels or [1, 8, 8]
            # 卷积核：对应图片的Kernel size {15,3,3}
            self.time_conv_kernels = time_conv_kernels or [15, 3, 3]
            # 填充：对应图片的Padding {7,1,1}
            self.time_conv_paddings = time_conv_paddings or [7, 1, 1]
            # ===========================================================
            assert len(self.time_conv_channels) == len(self.time_conv_kernels) == len(self.time_conv_paddings), \
                "时域卷积的通道、核、填充数量必须一致"
            
            # 构建时域卷积层（保留批归一化）
            self.time_conv_layers = nn.Sequential()
            in_channels = 1  # 对应图片的Input channels第一个元素{1}
            input_length = self.window_length  # 初始输入长度
            for i, (out_ch, kernel, padding) in enumerate(zip(
                self.time_conv_channels, self.time_conv_kernels, self.time_conv_paddings
            )):
                # 步幅：对应图片的Stride {8,1,1}（第一层为8，其余为1）
                stride = 8 if i == 0 else 1
                # 添加卷积层（使用图片指定的padding，不再自动计算）
                self.time_conv_layers.add_module(
                    f"time_conv_{i}", 
                    nn.Conv1d(in_channels, out_ch, kernel, stride=stride, padding=padding)
                )
                self.time_conv_layers.add_module(f"time_bn_{i}", nn.BatchNorm1d(out_ch))  # 保留批归一化
                self.time_conv_layers.add_module(f"time_relu_{i}", nn.ReLU())
                # 更新输入通道（对应图片的Input channels后续元素{8,8}）
                in_channels = out_ch
                # 跟踪维度变化（仅调试用）
                input_length = (input_length + 2 * padding - kernel) // stride + 1
            self.time_feat_dim = self.time_conv_channels[-1]  # 最终时域特征维度为8
        
        # 3. 计算拼接后的总原始特征维度
        self.total_raw_dim = self.raw_rhythm_dim + self.time_feat_dim
        # 4. 计算d_model（基于总原始维度，保证能被n_head整除）
        if d_model is None:
            self.d_model = self._get_divisible_dim(self.total_raw_dim)
        else:
            assert d_model % self.n_head == 0, f"d_model ({d_model}) must be divisible by n_head ({n_head})"
            self.d_model = d_model
        
        # 节律提取层（空频特征）
        if self.rhythm_mode == "conv":
            self.rhythm_conv = nn.Conv1d(1, self.n_rhythm_filters, 10, 1, padding=1)
            self.relu = nn.ReLU()

        # 核心投影层：将拼接后的总原始特征维度映射到d_model
        self.feat_proj = nn.Linear(self.total_raw_dim, self.d_model)
        # 多头注意力层
        self.multihead_attn = nn.MultiheadAttention(self.d_model, self.n_head, batch_first=True)
        # 位置编码函数
        self.pos_encoding = self._get_pos_encoding

    def _get_divisible_dim(self, raw_dim: int) -> int:
        """计算大于等于raw_dim的最小的能被n_head整除的数"""
        if raw_dim % self.n_head == 0:
            return raw_dim
        else:
            return ((raw_dim // self.n_head) + 1) * self.n_head

    def _get_same_padding(self, kernel_size: int, stride: int) -> int:
        """
        计算实现same padding所需的整数padding值（适用于1D层）
        公式：padding = ((stride - 1) * input_length + kernel_size - stride) // 2
        简化版（不依赖输入长度，保证维度不缩小）：padding = (kernel_size - 1) // 2
        """
        return (kernel_size - 1) // 2

    def _sliding_window(self, x: torch.Tensor) -> torch.Tensor:
        """
        适配输入形状：(batch, chan, timepoints)
        输出形状：(batch, chan, window_length, n_patches)
        """
        batch, channel, time_points = x.shape
        x_reshaped = x.reshape(batch * channel, 1, time_points)
        patches = x_reshaped.unfold(2, self.window_length, self.step_length)
        patches = patches.squeeze(1).permute(0, 2, 1)
        patches = patches.reshape(batch, channel, self.window_length, -1)
        return patches

    def _fft_process(self, x: torch.Tensor) -> torch.Tensor:
        """FFT处理，提取频域特征"""
        fft_vals = torch.fft.fft(x, dim=2)
        fft_amp = torch.abs(fft_vals) / self.window_length
        fft_amp = fft_amp[:, :, :self.window_length // 2, :]
        freq_axis = torch.fft.fftfreq(self.window_length, 1/self.fs)[:self.window_length // 2].to(x.device)
        freq_mask = (freq_axis >= 0) & (freq_axis <= self.max_freq)
        fft_amp = fft_amp[:, :, freq_mask, :]
        self.freq_axis = freq_axis[freq_mask]
        return fft_amp

    def _extract_time_features(self, x: torch.Tensor) -> torch.Tensor:
        """
        提取时域特征（输入为滑动窗口后的时域数据）
        输入：x - (batch, chan, window_length, n_patches)
        输出：time_features - (batch, chan, time_feat_dim, n_patches)
        """
        batch, channel, window_len, n_patches = x.shape
        # 重塑为(batch*channel*n_patches, 1, window_len)，适配卷积输入格式
        x_reshaped = x.permute(0, 1, 3, 2).reshape(-1, 1, window_len)
        conv_out = self.time_conv_layers(x_reshaped)
        # 全局平均池化，消除时间维度，得到时域特征
        time_feat = torch.mean(conv_out, dim=2, keepdim=True)
        # 重塑回原维度：(batch, chan, n_patches, time_feat_dim)
        time_feat = time_feat.reshape(batch, channel, n_patches, -1)
        # 调整维度为(batch, chan, time_feat_dim, n_patches)
        time_features = time_feat.permute(0, 1, 3, 2)
        return time_features

    def _extract_rhythm_features(self, fft_features: torch.Tensor, patches: torch.Tensor) -> torch.Tensor:
        """
        提取空频特征，并与时域特征拼接（如果开启）
        输入：
            fft_features - (batch, chan, n_freqs, n_patches)（空频特征输入）
            patches - (batch, chan, window_length, n_patches)（时域特征输入）
        输出：merged_features - (batch, chan, d_model, n_patches)
        """
        batch, channel, n_freqs, n_patches = fft_features.shape
        
        # 1. 提取空频特征（rhythm_features）
        if self.rhythm_mode == "agg":
            rhythm_features = []
            for _, (f_low, f_high) in self.rhythms.items():
                rhythm_mask = (self.freq_axis >= f_low) & (self.freq_axis <= f_high)
                rhythm_amp = fft_features[:, :, rhythm_mask, :]
                rhythm_feat = torch.mean(rhythm_amp ** 2, dim=2, keepdim=True)
                rhythm_features.append(rhythm_feat)
            rhythm_features = torch.cat(rhythm_features, dim=2)  # (batch, chan, n_rhythms, n_patches)
        else:
            x_reshaped = fft_features.permute(0, 1, 3, 2).reshape(-1, 1, n_freqs)
            conv_out = self.relu(self.rhythm_conv(x_reshaped))
            rhythm_feat = torch.mean(conv_out, dim=2, keepdim=True)
            rhythm_feat = rhythm_feat.reshape(batch, channel, n_patches, self.n_rhythm_filters)
            rhythm_features = rhythm_feat.permute(0, 1, 3, 2)  # (batch, chan, n_rhythm_filters, n_patches)
        
        # 2. 提取时域特征并拼接（如果开启）
        if self.time_feature_enabled:
            time_features = self._extract_time_features(patches)  # (batch, chan, time_feat_dim, n_patches)
            # 在特征维度（dim=2）拼接空频和时域特征
            merged_raw_features = torch.cat([rhythm_features, time_features], dim=2)  # (batch, chan, total_raw_dim, n_patches)
        else:
            merged_raw_features = rhythm_features  # (batch, chan, raw_rhythm_dim, n_patches)
        
        # 3. 投影到d_model维度（先调整维度适配Linear层）
        merged_raw_features = merged_raw_features.permute(0, 1, 3, 2)  # (batch, chan, n_patches, total_raw_dim)
        merged_features = self.feat_proj(merged_raw_features)  # (batch, chan, n_patches, d_model)
        merged_features = merged_features.permute(0, 1, 3, 2)  # (batch, chan, d_model, n_patches)
        
        return merged_features

    def _spatial_attention(self, x: torch.Tensor) -> torch.Tensor:
        """空间注意力层"""
        batch, channel, n_rhythm_feat, n_patches = x.shape
        x_reshaped = x.permute(0, 3, 1, 2).reshape(batch * n_patches, channel, self.d_model)
        attn_output, _ = self.multihead_attn(x_reshaped, x_reshaped, x_reshaped)
        spatial_feature = torch.sum(attn_output, dim=1)
        spatial_feature = spatial_feature.reshape(batch, n_patches, self.d_model)
        return spatial_feature

    def _cosine_similarity(self, a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
        """余弦相似度计算"""
        return F.cosine_similarity(a, b, dim=-1)

    def _merge_similar_patches(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """合并相似patch并返回：(合并后特征, padding_mask)"""
        if self.window_length != self.step_length:
            padding_mask = torch.zeros(x.shape[0], x.shape[1], dtype=torch.bool, device=x.device)
            return x, padding_mask

        batch, n_patches, d_model = x.shape
        merged_batch = []
        padding_masks = []

        for b in range(batch):
            current_patches = x[b]
            merged = []
            current_group = [current_patches[0]]

            for i in range(1, n_patches):
                sim = self._cosine_similarity(current_group[-1], current_patches[i])
                if sim >= self.merge_threshold:
                    current_group.append(current_patches[i])
                else:
                    merged.append(torch.stack(current_group).mean(dim=0))
                    current_group = [current_patches[i]]
            merged.append(torch.stack(current_group).mean(dim=0))
            merged = torch.stack(merged)

            # 补零到原n_patches长度
            pad_len = n_patches - len(merged)
            padding_mask = torch.cat([torch.zeros(len(merged), dtype=torch.bool, device=x.device), torch.ones(pad_len, dtype=torch.bool, device=x.device)], dim=0)
            merged = F.pad(merged, (0, 0, 0, pad_len))  # (n_patches, d_model)

            merged_batch.append(merged)
            padding_masks.append(padding_mask)

        merged_batch = torch.stack(merged_batch)  # (batch, n_patches, d_model)
        padding_masks = torch.stack(padding_masks)  # (batch, n_patches)
        return merged_batch, padding_masks

    def _get_pos_encoding(self, x: torch.Tensor) -> torch.Tensor:
        """位置编码（处理奇数d_model的情况）"""
        batch, n_patches, d_model = x.shape
        pos = torch.arange(n_patches, dtype=torch.float32, device=x.device).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2, dtype=torch.float32, device=x.device) * (-torch.log(torch.tensor(10000.0)) / d_model))
        pos_enc = torch.zeros((n_patches, d_model), device=x.device)
        pos_enc[:, 0::2] = torch.sin(pos * div_term)
        # 处理d_model为奇数的情况，避免索引越界
        pos_enc[:, 1::2] = torch.cos(pos * div_term) if d_model % 2 == 0 else torch.cos(pos * div_term[:-1])
        pos_enc = pos_enc.unsqueeze(0).repeat(batch, 1, 1)
        return x + pos_enc

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """
        输入：x - (batch, chan, timepoints)
        返回：(编码特征, padding_mask)
            编码特征：(batch, n_patches, d_model)
            padding_mask：(batch, n_patches)，True表示补零位置
        """
        # 1. 滑动窗口分块
        patches = self._sliding_window(x)
        # 2. FFT提取频域特征
        fft_features = self._fft_process(patches)
        # 3. 提取空频+时域特征（拼接后投影）
        merged_features = self._extract_rhythm_features(fft_features, patches)
        # 4. 空间注意力计算
        spatial_attn_features = self._spatial_attention(merged_features)

        # 5. 合并相似patch
        if self.merge_enabled:
            spatial_attn_features, padding_mask = self._merge_similar_patches(spatial_attn_features)
        else:
            padding_mask = torch.zeros(spatial_attn_features.shape[0], spatial_attn_features.shape[1], dtype=torch.bool, device=x.device)

        # 6. 位置编码
        final_features = self.pos_encoding(spatial_attn_features)
        return final_features, padding_mask

import torch
import torch.nn as nn
import torch.nn.functional as F

class EEGSTFEncoder(nn.Module):
    """
    修复分patch维度错误的EEG时空频编码器
    核心修正：先对时间维度分patch，再提取每个patch的时空频特征
    保留：5种节律专属卷积核、空洞卷积、可选分patch、输出形状兼容
    """
    def __init__(
        self,
        window_length: int = 128,
        step_length: int = 64,
        fs: int = 250,
        max_freq: int = 50,
        merge_threshold: float = 0.9,
        merge_enabled: bool = False,
        d_model: int = None,
        n_head: int = 8,
        # 节律卷积核参数（5种EEG节律专属）
        rhythm_conv_kernels: dict = None,
        rhythm_conv_strides: dict = None,
        rhythm_conv_paddings: dict = None,
        # 空洞卷积参数
        dilated_conv_channels: list = None,
        dilated_conv_kernels: list = None,
        dilated_conv_dilations: list = None,
        # 分patch控制
        patch_enabled: bool = True,
    ):
        super(EEGSTFEncoder, self).__init__()
        # 基础参数
        self.window_length = window_length
        self.step_length = step_length
        self.fs = fs
        self.max_freq = max_freq
        self.merge_threshold = merge_threshold
        self.merge_enabled = merge_enabled
        self.patch_enabled = patch_enabled
        
        # 1. EEG节律定义及默认卷积核参数（适配250Hz采样）
        self.rhythms = {
            'delta': (1, 4), 'theta': (4, 8), 'alpha': (8, 13), 
            'beta': (13, 30), 'gamma': (30, 50)
        }
        self.rhythm_names = list(self.rhythms.keys())
        self.n_rhythms = len(self.rhythms)
        
        # 2. 节律卷积核默认参数（核心设计）
        default_kernels = {'delta':32, 'theta':16, 'alpha':8, 'beta':4, 'gamma':2}
        default_strides = {r:1 for r in self.rhythm_names}
        default_paddings = {'delta':15, 'theta':7, 'alpha':3, 'beta':1, 'gamma':0}
        
        self.rhythm_kernels = rhythm_conv_kernels or default_kernels
        self.rhythm_strides = rhythm_conv_strides or default_strides
        self.rhythm_paddings = rhythm_conv_paddings or default_paddings
        
        # 参数校验
        assert set(self.rhythm_kernels.keys()) == set(self.rhythm_names), \
            f"必须为{self.rhythm_names}全部节律配置卷积核大小"
        
        # 3. 5分支节律卷积层（每个分支对应一种节律）
        self.rhythm_conv_branches = nn.ModuleDict()
        for rhythm in self.rhythm_names:
            self.rhythm_conv_branches[rhythm] = nn.Sequential(
                nn.Conv1d(
                    in_channels=1,
                    out_channels=8,  # 每个节律输出8维特征
                    kernel_size=self.rhythm_kernels[rhythm],
                    stride=self.rhythm_strides[rhythm],
                    padding=self.rhythm_paddings[rhythm]
                ),
                nn.BatchNorm1d(8),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1)  # 池化到固定维度
            )
        self.time_feat_dim = self.n_rhythms * 8  # 5*8=40
        
        # 4. 空洞卷积（空间特征提取）
        self.dilated_conv_channels = dilated_conv_channels or [self.time_feat_dim, 32, 16]
        self.dilated_conv_kernels = dilated_conv_kernels or [3, 3, 3]
        self.dilated_conv_dilations = dilated_conv_dilations or [1, 2, 4]
        
        assert len(self.dilated_conv_channels) == len(self.dilated_conv_kernels) == \
               len(self.dilated_conv_dilations), "空洞卷积参数长度必须一致"
        
        self.dilated_conv_layers = nn.Sequential()
        in_ch = self.dilated_conv_channels[0]
        for i, (out_ch, kernel, dilation) in enumerate(zip(
            self.dilated_conv_channels[1:],
            self.dilated_conv_kernels,
            self.dilated_conv_dilations
        )):
            self.dilated_conv_layers.add_module(
                f"dilated_conv_{i}",
                nn.Conv1d(in_ch, out_ch, kernel, dilation=dilation, padding="same")
            )
            self.dilated_conv_layers.add_module(f"dilated_bn_{i}", nn.BatchNorm1d(out_ch))
            self.dilated_conv_layers.add_module(f"dilated_relu_{i}", nn.ReLU())
            in_ch = out_ch
        self.spatial_feat_dim = in_ch  # 空洞卷积输出维度
        
        # 5. 维度适配（兼容原代码）
        self.total_raw_dim = self.spatial_feat_dim
        if d_model is None:
            self.d_model = self._get_divisible_dim(self.total_raw_dim, n_head)
        else:
            assert d_model % n_head == 0, f"d_model ({d_model}) must be divisible by n_head ({n_head})"
            self.d_model = d_model
        
        self.feat_proj = nn.Linear(self.total_raw_dim, self.d_model)
        self.pos_encoding = self._get_pos_encoding

    def _get_divisible_dim(self, raw_dim: int, n_head: int) -> int:
        """计算能被n_head整除的最小维度"""
        if raw_dim % n_head == 0:
            return raw_dim
        else:
            return ((raw_dim // n_head) + 1) * n_head

    def _sliding_window_patch(self, x: torch.Tensor) -> tuple[torch.Tensor, int]:
        """
        对原始EEG的时间维度分patch（修正核心）
        输入：x (batch, chan, timepoints)
        输出：patches (batch, chan, window_length, n_patches), n_patches
        """
        if not self.patch_enabled:
            # 关闭分patch：将整个时间序列作为1个patch
            batch, chan, timepoints = x.shape
            # 补零或截断到window_length
            if timepoints < self.window_length:
                pad_len = self.window_length - timepoints
                x = F.pad(x, (0, pad_len))  # (batch, chan, window_length)
            elif timepoints > self.window_length:
                x = x[..., :self.window_length]
            return x.unsqueeze(-1), 1  # (batch, chan, window_length, 1)
        
        # 开启分patch：滑动窗口切分时间维度
        batch, chan, timepoints = x.shape
        x_reshaped = x.reshape(batch * chan, 1, timepoints)
        # 在时间维度（dim=2）做unfold
        patches = x_reshaped.unfold(2, self.window_length, self.step_length)
        patches = patches.squeeze(1).permute(0, 2, 1)
        patches = patches.reshape(batch, chan, self.window_length, -1)
        n_patches = patches.shape[-1]
        return patches, n_patches

    def _rhythm_time_feat_extraction(self, x: torch.Tensor) -> torch.Tensor:
        """
        对每个patch提取多分支节律时序特征
        输入：x (batch, chan, window_length, n_patches)
        输出：rhythm_feat (batch, chan, time_feat_dim, n_patches)
        """
        batch, chan, win_len, n_patches = x.shape
        # 重塑为(batch*chan*n_patches, 1, window_length)
        x_reshaped = x.permute(0, 1, 3, 2).reshape(-1, 1, win_len)
        
        # 每个节律分支提取特征
        branch_features = []
        for rhythm in self.rhythm_names:
            branch_feat = self.rhythm_conv_branches[rhythm](x_reshaped)  # (batch*chan*n_patches, 8, 1)
            branch_feat = branch_feat.squeeze(-1)  # (batch*chan*n_patches, 8)
            branch_features.append(branch_feat)
        
        # 融合所有节律特征
        rhythm_feat = torch.cat(branch_features, dim=-1)  # (batch*chan*n_patches, 40)
        # 恢复维度：(batch, chan, n_patches, time_feat_dim) → (batch, chan, time_feat_dim, n_patches)
        rhythm_feat = rhythm_feat.reshape(batch, chan, n_patches, self.time_feat_dim)
        rhythm_feat = rhythm_feat.permute(0, 1, 3, 2)
        return rhythm_feat

    def _spatial_dilated_conv(self, x: torch.Tensor) -> torch.Tensor:
        """
        空洞卷积提取空间特征
        输入：x (batch, chan, time_feat_dim, n_patches)
        输出：spatial_feat (batch, n_patches, spatial_feat_dim)
        """
        batch, chan, feat_dim, n_patches = x.shape
        
        # 调整维度：(batch*n_patches, feat_dim, chan) → 适配空洞卷积（空间维度=通道数）
        x_reshaped = x.permute(0, 3, 2, 1).reshape(batch * n_patches, feat_dim, chan)
        spatial_feat = self.dilated_conv_layers(x_reshaped)  # (batch*n_patches, spatial_feat_dim, chan)
        
        # 全局平均池化聚合空间特征
        spatial_feat = torch.mean(spatial_feat, dim=-1)  # (batch*n_patches, spatial_feat_dim)
        # 恢复维度：(batch, n_patches, spatial_feat_dim)
        spatial_feat = spatial_feat.reshape(batch, n_patches, self.spatial_feat_dim)
        return spatial_feat

    def _merge_similar_patches(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """相似patch合并（与原逻辑一致）"""
        batch, n_patches, d_model = x.shape
        merged_batch = []
        padding_masks = []

        for b in range(batch):
            current_patches = x[b]
            merged = []
            current_group = [current_patches[0]]

            for i in range(1, n_patches):
                sim = F.cosine_similarity(current_group[-1], current_patches[i], dim=-1)
                if sim >= self.merge_threshold:
                    current_group.append(current_patches[i])
                else:
                    merged.append(torch.stack(current_group).mean(dim=0))
                    current_group = [current_patches[i]]
            merged.append(torch.stack(current_group).mean(dim=0))
            merged = torch.stack(merged)

            # 补零到原n_patches长度
            pad_len = n_patches - len(merged)
            padding_mask = torch.cat([
                torch.zeros(len(merged), dtype=torch.bool, device=x.device),
                torch.ones(pad_len, dtype=torch.bool, device=x.device)
            ], dim=0)
            merged = F.pad(merged, (0, 0, 0, pad_len))

            merged_batch.append(merged)
            padding_masks.append(padding_mask)

        return torch.stack(merged_batch), torch.stack(padding_masks)

    def _get_pos_encoding(self, x: torch.Tensor) -> torch.Tensor:
        """位置编码（与原逻辑一致）"""
        batch, n_patches, d_model = x.shape
        pos = torch.arange(n_patches, dtype=torch.float32, device=x.device).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2, dtype=torch.float32, device=x.device) * 
                            (-torch.log(torch.tensor(10000.0)) / d_model))
        pos_enc = torch.zeros((n_patches, d_model), device=x.device)
        pos_enc[:, 0::2] = torch.sin(pos * div_term)
        pos_enc[:, 1::2] = torch.cos(pos * div_term) if d_model % 2 == 0 else torch.cos(pos * div_term[:-1])
        pos_enc = pos_enc.unsqueeze(0).repeat(batch, 1, 1)
        return x + pos_enc

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """
        修正后的前向流程（核心）：
        原始数据 → 时间维度分patch → 每个patch提取节律时序特征 → 空洞卷积空间特征 → 投影 → 合并patch → 位置编码
        输入：x (batch, chan, timepoints)
        输出：(batch, n_patches, d_model), (batch, n_patches)
        """
        batch = x.shape[0]
        
        # 1. 对时间维度分patch（修正核心）
        patches, n_patches = self._sliding_window_patch(x)  # (batch, chan, window_length, n_patches)
        
        # 2. 提取每个patch的节律时序特征
        rhythm_feat = self._rhythm_time_feat_extraction(patches)  # (batch, chan, 40, n_patches)
        
        # 3. 空洞卷积提取空间特征
        spatial_feat = self._spatial_dilated_conv(rhythm_feat)  # (batch, n_patches, spatial_feat_dim)
        
        # 4. 特征投影到d_model
        projected_feat = self.feat_proj(spatial_feat)  # (batch, n_patches, d_model)
        
        # 5. 相似patch合并（可选）
        if self.merge_enabled:
            projected_feat, padding_mask = self._merge_similar_patches(projected_feat)
        else:
            padding_mask = torch.zeros(batch, n_patches, dtype=torch.bool, device=x.device)
        
        # 6. 位置编码
        final_feat = self.pos_encoding(projected_feat)
        
        return final_feat, padding_mask

# ------------------- 测试代码（验证修复效果） -------------------
if __name__ == "__main__":
    # 模拟EEG数据（与报错场景一致）
    batch_size = 2
    n_channels = 32
    time_points = 1000
    eeg_data = torch.randn(batch_size, n_channels, time_points)
    print(f"输入数据形状：{eeg_data.shape}")
    print("-" * 60)

    # 测试开启分patch（原报错场景）
    print("测试开启分patch（修复后）：")
    encoder = EEGSTFEncoder(
        window_length=128,
        step_length=64,
        fs=250,
        max_freq=50,
        patch_enabled=True,
        merge_enabled=False
    )
    # 打印节律卷积核参数
    for rhythm in encoder.rhythm_names:
        conv_layer = encoder.rhythm_conv_branches[rhythm][0]
        print(f"{rhythm}节律 → 卷积核：{conv_layer.kernel_size[0]}, Padding：{conv_layer.padding[0]}")
    
    with torch.no_grad():
        features, padding_mask = encoder(eeg_data)
    
    print(f"\n编码特征形状：{features.shape} → (batch, n_patches, d_model)")
    print(f"Padding Mask形状：{padding_mask.shape}")
    print(f"n_patches数量：{features.shape[1]}")
    print(f"d_model值：{encoder.d_model}")
    print("-" * 60)

    # 测试关闭分patch
    print("\n测试关闭分patch：")
    encoder_no_patch = EEGSTFEncoder(
        window_length=128,
        step_length=64,
        fs=250,
        max_freq=50,
        patch_enabled=False,
        merge_enabled=False
    )
    with torch.no_grad():
        features_no_patch, padding_mask_no_patch = encoder_no_patch(eeg_data)
    
    print(f"编码特征形状：{features_no_patch.shape} → n_patches=1")
    print(f"Padding Mask补零数：{padding_mask_no_patch.sum().item()}")

# # ------------------- 测试代码 -------------------
# if __name__ == "__main__":
#     # 1. 设置超参数（模拟EEG数据的常见参数）
#     batch_size = 2  # 批次大小
#     n_channels = 32  # EEG通道数（如32导电极）
#     time_points = 1000  # 时间点数量（250Hz采样的话，就是4秒数据）
#     window_length = 128  # 滑动窗口长度
#     step_length = 64  # 步长
#     fs = 250  # 采样频率
#     max_freq = 50  # 最大分析频率

#     # 2. 创建模拟EEG数据：(batch, chan, timepoints)
#     eeg_data = torch.randn(batch_size, n_channels, time_points)
#     print(f"输入数据形状：{eeg_data.shape}")
#     print("-" * 50)

#     # 3. 测试不同配置的EEGEncoder（适配新的时域卷积参数）
#     test_cases = [
#         ("conv模式，不合并patch，关闭时域特征", {"rhythm_mode": "conv", "merge_enabled": False, "time_feature_enabled": False}),
#         ("agg模式，不合并patch，关闭时域特征（自动计算d_model=8）", {"rhythm_mode": "agg", "merge_enabled": False, "time_feature_enabled": False}),
#         ("agg模式，不合并patch，开启时域特征（总原始维度=5+10=15→d_model=16）", {"rhythm_mode": "agg", "merge_enabled": False, "time_feature_enabled": True}),
#         ("conv模式，合并patch，开启时域特征（步长等于窗口长度）", {"rhythm_mode": "conv", "merge_enabled": True, "step_length": window_length, "time_feature_enabled": True}),
#         ("agg模式，指定d_model=24，开启时域特征", {"rhythm_mode": "agg", "merge_enabled": False, "time_feature_enabled": True, "d_model": 24}),
#     ]

#     for case_name, config in test_cases:
#         print(f"\n测试用例：{case_name}")
#         # 更新步长（如果配置中有）
#         current_step = config.pop("step_length", step_length)
#         # 实例化模型
#         encoder = EEGEncoder(
#             window_length=window_length,
#             step_length=current_step,
#             fs=fs,
#             max_freq=max_freq,** config
#         )
#         # 前向传播
#         with torch.no_grad():  # 测试时禁用梯度计算，节省资源
#             features, padding_mask = encoder(eeg_data)
#         # 打印输出信息
#         print(f"编码特征形状：{features.shape}")  # (batch, n_patches, d_model)
#         print(f"Padding Mask形状：{padding_mask.shape}")  # (batch, n_patches)
#         print(f"Padding Mask中补零位置数量：{padding_mask.sum().item()}")
#         print(f"d_model值：{encoder.d_model}")
#         print(f"总原始特征维度：{encoder.total_raw_dim} → 投影后维度：{encoder.d_model}")
#         print(f"时域特征维度：{encoder.time_feat_dim}（2*节律维度{encoder.n_rhythms}）")
#         print("-" * 50)