from typing import Tuple

import torch
import torch.nn as nn


class NodeTransformerEncoder(nn.Module):
    """
    节点级 Transformer 编码器。

    输入: 每个 batch 的节点时间序列张量，形状 [batch, n_stocks, 36, lookback]
    输出: 每个节点的低维嵌入，形状 [batch, n_stocks, d_model]

    设计: d_model=32, nhead=8，时间维上做均值池化得到长度为 32 的向量。
    """

    def __init__(self, d_model: int = 32, nhead: int = 8, num_layers: int = 2, dropout: float = 0.1):
        super().__init__()
        self.d_model = d_model

        # 将每个时间步的 36 维特征投影到 d_model 维
        self.input_proj = nn.Linear(36, d_model)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=4 * d_model,
            dropout=dropout,
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        # 池化：在时间维上做均值池化
        self.pool = nn.AdaptiveAvgPool1d(1)

    def forward(self, node_feats: torch.Tensor) -> torch.Tensor:
        # node_feats: [B, N, 36, L]
        B, N, F, L = node_feats.shape
        assert F == 36, "Expected 36 features per timestep"

        # 重排为序列优先的形状: [B*N, L, 36]
        x = node_feats.permute(0, 1, 3, 2).reshape(B * N, L, F)
        x = self.input_proj(x)  # [B*N, L, d_model]
        # 此处省略显式位置编码；对于较短 L，编码器依然可通过权重学习序列结构
        x = self.encoder(x)  # [B*N, L, d_model]

        # 时间维池化 -> [B*N, d_model]
        x = x.permute(0, 2, 1)  # [B*N, d_model, L]
        x = self.pool(x).squeeze(-1)
        x = x.reshape(B, N, self.d_model)
        return x


