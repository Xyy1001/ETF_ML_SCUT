import os
import numpy as np
import pandas as pd
from sklearn.covariance import GraphicalLasso
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm
import warnings

# 忽略警告
warnings.filterwarnings('ignore')
# 解决中文显示问题
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# ================= 配置部分 =================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 数据路径: 上一级目录 -> 数据工程 -> RC矩阵
DATA_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', '数据工程', 'RC矩阵'))
OUTPUT_DIR = CURRENT_DIR

# 候选 lambda
# 原定 lambda: [0.001, 0.005, 0.01, 0.05, 0.1, 0.2]
# 根据诊断，数据协方差较小 (~0.0002)，需要更小的 lambda 才能捕捉结构
LAMBDAS = [0.005, 0.01, 0.05, 0.1, 0.2]

# 股票数量
NUM_STOCKS = 26

def load_data(data_dir):
    """
    读取所有 .npy 格式的 RC 矩阵，并按时间排序
    返回: list of (date, matrix)
    """
    print(f"正在从 {data_dir} 读取数据...")
    data_list = []
    
    # 遍历年份
    if not os.path.exists(data_dir):
        print(f"错误：找不到数据目录 {data_dir}")
        return []

    years = sorted(os.listdir(data_dir))
    for year in years:
        year_dir = os.path.join(data_dir, year)
        if not os.path.isdir(year_dir): continue
        
        # 遍历月份
        for month in sorted(os.listdir(year_dir)):
            month_dir = os.path.join(year_dir, month)
            if not os.path.isdir(month_dir): continue
            
            # 遍历日期文件
            for file_name in sorted(os.listdir(month_dir)):
                if file_name.endswith('.npy'):
                    file_path = os.path.join(month_dir, file_name)
                    try:
                        # 解析日期
                        date_str = os.path.splitext(file_name)[0]
                        # 读取矩阵
                        matrix = np.load(file_path)
                        
                        # 简单校验形状
                        if matrix.shape != (NUM_STOCKS, NUM_STOCKS):
                            print(f"警告: 文件 {file_name} 形状为 {matrix.shape}，跳过")
                            continue

                        # 检查 NaN 或 Inf
                        if not np.isfinite(matrix).all():
                            # print(f"警告: 文件 {file_name} 包含 NaN 或 Inf，跳过")
                            continue
                            
                        data_list.append((date_str, matrix))
                    except Exception as e:
                        print(f"读取文件 {file_path} 失败: {e}")
                        
    # 按日期排序
    data_list.sort(key=lambda x: x[0])
    
    print(f"共读取到 {len(data_list)} 个交易日的 RC 矩阵")
    return [x[1] for x in data_list], [x[0] for x in data_list]

def calculate_score(S_val, Theta):
    """
    计算验证集负对数似然
    score = Tr(S_val * Theta) - logdet(Theta)
    """
    # 计算 logdet
    sign, logdet = np.linalg.slogdet(Theta)
    if sign <= 0:
        # 如果行列式非正，说明不是正定矩阵，返回无穷大惩罚
        return np.inf
        
    term1 = np.trace(S_val @ Theta)
    score = term1 - logdet
    return score

def main():
    # 1. 读取数据
    rc_matrices, dates = load_data(DATA_DIR)
    
    if not rc_matrices:
        print("未读取到数据，程序终止")
        return

    n_samples = len(rc_matrices)
    print(f"样本总数: {n_samples}")

    # 转换为 numpy 数组以便索引 (N, 26, 26)
    rc_array = np.array(rc_matrices)

    # 2. 划分五折 (Step 1)
    # 简单的按顺序切分
    fold_size = n_samples // 5
    folds = []
    
    # 前4折大小为 fold_size，最后一折包含剩余所有
    start = 0
    for i in range(5):
        if i < 4:
            end = start + fold_size
        else:
            end = n_samples
        folds.append((start, end))
        start = end
        
    print(f"五折划分索引: {folds}")

    # 3. 对每个 lambda 做交叉验证 (Step 3)
    cv_scores = {} # lambda -> average_score
    
    print("\n开始交叉验证...")
    for lam in LAMBDAS:
        print(f"\n评估 lambda = {lam}")
        fold_scores = []
        
        for fold_idx, (val_start, val_end) in enumerate(folds):
            # 构造训练集和验证集索引
            # 验证集索引
            val_indices = np.arange(val_start, val_end)
            # 训练集索引 = 总索引 - 验证集索引
            all_indices = np.arange(n_samples)
            train_indices = np.setdiff1d(all_indices, val_indices)
            
            # 1️⃣ 计算 S_train
            S_train = np.mean(rc_array[train_indices], axis=0)
            
            # 缩放数据，尝试解决精度问题
            scale_factor = 100.0
            S_train_scaled = S_train * (scale_factor ** 2)
            
            # 2️⃣ 用 S_train 跑 GL 得到 Theta
            # sklearn 的 GraphicalLasso 参数 alpha 对应这里的 lambda
            try:
                # 注意 lambda 也要相应缩放？
                # 目标函数: tr(S*Theta) - logdet(Theta) + alpha * ||Theta||_1
                # 如果 S -> k*S, 此时 Theta -> Theta/k (精度矩阵是逆协方差)
                # tr(k*S * Theta/k) = tr(S*Theta) 不变
                # logdet(Theta/k) = logdet(Theta) - p*log(k) 常数差
                # alpha * ||Theta/k||_1 = alpha/k * ||Theta||_1
                # 所以如果在缩放后的数据上运行，且希望等效于原 alpha，则 scaled_alpha = alpha / k ?
                # 实际上直接在缩放数据上跑，alpha 相对 S 的大小就变了，更容易产生非零边
                
                model = GraphicalLasso(alpha=lam, mode='cd', tol=1e-4, max_iter=100, verbose=False)
                model.fit(S_train_scaled)
                Theta_scaled = model.precision_
                
                # 还原 Theta
                Theta = Theta_scaled * (scale_factor ** 2)
                
            except Exception as e:
                print(f"  Fold {fold_idx+1}: GL 求解失败 ({e})，跳过")
                fold_scores.append(np.inf)
                continue
                
            # 3️⃣ 计算 S_val
            S_val = np.mean(rc_array[val_indices], axis=0)
            
            # 4️⃣ 计算 score
            score = calculate_score(S_val, Theta)
            fold_scores.append(score)
            
            # print(f"  Fold {fold_idx+1} Score: {score:.6f}")
            
        # Step 4: 对五折取平均
        avg_score = np.mean(fold_scores)
        cv_scores[lam] = avg_score
        print(f"lambda = {lam} 的平均 CV Score: {avg_score:.6f}")

    # Step 5: 选择最佳 lambda
    best_lambda = min(cv_scores, key=cv_scores.get)
    print(f"\n" + "="*40)
    print(f"最优 lambda: {best_lambda} (Score: {cv_scores[best_lambda]:.6f})")
    print("="*40)

    # 最后的计算
    print(f"\n使用最优 lambda = {best_lambda} 在全量数据上计算最终结果...")
    
    # 用全部训练数据算 S_full
    S_full = np.mean(rc_array, axis=0)
    
    # 诊断信息
    max_off_diag = np.max(np.abs(S_full - np.diag(np.diag(S_full))))
    print(f"\n[诊断] S_full 最大非对角线元素绝对值: {max_off_diag:.6f}")
    
    # 缩放全量数据
    scale_factor = 100.0
    S_full_scaled = S_full * (scale_factor ** 2)
    
    # 计算 Theta_final
    # 使用最优 lambda 在缩放数据上拟合
    final_model = GraphicalLasso(alpha=best_lambda, mode='cd', tol=1e-4, max_iter=100)
    final_model.fit(S_full_scaled)
    Theta_scaled = final_model.precision_
    
    # 还原 Theta_final
    Theta_final = Theta_scaled * (scale_factor ** 2)
    
    # 计算邻接矩阵 A
    # 如果 Theta_final 取值不为0，则 A 取值为1，否则为0
    # 注意：由于缩放，Theta 值变大了，判断阈值可能需要调整？
    # 不，Theta_final 已经还原，所以还是用原来的阈值
    # 或者用相对阈值： > max(abs(Theta)) * 1e-4
    max_val = np.max(np.abs(Theta_final))
    threshold = 1e-5 * max_val
    print(f"[阈值] 判定非零的阈值: {threshold}")
    
    A = (np.abs(Theta_final) > threshold).astype(int)
    
    # 强制对角线为0
    np.fill_diagonal(A, 0)
    
    # 输出结果
    print("\nTheta_final 矩阵形状:", Theta_final.shape)
    print("Adjacency Matrix A 形状:", A.shape)
    
    # 计算边数
    num_edges = np.sum(A) // 2
    max_possible_edges = NUM_STOCKS * (NUM_STOCKS - 1) // 2
    
    print(f"A 中非零边数 (不含对角线): {np.sum(A)}")
    print(f"实际连边数量 (无向图): {num_edges}")
    print(f"理论最大连边数量: {max_possible_edges}")
    print(f"网络密度: {num_edges / max_possible_edges:.2%}")
    
    # 保存结果 (可选)
    np.save(os.path.join(OUTPUT_DIR, 'Theta_final.npy'), Theta_final)
    np.save(os.path.join(OUTPUT_DIR, 'Adjacency_Matrix.npy'), A)
    print("矩阵已保存到当前目录。")
    
    # 绘图输出
    plt.figure(figsize=(12, 10))
    sns.heatmap(A, cmap='Blues', square=True, cbar=False)
    plt.title(f'Adjacency Matrix (lambda={best_lambda})')
    plt.xlabel('Stock Index')
    plt.ylabel('Stock Index')
    
    plot_path = os.path.join(OUTPUT_DIR, 'Adjacency_Matrix.png')
    plt.savefig(plot_path)
    print(f"邻接矩阵热力图已保存: {plot_path}")
    
    # 同时绘制 Theta_final 热力图
    plt.figure(figsize=(12, 10))
    sns.heatmap(Theta_final, cmap='RdBu_r', center=0, square=True)
    plt.title(f'Precision Matrix Theta (lambda={best_lambda})')
    
    theta_plot_path = os.path.join(OUTPUT_DIR, 'Theta_final_Heatmap.png')
    plt.savefig(theta_plot_path)
    print(f"Theta 矩阵热力图已保存: {theta_plot_path}")

if __name__ == "__main__":
    main()
