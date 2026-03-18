#!/usr/bin/env python3
"""
评估脚本统一入口

用法：
    python evaluate.py --config configs/experiments.yaml::adc_4bit --type reconstruction
    python evaluate.py --config configs/experiments.yaml::adc_4bit --type probe

支持：
1. 重构质量评估
2. 线性探针评估
3. 多探针任务评估
"""

import sys
import argparse
import logging
from pathlib import Path
import torch
import yaml
import traceback

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

from eegtokenizer_v2.models import EEGClassifier
from eegtokenizer_v2.tokenizers import ADCTokenizer
from eegtokenizer_v2.data.loader import EEGDataLoader
from eegtokenizer_v2.evaluation import (
    ReconstructionEvaluator,
    SpectralReconstructionEvaluator,
    MultiProbeEvaluator,
    evaluate_reconstruction_quality,
    evaluate_probe_tasks
)

# 配置日志
def setup_logging(log_dir: str):
    """配置日志"""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / f'evaluate_{timestamp}.log'

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

    return logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """加载配置文件"""
    config_path = Path(config_path)

    if '::' in str(config_path):
        yaml_file, exp_key = str(config_path).split('::')
        with open(yaml_file) as f:
            full_config = yaml.safe_load(f)
        config = full_config.get(exp_key, {})
    else:
        with open(config_path) as f:
            config = yaml.safe_load(f)

    return config


def create_model(config: dict):
    """创建模型"""
    tokenizer_config = config['model']['tokenizer']

    if tokenizer_config['name'] == 'ADCTokenizer':
        tokenizer = ADCTokenizer(
            window_length=tokenizer_config.get('window_length', 250),
            step_length=tokenizer_config.get('step_length', 125),
            num_bits=tokenizer_config.get('num_bits', 4),
            quant_type=tokenizer_config.get('quant_type', 'scalar'),
            agg_type=tokenizer_config.get('agg_type', 'mean'),
            n_head=tokenizer_config.get('n_head', 8)
        )
    else:
        raise ValueError(f"Unknown tokenizer: {tokenizer_config['name']}")

    model_config = config['model']['classifier']
    num_classes = model_config.get('num_classes', 4)
    nhead = model_config.get('nhead', 8)
    num_layers = model_config.get('num_layers', 2)
    dropout = model_config.get('dropout', 0.1)

    model = EEGClassifier(
        tokenizer=tokenizer,
        num_classes=num_classes,
        nhead=nhead,
        num_layers=num_layers,
        dropout=dropout
    )

    return model


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='EEGTokenizer 评估脚本')
    parser.add_argument('--config', type=str, required=True, help='配置文件路径')
    parser.add_argument('--type', type=str, required=True, choices=['reconstruction', 'probe', 'spectral', 'all'], help='评估类型')
    parser.add_argument('--gpu', type=int, default=0, help='GPU ID')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    args = parser.parse_args()

    # 设置设备
    device = f"cuda:{args.gpu}" if torch.cuda.is_available() else "cpu"

    # 加载配置
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"❌ 配置文件加载失败: {e}")
        print(traceback.format_exc())
        sys.exit(1)

    # 设置日志
    save_dir = config.get('training', {}).get('save_dir', './results')
    logger = setup_logging(save_dir)

    logger.info("=" * 60)
    logger.info("EEGTokenizer 评估开始")
    logger.info("=" * 60)
    logger.info(f"配置文件: {args.config}")
    logger.info(f"评估类型: {args.type}")
    logger.info(f"GPU: {device}")
    logger.info("=" * 60)

    try:
        # 加载数据
        logger.info("加载数据...")
        data_loader = EEGDataLoader(
            data_dir=config['data']['data_dir'],
            subject_id=config['data']['subject_id'],
            data_mode=config['data']['data_mode']
        )
        train_loader, val_loader, test_loader = data_loader.load_single_subject(
            train_ratio=config['data']['train_ratio'],
            val_ratio=config['data']['val_ratio'],
            batch_size=config['data']['batch_size'],
            num_workers=config['data']['num_workers']
        )

        logger.info(f"数据加载完成")
        logger.info(f"  训练集: {len(train_loader.dataset)} 样本")
        logger.info(f"  验证集: { len(val_loader.dataset)} 样本")
        logger.info(f"  测试集: {len(test_loader.dataset)} 样本")

        # 创建模型
        logger.info("创建模型...")
        model = create_model(config)
        logger.info(f"模型: {config['model']['type']} + {config['model']['tokenizer']['name']}")

        # 移到设备
        model = model.to(device)

        # 根据类型评估
        if args.type == 'reconstruction' or args.type == 'all':
            logger.info("开始重构质量评估...")
            if args.type == 'all':
                evaluator = SpectralReconstructionEvaluator(device)
                metrics = evaluator.evaluate(model, test_loader, save_dir=f"{save_dir}/spectral")
            else:
                metrics = evaluate_reconstruction_quality(model, test_loader, device, save_dir=f"{save_dir}/reconstruction")

            logger.info("重构质量评估完成")
            logger.info(f"  MSE: {metrics['mse']:.6f}")
            logger.info(f"  MAE: {metrics['mae']:.6f}")
            logger.info(f"  SNR: {metrics['snr']:.2f} dB")

        if args.type == 'probe' or args.type == 'all':
            logger.info("开始探针任务评估...")
            if args.type == 'all':
                metrics = evaluate_probe_tasks(model, test_loader, device, save_dir=f"{save_dir}/probe")
            else:
                # 单独评估
                from eegtokenizer_v2.evaluation.probe_tasks import ProbeTrainer

                probe_trainer = ProbeTrainer("motor_imagery", device)
                metrics = probe_trainer.evaluate(model, test_loader, save_dir=f"{save_dir}/probe_single")

            logger.info("探针任务评估完成")
            if 'rhythm_classification' in metrics:
                logger.info(f"  节律分类: Accuracy={metrics['rhythm_classification']['accuracy']:.4f}")
            if 'motor_imagery' in metrics:
                logger.info(f"  运动想象: Accuracy={metrics['motor_imagery']['accuracy']:.4f}")

        if args.type == 'spectral' or args.type == 'all':
            logger.info("开始频域重构评估...")
            evaluator = SpectralReconstructionEvaluator(device)
            metrics = evaluator.evaluate(model, test_loader, save_dir=f"{save_dir}/spectral")

            logger.info("频域重构评估完成")
            for band_name, band_metrics in metrics.items():
                logger.info(f"  {band_name}: MSE={band_metrics['mse']:.6f}, MAE={band_metrics['mae']:.6f}")

        logger.info("=" * 60)
        logger.info("✅ 评估完成！")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ 评估失败: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
