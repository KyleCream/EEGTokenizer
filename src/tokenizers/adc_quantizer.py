import torch
import torch.nn as nn
import torch.nn.functional as F


class ADCQuantizer(nn.Module):
    """
    ADC 风格数字量化 Tokenizer
    
    核心思想：
    1. 固定时间分割成 patch
    2. 类似硬件 ADC 的标量量化
    3. 支持不同精度（1/2/4/8/16bit）
    4. 多种码字聚合方式
    
    输入: (batch, channels, timepoints)
    输出: (batch, n_patches, d_model) + padding_mask
    """
    
    def __init__(
        self,
        window_length: int = 250,      # 每个 patch 的时间长度
        step_length: int = 125,        # 滑动步长
        patch_enabled: bool = True,     # 是否分 patch
        num_bits: int = 4,              # 量化精度（bit）
        quant_type: str = "scalar",     # 量化类型：scalar/vector/product
        agg_type: str = "mean",         # 聚合方式：mean/attention/gate
        d_model: int = 64,              # 输出维度
        n_head: int = 8,                # 注意力头数（用于 agg_type=attention）
        channels: int = 22,             # EEG 通道数
        value_range: tuple = (-100, 100)  # EEG 信号范围（μV）
    ):
        super().__init__()
        self.window_length = window_length
        self.step_length = step_length
        self.patch_enabled = patch_enabled
        self.num_bits = num_bits
        self.quant_type = quant_type
        self.agg_type = agg_type
        self.channels = channels
        self.value_range = value_range
        
        # 计算量化级别数
        self.quant_levels = 2 ** num_bits
        
        # 计算 d_model（确保能被 n_head 整除）
        if d_model is None:
            self.d_model = self._get_divisible_dim(channels * (1 if quant_type == "scalar" else 4), n_head)
        else:
            assert d_model % n_head == 0, f"d_model must be divisible by n_head"
            self.d_model = d_model
        
        # 量化参数（可学习或固定）
        self.register_buffer("min_val", torch.tensor(value_range[0], dtype=torch.float32))
        self.register_buffer("max_val", torch.tensor(value_range[1], dtype=torch.float32))
        
        # 码字投影层
        self.code_embedding = nn.Embedding(self.quant_levels * channels, self.d_model // channels)
        
        # 聚合层
        if agg_type == "attention":
            self.attention_agg = nn.MultiheadAttention(self.d_model, n_head, batch_first=True)
        elif agg_type == "gate":
            self.gate_agg = nn.GRUCell(self.d_model, self.d_model)
        
        # 最终投影
        self.final_proj = nn.Linear(self.d_model, self.d_model)
    
    def _get_divisible_dim(self, raw_dim: int, n_head: int) -> int:
        """计算能被 n_head 整除的最小维度"""
        if raw_dim % n_head == 0:
            return raw_dim
        else:
            return ((raw_dim // n_head) + 1) * n_head
    
    def _sliding_window_patch(self, x: torch.Tensor) -> tuple[torch.Tensor, int]:
        """
        时间维度分 patch
        输入: (batch, channels, timepoints)
        输出: (batch, channels, window_length, n_patches), n_patches
        """
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
    
    def _scalar_quantize(self, x: torch.Tensor) -> torch.Tensor:
        """
        标量量化（每个通道独立量化）
        输入: (batch, channels, window_length, n_patches)
        输出: (batch, channels, n_patches) - 量化后的码字索引
        """
        batch, chan, win_len, n_patches = x.shape
        
        # 先在时间维度聚合（mean/sum/max，这里用 mean）
        patch_agg = torch.mean(x, dim=2)  # (batch, channels, n_patches)
        
        # 归一化到 [0, 1]
        normalized = (patch_agg - self.min_val) / (self.max_val - self.min_val + 1e-8)
        normalized = torch.clamp(normalized, 0.0, 1.0)
        
        # 量化到 [0, quant_levels-1]
        quantized = torch.round(normalized * (self.quant_levels - 1)).long()
        
        # 加上通道偏移，让每个通道的码字空间独立
        quantized = quantized + torch.arange(chan, device=x.device).unsqueeze(0).unsqueeze(2) * self.quant_levels
        
        return quantized
    
    def _aggregate_codes(self, code_indices: torch.Tensor) -> torch.Tensor:
        """
        码字聚合
        输入: (batch, channels, n_patches) - 码字索引
        输出: (batch, n_patches, d_model)
        """
        batch, chan, n_patches = code_indices.shape
        
        # 嵌入码字
        code_embeds = self.code_embedding(code_indices)  # (batch, channels, n_patches, d_model//channels)
        
        # 拼接通道维度
        patch_embeds = code_embeds.permute(0, 2, 1, 3).reshape(batch, n_patches, -1)  # (batch, n_patches, d_model)
        
        # 聚合
        if self.agg_type == "mean":
            return patch_embeds  # 已经是拼接后的表示
        elif self.agg_type == "attention":
            attn_out, _ = self.attention_agg(patch_embeds, patch_embeds, patch_embeds)
            return attn_out
        elif self.agg_type == "gate":
            # 简单的门控聚合
            agg_states = []
            state = torch.zeros(batch, self.d_model, device=patch_embeds.device)
            for i in range(n_patches):
                state = self.gate_agg(patch_embeds[:, i, :], state)
                agg_states.append(state)
            return torch.stack(agg_states, dim=1)
        else:
            return patch_embeds
    
    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """
        输入: x - (batch, channels, timepoints)
        输出: (features, padding_mask)
            features: (batch, n_patches, d_model)
            padding_mask: (batch, n_patches)
        """
        batch = x.shape[0]
        
        # 1. 时间分 patch
        patches, n_patches = self._sliding_window_patch(x)
        
        # 2. 量化
        if self.quant_type == "scalar":
            code_indices = self._scalar_quantize(patches)
        else:
            # TODO: vector/product quantization
            code_indices = self._scalar_quantize(patches)
        
        # 3. 聚合
        features = self._aggregate_codes(code_indices)
        
        # 4. 最终投影
        features = self.final_proj(features)
        
        # 5. padding mask（这里简单设为全 False）
        padding_mask = torch.zeros(batch, n_patches, dtype=torch.bool, device=x.device)
        
        return features, padding_mask


class ADCDetokenizer(nn.Module):
    """
    ADC 量化的逆过程（用于重构质量评估）
    """
    
    def __init__(self, quantizer: ADCQuantizer):
        super().__init__()
        self.quantizer = quantizer
        self.d_model = quantizer.d_model
        self.channels = quantizer.channels
        self.window_length = quantizer.window_length
        self.step_length = quantizer.step_length
        
        # 逆投影层
        self.inv_proj = nn.Linear(self.d_model, self.channels)
    
    def forward(self, features: torch.Tensor) -> torch.Tensor:
        """
        从 token 特征重构 EEG 信号
        输入: (batch, n_patches, d_model)
        输出: (batch, channels, timepoints)
        """
        batch, n_patches, _ = features.shape
        
        # 逆投影
        channel_vals = self.inv_proj(features)  # (batch, n_patches, channels)
        
        # 反量化
        min_val = self.quantizer.min_val
        max_val = self.quantizer.max_val
        quant_levels = self.quantizer.quant_levels
        
        # 简单的重叠相加重构
        timepoints = n_patches * self.step_length + (self.window_length - self.step_length)
        reconstructed = torch.zeros(batch, self.channels, timepoints, device=features.device)
        weight = torch.zeros(batch, self.channels, timepoints, device=features.device)
        
        for i in range(n_patches):
            start = i * self.step_length
            end = start + self.window_length
            
            # 用 patch 的值填充整个窗口（简单策略）
            patch_vals = channel_vals[:, i, :].unsqueeze(2).expand(-1, -1, self.window_length)
            reconstructed[:, :, start:end] += patch_vals
            weight[:, :, start:end] += 1
        
        # 平均重叠区域
        reconstructed = reconstructed / (weight + 1e-8)
        
        return reconstructed
