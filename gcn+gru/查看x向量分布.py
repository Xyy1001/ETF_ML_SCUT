import os
import numpy as np
import pandas as pd
from tqdm import tqdm
import warnings
import matplotlib.pyplot as plt
import seaborn as sns

# 忽略警告
warnings.filterwarnings('ignore')
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# ================= 配置部分 =================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
X_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', '数据工程', 'x'))

def analyze_x_vectors():
    print("正在加载所有 x 向量数据...")
    
    all_values = []
    file_count = 0
    
    # 遍历 X_DIR
    for year in sorted(os.listdir(X_DIR)):
        year_dir = os.path.join(X_DIR, year)
        if not os.path.isdir(year_dir): continue
        for month in sorted(os.listdir(year_dir)):
            month_dir = os.path.join(year_dir, month)
            if not os.path.isdir(month_dir): continue
            for f in sorted(os.listdir(month_dir)):
                if f.endswith('.npy'):
                    path = os.path.join(month_dir, f)
                    try:
                        vector = np.load(path)
                        if not np.isfinite(vector).all(): continue
                        
                        # vector shape (325, 1) or (325,)
                        all_values.append(vector.flatten())
                        file_count += 1
                    except: pass
                    
    if not all_values:
        print("未找到有效数据")
        return

    # 合并为一个大数组
    all_values = np.concatenate(all_values)
    total_count = len(all_values)
    
    print(f"\n共分析了 {file_count} 个交易日的数据")
    print(f"总计相关系数样本数: {total_count}")
    
    # 统计正负值
    pos_count = np.sum(all_values > 0)
    neg_count = np.sum(all_values < 0)
    zero_count = np.sum(all_values == 0)
    
    pos_ratio = pos_count / total_count
    neg_ratio = neg_count / total_count
    zero_ratio = zero_count / total_count
    
    print("\n" + "="*40)
    print(f"正值数量: {pos_count} ({pos_ratio:.2%})")
    print(f"负值数量: {neg_count} ({neg_ratio:.2%})")
    print(f"零值数量: {zero_count} ({zero_ratio:.2%})")
    print("="*40)
    
    # 统计基本信息
    print(f"\n最大值: {np.max(all_values):.4f}")
    print(f"最小值: {np.min(all_values):.4f}")
    print(f"均值:   {np.mean(all_values):.4f}")
    print(f"中位数: {np.median(all_values):.4f}")
    print(f"标准差: {np.std(all_values):.4f}")
    
    # 绘制分布直方图
    plt.figure(figsize=(10, 6))
    sns.histplot(all_values, bins=100, kde=True, color='skyblue')
    plt.title('相关系数 (x向量) 数值分布')
    plt.xlabel('Correlation Coefficient')
    plt.ylabel('Count')
    plt.axvline(0, color='red', linestyle='--', label='Zero')
    plt.legend()
    
    output_path = os.path.join(CURRENT_DIR, 'x_vector_distribution.png')
    plt.savefig(output_path)
    print(f"\n分布直方图已保存至: {output_path}")

if __name__ == "__main__":
    analyze_x_vectors()
