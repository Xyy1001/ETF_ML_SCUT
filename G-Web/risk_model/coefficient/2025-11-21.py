import pandas as pd
import numpy as np
import os

# 定义原始数据目录的路径
raw_data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')

# 获取所有Excel文件的列表
excel_files = [f for f in os.listdir(raw_data_path) if f.endswith('.xlsx')]
excel_files.sort() # 对文件进行排序以确保顺序一致

# 检查是否有26个文件
if len(excel_files) != 26:
    print(f"Warning: Expected 26 excel files, but found {len(excel_files)}.")

# 从每个Excel文件中读取第38列（索引为37）
log_returns_list = []
for file in excel_files:
    file_path = os.path.join(raw_data_path, file)
    # 假设数据在第一个工作表中，第一行为表头
    # 使用iloc选择第38列（索引为37），并跳过表头
    df = pd.read_excel(file_path, header=0, usecols=[37])
    log_returns_list.append(df)

# 将所有对数收益率合并到一个DataFrame中
if not log_returns_list:
    print("Error: No data loaded. Exiting.")
else:
    log_returns_df = pd.concat(log_returns_list, axis=1)
    log_returns_df.columns = [f.split('.')[0] for f in excel_files]

    # 总交易日数
    total_days = len(log_returns_df)
    print(f"Total trading days found: {total_days}")

    # 定义窗口大小
    window_size = 100

    # 计算滚动协方差矩阵
    covariance_matrices = []
    for i in range(total_days - window_size + 1):
        window_data = log_returns_df.iloc[i:i+window_size]
        cov_matrix = window_data.cov().values
        covariance_matrices.append(cov_matrix)

    # 转换为NumPy数组
    covariance_matrices_np = np.array(covariance_matrices)

    # 将结果保存在src文件夹中
    output_path = os.path.join(os.path.dirname(__file__), 'covariance_matrices.npy')
    np.save(output_path, covariance_matrices_np)

    print(f"Calculated {len(covariance_matrices)} covariance matrices.")
    print(f"Saved covariance matrices to {output_path}")

    # 打印第一个协方差矩阵
    if len(covariance_matrices) > 0:
        print("\n第一个协方差矩阵 (形状: {covariance_matrices[0].shape}):")
        print(covariance_matrices[0])

    # 分析协方差矩阵
    if covariance_matrices_np.shape[0] == 3694:
        # 沿第一个轴（代表3694个矩阵）计算最大值、最小值和平均值
        max_cov_matrix = np.max(covariance_matrices_np, axis=0)
        min_cov_matrix = np.min(covariance_matrices_np, axis=0)
        mean_cov_matrix = np.mean(covariance_matrices_np, axis=0)

        print("\n由最大值构成的协方差矩阵:")
        print(max_cov_matrix)

        print("\n由最小值构成的协方差矩阵:")
        print(min_cov_matrix)

        print("\n由平均值构成的协方差矩阵:")
        print(mean_cov_matrix)
    else:
        print(f"\n警告: 协方差矩阵的数量为 {covariance_matrices_np.shape[0]}，而不是预期的3694个，因此跳过分析。")
