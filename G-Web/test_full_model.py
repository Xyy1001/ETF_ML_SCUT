#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整的预测模型测试
"""
import os
import sys
import numpy as np
import torch
import torch.nn as nn
import math

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(__file__))

def test_gru_and_transformer():
    """完整测试GRU和Transformer模型的加载和预测"""
    
    MODEL_PATH = {
        'gru': os.path.join(os.path.dirname(__file__), 'predict_model', 'GRU'),
        'transformer': os.path.join(os.path.dirname(__file__), 'predict_model', 'Transformer')
    }
    
    def normalize_data(data):
        data_min = np.min(data)
        data_max = np.max(data)
        normalized = (data - data_min) / (data_max - data_min + 1e-10)
        return normalized, {'min': data_min, 'max': data_max}
    
    def denormalize_data(data, params):
        return data * (params['max'] - params['min']) + params['min']
    
    # ========== LSTM_GRU 模型定义 ==========
    class LSTM_GRU_Model(nn.Module):
        def __init__(
            self,
            input_size=1,
            lstm_hidden_size=64,
            lstm_layers=1,
            gru_hidden_size=64,
            gru_layers=1,
            dropout=0.1,
            output_size=1,
            output_window=10,
        ):
            super().__init__()
            self.output_window = output_window
            self.lstm = nn.LSTM(
                input_size,
                lstm_hidden_size,
                lstm_layers,
                batch_first=True,
                dropout=dropout if lstm_layers > 1 else 0.0,
            )
            self.gru = nn.GRU(
                lstm_hidden_size,
                gru_hidden_size,
                gru_layers,
                batch_first=True,
                dropout=dropout if gru_layers > 1 else 0.0,
            )
            self.fc = nn.Linear(gru_hidden_size, output_size * output_window)

        def forward(self, x):
            lstm_out, _ = self.lstm(x)
            gru_out, _ = self.gru(lstm_out)
            last_output = gru_out[:, -1, :]
            output = self.fc(last_output)
            return output.view(x.size(0), self.output_window, -1)
    
    # ========== Transformer 模型定义 ==========
    class PositionalEncoding(nn.Module):
        def __init__(self, d_model, dropout=0.1, max_len=5000):
            super(PositionalEncoding, self).__init__()
            self.dropout = nn.Dropout(p=dropout)
            
            pe = torch.zeros(max_len, d_model)
            position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
            div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
            pe[:, 0::2] = torch.sin(position * div_term)
            pe[:, 1::2] = torch.cos(position * div_term)
            pe = pe.unsqueeze(1)
            self.register_buffer('pe', pe)
        
        def forward(self, x):
            x = x + self.pe[:x.size(0)]
            return self.dropout(x)
    
    class MultiVariateLSTM_Transformer(nn.Module):
        def __init__(self, input_size=1, lstm_hidden_size=64, lstm_layers=2,
                     trans_layers=2, trans_heads=4, trans_ffn_hidden=128, 
                     dropout=0.1, output_size=1, output_window=10):
            super(MultiVariateLSTM_Transformer, self).__init__()
            self.lstm_hidden_size = lstm_hidden_size
            self.lstm_layers = lstm_layers
            self.output_window = output_window
            
            self.lstm = nn.LSTM(input_size, lstm_hidden_size, lstm_layers, 
                               batch_first=True, dropout=dropout if lstm_layers > 1 else 0.0)
            
            self.pos_encoder = PositionalEncoding(d_model=lstm_hidden_size, dropout=dropout)
            
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=lstm_hidden_size, 
                nhead=trans_heads,
                dim_feedforward=trans_ffn_hidden, 
                dropout=dropout,
                batch_first=False
            )
            self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=trans_layers)
            
            self.fc = nn.Linear(lstm_hidden_size, output_size * output_window)
        
        def forward(self, x):
            batch_size = x.size(0)
            lstm_out, _ = self.lstm(x)
            lstm_out = lstm_out.transpose(0, 1)
            lstm_out = self.pos_encoder(lstm_out)
            transformer_out = self.transformer_encoder(lstm_out)
            last_output = transformer_out[-1]
            output = self.fc(last_output)
            output = output.view(batch_size, self.output_window, -1)
            return output
    
    print("=" * 80)
    print("测试模型加载和预测")
    print("=" * 80)
    
    # 测试数据
    test_price = np.array([10 + i * 0.1 + np.random.normal(0, 0.2) for i in range(100)])
    test_stock = '000001.SZ'
    
    # ========== 测试 GRU ==========
    print(f"\n【GRU 模型】")
    print("-" * 80)
    
    try:
        # 创建模型
        gru_model = LSTM_GRU_Model(
            input_size=1, lstm_hidden_size=64, lstm_layers=1,
            gru_hidden_size=64, gru_layers=1, dropout=0.1,
            output_size=1, output_window=10
        )
        print(f"✓ 模型创建成功")
        
        # 加载权重
        gru_path = os.path.join(MODEL_PATH['gru'], f'{test_stock}.pth')
        if os.path.exists(gru_path):
            checkpoint = torch.load(gru_path, map_location='cpu')
            missing, unexpected = gru_model.load_state_dict(checkpoint, strict=False)
            print(f"✓ 模型权重加载成功")
            print(f"  - missing keys: {len(missing)}")
            print(f"  - unexpected keys: {len(unexpected)}")
        
        gru_model.eval()
        
        # 进行预测
        normalized_data, norm_params = normalize_data(test_price)
        predictions = []
        input_window = 64
        current_seq = normalized_data[-input_window:].reshape(-1, 1)
        
        for step in range(10):
            with torch.no_grad():
                input_tensor = torch.FloatTensor(current_seq).unsqueeze(0)
                output = gru_model(input_tensor)
                next_pred = output[0, 0, 0].item()
            
            predictions.append(next_pred)
            current_seq = np.vstack([current_seq[1:], [[next_pred]]])
        
        predictions = np.array(predictions)
        predictions = denormalize_data(predictions, norm_params)
        
        print(f"✓ 预测完成")
        print(f"  - 预测值: {predictions}")
        print(f"  - 变化范围: {predictions.min():.4f} ~ {predictions.max():.4f}")
        print(f"  - 是否都相同: {len(set([round(p, 4) for p in predictions])) == 1}")
        
    except Exception as e:
        print(f"❌ GRU 模型测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # ========== 测试 Transformer ==========
    print(f"\n【Transformer 模型】")
    print("-" * 80)
    
    try:
        # 创建模型
        tf_model = MultiVariateLSTM_Transformer(
            input_size=1, lstm_hidden_size=64, lstm_layers=2,
            trans_layers=2, trans_heads=4, trans_ffn_hidden=128,
            dropout=0.1, output_size=1, output_window=10
        )
        print(f"✓ 模型创建成功")
        
        # 加载权重
        tf_path = os.path.join(MODEL_PATH['transformer'], f'{test_stock}.pth')
        if os.path.exists(tf_path):
            checkpoint = torch.load(tf_path, map_location='cpu')
            missing, unexpected = tf_model.load_state_dict(checkpoint, strict=False)
            print(f"✓ 模型权重加载成功")
            print(f"  - missing keys: {len(missing)}")
            print(f"  - unexpected keys: {len(unexpected)}")
        
        tf_model.eval()
        
        # 进行预测
        normalized_data, norm_params = normalize_data(test_price)
        predictions = []
        input_window = 64
        current_seq = normalized_data[-input_window:].reshape(-1, 1)
        
        for step in range(10):
            with torch.no_grad():
                input_tensor = torch.FloatTensor(current_seq).unsqueeze(0)
                output = tf_model(input_tensor)
                next_pred = output[0, 0, 0].item()
            
            predictions.append(next_pred)
            current_seq = np.vstack([current_seq[1:], [[next_pred]]])
        
        predictions = np.array(predictions)
        predictions = denormalize_data(predictions, norm_params)
        
        print(f"✓ 预测完成")
        print(f"  - 预测值: {predictions}")
        print(f"  - 变化范围: {predictions.min():.4f} ~ {predictions.max():.4f}")
        print(f"  - 是否都相同: {len(set([round(p, 4) for p in predictions])) == 1}")
        
    except Exception as e:
        print(f"❌ Transformer 模型测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)

if __name__ == '__main__':
    test_gru_and_transformer()
