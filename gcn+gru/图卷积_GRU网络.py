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
# 修改输出目录为子文件夹
OUTPUT_DIR = os.path.join(CURRENT_DIR, '样本外检验结果', 'GCN_GRU')
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
    
# 基准损失文件仍在上一级目录
BASE_LOSS_PATH = os.path.join(CURRENT_DIR, '样本外检验结果', 'base_losses.npy')

# GL 矩阵文件通常复用上一级的，或者在子目录重新生成
# 为了简单，我们让 compute_gl_adjacency 在子目录生成/读取
# 或者指向公共目录。这里指向子目录。

# 参数
TEST_SIZE = 96
GL_WINDOW_SIZE = 500
LAMBDA_GL = 0.1
HIDDEN_DIM = 16
LEARNING_RATE = 0.0005
EPOCHS = 500
BATCH_SIZE = 1 # GRU 需要序列信息，通常使用 batch_size=1 或者精心设计的 batching
# 为了简单实现时序依赖 N_t = GRU(Nt_1, N_{t-1})，我们需要按时间顺序输入
# 因此 Batch Size 设为 1 (Sequence Length = Total Train Days) 或者在 Dataset 中返回整个序列
# 考虑到数据量不大，我们可以把整个训练集作为一个 Batch (Sequence)

NUM_STOCKS = 26
NUM_PAIRS = 325
V_SCALE = 10000.0
WEIGHT_DECAY = 1e-4

# 设备配置
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Using device: {DEVICE}")

# ================= 数据集类 (修改为返回整个序列) =================

class TimeSeriesDataset(Dataset):
    def __init__(self, data_list, adj_list):
        """
        data_list: list of (M_t, target_t) 按时间排序
        adj_list: list of A_t
        """
        # 将 list 转换为 tensor 序列
        # M_t shape: (Time, Nodes, Features)
        # Target shape: (Time, Nodes)
        # Adj shape: (Time, Nodes, Nodes)
        
        self.M_seq = torch.stack([torch.FloatTensor(m) for m, _ in data_list])
        self.target_seq = torch.stack([torch.FloatTensor(t) for _, t in data_list])
        self.adj_seq = torch.stack([torch.FloatTensor(a) for a in adj_list])
        
    def __len__(self):
        return 1 # 只有一个序列
    
    def __getitem__(self, idx):
        return self.M_seq, self.adj_seq, self.target_seq

# ================= 模型定义 (GCN-GRU) =================

class GCN_GRU(nn.Module):
    def __init__(self, input_dim=3, hidden_dim=16, output_dim=1):
        super(GCN_GRU, self).__init__()
        self.hidden_dim = hidden_dim
        
        # GCN 部分 (Nt_1 计算)
        self.theta = nn.Linear(input_dim * 2, hidden_dim)
        self.relu = nn.ReLU()
        
        # GRU 部分
        # 输入维度: hidden_dim (Nt_1 的维度)
        # 隐藏层维度: hidden_dim (N_t 的维度)
        # GRUCell 处理单个时间步
        self.gru_cell = nn.GRUCell(hidden_dim, hidden_dim)
        
        # 输出层
        self.S = nn.Linear(hidden_dim, output_dim)
        
    def forward(self, M_seq, W_seq):
        """
        M_seq: (Time, Nodes, 3)
        W_seq: (Time, Nodes, Nodes)
        返回: (Time, Nodes)
        """
        seq_len, num_nodes, _ = M_seq.size()
        outputs = []
        
        # 初始化 N_{t-1} 为 0
        # GRUCell 需要 input (Batch, Input_Dim) 和 hidden (Batch, Hidden_Dim)
        # 这里我们将 Nodes 视为 Batch 维度，因为 GRU 是对每个节点独立的时间序列建模
        # 或者是对整个图状态建模？
        # 题目: N_t = GRU(Nt(1), N_{t-1})
        # Nt(1) 是 (Nodes, Hidden)
        # N_{t-1} 也是 (Nodes, Hidden)
        # 这意味着每个节点有自己的 GRU 状态，或者参数共享但状态独立
        
        h_t = torch.zeros(num_nodes, self.hidden_dim).to(M_seq.device)
        
        for t in range(seq_len):
            Mt = M_seq[t] # (Nodes, 3)
            Wt = W_seq[t] # (Nodes, Nodes)
            
            # 1. GCN Layer -> Nt(1)
            # Mt_tilde = W * Mt
            Mt_tilde = torch.mm(Wt, Mt) # (Nodes, 3)
            Nt_0 = torch.cat([Mt, Mt_tilde], dim=1) # (Nodes, 6)
            Nt_1 = self.relu(self.theta(Nt_0)) # (Nodes, Hidden)
            
            # 2. GRU Layer -> N_t
            # h_t = GRU(input=Nt_1, hidden=h_t_prev)
            h_t = self.gru_cell(Nt_1, h_t) # (Nodes, Hidden)
            
            # 3. Output -> vt
            out_t = self.S(h_t) # (Nodes, 1)
            outputs.append(out_t)
            
        return torch.stack(outputs).squeeze(-1) # (Time, Nodes)

    def forward_step(self, Mt, Wt, h_t_prev):
        """
        单步预测 (用于测试阶段)
        """
        # GCN
        Mt_tilde = torch.mm(Wt, Mt)
        Nt_0 = torch.cat([Mt, Mt_tilde], dim=1)
        Nt_1 = self.relu(self.theta(Nt_0))
        
        # GRU
        h_t = self.gru_cell(Nt_1, h_t_prev)
        
        # Output
        out_t = self.S(h_t)
        
        return out_t.squeeze(-1), h_t

# ================= 辅助函数 =================

def compute_gl_adjacency(rc_matrices, date_str):
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
    train_end_idx = len(dates) - TEST_SIZE
    train_dates = dates[:train_end_idx]
    
    # 训练起始点 1500
    train_start_idx = 1500
    
    v_data = []
    v_adj = []
    x_data = []
    x_adj = []
    
    current_gl_adj = None
    linear_adj = get_fixed_adjacency('linear', dim=325)
    linear_W = normalize_adjacency(linear_adj)
    
    for i in tqdm(range(train_start_idx, train_end_idx), desc="构建训练集"):
        curr_date = dates[i]
        
        # v data
        need_update = False
        if i == train_start_idx:
            need_update = True
        else:
            prev_date = dates[i-1]
            if get_month_str(curr_date) != get_month_str(prev_date):
                need_update = True
        
        if need_update:
            window_start = i - GL_WINDOW_SIZE
            window_rcs = [rc_dict[d] for d in dates[window_start:i]]
            current_gl_adj = compute_gl_adjacency(window_rcs, curr_date)
            
        current_gl_W = normalize_adjacency(current_gl_adj)
        
        v_lag1 = v_dict[dates[i-1]]
        v_lag_w = np.mean([v_dict[dates[k]] for k in range(i-5, i-1)], axis=0)
        v_lag_m = np.mean([v_dict[dates[k]] for k in range(i-22, i-5)], axis=0)
        
        Mt = np.hstack([v_lag1, v_lag_w, v_lag_m]) * V_SCALE
        target = v_dict[curr_date].flatten() * V_SCALE
        
        v_data.append((Mt, target))
        v_adj.append(current_gl_W)
        
        # x data
        x_lag1 = x_dict[dates[i-1]]
        x_lag_w = np.mean([x_dict[dates[k]] for k in range(i-5, i-1)], axis=0)
        x_lag_m = np.mean([x_dict[dates[k]] for k in range(i-22, i-5)], axis=0)
        
        Mt_x = np.hstack([x_lag1, x_lag_w, x_lag_m])
        target_x = x_dict[curr_date].flatten()
        
        x_data.append((Mt_x, target_x))
        x_adj.append(linear_W)

    return v_data, v_adj, x_data, x_adj

def train_model(model_name, dataset, input_dim=3, hidden_dim=16, epochs=50):
    print(f"\n开始训练 {model_name} 模型 (GCN-GRU)...")
    # Batch Size = 1 (Full Sequence Training)
    loader = DataLoader(dataset, batch_size=1, shuffle=False)
    
    model = GCN_GRU(input_dim, hidden_dim).to(DEVICE)
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    criterion = nn.MSELoss()
    
    loss_history = []
    
    model.train()
    for epoch in range(epochs):
        epoch_loss = 0
        for M_seq, W_seq, target_seq in loader:
            M_seq = M_seq.squeeze(0).to(DEVICE) # (Time, Nodes, 3)
            W_seq = W_seq.squeeze(0).to(DEVICE)
            target_seq = target_seq.squeeze(0).to(DEVICE)
            
            optimizer.zero_grad()
            
            # Forward pass over the entire sequence
            outputs = model(M_seq, W_seq)
            
            loss = criterion(outputs, target_seq)
            loss.backward()
            
            # 梯度裁剪防止梯度爆炸
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            
            optimizer.step()
            epoch_loss += loss.item()
            
        loss_history.append(epoch_loss)
        if (epoch + 1) % 10 == 0:
            print(f"Epoch [{epoch+1}/{epochs}], Loss: {epoch_loss:.6e}")
            
    # 保存模型
    model_path = os.path.join(OUTPUT_DIR, f'{model_name}_gru_model.pth')
    torch.save(model.state_dict(), model_path)
    print(f"模型已保存至: {model_path}")
    
    # 绘制损失曲线
    plt.figure()
    plt.plot(loss_history)
    plt.title(f'{model_name} (GRU) Training Loss')
    plt.xlabel('Epoch')
    plt.ylabel('MSE Loss')
    plt.savefig(os.path.join(OUTPUT_DIR, f'{model_name}_gru_loss.png'))
    plt.close()
    
    return model

def plot_covariance_comparison(H_true, H_pred, date):
    fig, axes = plt.subplots(1, 2, figsize=(20, 8))
    vmin = min(np.min(H_true), np.min(H_pred))
    vmax = max(np.max(H_true), np.max(H_pred))
    sns.heatmap(H_true, ax=axes[0], cmap='RdBu_r', center=0, square=True, vmin=vmin, vmax=vmax)
    axes[0].set_title(f'真实协方差矩阵 ({date})')
    sns.heatmap(H_pred, ax=axes[1], cmap='RdBu_r', center=0, square=True, vmin=vmin, vmax=vmax)
    axes[1].set_title(f'GCN-GRU 预测矩阵 ({date})')
    plt.savefig(os.path.join(OUTPUT_DIR, f'GCN_GRU_Comparison_{date}.png'))
    plt.close()

def plot_correlation_comparison(R_true, R_pred, date):
    fig, axes = plt.subplots(1, 2, figsize=(20, 8))
    vmin = min(np.min(R_true), np.min(R_pred))
    vmax = max(np.max(R_true), np.max(R_pred))
    sns.heatmap(R_true, ax=axes[0], cmap='coolwarm', center=0, square=True, vmin=vmin, vmax=vmax)
    axes[0].set_title(f'真实相关系数矩阵 ({date})')
    sns.heatmap(R_pred, ax=axes[1], cmap='coolwarm', center=0, square=True, vmin=vmin, vmax=vmax)
    axes[1].set_title(f'GCN-GRU 预测相关系数 ({date})')
    plt.savefig(os.path.join(OUTPUT_DIR, f'GCN_GRU_Correlation_Comparison_{date}.png'))
    plt.close()

def test_models(dates, rc_dict, x_dict, v_dict):
    print("\n开始样本外测试 (GCN-GRU)...")
    
    v_model = GCN_GRU(input_dim=3, hidden_dim=HIDDEN_DIM).to(DEVICE)
    x_model = GCN_GRU(input_dim=3, hidden_dim=HIDDEN_DIM).to(DEVICE)
    
    v_path = os.path.join(OUTPUT_DIR, 'v_model_gru_model.pth')
    x_path = os.path.join(OUTPUT_DIR, 'x_model_gru_model.pth')
    
    if not os.path.exists(v_path) or not os.path.exists(x_path):
        print("模型文件不存在")
        return
        
    v_model.load_state_dict(torch.load(v_path))
    x_model.load_state_dict(torch.load(x_path))
    
    # 使用正确的基准损失路径
    base_losses = np.load(BASE_LOSS_PATH)
    
    test_dates = dates[-TEST_SIZE:]
    le_list, lf_list, lq_list = [], [], []
    plot_indices = [0, TEST_SIZE//2, TEST_SIZE-1]
    
    v_model.eval()
    x_model.eval()
    
    # 需要先跑一遍训练集来获取最终的 hidden state
    # 或者，我们假设测试集的第一个 h_t 初始化为 0 (不太准确，但可行)
    # 更好的做法是：利用训练集最后的状态作为测试集的初始状态
    # 为了实现这一点，我们需要再跑一遍前向传播（不计算梯度）
    
    print("预热模型状态...")
    v_data, v_adj, x_data, x_adj = prepare_data(dates, rc_dict, x_dict, v_dict)
    
    # 预热 v_model
    M_seq_v = torch.stack([torch.FloatTensor(m) for m, _ in v_data]).to(DEVICE)
    W_seq_v = torch.stack([torch.FloatTensor(a) for a in v_adj]).to(DEVICE)
    with torch.no_grad():
        _, h_t_v = v_model.forward_step(M_seq_v[-1], W_seq_v[-1], torch.zeros(NUM_STOCKS, HIDDEN_DIM).to(DEVICE))
        # Wait, forward_step 只跑一步。我们需要跑整个序列得到最后的 h_t
        # 修改 GCN_GRU.forward 让它返回最后的 hidden state?
        # 或者我们直接手动循环
        
        h_t_v = torch.zeros(NUM_STOCKS, HIDDEN_DIM).to(DEVICE)
        for t in range(len(M_seq_v)):
            _, h_t_v = v_model.forward_step(M_seq_v[t], W_seq_v[t], h_t_v)
            
    # 预热 x_model
    M_seq_x = torch.stack([torch.FloatTensor(m) for m, _ in x_data]).to(DEVICE)
    W_seq_x = torch.stack([torch.FloatTensor(a) for a in x_adj]).to(DEVICE)
    with torch.no_grad():
        h_t_x = torch.zeros(NUM_PAIRS, HIDDEN_DIM).to(DEVICE)
        for t in range(len(M_seq_x)):
            _, h_t_x = x_model.forward_step(M_seq_x[t], W_seq_x[t], h_t_x)
            
    print("状态预热完成，开始滚动预测...")
    
    current_gl_adj = None
    linear_adj = get_fixed_adjacency('linear', dim=325)
    linear_W = normalize_adjacency(linear_adj)
    linear_W_tensor = torch.FloatTensor(linear_W).to(DEVICE)
    
    with torch.no_grad():
        for i, target_date in enumerate(tqdm(test_dates, desc="测试中")):
            idx = dates.index(target_date)
            
            # v model input
            need_update = False
            if i == 0: need_update = True
            else:
                if get_month_str(target_date) != get_month_str(test_dates[i-1]): need_update = True
            
            if need_update:
                window_start = idx - GL_WINDOW_SIZE
                window_rcs = [rc_dict[d] for d in dates[window_start:idx]]
                current_gl_adj = compute_gl_adjacency(window_rcs, target_date)
            
            current_gl_W = normalize_adjacency(current_gl_adj)
            current_gl_W_tensor = torch.FloatTensor(current_gl_W).to(DEVICE)
            
            v_lag1 = v_dict[dates[idx-1]]
            v_lag_w = np.mean([v_dict[dates[k]] for k in range(idx-5, idx-1)], axis=0)
            v_lag_m = np.mean([v_dict[dates[k]] for k in range(idx-22, idx-5)], axis=0)
            Mt_v = np.hstack([v_lag1, v_lag_w, v_lag_m]) * V_SCALE
            Mt_v_tensor = torch.FloatTensor(Mt_v).to(DEVICE)
            
            # Step forward
            v_pred_tensor, h_t_v = v_model.forward_step(Mt_v_tensor, current_gl_W_tensor, h_t_v)
            v_pred = v_pred_tensor.cpu().numpy().flatten() / V_SCALE
            
            # x model input
            x_lag1 = x_dict[dates[idx-1]]
            x_lag_w = np.mean([x_dict[dates[k]] for k in range(idx-5, idx-1)], axis=0)
            x_lag_m = np.mean([x_dict[dates[k]] for k in range(idx-22, idx-5)], axis=0)
            Mt_x = np.hstack([x_lag1, x_lag_w, x_lag_m])
            Mt_x_tensor = torch.FloatTensor(Mt_x).to(DEVICE)
            
            # Step forward
            x_pred_tensor, h_t_x = x_model.forward_step(Mt_x_tensor, linear_W_tensor, h_t_x)
            x_pred = x_pred_tensor.cpu().numpy().flatten()
            
            # 合成
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
                
            np.save(os.path.join(OUTPUT_DIR, f'GCN_GRU_Pred_{target_date}.npy'), H_pred)
            
            if i in plot_indices:
                plot_covariance_comparison(H_true, H_pred, target_date)
                x_true = x_dict[target_date]
                R_true = vector_to_matrix(x_true, dim=26)
                plot_correlation_comparison(R_true, R_pred, target_date)
                
            le, lf, lq = calculate_losses(H_true, H_pred)
            if not np.isnan(lq):
                le_list.append(le)
                lf_list.append(lf)
                lq_list.append(lq)
                
    avg_le = np.mean(le_list)
    avg_lf = np.mean(lf_list)
    avg_lq = np.mean(lq_list)
    
    print("\n" + "="*40)
    print("GCN-GRU 测试结果:")
    print(f"LE: {avg_le:.4f} (Ratio: {avg_le/base_losses[0]:.4f})")
    print(f"LF: {avg_lf:.4f} (Ratio: {avg_lf/base_losses[1]:.4f})")
    print(f"LQ: {avg_lq:.4f} (Ratio: {avg_lq/base_losses[2]:.4f})")
    print("="*40)
    
    res_df = pd.DataFrame([{
        'Model': 'GCN-GRU',
        'LE': avg_le, 'LF': avg_lf, 'LQ': avg_lq,
        'Ratio_LE': avg_le/base_losses[0],
        'Ratio_LF': avg_lf/base_losses[1],
        'Ratio_LQ': avg_lq/base_losses[2]
    }])
    res_df.to_csv(os.path.join(OUTPUT_DIR, 'GCN_GRU_test_results.csv'), index=False)

def main():
    dates, rc_dict, x_dict, v_dict = load_data()
    v_data, v_adj, x_data, x_adj = prepare_data(dates, rc_dict, x_dict, v_dict)
    
    v_dataset = TimeSeriesDataset(v_data, v_adj)
    x_dataset = TimeSeriesDataset(x_data, x_adj)
    
    v_model = train_model('v_model', v_dataset, input_dim=3, hidden_dim=HIDDEN_DIM, epochs=1000)
    x_model = train_model('x_model', x_dataset, input_dim=3, hidden_dim=HIDDEN_DIM, epochs=250)
    
    test_models(dates, rc_dict, x_dict, v_dict)

if __name__ == "__main__":
    main()
