#!/usr/bin/env python3
"""
统一训练入口

用法：
    python train.py --config configs/experiments.yaml::adc_4bit

支持：
1. 配置文件（YAML）
2. 命令行参数
3. 完整的日志管理
4. 错误处理
5. 模型保存
"""

import sys
import argparse
import logging
from pathlib import Path
import torch
import yaml
import traceback
from datetime import datetime

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

from eegtokenizer_v2.tokenizers import ADCTokenizer
from eegtokenizer_v2.models import EEGClassifier
from eegtokenizer_v2.data.loader import EEGDataLoader
from eegtokenizer_v2.training.trainer import Trainer

# 配置日志
def setup_logging(log_dir: str):
    """配置日志"""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / f'train_{timestamp}.log'

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
    """
    加载配置文件

    支持格式：
    - configs/experiments.yaml::adc_4bit（加载特定实验）
    - configs/experiments.yaml（加载全部）
    - path/to/config.yaml
    """
    config_path = Path(config_path)

    # 处理 YAML::key 格式
    if '::' in str(config_path):
        yaml_file, exp_key = str(config_path).split('::')
        with open(yaml_file) as f:
            full_config = yaml.safe_load(f)
        config = full_config.get(exp_key, {})
    else:
        with open(config_path) as f:
            config = yaml.safe_load(f)

    return config


def create_tokenizer(config: dict):
    """创建 tokenizer"""
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

    return tokenizer


def create_model(config: dict):
    """创建模型"""
    tokenizer = create_tokenizer(config)

    model_config = config['model']['classifier']
    num_classes = model_config.get('num_classes', 4)
    nhead = model_config.get('nhead', 8)
    num_layers = model_config.get('num_layers', 2)
    dropout = model_config.get('dropout', 0.1)

    if model_config['type'] == 'Transformer':
        model = EEGClassifier(
            tokenizer=tokenizer,
            num_classes=num_classes,
            nhead=nhead,
            num_layers=num_layers,
            dropout=dropout
        )
    else:
        raise ValueError(f"Unknown model type: {model_config['type']}")

    return model


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='EEGTokenizer 训练脚本')
    parser.add_argument('--config', type=str, required=True, help='配置文件路径')
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
    save_dir = config.get('training', {}).get('save_dir', './checkpoints')
    logger = setup_logging(save_dir)

    logger.info("=" * 60)
    logger.info("EEGTokenizer 训练开始")
    logger.info("=" * 60)
    logger.info(f"配置文件: {args.config}")
    logger.info(f"GPU: {device}")
    logger.info(f"调试模式: {args.debug}")
    logger.info("=" * 60)

    try:
        # 创建模型
        logger.info("创建模型...")
        model = create_model(config)
        logger.info(f"模型: {config['model']['type']} + {config['model']['tokenizer']['name']}")

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

        # 创建训练器
        logger.info("创建训练器...")
        trainer = Trainer(model, config, device)

        # 开始训练
        logger.info("开始训练...")
        trainer.train(train_loader, val_loader)

        # 完成
        logger.info("=" * 60)
        logger.info("✅ 训练完成！")
        logger.info(f"最佳验证准确率: {trainer.best_val_acc:.4f}")
        logger.info(f"检查点保存位置: {trainer.save_dir}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ 训练失败: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
