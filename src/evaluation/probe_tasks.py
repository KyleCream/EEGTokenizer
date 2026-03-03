import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.metrics import accuracy_score, f1_score
import numpy as np
from typing import Dict, Tuple


class SimpleProbe(nn.Module):
    """简单探针分类器"""
    
    def __init__(self, input_dim: int, num_classes: int, hidden_dim: int = 64):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(hidden_dim, num_classes)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.fc1(x)
        x = self.relu(x)
        x = self.fc2(x)
        return x


class ProbeTaskEvaluator:
    """
    探针任务评估器
    
    在冻结 tokenizer 的情况下，评估表示质量
    """
    
    def __init__(
        self,
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
        lr: float = 1e-3,
        epochs: int = 50,
        batch_size: int = 32
    ):
        self.device = device
        self.lr = lr
        self.epochs = epochs
        self.batch_size = batch_size
    
    def _extract_features(
        self,
        tokenizer: nn.Module,
        data_loader: torch.utils.data.DataLoader
    ) -> Tuple[np.ndarray, np.ndarray]:
        """提取 tokenizer 的特征表示"""
        tokenizer.eval()
        all_features = []
        all_labels = []
        
        with torch.no_grad():
            for batch_data, batch_labels in data_loader:
                batch_data = batch_data.to(self.device)
                features, _ = tokenizer(batch_data)
                
                # 对序列维度做平均池化 (batch, n_patches, d_model) -> (batch, d_model)
                pooled_features = torch.mean(features, dim=1)
                
                all_features.append(pooled_features.cpu().numpy())
                all_labels.append(batch_labels.numpy())
        
        return np.concatenate(all_features, axis=0), np.concatenate(all_labels, axis=0)
    
    def evaluate_classification(
        self,
        tokenizer: nn.Module,
        train_loader: torch.utils.data.DataLoader,
        val_loader: torch.utils.data.DataLoader,
        num_classes: int = 4
    ) -> Dict[str, float]:
        """
        评估分类探针任务
        
        返回:
            {
                'train_acc': 训练集准确率,
                'val_acc': 验证集准确率,
                'val_f1': 验证集 F1 分数
            }
        """
        # 1. 提取特征
        print("Extracting training features...")
        train_features, train_labels = self._extract_features(tokenizer, train_loader)
        print("Extracting validation features...")
        val_features, val_labels = self._extract_features(tokenizer, val_loader)
        
        # 2. 创建数据加载器
        train_dataset = torch.utils.data.TensorDataset(
            torch.tensor(train_features, dtype=torch.float32),
            torch.tensor(train_labels, dtype=torch.long)
        )
        val_dataset = torch.utils.data.TensorDataset(
            torch.tensor(val_features, dtype=torch.float32),
            torch.tensor(val_labels, dtype=torch.long)
        )
        
        train_loader_probe = torch.utils.data.DataLoader(
            train_dataset, batch_size=self.batch_size, shuffle=True
        )
        val_loader_probe = torch.utils.data.DataLoader(
            val_dataset, batch_size=self.batch_size, shuffle=False
        )
        
        # 3. 初始化探针模型
        input_dim = train_features.shape[1]
        probe = SimpleProbe(input_dim, num_classes).to(self.device)
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(probe.parameters(), lr=self.lr)
        
        # 4. 训练探针
        best_val_acc = 0.0
        best_val_f1 = 0.0
        
        for epoch in range(self.epochs):
            probe.train()
            train_preds = []
            train_true = []
            
            for batch_x, batch_y in train_loader_probe:
                batch_x = batch_x.to(self.device)
                batch_y = batch_y.to(self.device)
                
                optimizer.zero_grad()
                outputs = probe(batch_x)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                
                _, preds = torch.max(outputs, 1)
                train_preds.extend(preds.cpu().numpy())
                train_true.extend(batch_y.cpu().numpy())
            
            # 验证
            probe.eval()
            val_preds = []
            val_true = []
            
            with torch.no_grad():
                for batch_x, batch_y in val_loader_probe:
                    batch_x = batch_x.to(self.device)
                    outputs = probe(batch_x)
                    _, preds = torch.max(outputs, 1)
                    val_preds.extend(preds.cpu().numpy())
                    val_true.extend(batch_y.numpy())
            
            # 计算指标
            train_acc = accuracy_score(train_true, train_preds)
            val_acc = accuracy_score(val_true, val_preds)
            val_f1 = f1_score(val_true, val_preds, average='weighted')
            
            if val_acc > best_val_acc:
                best_val_acc = val_acc
                best_val_f1 = val_f1
        
        return {
            'train_acc': float(train_acc),
            'val_acc': float(best_val_acc),
            'val_f1': float(best_val_f1)
        }
