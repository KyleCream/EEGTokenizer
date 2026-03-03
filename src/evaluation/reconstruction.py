import torch
import torch.nn as nn
import numpy as np
from typing import Dict, Tuple


class ReconstructionEvaluator:
    """
    重构质量评估器
    
    评估 tokenize → detokenize 的恢复质量
    """
    
    def __init__(self, device: str = "cuda" if torch.cuda.is_available() else "cpu"):
        self.device = device
    
    def evaluate(
        self,
        tokenizer: nn.Module,
        detokenizer: nn.Module,
        data_loader: torch.utils.data.DataLoader
    ) -> Dict[str, float]:
        """
        评估重构质量
        
        返回:
            {
                'mse': 均方误差,
                'mae': 平均绝对误差,
                'snr': 信噪比 (dB),
                'mean_amp_error': 平均幅度误差
            }
        """
        tokenizer.eval()
        detokenizer.eval()
        
        all_mse = []
        all_mae = []
        all_snr = []
        all_amp_error = []
        
        with torch.no_grad():
            for batch_data, _ in data_loader:
                batch_data = batch_data.to(self.device)
                
                # Tokenize
                features, padding_mask = tokenizer(batch_data)
                
                # Detokenize
                reconstructed = detokenizer(features)
                
                # 对齐长度（detokenizer 可能输出长度不同）
                if reconstructed.shape[2] > batch_data.shape[2]:
                    reconstructed = reconstructed[..., :batch_data.shape[2]]
                elif reconstructed.shape[2] < batch_data.shape[2]:
                    pad_len = batch_data.shape[2] - reconstructed.shape[2]
                    reconstructed = torch.nn.functional.pad(reconstructed, (0, pad_len))
                
                # 计算指标
                mse = torch.mean((batch_data - reconstructed) ** 2).item()
                mae = torch.mean(torch.abs(batch_data - reconstructed)).item()
                
                # SNR
                signal_power = torch.mean(batch_data ** 2).item()
                noise_power = mse
                snr = 10 * np.log10(signal_power / (noise_power + 1e-8)) if noise_power > 0 else float('inf')
                
                # 幅度误差
                orig_amp = torch.mean(torch.abs(batch_data)).item()
                recon_amp = torch.mean(torch.abs(reconstructed)).item()
                amp_error = abs(orig_amp - recon_amp) / (orig_amp + 1e-8)
                
                all_mse.append(mse)
                all_mae.append(mae)
                all_snr.append(snr)
                all_amp_error.append(amp_error)
        
        return {
            'mse': float(np.mean(all_mse)),
            'mae': float(np.mean(all_mae)),
            'snr': float(np.mean(all_snr)),
            'mean_amp_error': float(np.mean(all_amp_error))
        }
    
    def evaluate_per_channel(
        self,
        tokenizer: nn.Module,
        detokenizer: nn.Module,
        data_loader: torch.utils.data.DataLoader,
        channels: int = 22
    ) -> Dict[int, Dict[str, float]]:
        """
        分通道评估重构质量
        """
        tokenizer.eval()
        detokenizer.eval()
        
        channel_metrics = {ch: {'mse': [], 'mae': [], 'snr': []} for ch in range(channels)}
        
        with torch.no_grad():
            for batch_data, _ in data_loader:
                batch_data = batch_data.to(self.device)
                
                features, padding_mask = tokenizer(batch_data)
                reconstructed = detokenizer(features)
                
                if reconstructed.shape[2] > batch_data.shape[2]:
                    reconstructed = reconstructed[..., :batch_data.shape[2]]
                elif reconstructed.shape[2] < batch_data.shape[2]:
                    pad_len = batch_data.shape[2] - reconstructed.shape[2]
                    reconstructed = torch.nn.functional.pad(reconstructed, (0, pad_len))
                
                for ch in range(channels):
                    orig_ch = batch_data[:, ch, :]
                    recon_ch = reconstructed[:, ch, :]
                    
                    mse = torch.mean((orig_ch - recon_ch) ** 2).item()
                    mae = torch.mean(torch.abs(orig_ch - recon_ch)).item()
                    
                    signal_power = torch.mean(orig_ch ** 2).item()
                    noise_power = mse
                    snr = 10 * np.log10(signal_power / (noise_power + 1e-8)) if noise_power > 0 else float('inf')
                    
                    channel_metrics[ch]['mse'].append(mse)
                    channel_metrics[ch]['mae'].append(mae)
                    channel_metrics[ch]['snr'].append(snr)
        
        # 平均
        results = {}
        for ch in range(channels):
            results[ch] = {
                'mse': float(np.mean(channel_metrics[ch]['mse'])),
                'mae': float(np.mean(channel_metrics[ch]['mae'])),
                'snr': float(np.mean(channel_metrics[ch]['snr']))
            }
        return results
