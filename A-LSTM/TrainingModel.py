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
import argparse
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

DEFAULT_FOLDER_PATH = "/root/ETF/data/raw_data"

def fill_missing_values(df):
    """
    对DataFrame中的每一列进行缺失值填充
    优先使用前向填充，无法前向填充时使用后向填充
    
    参数:
        df: DataFrame
    
    返回:
        df: 填充后的DataFrame
    """
    print("开始缺失值填充...")
    
    # 检查每列的缺失值情况
    missing_info = df.isnull().sum()
    print(f"缺失值统计:\n{missing_info[missing_info > 0]}")
    
    # 对每一列进行缺失值填充
    for col in df.columns:
        if df[col].isnull().any():
            # 先进行前向填充
            df[col] = df[col].fillna(method='ffill')
            # 如果还有缺失值，进行后向填充
            df[col] = df[col].fillna(method='bfill')
    
    # 检查填充后的缺失值情况
    remaining_missing = df.isnull().sum().sum()
    print(f"填充后剩余缺失值数量: {remaining_missing}")
    
    return df

def load_stock_data_csv(folder_path):
    # 循环读取文件夹中所有文件的数据
    # folder = "Transformer+LSTM/Advanced/sketch"
    # folder = input("请输入数据文件夹路径: ")
    folder = folder_path
    if not folder:
        print("未提供数据文件夹路径")
        return None
    if not os.path.exists(folder):
        print(f"文件夹不存在，请检查路径: {folder}")
        return None
    if not os.path.isdir(folder):
        print(f"路径不是文件夹，请检查路径: {folder}")
        return None
    files = os.listdir(folder)

    # 读取数据，并将表格名字赋值为DataFrame的属性
    dataframes = []
    for file in files:
        if file.endswith(".csv"):
            df = pd.read_csv(os.path.join(folder, file))
            df = fill_missing_values(df)
            df.name = re.sub(r'\.csv$', '', file)  # 去掉.csv后缀
            dataframes.append(df)

    if not dataframes:
        print("未找到任何CSV文件")
        return None

    print(f"读取到 {len(dataframes)} 个数据文件")
    print(f"数据文件列表: {files}")
    # print(dataframes)
    return dataframes

def load_stock_data_xlsx():
    '''数据字段如下：
    ts_code	
    trade_date	
    open	
    high	
    low	
    close	
    pre_close	
    change	
    pct_chg	
    vol	
    amount	
    成交量变动率	
    MTM(5)	
    MTM(10)	
    MTM(20)	
    MA(5)	
    MA(10)	
    MA(20)	
    EMA(5)	
    EMA(10)	
    EMA(20)	
    MA(12)	
    MA(26)	
    EMA(12)	
    EMA(26)	
    DIF	
    DIF的9日MA	
    DEA
    MACD
    TR
    ATR
    涨幅Ut
    跌幅Dt
    平均涨幅AUt
    平均跌幅ADt
    相对强弱RS
    RSI
    对数收益率
    '''
    # 循环读取文件夹中所有文件的数据
    # folder = "Transformer+LSTM/Advanced/sketch"
    folder = input("请输入数据文件夹路径: ")
    if not os.path.exists(folder):
        print(f"文件夹不存在，请检查路径: {folder}")
        return None
    if not os.path.isdir(folder):
        print(f"路径不是文件夹，请检查路径: {folder}")
        return None
    
    files = os.listdir(folder)
    # 读取数据
    dataframes = []
    for file in files:
        if file.endswith(".xlsx") or file.endswith(".xls"):
            df = pd.read_excel(os.path.join(folder, file))
            dataframes.append(df)

    # 循环去掉每个表格中ts_code和trade_date字段
    # ts_code无法被drop，是因为它是索引列
    # 所以需要先更换索引列再drop

    for i in range(len(dataframes)):
        dataframes[i] = dataframes[i].set_index(['trade_date'])
        dataframes[i] = dataframes[i].drop(columns=['ts_code'])

    print(f"读取到 {len(dataframes)} 个数据文件")
    print(f"数据文件列表: {files}")
    # print(dataframes)
    return dataframes

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
    def __init__(self, data, input_window=100, output_window=10, target_col='close'):
        """
        股票时间序列数据集
        参数：
            data: 完整数据DataFrame (n_samples, n_features+1)
            input_window: 输入窗口长度（历史天数，默认100）
            output_window: 输出窗口长度（预测天数，默认10）
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
        # total days covered by one sample (input + target)
        self.total_window = self.input_window + self.output_window
        
        # 计算有效样本数量
        self.n_samples = len(self.target) - input_window - output_window + 1
        
        print(f"数据集样本数量: {self.n_samples}")
        print(f"目标变量形状: {self.target.shape}")
        print(f"特征变量形状: {self.features.shape}")
        print(f"每个样本包含天数: {self.total_window} (input={self.input_window}, output={self.output_window})")
    
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

        # 合并输入：目标变量 + 特征变量 (input_window, n_features)
        input_combined = np.column_stack([input_target_scaled, input_features_scaled])

        return (
            torch.FloatTensor(input_combined),  # (input_window, n_features)
            torch.FloatTensor(output_target_scaled),  # (output_window,)
            torch.FloatTensor(output_target_arr),  # 原始输出目标（用于计算MSE）
            target_scaler  # 用于反标准化
        )

'''
# 测试数据集类
# 分割原始数据
data_sample = dataframes[0]
train_data, test_data = train_test_split(data_sample, test_size=0.21, shuffle=False)

# 构建训练集
# 分别创建训练集和测试集数据集
# 设置窗口参数

input_window = 100
output_window = 10
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
    train_accuracies = []
    
    model.train()
    print("开始训练...")
    
    for epoch in range(num_epochs):
        epoch_loss = 0
        epoch_mape = 0
        batch_count = 0
        mape_samples = 0
        
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
            
            # 计算反标准化后的MSE损失与MAPE（仅用于监控）
            batch_loss = 0
            batch_mape = 0
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

                    # 计算该样本的MAPE
                    denom = np.maximum(np.abs(target_original), 1e-6)
                    sample_mape = np.mean(np.abs(pred_original - target_original) / denom)
                    if not np.isnan(sample_mape):
                        batch_mape += sample_mape
                except Exception as e:
                    print(f"反标准化错误: {e}")
                    continue
            
            # 平均批次损失
            if valid_samples > 0:
                batch_loss = batch_loss / valid_samples
                epoch_loss += batch_loss
                if batch_mape > 0:
                    epoch_mape += batch_mape / valid_samples
                    mape_samples += 1
            else:
                epoch_loss += loss.item()  # 使用标准化损失作为备选
            
            batch_count += 1
        
        avg_loss = epoch_loss / batch_count
        train_losses.append(avg_loss)

        # 训练准确率(1 - MAPE)，用于曲线展示
        if mape_samples > 0:
            avg_mape = epoch_mape / mape_samples
            accuracy_rate = max(0.0, 1.0 - avg_mape)
        else:
            accuracy_rate = 0.0
        train_accuracies.append(accuracy_rate)
        
        if (epoch + 1) % 10 == 0:
            print(f'Epoch [{epoch+1}/{num_epochs}], Loss (反标准化后): {avg_loss:.6f}')
    
    print("训练完成！")
    # 保存模型
    torch.save(model.state_dict(), model_path)
    print(f"模型已保存到 {model_path}")

    return train_losses, train_accuracies

def parse_args():
    parser = argparse.ArgumentParser(description="训练 LSTM + Transformer 股票预测模型")
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="CSV数据文件夹路径（为空则提示输入）",
    )
    parser.add_argument(
        "--input-window",
        type=int,
        default=100,
        help="输入窗口长度（历史天数）",
    )
    parser.add_argument(
        "--output-window",
        type=int,
        default=10,
        help="输出窗口长度（预测天数）",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=100,
        help="训练轮数",
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=0.005,
        help="学习率",
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default="ETF/model",
        help="模型保存目录",
    )
    parser.add_argument(
        "--plot-dir",
        type=str,
        default="ETF/plots",
        help="训练曲线图保存目录",
    )
    return parser.parse_args()


def resolve_data_dir(cli_path):
    if cli_path:
        return cli_path
    user_input = input(f"请输入CSV数据文件夹路径 (默认: {DEFAULT_FOLDER_PATH}): ").strip()
    return user_input if user_input else DEFAULT_FOLDER_PATH


# 主程序
if __name__ == "__main__":
    args = parse_args()
    data_dir = resolve_data_dir(args.data_dir)

    # 加载股票数据
    dataframes = load_stock_data_csv(data_dir)

    if not dataframes:
        print("数据加载失败，程序结束。")
        raise SystemExit(1)

    print("数据加载完成！")
    print(f"数据集数量: {len(dataframes)}")

     # 设置窗口参数
    input_window = args.input_window
    output_window = args.output_window

    # 循环使用每个数据文件进行模型训练
    for i in range(len(dataframes)):
        data = dataframes[i]
        # 预处理：清理缺失/无穷值
        data = preprocess_data(data)
        # 分割原始数据
        train_data, test_data = train_test_split(data, test_size=0.1, shuffle=False)

        train_dataset = StockTimeSeriesDataset(train_data, input_window, output_window)
        test_dataset = StockTimeSeriesDataset(test_data, input_window, output_window)
        print(f"训练集样本数: {len(train_dataset)}")
        print(f"测试集样本数: {len(test_dataset)}")

        # 创建数据加载器
        train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True, collate_fn=custom_collate_fn)
        test_loader = DataLoader(test_dataset, batch_size=1, shuffle=False, collate_fn=custom_collate_fn)

        # 以股票文件名作为模型保存路径的一部分
        os.makedirs(args.model_dir, exist_ok=True)
        path = os.path.join(args.model_dir, f"{data.name}.pth")

        # 训练并保存模型
        train_losses, train_accuracies = train_and_save_model(
            train_loader,
            num_epochs=args.epochs,
            learning_rate=args.lr,
            model_path=path,
        )

        # 保存训练曲线图
        os.makedirs(args.plot_dir, exist_ok=True)
        plot_path = os.path.join(args.plot_dir, f"{data.name}.png")

        epochs = np.arange(1, len(train_losses) + 1)
        fig, ax1 = plt.subplots(figsize=(10, 6))
        ax1.plot(epochs, train_losses, color="tab:blue", label="Loss (MSE)")
        ax1.set_xlabel("Epoch")
        ax1.set_ylabel("Loss (MSE)", color="tab:blue")
        ax1.tick_params(axis="y", labelcolor="tab:blue")

        ax2 = ax1.twinx()
        ax2.plot(epochs, train_accuracies, color="tab:orange", label="Accuracy Rate (1 - MAPE)")
        ax2.set_ylabel("Accuracy Rate", color="tab:orange")
        ax2.tick_params(axis="y", labelcolor="tab:orange")

        plt.title(f"Training Curves - {data.name}")
        fig.tight_layout()
        plt.savefig(plot_path)
        plt.close(fig)
        print(f"训练曲线已保存到 {plot_path}")