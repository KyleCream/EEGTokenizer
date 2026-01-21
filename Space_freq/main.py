import os
import time
import random  # 新增：导入random库
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import numpy as np
from loaddata import EEGDataLoader
from encode import EEGEncoder, EEGSTFEncoder
from MYmodel import EEGClassifier, EEGClassifierCNN
import torch
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR, CosineAnnealingWarmRestarts  # 余弦退火的两个版本

import os
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingWarmRestarts

import os
import time
import random
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import numpy as np
from loaddata import EEGDataLoader
from encode import EEGSTFEncoder  # 只保留EEGSTFEncoder，移除EEGEncoder
from MYmodel import EEGClassifier, EEGClassifierCNN  # 保留分类器
# ==================== 补充缺失的import（matplotlib） ====================
import matplotlib.pyplot as plt
from torch.optim.lr_scheduler import CosineAnnealingWarmRestarts

# 设置matplotlib样式（确保英文显示正常）
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 10
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['legend.fontsize'] = 10
plt.rcParams['figure.dpi'] = 100
plt.rcParams['savefig.dpi'] = 300

# ==================== 固定随机种子的函数 ====================
def set_seed(seed=42):
    """固定所有核心的随机种子，保证实验可重复性"""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    os.environ['PYTHONHASHSEED'] = str(seed)

# ==================== 日志写入函数 ====================
def write_log(message):
    """同时向控制台和日志文件写入信息"""
    print(message)
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(message + '\n')

# ==================== 训练/评估函数 ====================
def train_epoch(model, train_loader, criterion, optimizer, scheduler, device):
    """训练一个epoch（新增scheduler参数）"""
    model.train()
    total_loss = 0.0
    all_preds = []
    all_labels = []
    
    for batch_data, batch_labels in train_loader:
        batch_data = batch_data.to(device)
        batch_labels = batch_labels.to(device)
        
        optimizer.zero_grad()
        outputs = model(batch_data)
        loss = criterion(outputs, batch_labels)
        
        loss.backward()
        optimizer.step()
        
        total_loss += loss.item() * batch_data.size(0)
        _, preds = torch.max(outputs, 1)
        all_preds.extend(preds.cpu().numpy())
        all_labels.extend(batch_labels.cpu().numpy())
    
    # 学习率调度器步进（每个epoch更新一次）
    if scheduler is not None:
        scheduler.step()
    
    avg_loss = total_loss / len(train_loader.dataset)
    acc = accuracy_score(all_labels, all_preds)
    precision = precision_score(all_labels, all_preds, average='weighted', zero_division=0)
    recall = recall_score(all_labels, all_preds, average='weighted', zero_division=0)
    f1 = f1_score(all_labels, all_preds, average='weighted', zero_division=0)
    
    return avg_loss, acc, precision, recall, f1

def evaluate(model, data_loader, criterion, device):
    """在验证集或测试集上评估模型"""
    model.eval()
    total_loss = 0.0
    all_preds = []
    all_labels = []
    
    with torch.no_grad():
        for batch_data, batch_labels in data_loader:
            batch_data = batch_data.to(device)
            batch_labels = batch_labels.to(device)
            
            outputs = model(batch_data)
            loss = criterion(outputs, batch_labels)
            
            total_loss += loss.item() * batch_data.size(0)
            _, preds = torch.max(outputs, 1)
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(batch_labels.cpu().numpy())
    
    avg_loss = total_loss / len(data_loader.dataset)
    acc = accuracy_score(all_labels, all_preds)
    precision = precision_score(all_labels, all_preds, average='weighted', zero_division=0)
    recall = recall_score(all_labels, all_preds, average='weighted', zero_division=0)
    f1 = f1_score(all_labels, all_preds, average='weighted', zero_division=0)
    
    return avg_loss, acc, precision, recall, f1

# ==================== 绘图函数（提取为全局函数） ====================
def plot_training_metrics(subject_id, train_metrics, val_metrics, num_epochs, save_dir):
    """
    绘制训练指标图表
    train_metrics/val_metrics: [losses, accs, precisions, recalls, f1s]
    """
    os.makedirs(save_dir, exist_ok=True)
    train_losses, train_accs, train_precisions, train_recalls, train_f1s = train_metrics
    val_losses, val_accs, val_precisions, val_recalls, val_f1s = val_metrics
    epochs = range(1, num_epochs + 1)
    
    # 1. Loss Curve
    plt.figure(figsize=(10, 6))
    plt.plot(epochs, train_losses, 'b-', label='Training Loss', linewidth=1)
    plt.plot(epochs, val_losses, 'r-', label='Validation Loss', linewidth=1)
    plt.title(f'Training and Validation Loss - Subject {subject_id}')
    plt.xlabel('Epochs')
    plt.ylabel('Loss')
    plt.legend(loc='upper right')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, f"{subject_id}_loss_curve.png"), bbox_inches='tight')
    plt.close()
    
    # 2. Accuracy Curve
    plt.figure(figsize=(10, 6))
    plt.plot(epochs, train_accs, 'b-', label='Training Accuracy', linewidth=1)
    plt.plot(epochs, val_accs, 'r-', label='Validation Accuracy', linewidth=1)
    plt.title(f'Training and Validation Accuracy - Subject {subject_id}')
    plt.xlabel('Epochs')
    plt.ylabel('Accuracy')
    plt.ylim(0, 1.05)
    plt.legend(loc='lower right')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, f"{subject_id}_accuracy_curve.png"), bbox_inches='tight')
    plt.close()
    
    # 3. Combined Classification Metrics (4 in 1)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle(f'Classification Metrics Summary - Subject {subject_id}', fontsize=16)
    
    # Accuracy
    axes[0,0].plot(epochs, train_accs, 'b-', label='Training')
    axes[0,0].plot(epochs, val_accs, 'r-', label='Validation')
    axes[0,0].set_title('Accuracy')
    axes[0,0].set_xlabel('Epochs')
    axes[0,0].set_ylabel('Accuracy')
    axes[0,0].set_ylim(0, 1.05)
    axes[0,0].legend()
    axes[0,0].grid(True, alpha=0.3)
    
    # Precision
    axes[0,1].plot(epochs, train_precisions, 'b-', label='Training')
    axes[0,1].plot(epochs, val_precisions, 'r-', label='Validation')
    axes[0,1].set_title('Precision')
    axes[0,1].set_xlabel('Epochs')
    axes[0,1].set_ylabel('Precision')
    axes[0,1].set_ylim(0, 1.05)
    axes[0,1].legend()
    axes[0,1].grid(True, alpha=0.3)
    
    # Recall
    axes[1,0].plot(epochs, train_recalls, 'b-', label='Training')
    axes[1,0].plot(epochs, val_recalls, 'r-', label='Validation')
    axes[1,0].set_title('Recall')
    axes[1,0].set_xlabel('Epochs')
    axes[1,0].set_ylabel('Recall')
    axes[1,0].set_ylim(0, 1.05)
    axes[1,0].legend()
    axes[1,0].grid(True, alpha=0.3)
    
    # F1-Score
    axes[1,1].plot(epochs, train_f1s, 'b-', label='Training')
    axes[1,1].plot(epochs, val_f1s, 'r-', label='Validation')
    axes[1,1].set_title('F1-Score')
    axes[1,1].set_xlabel('Epochs')
    axes[1,1].set_ylabel('F1-Score')
    axes[1,1].set_ylim(0, 1.05)
    axes[1,1].legend()
    axes[1,1].grid(True, alpha=0.3)
    
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(os.path.join(save_dir, f"{subject_id}_classification_metrics.png"), bbox_inches='tight')
    plt.close()
    
    write_log(f"\nTraining metrics plots saved to: {save_dir}")

# ==================== 主函数 ====================
def main():
    # ==================== 核心配置（适配EEGSTFEncoder） ====================
    config = {
        'data': {
            'sample_rate': 250,
            'cutoff_frequency': 50,
            'data_path': '/home/zengkai/model_compare/data/BNCI2014_001',
            'target_length': 1000,
            'channels': 22,
            'augment_data': False,
            'data_mode': 'single',  # 'cross'（跨被试）/'single'（单被试）
            'single_subject_id': 'A01',
            'single_train_ratio': 0.7,
            'single_val_ratio': 0.15,
            'single_seed': 42,
            'seed': 42
        },
        'norm': {
            'norm_type': 'z_score',
            'norm_axis': (0, 2),
            'sample_axis': (1, 2),
            'min_max_range': (-1, 1),
            'eps': 1e-8
        },
        'model': {
            # EEGSTFEncoder核心参数（移除无效的rhythm_mode/time_feature_enabled）
            'window_length': 250,
            'step_length': 50,
            'merge_enabled': False,
            'merge_threshold': 0.9,
            'patch_enabled': True,
            'n_head': 8,
            'num_classes': 4,
            # 空洞卷积自定义参数（可选）
            'dilated_conv_channels': [40, 32, 16],
            'dilated_conv_kernels': [3, 3, 3],
            'dilated_conv_dilations': [1, 2, 4],
            # Transformer参数
            'num_transformer_layers': 1,
            'dim_feedforward': 64,
            # 分类器参数
            'dropout_rate': 0.3,
            'use_batch_norm': True,
            'use_residual': True  # Transformer残差连接
        },
        'training': {
            'device': 'cuda' if torch.cuda.is_available() else 'cpu',
            'val_ratio': 0.2,
            'batch_size': 128,
            'lr': 5e-4,
            'weight_decay': 1e-3,
            'epochs': 2000,
            # 余弦退火调度器参数
            "cosine_t0": 100,
            "cosine_t_mult": 2,
            "cosine_eta_min": 1e-5,
            # 绘图保存路径
            'plot_save_dir': '/home/zengkai/SSM-EEG/code/Space_freq/training_plots'
        },
        'logging': {
            'log_dir': '/home/zengkai/SSM-EEG/code/Space_freq',
            'log_file': 'training_log.txt'
        }
    }

    # ==================== 初始化日志 ====================
    global log_path
    os.makedirs(config['logging']['log_dir'], exist_ok=True)
    log_path = os.path.join(config['logging']['log_dir'], config['logging']['log_file'])
    
    # ==================== 固定种子 ====================
    set_seed(config['data']['seed'])
    write_log(f"已固定随机种子为: {config['data']['seed']}")

    # ==================== 记录基础信息 ====================
    start_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    write_log(f"===== 训练开始时间: {start_time} =====")
    write_log(f"使用设备: {config['training']['device']}")
    write_log(f"运行模式: {config['data']['data_mode']}")
    if config['data']['data_mode'] == 'single':
        write_log(f"单被试ID: {config['data']['single_subject_id']}")
        write_log(f"数据划分比例：训练{config['data']['single_train_ratio']*100:.1f}% | "
                  f"验证{config['data']['single_val_ratio']*100:.1f}% | "
                  f"测试{(1-config['data']['single_train_ratio']-config['data']['single_val_ratio'])*100:.1f}%")
    write_log(f"配置信息: {str(config)}\n")
    
    # ==================== 初始化数据加载器 ====================
    loader = EEGDataLoader(config)
    all_test_results = []

    # ==================== 分支1：跨被试模式（留一法） ====================
    if config['data']['data_mode'] == 'cross':
        loader.load_all_subjects()
        
        for test_sub in loader.all_subjects:
            write_log(f"\n{'='*60}")
            write_log(f"当前测试被试: {test_sub}")
            write_log(f"{'='*60}")
            
            # 划分数据集
            train_dataset, val_dataset, test_dataset = loader.leave_one_out_split(
                test_sub, val_ratio=config['training']['val_ratio']
            )
            
            # 创建数据加载器
            train_loader, val_loader, test_loader = loader.get_data_loaders(
                train_dataset, val_dataset, test_dataset,
                batch_size=config['training']['batch_size']
            )
            
            # -------------------------- 初始化模型 --------------------------
            # 初始化EEGSTFEncoder（适配所有参数）
            encoder = EEGSTFEncoder(
                window_length=config['model']['window_length'],
                step_length=config['model']['step_length'],
                fs=config['data']['sample_rate'],
                max_freq=config['data']['cutoff_frequency'],
                merge_threshold=config['model']['merge_threshold'],
                merge_enabled=config['model']['merge_enabled'],
                patch_enabled=config['model']['patch_enabled'],
                d_model=None,  # 自动计算适配n_head的维度
                n_head=config['model']['n_head'],
                dilated_conv_channels=config['model']['dilated_conv_channels'],
                dilated_conv_kernels=config['model']['dilated_conv_kernels'],
                dilated_conv_dilations=config['model']['dilated_conv_dilations']
            )
            
            # 初始化Transformer分类器
            device = config['training']['device']
            model = EEGClassifier(
                eeg_encoder=encoder,
                num_classes=config['model']['num_classes'],
                nhead=config['model']['n_head'],
                num_transformer_layers=config['model']['num_transformer_layers'],
                dim_feedforward=config['model']['dim_feedforward'],
                dropout_rate=config['model']['dropout_rate'],
                use_batch_norm=config['model']['use_batch_norm'],
                use_residual=config['model']['use_residual']
            ).to(device)
            
            # 定义损失函数、优化器、调度器
            criterion = nn.CrossEntropyLoss()
            optimizer = optim.AdamW(
                model.parameters(),
                lr=config['training']['lr'],
                weight_decay=config['training']['weight_decay']
            )
            scheduler = CosineAnnealingWarmRestarts(
                optimizer,
                T_0=config['training']['cosine_t0'],
                T_mult=config['training']['cosine_t_mult'],
                eta_min=config['training']['cosine_eta_min'],
                verbose=False  # 关闭调度器日志（避免刷屏）
            )
            
            # -------------------------- 训练过程 --------------------------
            # 初始化指标记录
            train_losses, val_losses = [], []
            train_accs, val_accs = [], []
            train_precisions, val_precisions = [], []
            train_recalls, val_recalls = [], []
            train_f1s, val_f1s = [], []
            
            best_val_acc = 0.0
            best_epoch = 0
            num_epochs = config['training']['epochs']
            
            for epoch in range(num_epochs):
                # 训练
                train_loss, train_acc, train_precision, train_recall, train_f1 = train_epoch(
                    model, train_loader, criterion, optimizer, scheduler, device
                )
                
                # 验证
                val_loss, val_acc, val_precision, val_recall, val_f1 = evaluate(
                    model, val_loader, criterion, device
                )
                
                # 记录指标
                train_losses.append(train_loss)
                val_losses.append(val_loss)
                train_accs.append(train_acc)
                val_accs.append(val_acc)
                train_precisions.append(train_precision)
                val_precisions.append(val_precision)
                train_recalls.append(train_recall)
                val_recalls.append(val_recall)
                train_f1s.append(train_f1)
                val_f1s.append(val_f1)
                
                # 日志输出
                log_msg = f"Epoch {epoch+1}/{num_epochs}\n"
                log_msg += f"  Training - Loss: {train_loss:.4f}, Accuracy: {train_acc:.4f}, "
                log_msg += f"Precision: {train_precision:.4f}, Recall: {train_recall:.4f}, F1: {train_f1:.4f}\n"
                log_msg += f"  Validation - Loss: {val_loss:.4f}, Accuracy: {val_acc:.4f}, "
                log_msg += f"Precision: {val_precision:.4f}, Recall: {val_recall:.4f}, F1: {val_f1:.4f}"
                write_log(log_msg)
                
                # 跟踪最佳模型
                if val_acc > best_val_acc:
                    best_val_acc = val_acc
                    best_epoch = epoch + 1
            
            # -------------------------- 评估与绘图 --------------------------
            write_log(f"\n最佳验证准确率: {best_val_acc:.4f} (在第 {best_epoch} 轮)")
            
            # 测试集评估
            test_loss, test_acc, test_precision, test_recall, test_f1 = evaluate(
                model, test_loader, criterion, device
            )
            
            test_msg = f"\n测试集结果:\n"
            test_msg += f"  损失: {test_loss:.4f}, 准确率: {test_acc:.4f}\n"
            test_msg += f"  精确率: {test_precision:.4f}, 召回率: {test_recall:.4f}, F1: {test_f1:.4f}"
            write_log(test_msg)
            
            all_test_results.append({
                'subject': test_sub,
                'acc': test_acc,
                'precision': test_precision,
                'recall': test_recall,
                'f1': test_f1
            })
            
            # 绘制跨被试单被试的训练曲线
            train_metrics = [train_losses, train_accs, train_precisions, train_recalls, train_f1s]
            val_metrics = [val_losses, val_accs, val_precisions, val_recalls, val_f1s]
            plot_training_metrics(
                test_sub, train_metrics, val_metrics, num_epochs,
                config['training']['plot_save_dir']
            )

    # ==================== 分支2：单被试模式 ====================
    elif config['data']['data_mode'] == 'single':
        single_sub_id = config['data']['single_subject_id']
        write_log(f"\n{'='*60}")
        write_log(f"单被试模式：加载被试 {single_sub_id}")
        write_log(f"{'='*60}")
        
        # 加载单被试数据
        try:
            loader.load_single_subject(single_sub_id)
        except ValueError as e:
            write_log(f"错误：{e}")
            return
        
        # 划分数据集
        train_dataset, val_dataset, test_dataset = loader.train_test_split_single_subject(
            single_sub_id, 
            train_ratio=config['data']['single_train_ratio'],
            val_ratio=config['data']['single_val_ratio'],
            seed=config['data']['single_seed']
        )
        
        # 创建数据加载器
        train_loader, val_loader, test_loader = loader.get_data_loaders(
            train_dataset, val_dataset, test_dataset,
            batch_size=config['training']['batch_size']
        )
        
        # -------------------------- 初始化模型 --------------------------
        # 初始化EEGSTFEncoder（核心修正：移除EEGEncoder，统一用EEGSTFEncoder）
        encoder = EEGSTFEncoder(
            window_length=config['model']['window_length'],
            step_length=config['model']['step_length'],
            fs=config['data']['sample_rate'],
            max_freq=config['data']['cutoff_frequency'],
            merge_threshold=config['model']['merge_threshold'],
            merge_enabled=config['model']['merge_enabled'],
            patch_enabled=config['model']['patch_enabled'],
            d_model=None,
            n_head=config['model']['n_head'],
            dilated_conv_channels=config['model']['dilated_conv_channels'],
            dilated_conv_kernels=config['model']['dilated_conv_kernels'],
            dilated_conv_dilations=config['model']['dilated_conv_dilations']
        )
        
        # 初始化分类器
        device = config['training']['device']
        model = EEGClassifier(
            eeg_encoder=encoder,
            num_classes=config['model']['num_classes'],
            nhead=config['model']['n_head'],
            num_transformer_layers=config['model']['num_transformer_layers'],
            dim_feedforward=config['model']['dim_feedforward'],
            dropout_rate=config['model']['dropout_rate'],
            use_batch_norm=config['model']['use_batch_norm'],
            use_residual=config['model']['use_residual']
        ).to(device)

        # 定义损失函数、优化器、调度器
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.AdamW(
            model.parameters(),
            lr=config['training']['lr'],
            weight_decay=config['training']['weight_decay']
        )
        scheduler = CosineAnnealingWarmRestarts(
            optimizer,
            T_0=config['training']['cosine_t0'],
            T_mult=config['training']['cosine_t_mult'],
            eta_min=config['training']['cosine_eta_min'],
            verbose=False
        )
        
        # -------------------------- 训练过程 --------------------------
        train_losses, val_losses = [], []
        train_accs, val_accs = [], []
        train_precisions, val_precisions = [], []
        train_recalls, val_recalls = [], []
        train_f1s, val_f1s = [], []
        
        best_val_acc = 0.0
        best_epoch = 0
        num_epochs = config['training']['epochs']
        
        for epoch in range(num_epochs):
            # 训练
            train_loss, train_acc, train_precision, train_recall, train_f1 = train_epoch(
                model, train_loader, criterion, optimizer, scheduler, device
            )
            
            # 验证
            val_loss, val_acc, val_precision, val_recall, val_f1 = evaluate(
                model, val_loader, criterion, device
            )
            
            # 记录指标
            train_losses.append(train_loss)
            val_losses.append(val_loss)
            train_accs.append(train_acc)
            val_accs.append(val_acc)
            train_precisions.append(train_precision)
            val_precisions.append(val_precision)
            train_recalls.append(train_recall)
            val_recalls.append(val_recall)
            train_f1s.append(train_f1)
            val_f1s.append(val_f1)
            
            # 日志输出
            log_msg = f"Epoch {epoch+1}/{num_epochs}\n"
            log_msg += f"  Training - Loss: {train_loss:.4f}, Accuracy: {train_acc:.4f}, "
            log_msg += f"Precision: {train_precision:.4f}, Recall: {train_recall:.4f}, F1: {train_f1:.4f}\n"
            log_msg += f"  Validation - Loss: {val_loss:.4f}, Accuracy: {val_acc:.4f}, "
            log_msg += f"Precision: {val_precision:.4f}, Recall: {val_recall:.4f}, F1: {val_f1:.4f}"
            write_log(log_msg)
            
            # 跟踪最佳模型
            if val_acc > best_val_acc:
                best_val_acc = val_acc
                best_epoch = epoch + 1
        
        # -------------------------- 评估与绘图 --------------------------
        write_log(f"\nBest Validation Accuracy: {best_val_acc:.4f} (at Epoch {best_epoch})")
        
        # 测试集评估
        test_loss, test_acc, test_precision, test_recall, test_f1 = evaluate(
            model, test_loader, criterion, device
        )
        
        test_msg = f"\nTest Set Results:\n"
        test_msg += f"  Loss: {test_loss:.4f}, Accuracy: {test_acc:.4f}\n"
        test_msg += f"  Precision: {test_precision:.4f}, Recall: {test_recall:.4f}, F1: {test_f1:.4f}"
        write_log(test_msg)
        
        all_test_results.append({
            'subject': single_sub_id,
            'acc': test_acc,
            'precision': test_precision,
            'recall': test_recall,
            'f1': test_f1
        })

        # 绘制训练曲线
        train_metrics = [train_losses, train_accs, train_precisions, train_recalls, train_f1s]
        val_metrics = [val_losses, val_accs, val_precisions, val_recalls, val_f1s]
        plot_training_metrics(
            single_sub_id, train_metrics, val_metrics, num_epochs,
            config['training']['plot_save_dir']
        )

    # ==================== 非法模式处理 ====================
    else:
        write_log(f"错误：无效的data_mode {config['data']['data_mode']}，请选择'single'或'cross'")
        return

    # ==================== 结果统计 ====================
    avg_acc = np.mean([r['acc'] for r in all_test_results])
    avg_precision = np.mean([r['precision'] for r in all_test_results])
    avg_recall = np.mean([r['recall'] for r in all_test_results])
    avg_f1 = np.mean([r['f1'] for r in all_test_results])
    
    write_log(f"\n{'='*60}")
    if config['data']['data_mode'] == 'cross':
        write_log("所有被试平均测试结果:")
    else:
        write_log(f"单被试 {config['data']['single_subject_id']} 测试结果:")
    write_log(f"平均准确率: {avg_acc:.4f}")
    write_log(f"平均精确率: {avg_precision:.4f}")
    write_log(f"平均召回率: {avg_recall:.4f}")
    write_log(f"平均F1分数: {avg_f1:.4f}")
    write_log(f"{'='*60}")
    
    # 记录结束时间
    end_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    write_log(f"\n===== 训练结束时间: {end_time} =====")

if __name__ == "__main__":
    main()