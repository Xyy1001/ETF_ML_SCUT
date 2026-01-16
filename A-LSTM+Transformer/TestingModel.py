"""
模型构建Transformer+LSTM
1. 构建Transformer+LSTM融合模型
2. 训练模型
3. 评估模型（不知道用什么可视化框架）
4. 保存模型
"""
from pyexpat import model
from re import split
import re
from sqlite3 import Time
import dotenv
import os
import pandas as pd
import numpy as np
import math
import warnings
# warnings.filterwarnings('ignore')
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.model_selection import train_test_split
import matplotlib.pyplot as plt

def load_stock_data():
    # 循环读取文件夹中所有文件的数据
    # folder = "Transformer+LSTM/Advanced/sketch"
    folder = input("请输入数据文件夹路径: ")
    files = os.listdir(folder)

    # 读取数据
    dataframes = []
    for file in files:
        if file.endswith(".csv"):
            df = pd.read_csv(os.path.join(folder, file))
            # 保存文件名到 DataFrame，便于后续输出
            try:
                df.name = file
            except Exception:
                pass
            dataframes.append(df)

    print(f"读取到 {len(dataframes)} 个数据文件")
    print(f"数据文件列表: {files}")
    # print(dataframes)
    return dataframes


def predict_next_n_days(data, model_path, input_window=100, predict_days=10):
    """
    使用训练好的模型（非严格加载权重）对给定股票数据预测未来 predict_days 天的 close。
    返回: numpy 数组 (predict_days,)
    """
    # 先预处理数据
    data = preprocess_data(data)

    # 构造数据集以获取 target/features
    dataset = StockTimeSeriesDataset(data, input_window=input_window, output_window=predict_days, target_col='close')

    # 从原始数组中取最后一个输入窗口（不依赖于dataset的最后样本输出）
    target_arr = dataset.target  # 1d numpy
    features_arr = dataset.features  # 2d numpy
    if len(target_arr) < input_window:
        raise ValueError("样本长度小于 input_window，无法预测")

    last_input_target = target_arr[-input_window:]
    last_input_features = features_arr[-input_window:, :]

    # 标准化逻辑与 Dataset.__getitem__ 保持一致：为每个 feature 用单独的 scaler
    target_scaler = StandardScaler()
    last_input_target_arr = np.nan_to_num(last_input_target, nan=0.0, posinf=0.0, neginf=0.0)
    if np.std(last_input_target_arr) <= 1e-8:
        input_target_scaled = last_input_target_arr - np.mean(last_input_target_arr)
    else:
        input_target_scaled = target_scaler.fit_transform(last_input_target_arr.reshape(-1, 1)).flatten()

    # features
    last_features_arr = np.nan_to_num(last_input_features, nan=0.0, posinf=0.0, neginf=0.0)
    input_features_scaled = np.zeros_like(last_features_arr)
    feature_scalers = []
    for i in range(last_features_arr.shape[1]):
        col = last_features_arr[:, i]
        col = np.nan_to_num(col, nan=0.0, posinf=0.0, neginf=0.0)
        if np.std(col) <= 1e-8:
            input_features_scaled[:, i] = col - np.mean(col)
            feature_scalers.append(None)
        else:
            fs = StandardScaler()
            input_features_scaled[:, i] = fs.fit_transform(col.reshape(-1, 1)).flatten()
            feature_scalers.append(fs)

    # 合并输入并转换为张量 (seq_len, input_size)
    input_combined = np.column_stack([input_target_scaled, input_features_scaled])
    # 终端清理和裁剪
    input_combined = np.nan_to_num(input_combined, nan=0.0, posinf=0.0, neginf=0.0)
    input_combined = np.clip(input_combined, -10.0, 10.0)
    input_tensor = torch.FloatTensor(input_combined).unsqueeze(0)  # (1, seq_len, input_size)

    # 构建模型，用 predict_days 作为 output_window
    inferred_input_size = input_combined.shape[-1]
    inferred_output_window = predict_days
    model = MultiVariateLSTM_Transformer(
        input_size=inferred_input_size,
        lstm_hidden_size=64,
        lstm_layers=2,
        trans_layers=2,
        trans_heads=4,
        trans_ffn_hidden=128,
        dropout=0.1,
        output_size=1,
        output_window=inferred_output_window,
    )

    if os.path.exists(model_path):
        try:
            state = torch.load(model_path, map_location='cpu')
            model.load_state_dict(state, strict=False)
        except Exception as e:
            print(f"加载模型权重失败: {e}")

    model.eval()
    with torch.no_grad():
        outputs = model(input_tensor)  # (1, output_window, 1)
        outputs = outputs.squeeze(0).squeeze(-1).cpu().numpy()  # (output_window,)

    # 反标准化（使用 target_scaler）
    try:
        pred_original = target_scaler.inverse_transform(outputs.reshape(-1, 1)).flatten()
    except Exception:
        # 如果 target_scaler 没有拟合（常数情况），直接返回 outputs
        pred_original = outputs

    return pred_original

# 预处理数据：加载数据，检查缺失值，归一化
def preprocess_data(data):
    """
    加载股票数据并处理缺失值
    参数：
        data: 待处理的数据（DataFrame格式）
    返回：
        features: 特征数据 (时间, 37个特征列)
        target: 目标变量 (close)
        dates: 时间列
    """
    # print(f"原始数据形状: {data.shape}")
    # print(f"列名: {data.columns.tolist()}")
    
    # 缺失值处理统计
    missing_info = {}
    total_missing = 0
     
    print("\n=== 缺失值检查和处理 ===")
    
    # 检查每一列的缺失值情况
    for i, col_name in enumerate(data.columns): # i是列索引，col_name是列名
        col_data = data.iloc[:, i] # 获取第i列数据
        # 检查缺失值和无穷值
        missing_count = col_data.isnull().sum() # 计算缺失值数量
        if pd.api.types.is_numeric_dtype(col_data): # 仅对数值列检查无穷值
            missing_count += np.isinf(col_data).sum()
        
        if missing_count > 0:
            print(f"列 {i+1} ({col_name}): 发现 {missing_count} 个缺失值")
            missing_info[f"列{i+1}_{col_name}"] = missing_count
            total_missing += missing_count
            
            # 前向填充处理
            if i == 0:  # 时间列特殊处理
                data.iloc[:, i] = data.iloc[:, i].fillna(method='ffill')
                # 如果第一个值就是缺失的，用后向填充
                data.iloc[:, i] = data.iloc[:, i].fillna(method='bfill')
            else:  # 数值列处理
                # 先处理无穷大值
                data.iloc[:, i] = data.iloc[:, i].replace([np.inf, -np.inf], np.nan)
                # 前向填充
                data.iloc[:, i] = data.iloc[:, i].fillna(method='ffill')
                # 如果第一个值就是缺失的，用后向填充
                data.iloc[:, i] = data.iloc[:, i].fillna(method='bfill')
                # 如果还有缺失值，用0填充
                data.iloc[:, i] = data.iloc[:, i].fillna(0)
        else:
            print(f"列 {i+1} ({col_name}): 无缺失值")
    
    # 输出缺失值处理总结
    print(f"\n缺失值处理总结:")
    print(f"总共处理了 {total_missing} 个缺失值")
    if missing_info:
        print("各列缺失值详情:")
        for col_info, count in missing_info.items():
            print(f"  {col_info}: {count} 个")
    else:
        print("数据完整，无缺失值")
    
    # 最终检查
    final_missing = data.isnull().sum().sum()
    if final_missing > 0:
        print(f"警告: 处理后仍有 {final_missing} 个缺失值")
    else:
        print(f"✓ 所有缺失值已成功处理")
    return data
'''
# 循环处理读取到的数据
for data in dataframes:
    data = preprocess_data(data)
    print(f"处理后数据形状: {data.shape}")

if os.path.exists("Transformer+LSTM/Advanced/data/integrated_data_fixed.csv"):
    os.remove("Transformer+LSTM/Advanced/data/integrated_data_fixed.csv")
    data = pd.read_csv("Transformer+LSTM/Advanced/data/integrated_data_fixed.csv")
else:
    data.to_csv("Transformer+LSTM/Advanced/data/integrated_data_fixed.csv")
'''

# 
# print(type(integrate_data_close.values))
'''
数据示例：
data shape: (2549, 3)
'''

'''
本来目的是要通过输入，求出基于股票用户的未来收入，但是没用户的股票数据，于是就没有办法训练
所以现在问题有回来了，我们现在已经有了数据，那么应该通过LSTM+Transformer的融合模型来预测什么数据呢？
首先，答案当然是时序数据，但是应该预测什么样的时许数据呢？
这里给出的答案就是通过预测用户多只股票的未来10天close的预测值，并且求出未来10close的均值
然后用这个均值来权衡这个股票的预测收益率
然后再结合用户现在的持仓资金比例，来预测用户的未来收益率
'''

# 设置随机种子
np.random.seed(42)
torch.manual_seed(42)

# 多变量时间序列数据集类
class StockTimeSeriesDataset(Dataset):
    def __init__(self, data, input_window=50, output_window=10, target_col='close'):
        """
        股票时间序列数据集
        参数：
            data: 完整数据DataFrame (n_samples, n_features+1)
            input_window: 输入窗口长度
            output_window: 输出窗口长度
            target_col: 目标变量列名(默认为'close')
        """
        # 分离目标变量和特征变量
        if target_col in data.columns:
            self.target = data[target_col].values  # 转为1维numpy数组
            # 特征为除目标列外的所有数值列
            self.features = data.drop(columns=[target_col]).select_dtypes(include=[np.number]).values
        else:
            # 如果没有指定列名,假设第一列是目标变量
            print(f"警告: 未找到列'{target_col}',使用第一列作为目标变量")
            self.target = data.iloc[:, 0].values
            self.features = data.iloc[:, 1:].select_dtypes(include=[np.number]).values
        
        self.input_window = input_window
        self.output_window = output_window
        
        # 计算有效样本数量
        self.n_samples = len(self.target) - input_window - output_window + 1
        
        print(f"数据集样本数量: {self.n_samples}")
        print(f"目标变量形状: {self.target.shape}")
        print(f"特征变量形状: {self.features.shape}")
    
    def __len__(self):
        return self.n_samples
    
    def __getitem__(self, idx):
        # 输入序列:包含目标变量和特征变量
        input_target = self.target[idx:idx + self.input_window]
        input_features = self.features[idx:idx + self.input_window]  # 原始特征数据
        
        # 对输入的目标变量序列进行标准化
        target_scaler = StandardScaler()
        # 检查标准差是否为0（转为numpy数组以避免Series歧义）
        input_target_arr = np.asarray(input_target)
        # 清理 NaN/Inf
        input_target_arr = np.nan_to_num(input_target_arr, nan=0.0, posinf=0.0, neginf=0.0)
        # 使用阈值判断近似零方差
        if np.std(input_target_arr) <= 1e-8:
            print(f"警告：样本{idx}的目标变量标准差为0，使用去均值处理")
            input_target_scaled = input_target_arr - np.mean(input_target_arr)
        else:
            input_target_scaled = target_scaler.fit_transform(input_target_arr.reshape(-1, 1)).flatten()
        
        # 对22个特征变量按变量分别进行标准化（先转为numpy数组）
        input_features_arr = np.asarray(input_features)
        # 清理 NaN/Inf
        input_features_arr = np.nan_to_num(input_features_arr, nan=0.0, posinf=0.0, neginf=0.0)
        input_features_scaled = np.zeros_like(input_features_arr)
        for i in range(input_features_arr.shape[1]):
            feature_data = input_features_arr[:, i]
            # 清理 NaN/Inf
            feature_data = np.nan_to_num(feature_data, nan=0.0, posinf=0.0, neginf=0.0)
            if np.std(feature_data) <= 1e-8:
                # 如果标准差为0，直接减去均值
                input_features_scaled[:, i] = feature_data - np.mean(feature_data)
            else:
                feature_scaler = StandardScaler()
                input_features_scaled[:, i] = feature_scaler.fit_transform(
                    feature_data.reshape(-1, 1)
                ).flatten()
        
        # 输出序列（目标变量）
        output_target = self.target[idx + self.input_window:idx + self.input_window + self.output_window]
        
        # 使用相同的标准化器对输出目标进行标准化
        output_target_arr = np.asarray(output_target)
        # 清理 NaN/Inf
        output_target_arr = np.nan_to_num(output_target_arr, nan=0.0, posinf=0.0, neginf=0.0)
        if np.std(input_target_arr) <= 1e-8:
            output_target_scaled = output_target_arr - np.mean(input_target_arr)
        else:
            output_target_scaled = target_scaler.transform(output_target_arr.reshape(-1, 1)).flatten()
        
        # 终端清理，确保送入模型的数据无 NaN/Inf
        input_target_scaled = np.nan_to_num(input_target_scaled, nan=0.0, posinf=0.0, neginf=0.0)
        input_features_scaled = np.nan_to_num(input_features_scaled, nan=0.0, posinf=0.0, neginf=0.0)
        output_target_scaled = np.nan_to_num(output_target_scaled, nan=0.0, posinf=0.0, neginf=0.0)
        output_target_arr = np.nan_to_num(output_target_arr, nan=0.0, posinf=0.0, neginf=0.0)

        # 合并输入：目标变量 + 特征变量 (50, 23)
        input_combined = np.column_stack([input_target_scaled, input_features_scaled])
        
        return (
            torch.FloatTensor(input_combined),  # (50, 23)
            torch.FloatTensor(output_target_scaled),  # (10,)
            torch.FloatTensor(output_target_arr),  # 原始输出目标（用于计算MSE）
            target_scaler  # 用于反标准化
        )

'''
# 测试数据集类
# 分割原始数据
data_sample = dataframes[0]
train_data, test_data = train_test_split(data_sample, test_size=0.1, shuffle=False)

# 构建训练集
# 分别创建训练集和测试集数据集
# 设置窗口参数

input_window = 100
output_window = 20
train_dataset = StockTimeSeriesDataset(train_data, train_data, input_window, output_window)
test_dataset = StockTimeSeriesDataset(test_data, test_data, input_window, output_window)
print(f"训练集样本数: {len(train_dataset)}")
print(f"测试集样本数: {len(test_dataset)}")
'''

# 位置编码类
class PositionalEncoding(nn.Module):
    def __init__(self, d_model, dropout=0.1, max_len=5000):
        super(PositionalEncoding, self).__init__()
        self.dropout = nn.Dropout(p=dropout)
        
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(1)
        self.register_buffer('pe', pe)
    
    def forward(self, x):
        x = x + self.pe[:x.size(0)]
        return self.dropout(x)

# LSTM + Transformer 融合模型（多变量版本）
class MultiVariateLSTM_Transformer(nn.Module):
    def __init__(self, input_size=23, lstm_hidden_size=64, lstm_layers=2,
                 trans_layers=2, trans_heads=4, trans_ffn_hidden=128, 
                 dropout=0.1, output_size=1, output_window=10):
        """
        多变量 LSTM + Transformer 融合模型
        参数：
            input_size: 输入特征维度（23：1个目标变量 + 22个特征变量）
            lstm_hidden_size: LSTM 隐藏层单元数
            lstm_layers: LSTM 层数
            trans_layers: Transformer Encoder 层数
            trans_heads: Transformer 多头注意力头数
            trans_ffn_hidden: Transformer FFN 隐藏层大小
            dropout: dropout 概率
            output_size: 输出特征维度（1，只预测close）
            output_window: 输出序列长度
        """
        super(MultiVariateLSTM_Transformer, self).__init__()
        self.lstm_hidden_size = lstm_hidden_size
        self.lstm_layers = lstm_layers
        self.output_window = output_window
        
        # LSTM 层：提取局部时序特征
        self.lstm = nn.LSTM(input_size, lstm_hidden_size, lstm_layers, 
                           batch_first=True, dropout=dropout)
        
        # 位置编码
        self.pos_encoder = PositionalEncoding(d_model=lstm_hidden_size, dropout=dropout)
        
        # Transformer Encoder 层
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=lstm_hidden_size, 
            nhead=trans_heads,
            dim_feedforward=trans_ffn_hidden, 
            dropout=dropout
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=trans_layers)
        
        # 输出层
        self.fc = nn.Linear(lstm_hidden_size, output_size * output_window)
    
    def forward(self, x):
        """
        前向传播
        参数：
            x: 输入张量 (batch_size, seq_len, input_size)
        返回：
            output: 预测结果 (batch_size, output_window, 1)
        """
        batch_size = x.size(0)
        
        # LSTM 层
        lstm_out, _ = self.lstm(x)  # (batch_size, seq_len, lstm_hidden_size)
        
        # 调整维度以适应 Transformer (seq_len, batch_size, lstm_hidden_size)
        lstm_out = lstm_out.transpose(0, 1)
        
        # 位置编码
        lstm_out = self.pos_encoder(lstm_out)
        
        # Transformer Encoder
        transformer_out = self.transformer_encoder(lstm_out)  # (seq_len, batch_size, lstm_hidden_size)
        
        # 取最后一个时间步的输出
        last_output = transformer_out[-1]  # (batch_size, lstm_hidden_size)
        
        # 全连接层生成预测
        output = self.fc(last_output)  # (batch_size, output_size * output_window)
        
        # 重塑为 (batch_size, output_window, output_size)
        output = output.view(batch_size, self.output_window, -1)
        
        return output

# 自定义数据加载器（处理标准化器）
def custom_collate_fn(batch):
    inputs, targets_scaled, targets_original, scalers = zip(*batch)
    inputs = torch.stack(inputs)
    targets_scaled = torch.stack(targets_scaled)
    targets_original = torch.stack(targets_original)
    # 清理可能残留的 NaN/Inf 并进行范围裁剪，提升数值稳定
    inputs = torch.nan_to_num(inputs, nan=0.0, posinf=0.0, neginf=0.0)
    targets_scaled = torch.nan_to_num(targets_scaled, nan=0.0, posinf=0.0, neginf=0.0)
    targets_original = torch.nan_to_num(targets_original, nan=0.0, posinf=0.0, neginf=0.0)
    inputs = torch.clamp(inputs, -10.0, 10.0)
    targets_scaled = torch.clamp(targets_scaled, -10.0, 10.0)
    return inputs, targets_scaled, targets_original, scalers

# 计算评估指标函数
def calculate_metrics(predictions, targets):
    """
    计算评估指标
    """
    mse = np.mean((predictions - targets) ** 2)
    mae = np.mean(np.abs(predictions - targets))
    rmse = np.sqrt(mse)
    return mse, mae, rmse

# 训练模型并保存
# 默认模型路径为Transformer+LSTM\Advanced\lstm_transformer_model.pth
def train_and_save_model(train_loader, num_epochs=50, learning_rate=0.001, model_path="Transformer+LSTM/Advanced/lstm_transformer_model.pth"):
    # 从一个样本批次中推断 input_size 与 output_window
    sample_inputs, sample_targets_scaled, _, _ = next(iter(train_loader))
    inferred_input_size = sample_inputs.shape[-1]
    inferred_output_window = sample_targets_scaled.shape[-1]

    # 构建与数据维度一致的模型
    path = input("请输入模型保存路径: ") or model_path
    model = MultiVariateLSTM_Transformer(
        input_size=inferred_input_size,
        lstm_hidden_size=64,
        lstm_layers=2,
        trans_layers=2,
        trans_heads=4,
        trans_ffn_hidden=128,
        dropout=0.1,
        output_size=1,
        output_window=inferred_output_window,
    )

    # 加载历史权重（如存在），使用非严格模式以适配结构变化
    if os.path.exists(path):
        try:
            state = torch.load(path, map_location='cpu')
            missing, unexpected = model.load_state_dict(state, strict=False)
            print("已加载历史权重（非严格模式）")
            if missing:
                print(f"未匹配层（新模型存在，权重缺失，已用新初始化）: {missing}")
            if unexpected:
                print(f"多余层（checkpoint存在，模型不使用）: {unexpected}")
        except Exception as e:
            print(f"加载历史权重失败，使用新初始化模型。原因: {e}")

    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate, weight_decay=1e-5)

    # 初始化模型权重（仅对未加载到的层生效）
    def init_weights(m):
        if isinstance(m, nn.Linear):
            if m.weight is not None and m.weight.requires_grad:
                torch.nn.init.xavier_uniform_(m.weight)
            if m.bias is not None and m.bias.requires_grad:
                torch.nn.init.zeros_(m.bias)
        elif isinstance(m, nn.LSTM):
            for name, param in m.named_parameters():
                if not param.requires_grad:
                    continue
                if 'weight' in name:
                    torch.nn.init.xavier_uniform_(param)
                elif 'bias' in name:
                    torch.nn.init.zeros_(param)

    model.apply(init_weights)

    # 训练模型
    train_losses = []
    
    model.train()
    print("开始训练...")
    
    for epoch in range(num_epochs):
        epoch_loss = 0
        batch_count = 0
        
        for inputs, targets_scaled, targets_original, scalers in train_loader:
            optimizer.zero_grad()
            outputs = model(inputs)  # (batch_size, output_window, 1)
            outputs = outputs.squeeze(-1)  # (batch_size, output_window)
            
            # 使用标准化后的数据进行反向传播（保持梯度计算的稳定性）
            loss = criterion(outputs, targets_scaled)
            
            # 检查loss是否为有限值（保留基本的数值稳定性检查）
            if not torch.isfinite(loss):
                print(f"警告：第{epoch+1}轮第{batch_count}批次loss异常: {loss.item()}")
                optimizer.zero_grad()
                continue
            
            # 反向传播
            loss.backward()
            
            # 梯度裁剪
            grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=0.5)
            if not torch.isfinite(grad_norm):
                print(f"警告：第{epoch+1}轮第{batch_count}批次梯度异常")
                optimizer.zero_grad()
                continue
            
            optimizer.step()
            
            # 计算反标准化后的MSE损失（仅用于监控）
            batch_loss = 0
            valid_samples = 0
            for i in range(outputs.shape[0]):
                try:
                    # 反标准化预测值和真实值
                    pred_original = scalers[i].inverse_transform(outputs[i].detach().cpu().numpy().reshape(-1, 1)).flatten()
                    target_original = targets_original[i].cpu().numpy()
                    
                    # 检查反标准化结果
                    if np.isnan(pred_original).any() or np.isnan(target_original).any():
                        continue
                    
                    # 计算该样本的MSE
                    sample_mse = np.mean((pred_original - target_original) ** 2)
                    if not np.isnan(sample_mse):
                        batch_loss += sample_mse
                        valid_samples += 1
                except Exception as e:
                    print(f"反标准化错误: {e}")
                    continue
            
            # 平均批次损失
            if valid_samples > 0:
                batch_loss = batch_loss / valid_samples
                epoch_loss += batch_loss
            else:
                epoch_loss += loss.item()  # 使用标准化损失作为备选
            
            batch_count += 1
        
        avg_loss = epoch_loss / batch_count
        train_losses.append(avg_loss)
        
        if (epoch + 1) % 10 == 0:
            print(f'Epoch [{epoch+1}/{num_epochs}], Loss (反标准化后): {avg_loss:.6f}')
    
    print("训练完成！")
    # 保存模型
    torch.save(model.state_dict(), model_path)
    print(f"模型已保存到 {model_path}")

# 测试模型
def test_model(model_path, test_loader, input_window=100, output_window=20):
    # 从一个样本批次中推断 input_size 与 output_window
    sample_inputs, sample_targets_scaled, _, _ = next(iter(test_loader))
    inferred_input_size = sample_inputs.shape[-1]
    inferred_output_window = sample_targets_scaled.shape[-1]

    # 加载模型
    # 构建与数据维度一致的模型
    path = model_path
    model = MultiVariateLSTM_Transformer(
        input_size=inferred_input_size,
        lstm_hidden_size=64,
        lstm_layers=2,
        trans_layers=2,
        trans_heads=4,
        trans_ffn_hidden=128,
        dropout=0.1,
        output_size=1,
        output_window=inferred_output_window,
    )

    # 加载历史权重（如存在），使用非严格模式以适配结构变化
    if os.path.exists(path):
        try:
            state = torch.load(path, map_location='cpu')
            missing, unexpected = model.load_state_dict(state, strict=False)
            print("已加载历史权重（非严格模式）")
            if missing:
                print(f"未匹配层（新模型存在，权重缺失，已用新初始化）: {missing}")
            if unexpected:
                print(f"多余层（checkpoint存在，模型不使用）: {unexpected}")
        except Exception as e:
            print(f"加载历史权重失败，使用新初始化模型。原因: {e}")
    
    # 测试模型
    model.eval()
    predictions_scaled = []
    predictions_original = []
    ground_truth_original = []
    all_scalers = []
    
    with torch.no_grad():
        for inputs, targets_scaled, targets_original, scalers in test_loader:
            outputs = model(inputs)
            outputs = outputs.squeeze(-1)  # (1, output_window)
            
            # 保存标准化后的预测值
            predictions_scaled.append(outputs.cpu().numpy())
            
            # 反标准化预测值
            pred_original = scalers[0].inverse_transform(outputs.cpu().numpy().reshape(-1, 1)).flatten()
            predictions_original.append(pred_original)
            
            # 保存原始真实值
            ground_truth_original.append(targets_original.cpu().numpy().flatten())
            all_scalers.extend(scalers)
    
    # 转换为numpy数组
    pred_original = np.array(predictions_original)  # (n_test_samples, output_window)
    gt_original = np.array(ground_truth_original)   # (n_test_samples, output_window)
    
    # 计算最终预测值：对重复预测的交易日取平均值
    # 根据测试样本数量推断最终预测长度：每个样本起点+步长
    num_samples = len(predictions_original)
    final_predictions_length = num_samples + output_window - 1
    
    # 初始化最终预测值和计数数组
    final_predictions = np.zeros(final_predictions_length)
    prediction_counts = np.zeros(final_predictions_length)
    # 真实值使用展开并按天对齐后的均值方式来近似（与预测平均相同的聚合逻辑）
    # 先展开 ground truth 为 (num_samples, output_window)
    gt_mat = gt_original  # (num_samples, output_window)
    final_ground_truth = np.zeros(final_predictions_length)
    gt_counts = np.zeros(final_predictions_length)
    for sample_idx in range(num_samples):
        for step in range(output_window):
            day = sample_idx + step
            if day < final_predictions_length:
                final_ground_truth[day] += gt_mat[sample_idx, step]
                gt_counts[day] += 1
    mask_gt = gt_counts > 0
    final_ground_truth[mask_gt] = final_ground_truth[mask_gt] / gt_counts[mask_gt]
    
    # 遍历每个测试样本的预测结果
    for sample_idx, sample_pred in enumerate(pred_original):
        # 每个样本预测output_window个值，对应的位置是sample_idx到sample_idx+output_window-1
        for pred_step in range(output_window):
            target_day = sample_idx + pred_step
            if target_day < final_predictions_length:
                final_predictions[target_day] += sample_pred[pred_step]
                prediction_counts[target_day] += 1
    
    # 计算平均值（避免除零）
    mask = prediction_counts > 0
    final_predictions[mask] = final_predictions[mask] / prediction_counts[mask]
    
    print(f"\n最终预测结果统计:")
    print(f"最终预测值长度: {len(final_predictions)}")
    print(f"真实值长度: {len(final_ground_truth)}")
    print(f"每个交易日平均被预测次数: {prediction_counts[mask].mean():.2f}")
    print(f"预测次数范围: [{prediction_counts[mask].min():.0f}, {prediction_counts[mask].max():.0f}]")
    
    print(f"\n预测结果形状: {pred_original.shape}")
    print(f"真实值形状: {gt_original.shape}")
    
    # 使用最终预测值和真实值用于图3和评估指标计算
    pred_flat_final = final_predictions  # 715个最终预测值
    gt_flat_final = final_ground_truth   # 715个对应真实值
    
    # 保留原始展平数据用于图4热力图
    pred_flat = pred_original.flatten()
    gt_flat = gt_original.flatten()
    
    # 数据可视化
    fig, axs = plt.subplots(2, 2, figsize=(15, 10))
    plt.subplots_adjust(hspace=0.4, wspace=0.3)
    
    # 图1：占位（如需原始 target，请在调用时传入或在外层提供）
    axs[0, 0].set_title("raw close", fontsize=14)
    axs[0, 0].set_axis_off()
    
    # 图2：训练损失曲线
    axs[0, 1].set_title("traning loss", fontsize=14)
    axs[0, 1].set_axis_off()
    
    # 图3：最终预测值与真实值对比（全部715个交易日）
    axs[1, 0].plot(gt_flat_final, label='real', color='blue', lw=1.5)
    axs[1, 0].plot(pred_flat_final, label='final prediction', color='red', lw=1.5, linestyle='--')
    axs[1, 0].set_title(f"comparison between real and prediction(Total {len(pred_flat_final)} dates)", fontsize=14)
    axs[1, 0].set_xlabel("trade date", fontsize=12)
    axs[1, 0].set_ylabel("close", fontsize=12)
    axs[1, 0].legend()
    axs[1, 0].grid(True)
    
    # 图4：预测误差热图
    error = np.abs(gt_flat - pred_flat)
    error_matrix = error[:len(error)//output_window*output_window].reshape(-1, output_window)
    cax = axs[1, 1].imshow(error_matrix, aspect='auto', cmap='inferno')
    axs[1, 1].set_title("Prediction error heatmap", fontsize=14)
    axs[1, 1].set_xlabel("prediction step", fontsize=12)
    axs[1, 1].set_ylabel("sample block", fontsize=12)
    fig.colorbar(cax, ax=axs[1, 1])
    
    plt.suptitle("LSTM+Transformer Fusion Model", fontsize=16)
    plt.tight_layout()
    plt.show()

    # 保存图像
    fig.savefig("Transformer+LSTM/Advanced/testing_model_results.png")
    
    # 计算评估指标（使用最终预测值）
    mse_final, mae_final, rmse_final = calculate_metrics(pred_flat_final, gt_flat_final)
    
    print(f"\n模型评估指标（最终预测值，715个交易日）:")
    print(f"MSE: {mse_final:.4f}")
    print(f"MAE: {mae_final:.4f}")
    print(f"RMSE: {rmse_final:.4f}")
    
    print(f"\n最终预测统计:")
    print(f"预测交易日数: {len(pred_flat_final)}")
    print(f"真实值范围: [{gt_flat_final.min():.2f}, {gt_flat_final.max():.2f}]")
    print(f"预测值范围: [{pred_flat_final.min():.2f}, {pred_flat_final.max():.2f}]")
    
    # 输出部分最终预测结果进行验证
    print(f"\n前5个最终预测值: {pred_flat_final[:5]}")
    print(f"前5个真实值: {gt_flat_final[:5]}")
    print(f"前5个误差: {np.abs(pred_flat_final[:5] - gt_flat_final[:5])}")
    
    # 同时输出原始样本级别的评估指标作为参考
    mse_sample, mae_sample, rmse_sample = calculate_metrics(pred_flat, gt_flat)
    print(f"\n样本级别评估指标（参考）:")
    print(f"MSE: {mse_sample:.4f}, MAE: {mae_sample:.4f}, RMSE: {rmse_sample:.4f}")
    print(f"样本总数: {len(pred_flat)}")

# 主程序
if __name__ == "__main__":
    # 加载股票数据
    dataframes = load_stock_data()

     # 设置窗口参数
    input_window = 100
    output_window = 20

    # 使用数据测试模型
    model_path = "Transformer+LSTM/Advanced/Models"
    output_dir = "Transformer+LSTM/Advanced/prediction"
    os.makedirs(output_dir, exist_ok=True)

    summary_rows = []
    for df in dataframes:
        # 每个 df 在 predict 中会被 preprocess
        name = getattr(df, 'name', None) or 'unknown'
        print(f"正在为 {name} 生成未来 {output_window} 天的 close 预测...")
        try:
            preds = predict_next_n_days(df, model_path, input_window=input_window, predict_days=output_window)
        except Exception as e:
            print(f"为 {name} 预测失败: {e}")
            continue

        # 保存为 csv
        dates = pd.RangeIndex(start=0, stop=len(preds), step=1)
        out_df = pd.DataFrame({'pred_close': preds}, index=dates)
        safe_name = re.sub(r"[^0-9A-Za-z._-]", "_", name)
        out_path = os.path.join(output_dir, f"predictions_{safe_name}.csv")
        out_df.to_csv(out_path, index_label='step')
        print(f"已保存: {out_path}")

        # 记录 summary
        summary_rows.append({'file': name, 'pred_min': float(np.min(preds)), 'pred_max': float(np.max(preds)), 'pred_mean': float(np.mean(preds))})

    # 保存 summary
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(os.path.join(output_dir, 'predictions_summary.csv'), index=False)
    print(f"所有预测已保存到 {output_dir}")