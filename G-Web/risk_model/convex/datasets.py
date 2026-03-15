import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from typing import Tuple
import os


class StockDataset(Dataset):
    """股票数据集类，用于加载预处理后的图数据。"""
    
    def __init__(self, node_features: np.ndarray, edge_features: np.ndarray, targets: np.ndarray):
        """
        初始化数据集。
        
        Args:
            node_features: 节点特征 [n_samples, n_stocks, 36, 100]
            edge_features: 边特征 [n_samples, n_stocks, n_stocks]
            targets: 目标 [n_samples, n_stocks, n_stocks]
        """
        self.node_features = torch.DoubleTensor(node_features)
        self.edge_features = torch.DoubleTensor(edge_features)
        self.targets = torch.DoubleTensor(targets)
        
        print(f"数据集初始化完成:")
        print(f"  节点特征形状: {self.node_features.shape}")
        print(f"  边特征形状: {self.edge_features.shape}")
        print(f"  目标形状: {self.targets.shape}")
    
    def __len__(self) -> int:
        return len(self.node_features)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        获取单个样本。
        
        Args:
            idx: 样本索引
            
        Returns:
            (node_features, edge_features, targets)
        """
        return (
            self.node_features[idx],  # [n_stocks, 36, 100]
            self.edge_features[idx],  # [n_stocks, n_stocks]
            self.targets[idx]         # [n_stocks, n_stocks]
        )


def load_train_dataset(data_dir: str = "data", use_normalized: bool = True) -> StockDataset:
    """加载训练数据集。
    
    Args:
        data_dir: 数据目录
        use_normalized: 是否使用标准化后的节点特征
        
    Returns:
        训练数据集
    """
    print("加载训练数据集...")
    
    # 选择使用原始特征还是标准化特征
    if use_normalized:
        node_features = np.load(os.path.join(data_dir, "train_node_features_norm.npy"))
        print("使用标准化后的节点特征")
    else:
        node_features = np.load(os.path.join(data_dir, "train_node_features_raw.npy"))
        print("使用原始节点特征")
    
    edge_features = np.load(os.path.join(data_dir, "train_edge_features.npy"))
    targets = np.load(os.path.join(data_dir, "train_targets.npy"))
    
    return StockDataset(node_features, edge_features, targets)


def load_test_dataset(data_dir: str = "data", use_normalized: bool = True) -> StockDataset:
    """加载测试数据集。
    
    Args:
        data_dir: 数据目录
        use_normalized: 是否使用标准化后的节点特征
        
    Returns:
        测试数据集
    """
    print("加载测试数据集...")
    
    # 选择使用原始特征还是标准化特征
    if use_normalized:
        node_features = np.load(os.path.join(data_dir, "test_node_features_norm.npy"))
        print("使用标准化后的节点特征")
    else:
        node_features = np.load(os.path.join(data_dir, "test_node_features_raw.npy"))
        print("使用原始节点特征")
    
    edge_features = np.load(os.path.join(data_dir, "test_edge_features.npy"))
    targets = np.load(os.path.join(data_dir, "test_targets.npy"))
    
    return StockDataset(node_features, edge_features, targets)


def get_data_info(data_dir: str = "data") -> dict:
    """获取数据集的基本信息。
    
    Args:
        data_dir: 数据目录
        
    Returns:
        包含数据集信息的字典
    """
    try:
        # 加载训练集信息
        train_node = np.load(os.path.join(data_dir, "train_node_features_raw.npy"))
        train_edge = np.load(os.path.join(data_dir, "train_edge_features.npy"))
        train_targets = np.load(os.path.join(data_dir, "train_targets.npy"))
        
        # 加载测试集信息
        test_node = np.load(os.path.join(data_dir, "test_node_features_raw.npy"))
        test_edge = np.load(os.path.join(data_dir, "test_edge_features.npy"))
        test_targets = np.load(os.path.join(data_dir, "test_targets.npy"))
        
        info = {
            "train_samples": train_node.shape[0],
            "test_samples": test_node.shape[0],
            "n_stocks": train_node.shape[1],
            "n_features": train_node.shape[2],
            "lookback_days": train_node.shape[3],             
            "edge_dim": (train_edge.shape[1], train_edge.shape[2]),
            "target_dim": (train_targets.shape[1], train_targets.shape[2]),
            "standardization_method": "per_sample",  # 标注标准化方法
            "note": "每个样本的特征矩阵独立标准化，按特征维度进行"
        }
        
        return info
        
    except Exception as e:
        print(f"获取数据信息失败: {e}")
        return {}


def get_dataloaders(
    train_node_feats: np.ndarray,
    train_edge_feat: np.ndarray, 
    train_targets: np.ndarray,
    test_node_feats: np.ndarray,
    test_edge_feat: np.ndarray,
    test_targets: np.ndarray,
    batch_size: int = 16
) -> tuple:
    """
    创建训练和测试数据加载器。
    
    Args:
        train_node_feats: 训练集节点特征 [n_samples, n_stocks, 36, 100]
        train_edge_feat: 训练集边特征 [n_samples, n_stocks, n_stocks]
        train_targets: 训练集目标 [n_samples, n_stocks, n_stocks]
        test_node_feats: 测试集节点特征 [n_samples, n_stocks, 36, 100]
        test_edge_feat: 测试集边特征 [n_samples, n_stocks, n_stocks]
        test_targets: 测试集目标 [n_samples, n_stocks, n_stocks]
        batch_size: 批次大小
        
    Returns:
        (train_loader, test_loader)
    """
    # 创建训练数据集
    train_dataset = StockDataset(train_node_feats, train_edge_feat, train_targets)
    
    # 创建测试数据集
    test_dataset = StockDataset(test_node_feats, test_edge_feat, test_targets)
    
    # 创建数据加载器
    train_loader = DataLoader(
        train_dataset, 
        batch_size=batch_size, 
        shuffle=True,
        drop_last=False
    )
    
    test_loader = DataLoader(
        test_dataset, 
        batch_size=batch_size, 
        shuffle=False,
        drop_last=False
    )
    
    print(f"数据加载器创建完成:")
    print(f"  训练集: {len(train_dataset)} 样本, {len(train_loader)} 批次")
    print(f"  测试集: {len(test_dataset)} 样本, {len(test_loader)} 批次")
    print(f"  批次大小: {batch_size}")
    
    return train_loader, test_loader


