from encode import EEGSTFEncoder  # 修正：使用EEGSTFEncoder而非EEGEncoder
import torch.nn as nn
import torch

# ------------------- 优化后的EEGClassifier（保留原有代码） -------------------
class EEGClassifier(nn.Module):
    def __init__(
        self,
        eeg_encoder: EEGSTFEncoder,
        num_classes: int,
        nhead: int = 8,
        num_transformer_layers: int = 2,
        dim_feedforward: int = 128,
        dropout_rate: float = 0.3,
        use_batch_norm: bool = False,
        use_residual: bool = False  # 新增：是否启用Transformer层的跨层残差连接
    ):
        super(EEGClassifier, self).__init__()
        self.eeg_encoder = eeg_encoder
        self.d_model = eeg_encoder.d_model
        self.dropout_rate = dropout_rate
        self.use_batch_norm = use_batch_norm
        self.use_residual = use_residual  # 保存残差连接开关

        # Transformer Encoder层
        transformer_layer = nn.TransformerEncoderLayer(
            d_model=self.d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            batch_first=True,
            activation="gelu",
            dropout=dropout_rate,
            layer_norm_eps=1e-5
        )
        self.transformer_encoder = nn.TransformerEncoder(transformer_layer, num_layers=num_transformer_layers)

        # 新增：残差连接后的层归一化（提升稳定性）
        self.residual_norm = nn.LayerNorm(self.d_model) if use_residual else nn.Identity()
        # 可选：残差连接后的Dropout（增强正则化）
        self.residual_dropout = nn.Dropout(dropout_rate) if use_residual else nn.Identity()

        # 分类头部分（保持不变）
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.dropout = nn.Dropout(dropout_rate)
        self.bn = nn.BatchNorm1d(self.d_model) if use_batch_norm else nn.Identity()
        self.fc_hidden1 = nn.Linear(self.d_model, self.d_model * 16)
        self.fc_hidden2 = nn.Linear(self.d_model * 16, self.d_model * 8)
        self.fc_out = nn.Linear(self.d_model * 8, num_classes)
        self.relu = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # 步骤1：EEG编码
        eeg_features, padding_mask = self.eeg_encoder(x)  # (batch, seq_len, d_model), (batch, seq_len)

        # 步骤2：Transformer建模
        transformer_out = self.transformer_encoder(eeg_features, src_key_padding_mask=padding_mask)  # (batch, seq_len, d_model)

        # 步骤3：添加跨层残差连接（核心修改）
        if self.use_residual:
            # 残差相加：Transformer输入 + Transformer输出
            transformer_out = eeg_features + transformer_out
            # 残差相加后做层归一化（重要：残差连接后通常配合归一化提升稳定性）
            transformer_out = self.residual_norm(transformer_out)
            # 可选：添加Dropout增强正则化
            transformer_out = self.residual_dropout(transformer_out)

        # 步骤4：序列维度聚合（保持不变）
        pooled = self.pool(transformer_out.permute(0, 2, 1)).squeeze(-1)  # (batch, d_model)

        # 步骤5：正则化处理（保持不变）
        pooled = self.bn(pooled)
        pooled = self.dropout(pooled)

        # 步骤6：分类（保持不变）
        hidden = self.relu(self.fc_hidden1(pooled))
        hidden = self.relu(self.fc_hidden2(hidden))
        hidden = self.dropout(hidden)
        logits = self.fc_out(hidden)

        return logits

# ------------------- 新增：CNN版EEGClassifier（解决过拟合问题） -------------------
class EEGClassifierCNN(nn.Module):
    def __init__(
        self,
        eeg_encoder: EEGSTFEncoder,
        num_classes: int,
        cnn_channels: list = None,  # CNN层的输出通道数
        kernel_sizes: list = None,   # 卷积核大小
        pool_sizes: list = None,     # 池化核大小
        dropout_rate: float = 0.2    # Dropout率（防过拟合）
    ):
        super(EEGClassifierCNN, self).__init__()
        self.eeg_encoder = eeg_encoder
        self.d_model = eeg_encoder.d_model  # 由EEGSTFEncoder确定

        # 默认CNN配置（适配大多数场景，用户可自定义）
        self.cnn_channels = cnn_channels if cnn_channels is not None else [self.d_model, self.d_model * 2, self.d_model * 4]
        self.kernel_sizes = kernel_sizes if kernel_sizes is not None else [3, 3, 3]
        self.pool_sizes = pool_sizes if pool_sizes is not None else [2, 2, 2]
        self.dropout_rate = dropout_rate
        self.num_classes = num_classes

        # 构建1D CNN层（处理序列特征：seq_len为序列长度，d_model为特征维度）
        self.cnn_layers = self._build_cnn_layers()

        # 分类头：全连接层（需要动态计算输入维度，这里先初始化，在forward中或用hook计算）
        self.fc = None  # 延迟初始化，因为seq_len是动态的（由EEG数据和encoder参数决定）
        self.dropout = nn.Dropout(dropout_rate)  # 防过拟合核心层

    def _build_cnn_layers(self):
        """构建1D CNN层堆叠：Conv1d + BatchNorm1d + ReLU + MaxPool1d + Dropout"""
        layers = nn.Sequential()
        in_channels = self.d_model  # 输入通道数：d_model（对应EEGSTFEncoder输出的特征维度）

        for i, (out_channels, kernel_size, pool_size) in enumerate(zip(self.cnn_channels, self.kernel_sizes, self.pool_sizes)):
            # 1D卷积（padding="same"保证序列长度不变，避免维度骤减）
            layers.add_module(
                f"conv1d_{i}",
                nn.Conv1d(in_channels, out_channels, kernel_size, padding="same")
            )
            # 批归一化（加速训练，稳定分布）
            layers.add_module(f"bn1d_{i}", nn.BatchNorm1d(out_channels))
            # 激活函数（ReLU比GELU更简单，适合CNN）
            layers.add_module(f"relu_{i}", nn.ReLU())
            # 最大池化（降维，减少计算量，提升泛化性）
            layers.add_module(f"maxpool1d_{i}", nn.MaxPool1d(pool_size))
            # Dropout（随机失活，防止过拟合）
            layers.add_module(f"dropout_{i}", nn.Dropout(self.dropout_rate))

            in_channels = out_channels  # 更新输入通道数

        return layers

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # 步骤1：EEG编码，得到特征和padding_mask（padding_mask在CNN中可通过mask_fill处理，这里简化为直接使用特征）
        eeg_features, padding_mask = self.eeg_encoder(x)  # (batch, seq_len, d_model), (batch, seq_len)

        # 步骤2：处理padding_mask（将补零位置的特征置为0，避免影响CNN计算）
        if padding_mask is not None:
            # padding_mask: (batch, seq_len) → 扩展维度: (batch, seq_len, 1) → 广播到(batch, seq_len, d_model)
            eeg_features = eeg_features.masked_fill(padding_mask.unsqueeze(-1), 0.0)

        # 步骤3：维度置换（适配1D CNN输入：(batch, in_channels, seq_len)，其中in_channels=d_model）
        x_cnn = eeg_features.permute(0, 2, 1)  # (batch, d_model, seq_len)

        # 步骤4：CNN特征提取
        cnn_out = self.cnn_layers(x_cnn)  # (batch, final_channels, final_seq_len)

        # 步骤5：特征展平（(batch, C, L) → (batch, C*L)）
        flattened = torch.flatten(cnn_out, start_dim=1)  # (batch, num_features)

        # 延迟初始化全连接层（解决seq_len动态变化的问题）
        if self.fc is None:
            self.fc = nn.Linear(flattened.shape[1], self.num_classes).to(flattened.device)

        # 步骤6：Dropout + 分类
        flattened = self.dropout(flattened)  # 额外的Dropout层，增强防过拟合
        logits = self.fc(flattened)  # (batch, num_classes)

        return logits

# ------------------- 优化后的测试部分（核心修改） -------------------
if __name__ == "__main__":
    # ===================== 1. 基础配置（贴合EEGSTFEncoder的核心参数） =====================
    batch_size = 4          # 批次大小
    n_channels = 32         # EEG通道数（32导电极，符合常见实验配置）
    time_points = 1000      # 时间点数量（250Hz采样 → 4秒数据）
    window_length = 128     # 时间patch窗口长度
    step_length = 64        # 滑动步长
    fs = 250                # 采样频率
    max_freq = 50           # 最大分析频率（EEG主要关注0-50Hz）
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"📌 测试基础配置")
    print(f"   设备：{device} | 批次大小：{batch_size} | EEG通道数：{n_channels} | 时间点：{time_points}")
    print("=" * 90)

    # 创建模拟EEG数据：(batch, chan, timepoints) → 符合EEGSTFEncoder输入要求
    eeg_data = torch.randn(batch_size, n_channels, time_points).to(device)
    print(f"📥 模拟EEG输入形状：{eeg_data.shape} (batch, chan, timepoints)")
    print("=" * 90)

    # ===================== 2. 测试用例设计（贴合EEGSTFEncoder核心特性） =====================
    # 覆盖场景：默认参数/关闭patch/开启patch合并/自定义空洞卷积/CNN高dropout
    test_cases = [
        # ------------------- Transformer分类器测试（核心场景） -------------------
        {
            "model_type": "transformer",
            "name": "基础场景：默认参数 + Transformer + 2分类",
            "encoder_kwargs": {
                "window_length": window_length,
                "step_length": step_length,
                "fs": fs,
                "max_freq": max_freq,
                "patch_enabled": True,  # 开启时间分patch（默认）
                "merge_enabled": False  # 关闭patch合并
            },
            "model_kwargs": {
                "num_classes": 2,
                "nhead": 8,
                "num_transformer_layers": 2,
                "use_residual": False  # 关闭残差
            }
        },
        {
            "model_type": "transformer",
            "name": "残差场景：关闭patch + Transformer（带残差） + 3分类",
            "encoder_kwargs": {
                "window_length": window_length,
                "step_length": step_length,
                "fs": fs,
                "max_freq": max_freq,
                "patch_enabled": False,  # 关闭分patch（整段时间作为1个patch）
                "merge_enabled": False
            },
            "model_kwargs": {
                "num_classes": 3,
                "nhead": 8,
                "use_residual": True,   # 开启Transformer残差连接
                "use_batch_norm": True  # 开启BatchNorm
            }
        },
        {
            "model_type": "transformer",
            "name": "合并场景：开启patch合并 + Transformer + 2分类",
            "encoder_kwargs": {
                "window_length": window_length,
                "step_length": step_length,
                "fs": fs,
                "max_freq": max_freq,
                "patch_enabled": True,
                "merge_enabled": True,  # 开启相似patch合并
                "merge_threshold": 0.9  # 合并阈值
            },
            "model_kwargs": {
                "num_classes": 2,
                "nhead": 8,
                "dropout_rate": 0.3
            }
        },
        # ------------------- CNN分类器测试（防过拟合场景） -------------------
        {
            "model_type": "cnn",
            "name": "CNN基础：自定义空洞卷积 + CNN默认配置 + 3分类",
            "encoder_kwargs": {
                "window_length": window_length,
                "step_length": step_length,
                "fs": fs,
                "max_freq": max_freq,
                # 自定义空洞卷积参数（覆盖默认）
                "dilated_conv_channels": [40, 64, 32],
                "dilated_conv_kernels": [3, 3, 3],
                "dilated_conv_dilations": [1, 2, 4]
            },
            "model_kwargs": {
                "num_classes": 3,
                "dropout_rate": 0.2  # 基础dropout
            }
        },
        {
            "model_type": "cnn",
            "name": "CNN防过拟合：高dropout + 自定义CNN参数 + 4分类",
            "encoder_kwargs": {
                "window_length": window_length,
                "step_length": step_length,
                "fs": fs,
                "max_freq": max_freq,
                "merge_enabled": True  # 开启patch合并
            },
            "model_kwargs": {
                "num_classes": 4,
                "cnn_channels": [16, 32, 64],    # 自定义CNN通道
                "kernel_sizes": [5, 3, 3],        # 自定义卷积核
                "pool_sizes": [2, 2, 2],          # 自定义池化核
                "dropout_rate": 0.5               # 高dropout防过拟合
            }
        }
    ]

    # ===================== 3. 执行测试用例（增强输出信息） =====================
    total_cases = len(test_cases)
    passed_cases = 0

    for idx, case in enumerate(test_cases, 1):
        print(f"\n🔍 【测试用例 {idx}/{total_cases}】：{case['name']}")
        print("-" * 70)

        try:
            # 步骤1：初始化EEGSTFEncoder（核心修正：替换原EEGEncoder）
            encoder = EEGSTFEncoder(**case["encoder_kwargs"]).to(device)
            
            # 步骤2：初始化分类器（Transformer/CNN）
            if case["model_type"] == "transformer":
                model = EEGClassifier(eeg_encoder=encoder, **case["model_kwargs"]).to(device)
            elif case["model_type"] == "cnn":
                model = EEGClassifierCNN(eeg_encoder=encoder, **case["model_kwargs"]).to(device)
            else:
                raise ValueError(f"不支持的模型类型：{case['model_type']}")

            # 步骤3：前向传播（禁用梯度，节省资源）
            with torch.no_grad():
                logits = model(eeg_data)
                # 单独获取编码器输出，用于验证维度
                eeg_features, padding_mask = encoder(eeg_data)

            # 步骤4：打印核心维度信息（增强可读性）
            n_patches = eeg_features.shape[1]  # seq_len = n_patches
            print(f"📊 核心维度验证：")
            print(f"   - 编码器输出特征：{eeg_features.shape} (batch, n_patches, d_model)")
            print(f"   - padding掩码形状：{padding_mask.shape} (batch, n_patches)")
            print(f"   - d_model值：encoder={encoder.d_model} | model={model.d_model}")
            print(f"   - 模型输出Logits：{logits.shape} (batch, num_classes)")
            if case["model_type"] == "cnn":
                # 额外打印CNN层输出维度（可选）
                x_cnn = eeg_features.permute(0, 2, 1)
                cnn_out = model.cnn_layers(x_cnn)
                print(f"   - CNN层输出：{cnn_out.shape} (batch, final_channels, final_seq_len)")

            # 步骤5：关键断言（验证核心逻辑）
            # 断言1：输出logits维度符合预期
            assert logits.shape == (batch_size, case["model_kwargs"]["num_classes"]), \
                f"Logits维度错误！预期({batch_size}, {case['model_kwargs']['num_classes']})，实际{logits.shape}"
            # 断言2：encoder和model的d_model一致
            assert encoder.d_model == model.d_model, \
                "Encoder与分类器的d_model不匹配！"
            # 断言3：n_patches符合预期（关闭patch时应为1）
            if not case["encoder_kwargs"].get("patch_enabled", True):
                assert n_patches == 1, f"关闭patch后n_patches应为1，实际{n_patches}"

            print("✅ 测试通过（所有断言验证成功）")
            passed_cases += 1

        except Exception as e:
            print(f"❌ 测试失败：{str(e)}")
            continue

    # ===================== 4. 测试总结 =====================
    print("\n" + "=" * 90)
    print(f"📈 测试总结：共{total_cases}个用例 | 通过{passed_cases}个 | 失败{total_cases - passed_cases}个")
    if passed_cases == total_cases:
        print("🎉 所有测试用例执行成功！")
    else:
        print("⚠️  部分测试用例失败，请检查参数配置！")