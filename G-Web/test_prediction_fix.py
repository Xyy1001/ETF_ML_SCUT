#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试预测修复
"""
import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(__file__))

# 导入预测函数
from predict_api import (
    predict_with_gru, 
    predict_with_transformer,
    load_stock_prices_with_dates,
    normalize_data,
    denormalize_data
)

def test_predictions():
    """测试GRU和Transformer预测"""
    
    # 测试股票列表
    test_stocks = ['000001.SZ', '000002.SZ', '000063.SZ']
    
    print("=" * 80)
    print("开始测试预测功能修复")
    print("=" * 80)
    
    for stock in test_stocks:
        print(f"\n【测试股票】{stock}")
        print("-" * 80)
        
        # 加载历史数据
        df = load_stock_prices_with_dates(stock)
        if df is None or df.empty:
            print(f"  ❌ 无法加载 {stock} 的数据")
            continue
        
        prices = df['Close'].values
        print(f"  ✓ 加载了 {len(prices)} 条历史价格数据")
        print(f"  - 价格范围: {prices.min():.2f} ~ {prices.max():.2f}")
        print(f"  - 最后5个价格: {prices[-5:]}")
        
        # 测试GRU预测
        print(f"\n  [GRU 预测]")
        try:
            gru_preds = predict_with_gru(prices, predict_days=10, stock_code=stock)
            print(f"  ✓ GRU预测成功")
            print(f"  - 预测值: {gru_preds}")
            print(f"  - 范围: {min(gru_preds):.2f} ~ {max(gru_preds):.2f}")
            
            # 检查是否是常数（这是bug的表现）
            if len(set([round(p, 2) for p in gru_preds])) == 1:
                print(f"  ⚠️ 警告：预测值都相同，可能模型未正确加载")
            else:
                print(f"  ✓ 预测值有变化（正常表现）")
                
        except Exception as e:
            print(f"  ❌ GRU预测失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 测试Transformer预测
        print(f"\n  [Transformer 预测]")
        try:
            tf_preds = predict_with_transformer(prices, predict_days=10, stock_code=stock)
            print(f"  ✓ Transformer预测成功")
            print(f"  - 预测值: {tf_preds}")
            print(f"  - 范围: {min(tf_preds):.2f} ~ {max(tf_preds):.2f}")
            
            # 检查是否是常数
            if len(set([round(p, 2) for p in tf_preds])) == 1:
                print(f"  ⚠️ 警告：预测值都相同，可能模型未正确加载")
            else:
                print(f"  ✓ 预测值有变化（正常表现）")
                
        except Exception as e:
            print(f"  ❌ Transformer预测失败: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    test_predictions()
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)
