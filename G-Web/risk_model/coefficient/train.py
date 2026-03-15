import os
import pickle
from typing import Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import yaml

from transformer_encoder import NodeTransformerEncoder
from gnn_model import GNNModel, frobenius_norm_loss, relative_frobenius_loss
from datasets import get_dataloaders


def _read_yaml_config(path: str):
    """读取 YAML 配置。"""
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def set_seed(seed: int = 42):
    """设置随机种子，确保可复现。"""
    import random
    import numpy as np
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def load_numpy_arrays(cfg):
    """加载预处理阶段保存的 numpy 数据。"""
    data_dir = "data"
    
    # 加载训练集数据
    train_node_feats = np.load(os.path.join(data_dir, "train_node_features_norm.npy"))
    train_edge_feat = np.load(os.path.join(data_dir, "train_edge_features.npy"))
    train_targets = np.load(os.path.join(data_dir, "train_targets.npy"))
    
    # 加载测试集数据
    test_node_feats = np.load(os.path.join(data_dir, "test_node_features_norm.npy"))
    test_edge_feat = np.load(os.path.join(data_dir, "test_edge_features.npy"))
    test_targets = np.load(os.path.join(data_dir, "test_targets.npy"))
    
    return (train_node_feats, train_edge_feat, train_targets, 
            test_node_feats, test_edge_feat, test_targets)


def train_model(config_path: str = 'configs/variables.yaml'):
    """训练入口：加载数据 → 编码器+GNN → 优化 → 保存模型与训练曲线。"""
    cfg = _read_yaml_config(config_path)
    set_seed(int(cfg['project'].get('seed', 42)))

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    (train_node_feats, train_edge_feat, train_targets,
     test_node_feats, test_edge_feat, test_targets) = load_numpy_arrays(cfg)

    train_loader, test_loader = get_dataloaders(
        train_node_feats=train_node_feats,
        train_edge_feat=train_edge_feat,
        train_targets=train_targets,
        test_node_feats=test_node_feats,
        test_edge_feat=test_edge_feat,
        test_targets=test_targets,
        batch_size=int(cfg['gnn_training']['batch_size']),
    )

    encoder = NodeTransformerEncoder(
        d_model=int(cfg['transformer']['d_model']),
        nhead=int(cfg['transformer']['nhead']),
        num_layers=int(cfg['transformer']['num_layers']),
        dropout=float(cfg['transformer']['dropout']),
    ).to(device).double()

    gnn = GNNModel(
        node_in_dim=int(cfg['transformer']['d_model']),
        hidden_dim=int(cfg['gnn_training']['hidden_dim']),
        num_layers=int(cfg['gnn_training']['num_layers']),
        num_heads=int(cfg['gnn_training']['num_heads']),
        dropout=float(cfg['gnn_training']['dropout']),
    ).to(device).double()

    params = list(encoder.parameters()) + list(gnn.parameters())
    # 从配置文件读取学习率和权重衰减参数
    optimizer = optim.Adam(
        params, 
        lr=float(cfg['gnn_training']['lr']), 
        weight_decay=float(cfg['gnn_training']['weight_decay'])
    )
    
    # 添加学习率调度器
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=5)

    epochs = int(cfg['gnn_training']['epochs'])

    os.makedirs('results', exist_ok=True)
    train_losses = []

    for epoch in range(1, epochs + 1):
        encoder.train(); gnn.train()
        epoch_loss = 0.0
        for nf, ef, tg in train_loader:
            nf = nf.to(device)
            ef = ef.to(device)
            tg = tg.to(device)

            optimizer.zero_grad()
            enc = encoder(nf)  # [B, N, d_model]
            pred = gnn(enc, ef)  # [B, N, N] - 预测的相关系数矩阵
            loss = frobenius_norm_loss(pred, tg)
            
            # 检查损失值
            if torch.isnan(loss) or torch.isinf(loss):
                print(f"警告：检测到NaN或无穷损失值，跳过此批次")
                continue
                
            loss.backward()
            
            # 更严格的梯度裁剪
            torch.nn.utils.clip_grad_norm_(params, max_norm=0.5)
            
            optimizer.step()
            epoch_loss += loss.item() * nf.size(0)
        epoch_loss /= len(train_loader.dataset)
        train_losses.append(epoch_loss)

        print(f"Epoch {epoch:03d} | TrainLoss {epoch_loss:.8f}")
        
        # 更新学习率（使用训练损失）
        scheduler.step(epoch_loss)

    # 保存模型
    model_path = cfg['gnn_training']['save_model_path']
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    torch.save({
        'encoder_state_dict': encoder.state_dict(),
        'gnn_state_dict': gnn.state_dict(),
        'config': cfg,
    }, model_path)

    # 保存训练曲线
    np.save(os.path.join('results', 'train_losses.npy'), np.array(train_losses, dtype=np.float64))

    print("训练完成，模型已保存。")


if __name__ == '__main__':
    train_model()


