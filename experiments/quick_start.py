import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import torch
from src.tokenizers import EEGSTFEncoder, ADCQuantizer
from src.tokenizers.adc_quantizer import ADCDetokenizer
from src.evaluation import ReconstructionEvaluator, ProbeTaskEvaluator
from src.utils import UnifiedEEGDataLoader


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    
    # ========== 1. 准备数据 ==========
    print("\n" + "="*60)
    print("1. Preparing mock data...")
    print("="*60)
    
    data_loader = UnifiedEEGDataLoader(
        batch_size=32,
        channels=22,
        timepoints=1000,
        num_classes=4,
        num_samples=500  # 小一点快速测试
    )
    
    train_loader, val_loader, test_loader = data_loader.generate_mock_data()
    print(f"Train batches: {len(train_loader)}")
    print(f"Val batches: {len(val_loader)}")
    print(f"Test batches: {len(test_loader)}")
    
    # ========== 2. 测试时空频编码器（基线）==========
    print("\n" + "="*60)
    print("2. Testing EEGSTFEncoder (baseline)...")
    print("="*60)
    
    stf_encoder = EEGSTFEncoder(
        window_length=128,
        step_length=64,
        fs=250,
        max_freq=50,
        patch_enabled=True
    ).to(device)
    
    # 测试前向传播
    for batch_x, _ in train_loader:
        batch_x = batch_x.to(device)
        features, mask = stf_encoder(batch_x)
        print(f"STF Encoder output shape: {features.shape}")
        print(f"STF d_model: {stf_encoder.d_model}")
        break
    
    # ========== 3. 测试 ADC 量化器（新方案）==========
    print("\n" + "="*60)
    print("3. Testing ADCQuantizer (new)...")
    print("="*60)
    
    # 测试不同精度
    for num_bits in [4, 8, 16]:
        print(f"\n--- Testing {num_bits}bit ---")
        adc_quantizer = ADCQuantizer(
            window_length=250,
            step_length=125,
            num_bits=num_bits,
            quant_type="scalar",
            agg_type="mean",
            channels=22
        ).to(device)
        
        adc_detokenizer = ADCDetokenizer(adc_quantizer).to(device)
        
        # 测试前向传播
        for batch_x, _ in train_loader:
            batch_x = batch_x.to(device)
            features, mask = adc_quantizer(batch_x)
            print(f"  {num_bits}bit Encoder output shape: {features.shape}")
            print(f"  {num_bits}bit d_model: {adc_quantizer.d_model}")
            
            # 测试重构
            reconstructed = adc_detokenizer(features)
            print(f"  {num_bits}bit Reconstructed shape: {reconstructed.shape}")
            break
    
    # ========== 4. 评估重构质量（ADC 4bit）==========
    print("\n" + "="*60)
    print("4. Evaluating reconstruction quality (ADC 4bit)...")
    print("="*60)
    
    adc_4bit = ADCQuantizer(
        window_length=250,
        step_length=125,
        num_bits=4,
        channels=22
    ).to(device)
    adc_detok_4bit = ADCDetokenizer(adc_4bit).to(device)
    
    recon_evaluator = ReconstructionEvaluator(device=device)
    recon_metrics = recon_evaluator.evaluate(adc_4bit, adc_detok_4bit, test_loader)
    
    print(f"Reconstruction metrics (ADC 4bit):")
    print(f"  MSE: {recon_metrics['mse']:.4f}")
    print(f"  MAE: {recon_metrics['mae']:.4f}")
    print(f"  SNR: {recon_metrics['snr']:.2f} dB")
    print(f"  Amp Error: {recon_metrics['mean_amp_error']:.2%}")
    
    # ========== 5. 探针任务评估 ==========
    print("\n" + "="*60)
    print("5. Evaluating probe task (ADC 4bit)...")
    print("="*60)
    
    probe_evaluator = ProbeTaskEvaluator(
        device=device,
        epochs=30,  # 快速测试，少跑点
        lr=1e-3
    )
    
    probe_metrics = probe_evaluator.evaluate_classification(
        adc_4bit,
        train_loader,
        val_loader,
        num_classes=4
    )
    
    print(f"Probe task metrics (ADC 4bit):")
    print(f"  Train Acc: {probe_metrics['train_acc']:.2%}")
    print(f"  Val Acc: {probe_metrics['val_acc']:.2%}")
    print(f"  Val F1: {probe_metrics['val_f1']:.4f}")
    
    print("\n" + "="*60)
    print("Quick start complete!")
    print("="*60)


if __name__ == "__main__":
    main()
