#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的预测修复测试 - 直接测试模型加载
"""
import os
import sys
import numpy as np
import torch
import torch.nn as nn

# 模型路径
MODEL_PATH = {
    'gru': os.path.join(os.path.dirname(__file__), 'predict_model', 'GRU'),
    'transformer': os.path.join(os.path.dirname(__file__), 'predict_model', 'Transformer')
}

def test_model_files_exist():
    """检查模型文件是否存在"""
    print("=" * 80)
    print("检查模型文件")
    print("=" * 80)
    
    # 检查GRU模型
    gru_dir = MODEL_PATH['gru']
    if os.path.exists(gru_dir):
        gru_files = [f for f in os.listdir(gru_dir) if f.endswith('.pth')]
        print(f"\n✓ GRU模型目录存在: {gru_dir}")
        print(f"  可用模型数: {len(gru_files)}")
        if gru_files:
            print(f"  示例模型: {gru_files[:3]}")
    else:
        print(f"\n❌ GRU模型目录不存在: {gru_dir}")
    
    # 检查Transformer模型
    tf_dir = MODEL_PATH['transformer']
    if os.path.exists(tf_dir):
        tf_files = [f for f in os.listdir(tf_dir) if f.endswith('.pth')]
        print(f"\n✓ Transformer模型目录存在: {tf_dir}")
        print(f"  可用模型数: {len(tf_files)}")
        if tf_files:
            print(f"  示例模型: {tf_files[:3]}")
    else:
        print(f"\n❌ Transformer模型目录不存在: {tf_dir}")

def test_model_loading():
    """测试加载单个模型文件"""
    print("\n" + "=" * 80)
    print("测试模型加载")
    print("=" * 80)
    
    test_stock = '000001.SZ'
    
    # 测试GRU模型加载
    print(f"\n【GRU 模型】({test_stock})")
    gru_path = os.path.join(MODEL_PATH['gru'], f'{test_stock}.pth')
    if os.path.exists(gru_path):
        try:
            checkpoint = torch.load(gru_path, map_location='cpu')
            print(f"  ✓ 模型文件加载成功")
            print(f"  - 文件大小: {os.path.getsize(gru_path) / 1024 / 1024:.2f} MB")
            print(f"  - Checkpoint类型: {type(checkpoint)}")
            
            if isinstance(checkpoint, dict):
                print(f"  - Keys: {list(checkpoint.keys())[:10]}")
                
                # 查看state dict的结构
                if isinstance(checkpoint, dict) and not any(k in checkpoint for k in ['state_dict', 'model_state_dict']):
                    # 直接是state_dict
                    state = checkpoint
                    print(f"  - State dict包含的层数: {len(state)}")
                    first_keys = list(state.keys())[:5]
                    print(f"  - 前5个键: {first_keys}")
            
        except Exception as e:
            print(f"  ❌ 加载失败: {e}")
    else:
        print(f"  ❌ 模型文件不存在: {gru_path}")
    
    # 测试Transformer模型加载
    print(f"\n【Transformer 模型】({test_stock})")
    tf_path = os.path.join(MODEL_PATH['transformer'], f'{test_stock}.pth')
    if os.path.exists(tf_path):
        try:
            checkpoint = torch.load(tf_path, map_location='cpu')
            print(f"  ✓ 模型文件加载成功")
            print(f"  - 文件大小: {os.path.getsize(tf_path) / 1024 / 1024:.2f} MB")
            print(f"  - Checkpoint类型: {type(checkpoint)}")
            
            if isinstance(checkpoint, dict):
                print(f"  - Keys: {list(checkpoint.keys())[:10]}")
                if isinstance(checkpoint, dict) and not any(k in checkpoint for k in ['state_dict', 'model_state_dict']):
                    state = checkpoint
                    print(f"  - State dict包含的层数: {len(state)}")
                    first_keys = list(state.keys())[:5]
                    print(f"  - 前5个键: {first_keys}")
            
        except Exception as e:
            print(f"  ❌ 加载失败: {e}")
    else:
        print(f"  ❌ 模型文件不存在: {tf_path}")

def test_model_architecture():
    """测试模型架构定义"""
    print("\n" + "=" * 80)
    print("测试模型架构")
    print("=" * 80)
    
    # GRU模型架构
    print("\n【GRU 架构】")
    try:
        class GRUPredictor(nn.Module):
            def __init__(self, input_size=1, hidden_size=64, num_layers=2, output_size=1, output_window=10):
                super(GRUPredictor, self).__init__()
                self.output_window = output_window
                self.gru = nn.GRU(input_size, hidden_size, num_layers, batch_first=True, 
                                dropout=0.1 if num_layers > 1 else 0.0)
                self.fc = nn.Linear(hidden_size, output_size * output_window)
            
            def forward(self, x):
                out, _ = self.gru(x)
                out = self.fc(out[:, -1, :])
                out = out.view(-1, self.output_window, 1)
                return out
        
        model = GRUPredictor()
        print(f"  ✓ GRU模型创建成功")
        print(f"  - 参数数量: {sum(p.numel() for p in model.parameters())}")
        
        # 测试forward
        test_input = torch.randn(1, 64, 1)
        output = model(test_input)
        print(f"  - 输入形状: {test_input.shape}")
        print(f"  - 输出形状: {output.shape}")
        print(f"  ✓ Forward pass 成功")
        
    except Exception as e:
        print(f"  ❌ GRU模型创建失败: {e}")
    
    # Transformer模型架构
    print("\n【Transformer 架构】")
    try:
        class TransformerPredictor(nn.Module):
            def __init__(self, input_size=1, d_model=64, num_heads=8, output_window=10):
                super(TransformerPredictor, self).__init__()
                self.output_window = output_window
                self.embedding = nn.Linear(input_size, d_model)
                encoder_layer = nn.TransformerEncoderLayer(
                    d_model=d_model, 
                    nhead=min(num_heads, 8),
                    batch_first=True,
                    dropout=0.1
                )
                self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=2)
                self.fc = nn.Linear(d_model, output_window)
            
            def forward(self, x):
                x = self.embedding(x)
                x = self.transformer(x)
                x = self.fc(x[:, -1, :])
                x = x.view(-1, self.output_window, 1)
                return x
        
        model = TransformerPredictor()
        print(f"  ✓ Transformer模型创建成功")
        print(f"  - 参数数量: {sum(p.numel() for p in model.parameters())}")
        
        # 测试forward
        test_input = torch.randn(1, 64, 1)
        output = model(test_input)
        print(f"  - 输入形状: {test_input.shape}")
        print(f"  - 输出形状: {output.shape}")
        print(f"  ✓ Forward pass 成功")
        
    except Exception as e:
        print(f"  ❌ Transformer模型创建失败: {e}")

if __name__ == '__main__':
    print("开始预测修复诊断")
    test_model_files_exist()
    test_model_loading()
    test_model_architecture()
    print("\n" + "=" * 80)
    print("诊断完成")
    print("=" * 80)
