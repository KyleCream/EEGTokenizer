import torch
import torch.nn as nn
import torch.nn.functional as F


class EEGSTFEncoder(nn.Module):
    """
    EEG 时空频编码器（重构自 Space_freq/encode.py）
    
    输入: (batch, channels, timepoints)
    输出: (batch, n_patches, d_model) + padding_mask
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
        rhythm_conv_kernels: dict = None,
        rhythm_conv_strides: dict = None,
        rhythm_conv_paddings: dict = None,
        dilated_conv_channels: list = None,
        dilated_conv_kernels: list = None,
        dilated_conv_dilations: list = None,
        patch_enabled: bool = True,
    ):
        super().__init__()
        self.window_length = window_length
        self.step_length = step_length
        self.fs = fs
        self.max_freq = max_freq
        self.merge_threshold = merge_threshold
        self.merge_enabled = merge_enabled
        self.patch_enabled = patch_enabled
        
        # EEG 节律定义
        self.rhythms = {
            'delta': (1, 4), 'theta': (4, 8), 'alpha': (8, 13), 
            'beta': (13, 30), 'gamma': (30, 50)
        }
        self.rhythm_names = list(self.rhythms.keys())
        self.n_rhythms = len(self.rhythms)
        
        # 节律卷积核默认参数
        default_kernels = {'delta':32, 'theta':16, 'alpha':8, 'beta':4, 'gamma':2}
        default_strides = {r:1 for r in self.rhythm_names}
        default_paddings = {'delta':15, 'theta':7, 'alpha':3, 'beta':1, 'gamma':0}
        
        self.rhythm_kernels = rhythm_conv_kernels or default_kernels
        self.rhythm_strides = rhythm_conv_strides or default_strides
        self.rhythm_paddings = rhythm_conv_paddings or default_paddings
        
        # 5分支节律卷积层
        self.rhythm_conv_branches = nn.ModuleDict()
        for rhythm in self.rhythm_names:
            self.rhythm_conv_branches[rhythm] = nn.Sequential(
                nn.Conv1d(
                    in_channels=1,
                    out_channels=8,
                    kernel_size=self.rhythm_kernels[rhythm],
                    stride=self.rhythm_strides[rhythm],
                    padding=self.rhythm_paddings[rhythm]
                ),
                nn.BatchNorm1d(8),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1)
            )
        self.time_feat_dim = self.n_rhythms * 8
        
        # 空洞卷积（空间特征提取）
        self.dilated_conv_channels = dilated_conv_channels or [self.time_feat_dim, 32, 16]
        self.dilated_conv_kernels = dilated_conv_kernels or [3, 3, 3]
        self.dilated_conv_dilations = dilated_conv_dilations or [1, 2, 4]
        
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
        self.spatial_feat_dim = in_ch
        
        # 维度适配
        self.total_raw_dim = self.spatial_feat_dim
        if d_model is None:
            self.d_model = self._get_divisible_dim(self.total_raw_dim, n_head)
        else:
            assert d_model % n_head == 0, f"d_model must be divisible by n_head"
            self.d_model = d_model
        
        self.feat_proj = nn.Linear(self.total_raw_dim, self.d_model)
        self.pos_encoding = self._get_pos_encoding
    
    def _get_divisible_dim(self, raw_dim: int, n_head: int) -> int:
        if raw_dim % n_head == 0:
            return raw_dim
        else:
            return ((raw_dim // n_head) + 1) * n_head
    
    def _sliding_window_patch(self, x: torch.Tensor) -> tuple[torch.Tensor, int]:
        if not self.patch_enabled:
            batch, chan, timepoints = x.shape
            if timepoints < self.window_length:
                pad_len = self.window_length - timepoints
                x = F.pad(x, (0, pad_len))
            elif timepoints > self.window_length:
                x = x[..., :self.window_length]
            return x.unsqueeze(-1), 1
        
        batch, chan, timepoints = x.shape
        x_reshaped = x.reshape(batch * chan, 1, timepoints)
        patches = x_reshaped.unfold(2, self.window_length, self.step_length)
        patches = patches.squeeze(1).permute(0, 2, 1)
        patches = patches.reshape(batch, chan, self.window_length, -1)
        n_patches = patches.shape[-1]
        return patches, n_patches
    
    def _rhythm_time_feat_extraction(self, x: torch.Tensor) -> torch.Tensor:
        batch, chan, win_len, n_patches = x.shape
        x_reshaped = x.permute(0, 1, 3, 2).reshape(-1, 1, win_len)
        
        branch_features = []
        for rhythm in self.rhythm_names:
            branch_feat = self.rhythm_conv_branches[rhythm](x_reshaped)
            branch_feat = branch_feat.squeeze(-1)
            branch_features.append(branch_feat)
        
        rhythm_feat = torch.cat(branch_features, dim=-1)
        rhythm_feat = rhythm_feat.reshape(batch, chan, n_patches, self.time_feat_dim)
        rhythm_feat = rhythm_feat.permute(0, 1, 3, 2)
        return rhythm_feat
    
    def _spatial_dilated_conv(self, x: torch.Tensor) -> torch.Tensor:
        batch, chan, feat_dim, n_patches = x.shape
        x_reshaped = x.permute(0, 3, 2, 1).reshape(batch * n_patches, feat_dim, chan)
        spatial_feat = self.dilated_conv_layers(x_reshaped)
        spatial_feat = torch.mean(spatial_feat, dim=-1)
        spatial_feat = spatial_feat.reshape(batch, n_patches, self.spatial_feat_dim)
        return spatial_feat
    
    def _merge_similar_patches(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
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
        batch = x.shape[0]
        
        patches, n_patches = self._sliding_window_patch(x)
        rhythm_feat = self._rhythm_time_feat_extraction(patches)
        spatial_feat = self._spatial_dilated_conv(rhythm_feat)
        projected_feat = self.feat_proj(spatial_feat)
        
        if self.merge_enabled:
            projected_feat, padding_mask = self._merge_similar_patches(projected_feat)
        else:
            padding_mask = torch.zeros(batch, n_patches, dtype=torch.bool, device=x.device)
        
        final_feat = self.pos_encoding(projected_feat)
        return final_feat, padding_mask
