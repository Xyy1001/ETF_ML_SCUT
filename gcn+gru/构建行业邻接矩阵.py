import os
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# 配置中文显示
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# 当前目录
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 股票代码列表 (保持顺序)
TARGET_STOCKS = [
    '000001', '000002', '000063', '000100', '000157', '000301', '000338', 
    '000408', '000425', '000538', '000568', '000596', '000617', '000625', 
    '000630', '000651', '000661', '000708', '000725', '000768', '000786', 
    '000800', '000807', '000858', '000876', '000895'
]

# 行业标号列表 (对应上述股票顺序)
# 来源：用户提供的申万一级行业分类标号
INDUSTRY_LABELS = [
    1,  # 000001 平安银行 (银行)
    2,  # 000002 万科A (房地产)
    3,  # 000063 中兴通讯 (通信)
    4,  # 000100 TCL科技 (电子)
    5,  # 000157 中联重科 (机械设备)
    6,  # 000301 东方盛虹 (石油石化)
    7,  # 000338 潍柴动力 (汽车)
    8,  # 000408 藏格矿业 (基础化工)
    5,  # 000425 徐工机械 (机械设备)
    9,  # 000538 云南白药 (医药生物)
    10, # 000568 泸州老窖 (食品饮料)
    10, # 000596 古井贡酒 (食品饮料)
    11, # 000617 中油资本 (非银金融)
    7,  # 000625 长安汽车 (汽车)
    12, # 000630 铜陵有色 (有色金属)
    13, # 000651 格力电器 (家用电器)
    9,  # 000661 长春高新 (医药生物)
    14, # 000708 中信特钢 (钢铁)
    4,  # 000725 京东方A (电子)
    15, # 000768 中航西飞 (国防军工)
    16, # 000786 北新建材 (建筑材料)
    7,  # 000800 一汽解放 (汽车)
    12, # 000807 云铝股份 (有色金属)
    10, # 000858 五粮液 (食品饮料)
    17, # 000876 新希望 (农林牧渔)
    10  # 000895 双汇发展 (食品饮料)
]

def build_industry_adjacency_matrix():
    print("开始构建申万行业邻接矩阵...")
    
    num_stocks = len(TARGET_STOCKS)
    if len(INDUSTRY_LABELS) != num_stocks:
        raise ValueError(f"行业标号数量 ({len(INDUSTRY_LABELS)}) 与股票数量 ({num_stocks}) 不匹配")
    
    # 初始化全零矩阵
    A = np.zeros((num_stocks, num_stocks), dtype=int)
    
    # 填充矩阵
    for i in range(num_stocks):
        for j in range(num_stocks):
            if i == j:
                continue # 对角线保持为 0
            
            # 如果行业标号相同，则相连
            if INDUSTRY_LABELS[i] == INDUSTRY_LABELS[j]:
                A[i, j] = 1
    
    print("矩阵构建完成。")
    print(f"矩阵形状: {A.shape}")
    print(f"非零边数 (不含对角线): {np.sum(A)}")
    print(f"实际连边数量 (无向图): {np.sum(A) // 2}")
    
    # 保存为 npy
    output_npy_path = os.path.join(CURRENT_DIR, 'Industry_Adjacency_Matrix.npy')
    np.save(output_npy_path, A)
    print(f"矩阵已保存至: {output_npy_path}")
    
    # 绘图
    plt.figure(figsize=(12, 10))
    sns.heatmap(A, cmap='Blues', square=True, cbar=False, linewidths=0.5, linecolor='gray')
    plt.title('申万行业分类邻接矩阵 (Industry Adjacency Matrix)')
    plt.xlabel('Stock Index')
    plt.ylabel('Stock Index')
    
    output_img_path = os.path.join(CURRENT_DIR, 'Industry_Adjacency_Matrix.png')
    plt.savefig(output_img_path)
    print(f"热力图已保存至: {output_img_path}")
    
    return A

if __name__ == "__main__":
    build_industry_adjacency_matrix()
