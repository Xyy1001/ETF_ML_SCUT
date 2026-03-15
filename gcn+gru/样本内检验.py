import os
import numpy as np
import pandas as pd
from tqdm import tqdm
import warnings
import statsmodels.api as sm
from statsmodels.stats.correlation_tools import cov_nearest

import matplotlib.pyplot as plt
import seaborn as sns

# 忽略警告
warnings.filterwarnings('ignore')
# 解决中文显示问题
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# ================= 配置部分 =================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 数据路径
RC_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', '数据工程', 'RC矩阵'))
X_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', '数据工程', 'x'))
GL_ADJ_PATH = os.path.join(CURRENT_DIR, 'Adjacency_Matrix.npy')
INDUSTRY_ADJ_PATH = os.path.join(CURRENT_DIR, 'Industry_Adjacency_Matrix.npy')

NUM_STOCKS = 26
NUM_PAIRS = NUM_STOCKS * (NUM_STOCKS - 1) // 2  # 325

# ================= 工具函数 =================

def load_data():
    """
    读取 RC 矩阵和 x 向量
    返回: 
        dates: sorted list of date strings
        rc_dict: {date: matrix (26, 26)}
        x_dict: {date: vector (325, 1)}
        v_dict: {date: vector (26, 1)}
    """
    print("正在加载数据...")
    dates = set()
    rc_dict = {}
    x_dict = {}
    v_dict = {}

    # 1. 读取 RC 矩阵 (用于获取 v_t 和 H_t)
    for year in sorted(os.listdir(RC_DIR)):
        year_dir = os.path.join(RC_DIR, year)
        if not os.path.isdir(year_dir): continue
        for month in sorted(os.listdir(year_dir)):
            month_dir = os.path.join(year_dir, month)
            if not os.path.isdir(month_dir): continue
            for f in sorted(os.listdir(month_dir)):
                if f.endswith('.npy'):
                    date = f.split('.')[0]
                    path = os.path.join(month_dir, f)
                    try:
                        matrix = np.load(path)
                        if not np.isfinite(matrix).all(): continue
                        
                        rc_dict[date] = matrix
                        v_t = np.diag(matrix).reshape(-1, 1)
                        v_dict[date] = v_t
                        dates.add(date)
                    except: pass

    # 2. 读取 x 向量
    for year in sorted(os.listdir(X_DIR)):
        year_dir = os.path.join(X_DIR, year)
        if not os.path.isdir(year_dir): continue
        for month in sorted(os.listdir(year_dir)):
            month_dir = os.path.join(year_dir, month)
            if not os.path.isdir(month_dir): continue
            for f in sorted(os.listdir(month_dir)):
                if f.endswith('.npy'):
                    date = f.split('.')[0]
                    path = os.path.join(month_dir, f)
                    try:
                        vector = np.load(path)
                        if not np.isfinite(vector).all(): continue
                        x_dict[date] = vector.reshape(-1, 1)
                        dates.add(date)
                    except: pass

    common_dates = sorted(list(dates.intersection(rc_dict.keys()).intersection(x_dict.keys())))
    print(f"共加载 {len(common_dates)} 个有效交易日数据")
    return common_dates, rc_dict, x_dict, v_dict

def get_adjacency_matrix(graph_type, dim=26):
    """
    获取邻接矩阵 A
    """
    if graph_type == 'empty':
        return np.zeros((dim, dim))
    
    elif graph_type == 'complete':
        A = np.ones((dim, dim))
        np.fill_diagonal(A, 0)
        return A
    
    elif graph_type == 'GL':
        if dim != 26: raise ValueError("GL 图仅适用于 dim=26")
        if not os.path.exists(GL_ADJ_PATH): raise FileNotFoundError(f"找不到 GL 文件: {GL_ADJ_PATH}")
        A = np.load(GL_ADJ_PATH)
        np.fill_diagonal(A, 0)
        
        # 调试信息: 检查 GL 矩阵是否全零
        if np.sum(A) == 0:
            print("  [警告] GL 邻接矩阵全为 0！请检查上一步生成的 Adjacency_Matrix.npy")
        # else:
        #     print(f"  [信息] GL 邻接矩阵加载成功，边数: {np.sum(A)//2}")
            
        return A
        
    elif graph_type == 'industry':
        if dim != 26: raise ValueError("申万行业图仅适用于 dim=26")
        if not os.path.exists(INDUSTRY_ADJ_PATH): raise FileNotFoundError(f"找不到行业矩阵文件: {INDUSTRY_ADJ_PATH}")
        A = np.load(INDUSTRY_ADJ_PATH)
        np.fill_diagonal(A, 0)
        return A
    
    elif graph_type == 'linear':
        if dim != 325: raise ValueError("线性图仅适用于 dim=325")
        # 构建线性图: 节点 (i,j) 与 (k,l) 相连当且仅当交集非空且不相等
        idx_to_pair = {}
        curr = 0
        for col in range(NUM_STOCKS):
            for row in range(col + 1, NUM_STOCKS):
                idx_to_pair[curr] = {row, col}
                curr += 1
                
        A = np.zeros((dim, dim))
        # 优化循环: 预计算每对的邻居
        # O(325^2) ~ 100,000 次循环，很快
        for k1 in range(dim):
            for k2 in range(k1 + 1, dim):
                if not idx_to_pair[k1].isdisjoint(idx_to_pair[k2]):
                    A[k1, k2] = 1
                    A[k2, k1] = 1
        return A
    
    else: raise ValueError(f"未知图类型: {graph_type}")

def normalize_adjacency(A):
    """
    计算 W = O^-0.5 * A * O^-0.5
    """
    if np.sum(np.abs(A)) == 0: return np.zeros_like(A, dtype=float)
    degrees = np.sum(A, axis=1)
    
    # 必须指定 dtype=float，否则如果是 int 数组，小数会被截断为 0
    inv_sqrt_degrees = np.zeros_like(degrees, dtype=float)
    mask = degrees > 0
    inv_sqrt_degrees[mask] = 1.0 / np.sqrt(degrees[mask])
    
    O_inv_sqrt = np.diag(inv_sqrt_degrees)
    W = O_inv_sqrt @ A @ O_inv_sqrt
    return W

def estimate_model(target_dict, W, dates):
    """
    严格按照 Pooled OLS with Individual Intercepts (Fixed Effects) 进行估计
    方程: y_{i,t} = alpha_i + beta * X_{i,t} + gamma * WX_{i,t} + u_{i,t}
    
    步骤:
    1. 构造面板数据堆叠形式 Y (NT x 1), X (NT x 6)
    2. 对 Y 和 X 进行组内去均值 (Within Transformation) 消除 alpha_i
    3. OLS 估计 beta, gamma
    4. 恢复 alpha_i = mean(y_i) - mean(X_i) * [beta, gamma]
    """
    start_idx = 22
    valid_dates = dates[start_idx:]
    T_eff = len(valid_dates)
    N = target_dict[dates[0]].shape[0]
    
    # 1. 构造 3D 数据矩阵 (T_total, N, 1)
    data_3d = np.zeros((len(dates), N, 1))
    for t, date in enumerate(dates):
        data_3d[t] = target_dict[date]
        
    # 2. 构造特征和标签
    Y_list = []
    X_list = []
    
    # 为了去均值，我们需要保留 (T, N) 的结构
    # X_raw shape: (T_eff, N, 6)
    X_raw = np.zeros((T_eff, N, 6))
    Y_raw = np.zeros((T_eff, N, 1))
    
    for i, t in enumerate(range(start_idx, len(dates))):
        # Target
        y_t = data_3d[t] # (N, 1)
        Y_raw[i] = y_t
        
        # Features
        # Lag terms
        v_lag1 = data_3d[t-1]
        v_lag_w = np.mean(data_3d[t-5 : t-1], axis=0)
        v_lag_m = np.mean(data_3d[t-22 : t-5], axis=0)
        
        # Spatial terms
        W_v_lag1 = W @ v_lag1
        W_v_lag_w = W @ v_lag_w
        W_v_lag_m = W @ v_lag_m
        
        # Stack features (N, 6)
        # 顺序: lag1, lag_w, lag_m, W_lag1, W_lag_w, W_lag_m
        feats = np.hstack([v_lag1, v_lag_w, v_lag_m, W_v_lag1, W_v_lag_w, W_v_lag_m])
        X_raw[i] = feats
        
    # 3. 组内去均值 (Within Transformation)
    # 对时间维度求均值 -> (1, N, 1) 和 (1, N, 6)
    Y_mean = np.mean(Y_raw, axis=0, keepdims=True)
    X_mean = np.mean(X_raw, axis=0, keepdims=True)
    
    Y_demeaned = Y_raw - Y_mean
    X_demeaned = X_raw - X_mean
    
    # 4. 堆叠为 2D 矩阵进行 OLS
    # (T_eff * N, 1)
    Y_pooled = Y_demeaned.reshape(-1, 1)
    # (T_eff * N, 6)
    X_pooled = X_demeaned.reshape(-1, 6)
    
    # OLS (无截距，因为已经去均值)
    model = sm.OLS(Y_pooled, X_pooled)
    results = model.fit()
    params = results.params # (6,) -> [beta_d, beta_w, beta_m, gamma_d, gamma_w, gamma_m]
    
    # 打印参数以便调试
    # print(f"  [参数估计] beta={params[:3]}, gamma={params[3:]}")
    
    # 5. 恢复 Alpha
    # alpha_i = mean(y_i) - mean(X_i) @ params
    # Y_mean shape (1, N, 1) -> squeeze -> (N, 1)
    # X_mean shape (1, N, 6) -> squeeze -> (N, 6)
    alpha = Y_mean.squeeze(0) - X_mean.squeeze(0) @ params.reshape(-1, 1) # (N, 1)
    
    return alpha, params

def predict_model(target_dict, W, dates, alpha, params):
    """
    使用估计出的参数进行预测
    Prediction = alpha + X @ params
    """
    start_idx = 22
    predictions = {}
    N = alpha.shape[0]
    
    # 为了构建特征，需要读取历史数据
    data_3d = np.zeros((len(dates), N, 1))
    for t, date in enumerate(dates):
        data_3d[t] = target_dict[date]
        
    for t in range(start_idx, len(dates)):
        # 构造特征 (与估计时完全一致)
        v_lag1 = data_3d[t-1]
        v_lag_w = np.mean(data_3d[t-5 : t-1], axis=0)
        v_lag_m = np.mean(data_3d[t-22 : t-5], axis=0)
        
        W_v_lag1 = W @ v_lag1
        W_v_lag_w = W @ v_lag_w
        W_v_lag_m = W @ v_lag_m
        
        feats = np.hstack([v_lag1, v_lag_w, v_lag_m, W_v_lag1, W_v_lag_w, W_v_lag_m]) # (N, 6)
        
        # 预测
        # alpha: (N, 1)
        # feats: (N, 6)
        # params: (6,)
        pred = alpha + feats @ params.reshape(-1, 1)
        
        predictions[dates[t]] = pred
        
    return predictions

def vector_to_matrix(x_vec, dim=26):
    """
    还原 R 矩阵，强制对角线为1，非对角线截断 [-1, 1]
    """
    R = np.eye(dim)
    curr = 0
    # x 向量是按列优先的下三角
    for col in range(dim):
        for row in range(col + 1, dim):
            val = x_vec[curr, 0]
            # 强制截断在 [-1, 1] 范围内
            if val > 1: val = 1.0
            if val < -1: val = -1.0
            
            R[row, col] = val
            R[col, row] = val
            curr += 1
    return R

def calculate_losses(H_true, H_pred):
    """
    计算 LE, LF, LQ
    """
    # LE: Euclidean distance of half-vectorization
    vech_true = H_true[np.tril_indices_from(H_true)]
    vech_pred = H_pred[np.tril_indices_from(H_pred)]
    diff_vech = vech_true - vech_pred
    le = np.sqrt(np.dot(diff_vech, diff_vech))
    
    # LF: Frobenius norm
    lf = np.linalg.norm(H_true - H_pred, 'fro')
    
    # LQ: QLIKE
    try:
        sign, logdet = np.linalg.slogdet(H_pred)
        if sign <= 0:
            lq = np.nan
        else:
            trace_term = np.trace(np.linalg.solve(H_pred, H_true))
            lq = logdet + trace_term
    except:
        lq = np.nan
        
    return le, lf, lq

def plot_covariance_comparison(H_true, H_pred, date, v_graph_type, x_graph_type):
    """
    绘制真实协方差矩阵与预测协方差矩阵的热力图对比
    """
    fig, axes = plt.subplots(1, 2, figsize=(20, 8))
    
    # 统一色阶范围
    # 取两张图中的最小值和最大值，确保颜色映射完全一致
    vmin = min(np.min(H_true), np.min(H_pred))
    vmax = max(np.max(H_true), np.max(H_pred))
    
    # 绘制真实矩阵
    sns.heatmap(H_true, ax=axes[0], cmap='RdBu_r', center=0, square=True, vmin=vmin, vmax=vmax)
    axes[0].set_title(f'真实协方差矩阵 ({date})')
    
    # 绘制预测矩阵
    sns.heatmap(H_pred, ax=axes[1], cmap='RdBu_r', center=0, square=True, vmin=vmin, vmax=vmax)
    axes[1].set_title(f'预测协方差矩阵 (v={v_graph_type}, x={x_graph_type})')
    
    plt.tight_layout()
    output_path = os.path.join(CURRENT_DIR, f'Covariance_Comparison_{date}_{v_graph_type}_{x_graph_type}.png')
    plt.savefig(output_path)
    plt.close()
    print(f"  [绘图] 已保存对比图 (统一色阶): {output_path}")

def run_evaluation(dates, rc_dict, v_dict, x_dict, v_graph_type, x_graph_type):
    """
    运行单次评估
    """
    print(f"  评估组合: v={v_graph_type}, x={x_graph_type}")
    
    # 1. 准备 W 矩阵
    # 增加调试：如果是 GL 图，检查 W 是否全零
    A_v = get_adjacency_matrix(v_graph_type, dim=26)
    W_v = normalize_adjacency(A_v)
    if v_graph_type == 'GL':
        print(f"  [调试] W_v (GL) 非零元素数: {np.count_nonzero(W_v)}")
        
    A_x = get_adjacency_matrix(x_graph_type, dim=325)
    W_x = normalize_adjacency(A_x)
    
    # 2. 估计参数 (v)
    alpha_v, params_v = estimate_model(v_dict, W_v, dates)
    if v_graph_type == 'GL':
        print(f"  [调试] v参数 gamma部分: {params_v[3:]}")
        
    # 预测 v
    v_preds = predict_model(v_dict, W_v, dates, alpha_v, params_v)
    
    # 3. 估计参数 (x)
    alpha_x, params_x = estimate_model(x_dict, W_x, dates)
    # 预测 x
    x_preds = predict_model(x_dict, W_x, dates, alpha_x, params_x)
    
    # 4. 合成与计算损失
    le_list, lf_list, lq_list = [], [], []
    valid_dates = sorted(v_preds.keys())
    
    for date in valid_dates:
        H_true = rc_dict[date]
        
        # 构造 H_pred
        v_vec = v_preds[date]
        # v 是方差，取平方根得到 std
        v_vec = np.maximum(v_vec, 1e-8) # 保证非负
        D_pred = np.diag(np.sqrt(v_vec).flatten())
        
        x_vec = x_preds[date]
        R_pred = vector_to_matrix(x_vec, dim=26)
        
        H_pred_raw = D_pred @ R_pred @ D_pred
        
        # 正定性修正
        try:
            np.linalg.cholesky(H_pred_raw)
            H_pred = H_pred_raw
        except np.linalg.LinAlgError:
            H_pred = cov_nearest(H_pred_raw, method='clipped', threshold=1e-6)
            
        le, lf, lq = calculate_losses(H_true, H_pred)
        if not np.isnan(lq): # 过滤无效值
            le_list.append(le)
            lf_list.append(lf)
            lq_list.append(lq)
            
    # 绘制最后一个交易日的对比图 (作为示例)
    if valid_dates:
        last_date = valid_dates[-1]
        
        # 重新获取 H_true 和 H_pred (需要再算一次，或者之前存下来)
        H_true = rc_dict[last_date]
        
        v_vec = v_preds[last_date]
        v_vec = np.maximum(v_vec, 1e-8)
        D_pred = np.diag(np.sqrt(v_vec).flatten())
        
        x_vec = x_preds[last_date]
        R_pred = vector_to_matrix(x_vec, dim=26)
        
        H_pred_raw = D_pred @ R_pred @ D_pred
        try:
            np.linalg.cholesky(H_pred_raw)
            H_pred = H_pred_raw
        except np.linalg.LinAlgError:
            H_pred = cov_nearest(H_pred_raw, method='clipped', threshold=1e-6)
            
        plot_covariance_comparison(H_true, H_pred, last_date, v_graph_type, x_graph_type)
            
    return np.mean(le_list), np.mean(lf_list), np.mean(lq_list)

def main():
    dates, rc_dict, x_dict, v_dict = load_data()
    if len(dates) < 23:
        print("数据量不足")
        return

    # 基准情况
    print("\n计算基准 (empty, empty)...")
    base_le, base_lf, base_lq = run_evaluation(dates, rc_dict, v_dict, x_dict, 'empty', 'empty')
    print(f"基准损失: LE={base_le:.4f}, LF={base_lf:.4f}, LQ={base_lq:.4f}")
    
    # 遍历组合
    v_graphs = ['empty', 'complete', 'GL', 'industry']
    x_graphs = ['empty', 'complete', 'linear']
    
    results = []
    print("\n开始遍历组合...")
    for vg in v_graphs:
        for xg in x_graphs:
            if vg == 'empty' and xg == 'empty':
                le, lf, lq = base_le, base_lf, base_lq
            else:
                le, lf, lq = run_evaluation(dates, rc_dict, v_dict, x_dict, vg, xg)
            
            results.append({
                'v_graph': vg, 'x_graph': xg,
                'Ratio_LE': le/base_le, 'Ratio_LF': lf/base_lf, 'Ratio_LQ': lq/base_lq,
                'Raw_LE': le, 'Raw_LF': lf, 'Raw_LQ': lq
            })
            print(f"    -> Ratio: LE={le/base_le:.4f}, LF={lf/base_lf:.4f}")

    # 保存
    df = pd.DataFrame(results)
    out_path = os.path.join(CURRENT_DIR, '样本内检验结果.csv')
    df.to_csv(out_path, index=False)
    
    print("\n" + "="*60)
    print(df[['v_graph', 'x_graph', 'Ratio_LE', 'Ratio_LF', 'Ratio_LQ']].to_string(index=False))
    print("="*60)
    print(f"结果已保存: {out_path}")

if __name__ == "__main__":
    main()
