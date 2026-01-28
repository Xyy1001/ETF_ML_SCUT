#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
边特征矩阵查看工具
用于查看和分析 train_edge_features.npy 文件中的协方差矩阵样本
"""

import numpy as np
import os

def load_and_analyze_edge_features():
    """
    加载并分析训练集的边特征矩阵
    """
    # 文件路径
    edge_features_path = "../data/train_edge_features.npy"
    
    # 如果相对路径不存在，尝试绝对路径
    if not os.path.exists(edge_features_path):
        # 获取当前脚本所在目录的父目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        edge_features_path = os.path.join(parent_dir, "data", "train_edge_features.npy")
    
    # 检查文件是否存在
    if not os.path.exists(edge_features_path):
        print(f"错误：文件 {edge_features_path} 不存在")
        return
    
    try:
        # 加载边特征数据
        edge_features = np.load(edge_features_path)
        print(f"边特征矩阵形状: {edge_features.shape}")
        print(f"数据类型: {edge_features.dtype}")
        print("="*60)
        
        # 获取基本统计信息
        n_samples, n_stocks, _ = edge_features.shape
        print(f"样本数量: {n_samples}")
        print(f"股票数量: {n_stocks}")
        print("="*60)
        
        # 显示前几个样本的边特征矩阵
        num_samples_to_show = min(3, n_samples)
        
        for i in range(num_samples_to_show):
            print(f"\n样本 {i+1} 的边特征矩阵（协方差矩阵）:")
            print("-"*40)
            
            # 获取当前样本的协方差矩阵
            cov_matrix = edge_features[i]
            
            # 显示矩阵
            print("协方差矩阵:")
            for row in range(n_stocks):
                row_str = ""
                for col in range(n_stocks):
                    row_str += f"{cov_matrix[row, col]:8.4f} "
                print(f"  [{row_str}]")
            
            # 统计信息
            print(f"\n矩阵统计信息:")
            print(f"  最小值: {np.min(cov_matrix):.6f}")
            print(f"  最大值: {np.max(cov_matrix):.6f}")
            print(f"  平均值: {np.mean(cov_matrix):.6f}")
            print(f"  标准差: {np.std(cov_matrix):.6f}")
            
            # 对角线元素（方差）
            diagonal = np.diag(cov_matrix)
            print(f"  对角线元素（方差）: {diagonal}")
            
            # 检查矩阵性质
            is_symmetric = np.allclose(cov_matrix, cov_matrix.T)
            print(f"  是否对称: {is_symmetric}")
            
            # 特征值
            eigenvals = np.linalg.eigvals(cov_matrix)
            print(f"  特征值: {eigenvals}")
            print(f"  是否正定: {np.all(eigenvals > 0)}")
            
            print("="*60)
        
        # 全局统计
        print(f"\n全局统计信息（所有 {n_samples} 个样本）:")
        print("-"*40)
        print(f"所有矩阵元素的统计:")
        print(f"  最小值: {np.min(edge_features):.6f}")
        print(f"  最大值: {np.max(edge_features):.6f}")
        print(f"  平均值: {np.mean(edge_features):.6f}")
        print(f"  标准差: {np.std(edge_features):.6f}")
        
        # 对角线元素统计（所有样本的方差）
        all_variances = []
        for i in range(n_samples):
            all_variances.extend(np.diag(edge_features[i]))
        all_variances = np.array(all_variances)
        
        print(f"\n所有样本的方差统计:")
        print(f"  方差最小值: {np.min(all_variances):.6f}")
        print(f"  方差最大值: {np.max(all_variances):.6f}")
        print(f"  方差平均值: {np.mean(all_variances):.6f}")
        print(f"  方差标准差: {np.std(all_variances):.6f}")
        
    except Exception as e:
        print(f"加载文件时出错: {e}")

def main():
    """
    主函数
    """
    print("边特征矩阵分析工具")
    print("="*60)
    load_and_analyze_edge_features()

if __name__ == "__main__":
    main()
