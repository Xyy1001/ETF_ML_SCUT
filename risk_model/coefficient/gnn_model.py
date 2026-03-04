from typing import Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


class GraphTransformerLayer(nn.Module):
    def __init__(self, in_dim: int, hidden_dim: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        self.num_heads = num_heads
        self.head_dim = hidden_dim // num_heads
        assert self.head_dim * num_heads == hidden_dim, "hidden_dim must be divisible by num_heads"

        self.q_lin = nn.Linear(in_dim, hidden_dim)
        self.k_lin = nn.Linear(in_dim, hidden_dim)
        self.v_lin = nn.Linear(in_dim, hidden_dim)
        self.out_lin = nn.Linear(hidden_dim, in_dim)

        self.edge_bias_lin = nn.Linear(1, num_heads, bias=False)

        self.dropout = nn.Dropout(dropout)
        self.layer_norm = nn.LayerNorm(in_dim)

    def forward(self, x: torch.Tensor, edge_matrix: torch.Tensor) -> torch.Tensor:
        # x: [B, N, F], edge_matrix: [B, N, N]
        B, N, _ = x.shape
        
        # 1. Project to Q, K, V
        q = self.q_lin(x).reshape(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.k_lin(x).reshape(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        v = self.v_lin(x).reshape(B, N, self.num_heads, self.head_dim).transpose(1, 2)

        # 2. Calculate raw attention scores
        attn_scores = torch.matmul(q, k.transpose(-2, -1)) / (self.head_dim ** 0.5)

        # 3. Inject structural bias from edge_matrix
        edge_bias = self.edge_bias_lin(edge_matrix.unsqueeze(-1)).permute(0, 3, 1, 2)
        attn_scores = attn_scores + edge_bias

        # 4. Apply softmax and dropout
        attn_probs = F.softmax(attn_scores, dim=-1)
        attn_probs = self.dropout(attn_probs)

        # 5. Aggregate values
        context = torch.matmul(attn_probs, v).transpose(1, 2).reshape(B, N, self.num_heads * self.head_dim)
        
        # 6. Output projection, residual connection, and layer norm
        output = self.out_lin(context)
        output = self.layer_norm(x + self.dropout(output))
        return output


class GNNModel(nn.Module):
    def __init__(self, node_in_dim: int = 32, hidden_dim: int = 32, num_layers: int = 2, num_heads: int = 4, dropout: float = 0.1):
        super().__init__()
        self.encoder = nn.ModuleList(
            [GraphTransformerLayer(node_in_dim, hidden_dim, num_heads, dropout) for _ in range(num_layers)]
        )
        self.decoder_proj = nn.Linear(hidden_dim, hidden_dim) # Project to a latent space for cosine similarity

    def forward(self, node_embeddings: torch.Tensor, edge_matrix: torch.Tensor) -> torch.Tensor:
        # node_embeddings: [B, N, 32], edge_matrix: [B, N, N]
        x = node_embeddings
        for layer in self.encoder:
            x = layer(x, edge_matrix)

        # Cosine Similarity Decoder
        z = self.decoder_proj(x)
        z_norm = F.normalize(z, p=2, dim=-1)  # L2 normalize
        pred_corr_matrix = torch.matmul(z_norm, z_norm.transpose(-2, -1))
        
        return pred_corr_matrix


def frobenius_norm_loss(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """计算差矩阵的Frobenius范数的平方，然后除以矩阵的元素数量。"""
    diff = pred - target
    # 计算Frobenius范数的平方
    frobenius_norm_sq = torch.sum(diff ** 2, dim=(-2, -1))
    # 获取矩阵的元素数量
    num_elements = target.shape[-1] * target.shape[-2]
    # 计算损失
    loss = frobenius_norm_sq / num_elements
    # 返回批次中所有样本损失的平均值
    return loss.mean()


def relative_frobenius_loss(pred: torch.Tensor, target: torch.Tensor, epsilon: float = 1e-8) -> torch.Tensor:
    """计算相对Frobenius损失。"""
    # 计算分子：预测值与目标值之差的Frobenius范数的平方
    numerator = torch.sum((pred - target) ** 2, dim=(-2, -1))
    
    # 计算分母：目标值的Frobenius范数的平方
    denominator = torch.sum(target ** 2, dim=(-2, -1))
    
    # 为避免除以零，添加一个小的epsilon
    loss = numerator / (denominator + epsilon)
    
    # 返回批次中所有样本损失的平均值
    return loss.mean()


