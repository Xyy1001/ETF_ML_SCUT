from typing import Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


class GraphConv(nn.Module):
    def __init__(self, in_dim: int, out_dim: int, dropout: float = 0.1):
        super().__init__()
        self.lin = nn.Linear(in_dim, out_dim)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, adj: torch.Tensor) -> torch.Tensor:
        # x: [B, N, F], adj: [B, N, N]
        # 优化版 GCN：y = D^{-1/2} (A + I) D^{-1/2} x W
        B, N, _ = x.shape
        
        # 1. 数值稳定性：限制邻接矩阵的值范围，防止极值
        adj = torch.clamp(adj, min=-10.0, max=10.0)
        
        # 2. 优化单位矩阵创建：使用更高效的方式
        I = torch.eye(N, device=x.device, dtype=adj.dtype)
        if B > 1:
            I = I.unsqueeze(0).expand(B, N, N)
        else:
            I = I.unsqueeze(0)
        
        # 3. 确保邻接矩阵对称性（对于无向图）
        adj_symmetric = (adj + adj.transpose(-2, -1)) * 0.5
        A_hat = adj_symmetric + I
        
        # 4. 优化度矩阵计算：使用更稳定的数值方法
        degree = A_hat.sum(dim=-1)  # [B, N]
        # 增加更大的数值稳定项，防止度为0的情况
        degree = torch.clamp(degree, min=1e-6)
        
        # 5. 计算度矩阵的逆平方根，使用更稳定的方法
        D_inv_sqrt = torch.pow(degree, -0.5)
        
        # 6. 检查并处理 NaN/无穷值
        if torch.isnan(D_inv_sqrt).any() or torch.isinf(D_inv_sqrt).any():
            print("Warning: NaN/Inf detected in D_inv_sqrt, replacing with safe values")
            D_inv_sqrt = torch.nan_to_num(D_inv_sqrt, nan=0.0, posinf=1.0, neginf=0.0)
        
        # 7. 使用广播进行归一化，避免创建大的对角矩阵
        # norm_adj = D_inv_sqrt @ A_hat @ D_inv_sqrt 的优化版本
        D_inv_sqrt_expanded = D_inv_sqrt.unsqueeze(-1)  # [B, N, 1]
        norm_adj = A_hat * D_inv_sqrt_expanded * D_inv_sqrt.unsqueeze(-2)  # [B, N, N]
        
        # 8. 再次检查归一化后的邻接矩阵
        if torch.isnan(norm_adj).any() or torch.isinf(norm_adj).any():
            print("Warning: NaN/Inf detected in normalized adjacency matrix")
            norm_adj = torch.nan_to_num(norm_adj, nan=0.0, posinf=1.0, neginf=0.0)
        
        # 9. 图卷积操作
        y = torch.bmm(norm_adj, x)  # 使用bmm进行批量矩阵乘法，更高效
        
        # 10. 线性变换前的数值检查
        if torch.isnan(y).any() or torch.isinf(y).any():
            print("Warning: NaN/Inf detected before linear transformation")
            y = torch.nan_to_num(y, nan=0.0, posinf=1.0, neginf=0.0)
        
        # 11. 限制激活函数前的值范围，防止梯度爆炸
        y = self.lin(y)
        y = torch.clamp(y, min=-10.0, max=10.0)
        
        return self.dropout(torch.relu(y))


class GNNModel(nn.Module):
    def __init__(self, node_in_dim: int = 32, hidden_dim: int = 32, num_layers: int = 2, dropout: float = 0.1):
        super().__init__()
        layers = []
        in_dim = node_in_dim
        for _ in range(num_layers):
            layers.append(GraphConv(in_dim, hidden_dim, dropout=dropout))
            in_dim = hidden_dim
        self.layers = nn.ModuleList(layers)

        # 解码器：基于节点对的 MLP，输出单个协方差矩阵，每个位置代表未来10天两只股票的协方差预测值
        pair_in = 2 * hidden_dim
        self.decoder = nn.Sequential(
            nn.Linear(pair_in, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 1),  # 为每个节点对输出1个协方差预测值
        )

    def forward(self, node_embeddings: torch.Tensor, edge_matrix: torch.Tensor) -> torch.Tensor:
        # node_embeddings: [B, N, 32], edge_matrix: [B, N, N]
        # N=26 表示26只股票，每个节点特征是32维向量
        x = node_embeddings
        for layer in self.layers:
            x = layer(x, edge_matrix)

        B, N, H = x.shape
        # 构造节点对特征
        xi = x.unsqueeze(2).expand(B, N, N, H)
        xj = x.unsqueeze(1).expand(B, N, N, H)
        pair = torch.cat([xi, xj], dim=-1)  # [B, N, N, 2H]

        # 解码得到每个节点对的协方差预测值（代表未来10天的协方差）
        pred = self.decoder(pair)  # [B, N, N, 1]
        pred = pred.squeeze(-1)  # [B, N, N] - 单个协方差矩阵
        return pred


def frobenius_mse_loss(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """Frobenius 范数的均方误差：对 [B, N, N] 协方差矩阵的逐元素平方后取平均。"""
    diff = pred - target
    loss = (diff ** 2).mean()
    return loss


