import os
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from tqdm import tqdm
import warnings
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.covariance import GraphicalLasso
from statsmodels.stats.correlation_tools import cov_nearest

# 复用之前的工具函数
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from 样本内检验 import (
    load_data, 
    normalize_adjacency, 
    vector_to_matrix,
    get_adjacency_matrix as get_fixed_adjacency
)
from 样本外检验 import calculate_losses

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
TEST_SIZE = 96
GL_WINDOW_SIZE = 500
LAMBDA_GL = 0.1
HIDDEN_DIM = 16
LEARNING_RATE = 0.001
EPOCHS = 150
BATCH_SIZE = 32
NUM_STOCKS = 26
NUM_PAIRS = 325
V_SCALE = 10000.0  # v 向量的缩放因子
WEIGHT_DECAY = 1e-4 # L2 正则化系数

# 设备配置
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Using device: {DEVICE}")

# ================= 数据集类 =================

class GCN_Dataset(Dataset):
    def __init__(self, data_list, adj_list):
        """
        data_list: list of (M_t, target_t)
        adj_list: list of A_t (adjacency matrix)
        """
        self.data_list = data_list
        self.adj_list = adj_list
        
    def __len__(self):
        return len(self.data_list)
    
    def __getitem__(self, idx):
        M_t, target_t = self.data_list[idx]
        A_t = self.adj_list[idx]
        return (
            torch.FloatTensor(M_t), 
            torch.FloatTensor(A_t), 
            torch.FloatTensor(target_t)
        )

# ================= 模型定义 =================

class ShallowGCN(nn.Module):
    def __init__(self, input_dim=3, hidden_dim=16, output_dim=1):
        super(ShallowGCN, self).__init__()
        # Nt_0 = [Mt, Mt_~] -> input_dim * 2
        self.theta = nn.Linear(input_dim * 2, hidden_dim)
        self.relu = nn.ReLU()
        self.S = nn.Linear(hidden_dim, output_dim)
        
    def forward(self, Mt, W):
        """
        Mt: (Batch, N, 3)
        W: (Batch, N, N)
        """
        # 1. 计算 Mt_~ = W * Mt
        Mt_tilde = torch.bmm(W, Mt) # (Batch, N, 3)
        
        # 2. Nt_0 = [Mt, Mt_~]
        Nt_0 = torch.cat([Mt, Mt_tilde], dim=2) # (Batch, N, 6)
        
        # 3. Nt_1 = Relu(Nt_0 * theta)
        Nt_1 = self.relu(self.theta(Nt_0)) # (Batch, N, F)
        
        # 4. vt^ = Nt_1 * S
        out = self.S(Nt_1) # (Batch, N, 1)
        
        return out.squeeze(-1) # (Batch, N)

# ================= 辅助函数 =================

def compute_gl_adjacency(rc_matrices, date_str):
    """
    计算 GL 邻接矩阵并保存 (复用样本外检验逻辑)
    """
    # 检查是否已存在
    npy_path = os.path.join(OUTPUT_DIR, f'GL_Adjacency_Window500_{date_str}.npy')
    if os.path.exists(npy_path):
        return np.load(npy_path)

    S_mean = np.mean(rc_matrices, axis=0)
    scale_factor = 100.0
    S_scaled = S_mean * (scale_factor ** 2)
    
    try:
        model = GraphicalLasso(alpha=LAMBDA_GL, mode='cd', tol=1e-4, max_iter=100, verbose=False)
        model.fit(S_scaled)
        Theta_scaled = model.precision_
        max_val = np.max(np.abs(Theta_scaled))
        threshold = 1e-5 * max_val
        A = (np.abs(Theta_scaled) > threshold).astype(float)
        np.fill_diagonal(A, 0)
    except:
        A = np.zeros((NUM_STOCKS, NUM_STOCKS))
        
    np.save(npy_path, A)
    return A

def get_month_str(date_str):
    return date_str[:7]

def prepare_data(dates, rc_dict, x_dict, v_dict):
    """
    准备训练数据
    """
    print("准备数据中...")
    
    # 确定训练集范围
    # 总样本 3793，测试集 96
    # 训练集: 0 ~ 3793-96-1
    train_end_idx = len(dates) - TEST_SIZE
    train_dates = dates[:train_end_idx]
    
    # 确定有效训练起始点 (因为需要回溯 500 天计算 GL，且模型需要回溯 22 天特征)
    # 对于 v 模型: 
    # 从 1501 个交易日开始预测训练 (index 1500)
    train_start_idx = 1500
    
    v_data = []
    v_adj = []
    
    x_data = []
    x_adj = []
    
    # 缓存当前的 GL 矩阵
    current_gl_adj = None
    
    # 线性图 (x模型全局使用)
    linear_adj = get_fixed_adjacency('linear', dim=325)
    linear_W = normalize_adjacency(linear_adj)
    
    for i in tqdm(range(train_start_idx, train_end_idx), desc="构建训练集"):
        curr_date = dates[i]
        
        # --- 1. v 模型数据准备 ---
        # 更新 GL 矩阵逻辑
        # 如果是第一个点，或者月份变化
        need_update = False
        if i == train_start_idx:
            need_update = True
        else:
            prev_date = dates[i-1]
            if get_month_str(curr_date) != get_month_str(prev_date):
                need_update = True
        
        if need_update:
            # 使用过去 500 天计算 GL
            window_start = i - GL_WINDOW_SIZE
            window_rcs = [rc_dict[d] for d in dates[window_start:i]]
            current_gl_adj = compute_gl_adjacency(window_rcs, curr_date)
            
        current_gl_W = normalize_adjacency(current_gl_adj)
        
        # 构建特征 Mt
        # v_t-1
        v_lag1 = v_dict[dates[i-1]]
        # v_t-5:t-2 (4天)
        v_lag_w = np.mean([v_dict[dates[k]] for k in range(i-5, i-1)], axis=0)
        # v_t-22:t-6 (17天)
        v_lag_m = np.mean([v_dict[dates[k]] for k in range(i-22, i-5)], axis=0)
        
        Mt = np.hstack([v_lag1, v_lag_w, v_lag_m]) # (N, 3)
        target = v_dict[curr_date].flatten() # (N,)
        
        # 应用缩放
        Mt = Mt * V_SCALE
        target = target * V_SCALE
        
        v_data.append((Mt, target))
        v_adj.append(current_gl_W)
        
        # --- 2. x 模型数据准备 ---
        # x 模型从第 23 个交易日开始就可以训练 (index 22)
        pass

    # 补充 x 模型数据 (从 index 1500 开始)
    print("补充 x 模型数据...")
    for i in tqdm(range(train_start_idx, train_end_idx), desc="构建 x 训练集"):
        curr_date = dates[i]
        
        x_lag1 = x_dict[dates[i-1]]
        x_lag_w = np.mean([x_dict[dates[k]] for k in range(i-5, i-1)], axis=0)
        x_lag_m = np.mean([x_dict[dates[k]] for k in range(i-22, i-5)], axis=0)
        
        Mt_x = np.hstack([x_lag1, x_lag_w, x_lag_m]) # (325, 3)
        target_x = x_dict[curr_date].flatten()
        
        x_data.append((Mt_x, target_x))
        # x 模型始终使用线性图
        x_adj.append(linear_W)

    return v_data, v_adj, x_data, x_adj

def train_model(model_name, dataset, input_dim=3, hidden_dim=16, epochs=50):
    print(f"\n开始训练 {model_name} 模型...")
    loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)
    model = ShallowGCN(input_dim, hidden_dim).to(DEVICE)
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    criterion = nn.MSELoss()
    
    loss_history = []
    
    model.train()
    for epoch in range(epochs):
        epoch_loss = 0
        for Mt, W, target in loader:
            Mt, W, target = Mt.to(DEVICE), W.to(DEVICE), target.to(DEVICE)
            
            optimizer.zero_grad()
            output = model(Mt, W)
            loss = criterion(output, target)
            loss.backward()
            optimizer.step()
            
            epoch_loss += loss.item()
            
        avg_loss = epoch_loss / len(loader)
        loss_history.append(avg_loss)
        if (epoch + 1) % 10 == 0:
            print(f"Epoch [{epoch+1}/{epochs}], Loss: {avg_loss:.6e}")
            
    # 保存模型
    model_path = os.path.join(OUTPUT_DIR, f'{model_name}_model.pth')
    torch.save(model.state_dict(), model_path)
    print(f"模型已保存至: {model_path}")
    
    # 绘制损失曲线
    plt.figure()
    plt.plot(loss_history)
    plt.title(f'{model_name} Training Loss')
    plt.xlabel('Epoch')
    plt.ylabel('MSE Loss')
    plt.savefig(os.path.join(OUTPUT_DIR, f'{model_name}_loss.png'))
    plt.close()
    
    return model

def plot_covariance_comparison(H_true, H_pred, date):
    """
    绘制对比图 (复用样本内检验逻辑，但增加 vmin/vmax 统一)
    """
    fig, axes = plt.subplots(1, 2, figsize=(20, 8))
    
    vmin = min(np.min(H_true), np.min(H_pred))
    vmax = max(np.max(H_true), np.max(H_pred))
    
    sns.heatmap(H_true, ax=axes[0], cmap='RdBu_r', center=0, square=True, vmin=vmin, vmax=vmax)
    axes[0].set_title(f'真实协方差矩阵 ({date})')
    
    sns.heatmap(H_pred, ax=axes[1], cmap='RdBu_r', center=0, square=True, vmin=vmin, vmax=vmax)
    axes[1].set_title(f'SGCN 预测矩阵 ({date})')
    
    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, f'SGCN_Comparison_{date}.png')
    plt.savefig(output_path)
    plt.close()
    print(f"  [绘图] 已保存对比图: {output_path}")

def plot_correlation_comparison(R_true, R_pred, date):
    """
    绘制相关系数矩阵对比图
    """
    fig, axes = plt.subplots(1, 2, figsize=(20, 8))
    
    # 相关系数范围本身在 [-1, 1]，但为了统一，取数据的实际范围
    vmin = min(np.min(R_true), np.min(R_pred))
    vmax = max(np.max(R_true), np.max(R_pred))
    
    # 使用 'coolwarm' 或 'RdBu_r' 这种适合正负值的配色
    sns.heatmap(R_true, ax=axes[0], cmap='coolwarm', center=0, square=True, vmin=vmin, vmax=vmax)
    axes[0].set_title(f'真实相关系数矩阵 ({date})')
    
    sns.heatmap(R_pred, ax=axes[1], cmap='coolwarm', center=0, square=True, vmin=vmin, vmax=vmax)
    axes[1].set_title(f'SGCN 预测相关系数 ({date})')
    
    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, f'SGCN_Correlation_Comparison_{date}.png')
    plt.savefig(output_path)
    plt.close()
    print(f"  [绘图] 已保存相关系数对比图: {output_path}")

def test_models(dates, rc_dict, x_dict, v_dict):
    """
    加载保存的模型参数进行样本外测试
    """
    print("\n开始样本外测试...")
    
    # 重新初始化模型并加载权重
    v_model = ShallowGCN(input_dim=3, hidden_dim=HIDDEN_DIM).to(DEVICE)
    x_model = ShallowGCN(input_dim=3, hidden_dim=HIDDEN_DIM).to(DEVICE)
    
    v_path = os.path.join(OUTPUT_DIR, 'v_model_model.pth')
    x_path = os.path.join(OUTPUT_DIR, 'x_model_model.pth')
    
    if not os.path.exists(v_path) or not os.path.exists(x_path):
        print(f"模型文件不存在，无法测试: {v_path} 或 {x_path}")
        return
        
    v_model.load_state_dict(torch.load(v_path))
    x_model.load_state_dict(torch.load(x_path))
    print(f"成功加载模型参数: {v_path}, {x_path}")
    
    # 加载基准损失
    base_loss_path = os.path.join(OUTPUT_DIR, 'base_losses.npy')
    if not os.path.exists(base_loss_path):
        print("未找到基准损失文件，无法计算比率")
        return
    base_losses = np.load(base_loss_path)
    print(f"基准损失 (LE, LF, LQ): {base_losses}")
    
    test_dates = dates[-TEST_SIZE:]
    
    le_list, lf_list, lq_list = [], [], []
    
    # 缓存 GL 矩阵 (测试阶段同样需要动态更新)
    current_gl_adj = None
    linear_adj = get_fixed_adjacency('linear', dim=325)
    linear_W = normalize_adjacency(linear_adj)
    linear_W_tensor = torch.FloatTensor(linear_W).unsqueeze(0).to(DEVICE) # (1, N, N)
    
    # 确定需要绘图的日期索引 (例如第 0, 48, 95 个)
    plot_indices = [0, TEST_SIZE//2, TEST_SIZE-1]
    
    v_model.eval()
    x_model.eval()
    
    with torch.no_grad():
        for i, target_date in enumerate(tqdm(test_dates, desc="测试中")):
            # 获取该日期在全列表中的索引
            idx = dates.index(target_date)
            
            # 1. 更新 v 模型的 GL 矩阵
            need_update = False
            if i == 0:
                need_update = True
            else:
                prev_date = test_dates[i-1]
                if get_month_str(target_date) != get_month_str(prev_date):
                    need_update = True
            
            if need_update:
                window_start = idx - GL_WINDOW_SIZE
                window_rcs = [rc_dict[d] for d in dates[window_start:idx]]
                current_gl_adj = compute_gl_adjacency(window_rcs, target_date)
                
            current_gl_W = normalize_adjacency(current_gl_adj)
            current_gl_W_tensor = torch.FloatTensor(current_gl_W).unsqueeze(0).to(DEVICE)
            
            # 2. 预测 v
            v_lag1 = v_dict[dates[idx-1]]
            v_lag_w = np.mean([v_dict[dates[k]] for k in range(idx-5, idx-1)], axis=0)
            v_lag_m = np.mean([v_dict[dates[k]] for k in range(idx-22, idx-5)], axis=0)
            
            Mt_v = np.hstack([v_lag1, v_lag_w, v_lag_m])
            # 应用缩放
            Mt_v = Mt_v * V_SCALE
            
            Mt_v_tensor = torch.FloatTensor(Mt_v).unsqueeze(0).to(DEVICE) # (1, N, 3)
            
            v_pred_tensor = v_model(Mt_v_tensor, current_gl_W_tensor)
            v_pred = v_pred_tensor.cpu().numpy().flatten()
            
            # 还原缩放
            v_pred = v_pred / V_SCALE
            
            # [调试] 检查预测值量级
            if i == 0:
                print(f"\n[调试] 预测值检查 (第一个测试日):")
                print(f"  v_pred 均值: {np.mean(v_pred):.6e} (预期 ~1e-4)")
                print(f"  v_pred 最大值: {np.max(v_pred):.6e}")
                print(f"  v_pred 最小值: {np.min(v_pred):.6e}")
            
            # 3. 预测 x
            x_lag1 = x_dict[dates[idx-1]]
            x_lag_w = np.mean([x_dict[dates[k]] for k in range(idx-5, idx-1)], axis=0)
            x_lag_m = np.mean([x_dict[dates[k]] for k in range(idx-22, idx-5)], axis=0)
            
            Mt_x = np.hstack([x_lag1, x_lag_w, x_lag_m])
            Mt_x_tensor = torch.FloatTensor(Mt_x).unsqueeze(0).to(DEVICE)
            
            x_pred_tensor = x_model(Mt_x_tensor, linear_W_tensor)
            x_pred = x_pred_tensor.cpu().numpy().flatten()
            
            # 4. 合成 H_pred
            H_true = rc_dict[target_date]
            
            v_vec = np.maximum(v_pred, 1e-8)
            D_pred = np.diag(np.sqrt(v_vec))
            R_pred = vector_to_matrix(x_pred.reshape(-1, 1), dim=26)
            
            H_pred_raw = D_pred @ R_pred @ D_pred
            
            try:
                np.linalg.cholesky(H_pred_raw)
                H_pred = H_pred_raw
            except:
                H_pred = cov_nearest(H_pred_raw, method='clipped', threshold=1e-6)
                
            # 保存预测矩阵
            npy_save_path = os.path.join(OUTPUT_DIR, f'SGCN_Pred_Cov_{target_date}.npy')
            np.save(npy_save_path, H_pred)
            
            # 绘图 (如果是选定日期)
            if i in plot_indices:
                plot_covariance_comparison(H_true, H_pred, target_date)
                
                # 额外绘制相关系数矩阵对比
                # 需要获取真实的 x_vec -> R_true
                x_true = x_dict[target_date]
                R_true = vector_to_matrix(x_true, dim=26)
                plot_correlation_comparison(R_true, R_pred, target_date)
                
            le, lf, lq = calculate_losses(H_true, H_pred)
            if not np.isnan(lq):
                le_list.append(le)
                lf_list.append(lf)
                lq_list.append(lq)
                
    # 汇总结果
    avg_le = np.mean(le_list)
    avg_lf = np.mean(lf_list)
    avg_lq = np.mean(lq_list)
    
    print("\n" + "="*40)
    print("浅层图卷积网络 (SGCN) 测试结果:")
    print(f"LE: {avg_le:.4f} (Ratio: {avg_le/base_losses[0]:.4f})")
    print(f"LF: {avg_lf:.4f} (Ratio: {avg_lf/base_losses[1]:.4f})")
    print(f"LQ: {avg_lq:.4f} (Ratio: {avg_lq/base_losses[2]:.4f})")
    print("="*40)
    
    # 保存结果到 csv
    res_df = pd.DataFrame([{
        'Model': 'SGCN',
        'LE': avg_le, 'LF': avg_lf, 'LQ': avg_lq,
        'Ratio_LE': avg_le/base_losses[0],
        'Ratio_LF': avg_lf/base_losses[1],
        'Ratio_LQ': avg_lq/base_losses[2]
    }])
    res_df.to_csv(os.path.join(OUTPUT_DIR, 'SGCN_test_results.csv'), index=False)

def main():
    # 1. 加载数据
    dates, rc_dict, x_dict, v_dict = load_data()
    
    # 2. 准备数据集
    v_data, v_adj, x_data, x_adj = prepare_data(dates, rc_dict, x_dict, v_dict)
    
    v_dataset = GCN_Dataset(v_data, v_adj)
    x_dataset = GCN_Dataset(x_data, x_adj)
    
    # 3. 训练模型 (如果需要重新训练，请取消注释)
    # v_model = train_model('v_model', v_dataset, input_dim=3, hidden_dim=HIDDEN_DIM, epochs=EPOCHS)
    # x_model = train_model('x_model', x_dataset, input_dim=3, hidden_dim=HIDDEN_DIM, epochs=EPOCHS)
    
    # 4. 测试模型 (直接加载参数)
    test_models(dates, rc_dict, x_dict, v_dict)

if __name__ == "__main__":
    main()
