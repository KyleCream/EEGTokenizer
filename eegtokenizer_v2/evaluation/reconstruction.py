"""
重构质量评估（修正版）

评估 tokenize → detokenize 的恢复质量

数据流程：
1. Tokenize: (batch, 22, 1000) → (batch, n_patches, d_model)
2. Detokenize: (batch, n_patches, d_model) → (batch, 22, 1000)

指标：
- MSE（均方误差）
- MAE（平均绝对误差）
- SNR（信噪比）
- 频域误差（各节律 band 的恢复误差）
"""

import torch
import torch.nn as nn
import numpy as np
import logging
from pathlib import Path
import json
from datetime import datetime
from typing import Dict

logger = logging.getLogger(__name__)


class ReconstructionEvaluator:
    """
    重构质量评估器（修正版）

    评估 tokenize → detokenize 的恢复质量
    """

    def __init__(self, device: str = "cuda" if torch.cuda.is_available() else "cpu"):
        self.device = device
        logger.info(f"ReconstructionEvaluator 初始化，设备: {device}")

    def evaluate(
        self,
        model: nn.Module,
        data_loader: torch.utils.data.DataLoader,
        save_dir: str = "./results/reconstruction"
    ) -> Dict[str, float]:
        """
        评估重构质量

        Args:
            model: 包含 tokenizer 的模型
            data_loader: 数据加载器
            save_dir: 结果保存目录

        Returns:
            metrics: 指标字典
        """
        model.eval()

        # 创建保存目录
        save_path = Path(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)

        all_mse = []
        all_mae = []
        all_snr = []
        all_amp_error = []

        with torch.no_grad():
            for batch_idx, (data, _) in enumerate(data_loader):
                data = data.to(self.device)
                batch_size, channels, sample = data.shape

                try:
                    # Tokenize
                    if hasattr(model, 'tokenizer'):
                        features, padding_mask = model.tokenizer(data)
                        # features: (batch, n_patches, d_model)
                    else:
                        logger.error("模型没有 tokenizer 属性")
                        return {}

                    # Detokenize（投影回 channels）
                    reconstructed = self._detokenize(features, data.shape)

                    # 计算指标
                    mse = torch.mean((data - reconstructed) ** 2).item()
                    mae = torch.mean(torch.abs(data - reconstructed)).item()

                    # SNR
                    signal_power = torch.mean(data ** 2).item()
                    noise_power = mse
                    snr = 10 * np.log10(signal_power / (noise_power + 1e-8)) if noise_power > 0 else float('inf')

                    # 幅度误差
                    orig_amp = torch.mean(torch.abs(data)).item()
                    recon_amp = torch.mean(torch.abs(reconstructed)).item()
                    amp_error = abs(orig_amp - recon_amp) / (orig_amp + 1e-8)

                    all_mse.append(mse)
                    all_mae.append(mae)
                    all_snr.append(snr)
                    all_amp_error.append(amp_error)

                except Exception as e:
                    logger.error(f"批次 {batch_idx} 评估失败: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    continue

        # 计算平均指标
        metrics = {
            'mse': float(np.mean(all_mse)),
            'mae': float(np.mean(all_mae)),
            'snr': float(np.mean(all_snr)),
            'mean_amp_error': float(np.mean(all_amp_error))
        }

        # 保存结果
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_file = save_path / f'reconstruction_{timestamp}.json'

        with open(result_file, 'w') as f:
            json.dump(metrics, f, indent=2)

        logger.info(f"重构质量评估完成")
        logger.info(f"  MSE: {metrics['mse']:.6f}")
        logger.info(f"  MAE: {metrics['mae']:.6f}")
        logger.info(f"  SNR: {metrics['snr']:.2f} dB")
        logger.info(f"  幅度误差: {metrics['mean_amp_error']:.6f}")
        logger.info(f"  结果已保存: {result_file}")

        return metrics

    def _detokenize(self, features: torch.Tensor, original_shape: tuple) -> torch.Tensor:
        """
        解码器（投影回原始形状）

        Args:
            features: token 特征, shape (batch, n_patches, d_model)
            original_shape: 原始数据形状, (batch, channels, sample)

        Returns:
            reconstructed: 重构的 EEG 信号, shape (batch, channels, sample)
        """
        batch_size, n_patches, d_model = features.shape
        _, channels, sample = original_shape

        # 反向投影：d_model → channels
        # 使用线性投影
        if not hasattr(self, 'detoken_projection'):
            # 创建投影层：d_model → channels
            self.detoken_projection = nn.Linear(d_model, channels).to(self.device)

        # 投影
        # features: (batch, n_patches, d_model) → (batch, n_patches, channels)
        patches = self.detoken_projection(features)

        # 反向聚合：n_patches → sample
        # 使用 fold 或简单的重复+裁剪
        # 这里简化：使用线性插值
        reconstructed = self._patches_to_signal(patches, sample)

        return reconstructed

    def _patches_to_signal(self, patches: torch.Tensor, target_length: int) -> torch.Tensor:
        """
        将 patches 重构为信号

        Args:
            patches: (batch, n_patches, channels)
            target_length: 目标长度（sample 维度）

        Returns:
            signal: (batch, channels, target_length)
        """
        batch_size, n_patches, channels = patches.shape

        # 简化版本：线性插值
        # patches: (batch, channels, n_patches)
        patches = patches.permute(0, 2, 1)

        # 使用上采样
        reconstructed = torch.nn.functional.interpolate(
            patches,
            size=target_length,
            mode='linear',
            align_corners=False
        )

        return reconstructed


def evaluate_reconstruction_quality(
    model: nn.Module,
    data_loader: torch.utils.data.DataLoader,
    device: str = "cuda",
    save_dir: str = "./results/reconstruction"
) -> Dict[str, float]:
    """
    评估重构质量（便捷函数）

    Args:
        model: 模型
        data_loader: 数据加载器
        device: 设备
        save_dir: 保存目录

    Returns:
        metrics: 指标字典
    """
    evaluator = ReconstructionEvaluator(device)
    return evaluator.evaluate(model, data_loader, save_dir)


# ==================== 频域误差分析 ====================

class SpectralReconstructionEvaluator(ReconstructionEvaluator):
    """
    频域重构质量评估器

    在不同频段（delta/theta/alpha/beta/gamma）上评估重构质量
    """

    def __init__(self, device: str = "cuda" if torch.cuda.is_available() else "cpu"):
        super().__init__(device)
        # 定义频段
        self.bands = {
            'delta': (0.5, 4),
            'theta': (4, 8),
            'alpha': (8, 12),
            'beta': (12, 30),
            'gamma': (30, 50)
        }

    def evaluate(
        self,
        model: nn.Module,
        data_loader: torch.utils.data.DataLoader,
        save_dir: str = "./results/spectral_reconstruction"
    ) -> Dict[str, Dict[str, float]]:
        """
        评估频域重构质量

        Returns:
            metrics: 总体指标 + 频域指标
        """
        model.eval()

        save_path = Path(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)

        all_band_errors = {band: {'mse': [], 'mae': []} for band in self.bands.keys()}

        with torch.no_grad():
            for batch_idx, (data, _) in enumerate(data_loader):
                data = data.to(self.device)

                # Tokenize
                if hasattr(model, 'tokenizer'):
                    features, _ = model.tokenizer(data)
                else:
                    logger.error("模型没有 tokenizer 属性")
                    return {}

                # Detokenize
                reconstructed = self._detokenize(features, data.shape)

                # 计算每个频段的误差
                error = data - reconstructed

                for band_name, (freq_low, freq_high) in self.bands.items():
                    # 使用 FFT 计算频域误差
                    fft_error = torch.fft.fft(error, dim=2)
                    fft_magnitude = torch.abs(fft_error)

                    # 找到对应的频率范围（简化版）
                    # 假设采样率 250Hz
                    fs = 250
                    freq_bins = data.shape[2]
                    freqs = torch.fft.fftfreq(freq_bins, 1/fs)

                    # 找到频段范围
                    mask = (freqs >= freq_low) & (freqs <= freq_high)
                    band_magnitude = fft_magnitude[:, :, mask]

                    # 计算误差
                    band_mse = torch.mean(band_magnitude ** 2).item()
                    band_mae = torch.mean(band_magnitude).item()

                    all_band_errors[band_name]['mse'].append(band_mse)
                    all_band_errors[band_name]['mae'].append(band_mae)

        # 聚合所有批次的指标
        final_metrics = {}
        for band_name in self.bands.keys():
            final_metrics[band_name] = {
                'mse': float(np.mean(all_band_errors[band_name]['mse'])),
                'mae': float(np.mean(all_band_errors[band_name]['mae']))
            }

        # 保存结果
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_file = save_path / f'spectral_reconstruction_{timestamp}.json'

        with open(result_file, 'w') as f:
            json.dump(final_metrics, f, indent=2)

        logger.info(f"频域重构质量评估完成")
        for band_name, metrics in final_metrics.items():
            logger.info(f"  {band_name}: MSE={metrics['mse']:.6f}, MAE={metrics['mae']:.6f}")

        return final_metrics
