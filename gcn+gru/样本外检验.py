import os
import numpy as np
import pandas as pd
from tqdm import tqdm
import warnings
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.covariance import GraphicalLasso
from statsmodels.stats.correlation_tools import cov_nearest

# 导入样本内检验的函数 (复用)
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from 样本内检验 import (
    load_data, 
    normalize_adjacency, 
    estimate_model, 
    predict_model, 
    vector_to_matrix, 
    # calculate_losses, # 不再导入，改用本地定义
    get_adjacency_matrix as get_fixed_adjacency # 重命名避免冲突
)

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
            # 使用 solve 替代 inv，数值上更稳定且稍快
            # trace(inv(H_pred) @ H_true) = trace(solve(H_pred, H_true))
            trace_term = np.trace(np.linalg.solve(H_pred, H_true))
            lq = logdet + trace_term
    except:
        lq = np.nan
        
    return le, lf, lq

# 忽略警告
warnings.filterwarnings('ignore')
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# ================= 配置部分 =================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(CURRENT_DIR, '样本外检验结果')
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# 参数
WINDOW_SIZE = 1000
TEST_SIZE = 96
LAMBDA_GL = 0.1
NUM_STOCKS = 26

# ================= 工具函数 =================

def compute_gl_adjacency(rc_matrices, date_str):
    """
    使用 GL 算法计算邻接矩阵
    rc_matrices: list of (26, 26) matrices
    """
    # 1. 计算 S (平均协方差)
    # 注意: GraphicalLasso 对数据缩放敏感。之前我们在超参数确定中发现
    # 需要将数据缩放 (x 10000) 后，lambda=0.1 才能得到合理的稀疏图
    
    S_mean = np.mean(rc_matrices, axis=0)
    
    # 缩放
    scale_factor = 100.0
    S_scaled = S_mean * (scale_factor ** 2)
    
    # 2. GL 求解
    try:
        model = GraphicalLasso(alpha=LAMBDA_GL, mode='cd', tol=1e-4, max_iter=100, verbose=False)
        model.fit(S_scaled)
        Theta_scaled = model.precision_
        
        # 还原 (虽然这一步对于确定非零结构不是必须的，因为结构在 scaled 上已经确定)
        # Theta = Theta_scaled * (scale_factor ** 2)
        
        # 确定邻接矩阵 A
        # 阈值判定
        max_val = np.max(np.abs(Theta_scaled))
        threshold = 1e-5 * max_val
        A = (np.abs(Theta_scaled) > threshold).astype(float) # 必须 float
        np.fill_diagonal(A, 0)
        
    except Exception as e:
        print(f"  [错误] GL 计算失败 ({date_str}): {e}")
        A = np.zeros((NUM_STOCKS, NUM_STOCKS))
        
    # 保存结果
    npy_path = os.path.join(OUTPUT_DIR, f'GL_Adjacency_{date_str}.npy')
    np.save(npy_path, A)
    
    # 绘图
    plt.figure(figsize=(10, 8))
    sns.heatmap(A, cmap='Blues', square=True, cbar=False)
    plt.title(f'GL Adjacency Matrix ({date_str})')
    plt.savefig(os.path.join(OUTPUT_DIR, f'GL_Adjacency_{date_str}.png'))
    plt.close()
    
    return A

def get_month_str(date_str):
    """提取年月 yyyy-mm"""
    return date_str[:7]

def main():
    # 1. 加载所有数据
    dates, rc_dict, x_dict, v_dict = load_data()
    
    if len(dates) < WINDOW_SIZE + TEST_SIZE:
        print(f"数据量不足: 总共 {len(dates)}, 需要 {WINDOW_SIZE + TEST_SIZE}")
        return
        
    # 确定测试集日期
    test_dates = dates[-TEST_SIZE:]
    print(f"测试集范围: {test_dates[0]} 至 {test_dates[-1]} (共 {len(test_dates)} 天)")
    
    # 定义组合
    v_graphs = ['empty', 'complete', 'GL', 'industry']
    x_graphs = ['empty', 'complete', 'linear']
    
    # 存储预测结果: {combination: {date: (le, lf, lq)}}
    results = {}
    for vg in v_graphs:
        for xg in x_graphs:
            results[(vg, xg)] = {}
            
    # 缓存当前的模型参数
    # current_params[(vg, xg)] = {'alpha_v': ..., 'params_v': ..., 'alpha_x': ..., 'params_x': ...}
    current_params = {}
    
    # 缓存当前的 GL 矩阵 (v_graph='GL' 时使用)
    current_gl_adj = None
    
    # 遍历测试集
    for i, target_date in enumerate(tqdm(test_dates, desc="样本外预测")):
        # 获取当前日期的月份
        current_month = get_month_str(target_date)
        
        # 判断是否需要更新参数
        # 规则: 第一个交易日，或者月份发生变化
        need_update = False
        if i == 0:
            need_update = True
        else:
            prev_date = test_dates[i-1]
            prev_month = get_month_str(prev_date)
            if current_month != prev_month:
                need_update = True
                
        if need_update:
            # print(f"  [更新] {target_date} (新月份/首日)，重新估计参数...")
            
            # 1. 确定训练窗口
            # 读取该交易日过去 1000 个交易日
            # 在 dates 列表中的索引
            target_idx = dates.index(target_date)
            train_start_idx = target_idx - WINDOW_SIZE
            train_dates = dates[train_start_idx : target_idx]
            
            if len(train_dates) != WINDOW_SIZE:
                print(f"  [警告] 训练窗口不足 1000 天 ({len(train_dates)})")
            
            # 2. 更新 GL 矩阵
            # 只有当 v_graph='GL' 时才需要 GL 矩阵
            # 提取 1000 天的 RC 矩阵
            train_rcs = [rc_dict[d] for d in train_dates]
            current_gl_adj = compute_gl_adjacency(train_rcs, target_date)
            
            # 3. 更新所有组合的参数
            for vg in v_graphs:
                # 准备 W_v
                if vg == 'GL':
                    A_v = current_gl_adj
                else:
                    # 使用样本内检验中定义的固定图 (empty, complete, industry)
                    # 注意: industry 也是固定的
                    if vg == 'industry':
                        # 这里需要特别处理，因为 get_fixed_adjacency 需要路径
                        # 我们直接调用样本内检验的函数，它会读取 Industry_Adjacency_Matrix.npy
                        # 确保该文件存在 (之前已经生成)
                        A_v = get_fixed_adjacency('industry', dim=26)
                    else:
                        A_v = get_fixed_adjacency(vg, dim=26)
                
                W_v = normalize_adjacency(A_v)
                
                # 估计 v 模型
                alpha_v, params_v = estimate_model(v_dict, W_v, train_dates)
                
                for xg in x_graphs:
                    # 准备 W_x
                    A_x = get_fixed_adjacency(xg, dim=325)
                    W_x = normalize_adjacency(A_x)
                    
                    # 估计 x 模型
                    alpha_x, params_x = estimate_model(x_dict, W_x, train_dates)
                    
                    # 存储参数
                    current_params[(vg, xg)] = {
                        'alpha_v': alpha_v, 'params_v': params_v, 'W_v': W_v,
                        'alpha_x': alpha_x, 'params_x': params_x, 'W_x': W_x
                    }
        
        # 预测当前交易日 (使用 current_params)
        # 注意: 预测时需要用到 target_date 的历史数据 (t-1, t-5...)
        # predict_model 函数是批量预测，我们这里只需要预测一天
        # 但为了复用代码，我们可以传入 [target_date]，但 predict_model 内部会有 start_idx=22 的截断
        # 所以我们需要构造一个小的时间序列，包含足够的历史数据，最后一天是 target_date
        
        # 构造预测所需的上下文
        # 至少需要 22 天前的数据来计算 lag_m
        target_idx = dates.index(target_date)
        context_start = target_idx - 25 # 多取一点
        context_dates = dates[context_start : target_idx + 1] # 包含 target_date
        
        # 对每种组合进行预测
        H_true = rc_dict[target_date]
        
        for vg in v_graphs:
            for xg in x_graphs:
                params = current_params[(vg, xg)]
                
                # 预测 v
                # 我们需要修改 predict_model 或者手动计算
                # 手动计算更高效，只算这一天
                
                # 构造特征向量 (N, 6)
                # v_lag1: t-1
                v_lag1 = v_dict[dates[target_idx-1]]
                # v_lag_w: t-5...t-2 (4天)
                v_lag_w = np.mean([v_dict[dates[i]] for i in range(target_idx-5, target_idx-1)], axis=0)
                # v_lag_m: t-22...t-6 (17天)
                v_lag_m = np.mean([v_dict[dates[i]] for i in range(target_idx-22, target_idx-5)], axis=0)
                
                W_v = params['W_v']
                feats_v = np.hstack([
                    v_lag1, v_lag_w, v_lag_m, 
                    W_v @ v_lag1, W_v @ v_lag_w, W_v @ v_lag_m
                ])
                
                v_pred = params['alpha_v'] + feats_v @ params['params_v'].reshape(-1, 1)
                
                # 预测 x
                x_lag1 = x_dict[dates[target_idx-1]]
                x_lag_w = np.mean([x_dict[dates[i]] for i in range(target_idx-5, target_idx-1)], axis=0)
                x_lag_m = np.mean([x_dict[dates[i]] for i in range(target_idx-22, target_idx-5)], axis=0)
                
                W_x = params['W_x']
                feats_x = np.hstack([
                    x_lag1, x_lag_w, x_lag_m,
                    W_x @ x_lag1, W_x @ x_lag_w, W_x @ x_lag_m
                ])
                
                x_pred = params['alpha_x'] + feats_x @ params['params_x'].reshape(-1, 1)
                
                # 合成 H_pred
                v_vec = np.maximum(v_pred, 1e-8)
                D_pred = np.diag(np.sqrt(v_vec).flatten())
                R_pred = vector_to_matrix(x_pred, dim=26)
                
                H_pred_raw = D_pred @ R_pred @ D_pred
                
                try:
                    np.linalg.cholesky(H_pred_raw)
                    H_pred = H_pred_raw
                except np.linalg.LinAlgError:
                    H_pred = cov_nearest(H_pred_raw, method='clipped', threshold=1e-6)
                
                # 计算损失
                le, lf, lq = calculate_losses(H_true, H_pred)
                results[(vg, xg)][target_date] = (le, lf, lq)

    # 汇总结果
    print("\n计算汇总统计量...")
    final_summary = []
    
    # 获取基准损失 (empty, empty)
    base_losses = {'LE': [], 'LF': [], 'LQ': []}
    for date in test_dates:
        le, lf, lq = results[('empty', 'empty')][date]
        if not np.isnan(lq):
            base_losses['LE'].append(le)
            base_losses['LF'].append(lf)
            base_losses['LQ'].append(lq)
            
    avg_base_le = np.mean(base_losses['LE'])
    avg_base_lf = np.mean(base_losses['LF'])
    avg_base_lq = np.mean(base_losses['LQ'])
    
    print(f"基准 (Empty-Empty) 平均损失: LE={avg_base_le:.4f}, LF={avg_base_lf:.4f}, LQ={avg_base_lq:.4f}")
    
    # 保存基准损失值到 npy (供后续模型比率计算使用)
    base_losses_array = np.array([avg_base_le, avg_base_lf, avg_base_lq])
    base_loss_path = os.path.join(OUTPUT_DIR, 'base_losses.npy')
    np.save(base_loss_path, base_losses_array)
    print(f"基准损失已保存至: {base_loss_path}")
    
    for vg in v_graphs:
        for xg in x_graphs:
            losses = {'LE': [], 'LF': [], 'LQ': []}
            for date in test_dates:
                le, lf, lq = results[(vg, xg)][date]
                if not np.isnan(lq):
                    losses['LE'].append(le)
                    losses['LF'].append(lf)
                    losses['LQ'].append(lq)
            
            avg_le = np.mean(losses['LE'])
            avg_lf = np.mean(losses['LF'])
            avg_lq = np.mean(losses['LQ'])
            
            final_summary.append({
                'v_graph': vg, 'x_graph': xg,
                'LE': avg_le, 'LF': avg_lf, 'LQ': avg_lq,
                'Ratio_LE': avg_le / avg_base_le,
                'Ratio_LF': avg_lf / avg_base_lf,
                'Ratio_LQ': avg_lq / avg_base_lq
            })
            
    # 输出与保存
    df_res = pd.DataFrame(final_summary)
    out_csv = os.path.join(OUTPUT_DIR, '样本外检验结果汇总.csv')
    df_res.to_csv(out_csv, index=False)
    
    print("\n" + "="*80)
    print(df_res[['v_graph', 'x_graph', 'Ratio_LE', 'Ratio_LF', 'Ratio_LQ']].to_string(index=False))
    print("="*80)
    print(f"结果已保存至: {out_csv}")

if __name__ == "__main__":
    main()
