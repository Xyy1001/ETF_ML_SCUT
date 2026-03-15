"""
Flask 后端服务示例
用于与 predict.html 前端页面集成

使用方法：
1. 确保安装了必要的包：pip install flask flask-cors numpy pandas torch
2. 运行此脚本：python predict_api.py
3. 访问 http://localhost:5000/predict.html
"""

from flask import Flask, jsonify, request, send_from_directory, make_response
from flask_cors import CORS
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, date
from typing import Optional
import os
import io
import csv
import json
from functools import lru_cache

from user_routes import user_bp, get_supported_stocks, get_user_manager, get_current_username
from daily_update_service import start_daily_update_scheduler

# 初始化 Flask 应用
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*", "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]}})

# 响应缓存优化
@app.after_request
def set_cache_headers(response):
    # HTML 页面禁用缓存，确保前端改动能立即生效
    if request.path == '/' or request.path.endswith('.html'):
        response.cache_control.max_age = 0
        response.cache_control.no_cache = True
        response.cache_control.no_store = True
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    if request.path.startswith('/api/'):
        # 持股列表要求强一致展示，禁止缓存
        if request.path.startswith('/api/users/holdings'):
            response.cache_control.max_age = 0
            response.cache_control.no_cache = True
            response.cache_control.no_store = True
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response

        if request.method == 'GET' and '/predict' not in request.path:
            response.cache_control.max_age = 300  # 5 分钟缓存静态数据
        else:
            response.cache_control.max_age = 0
            response.cache_control.no_cache = True
    return response

# ==================== 配置参数 ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

MODEL_PATH = {
    'gru': os.path.join(BASE_DIR, 'predict_model', 'GRU'),
    'transformer': os.path.join(BASE_DIR, 'predict_model', 'Transformer')
}
RISK_MODEL_DIR = os.path.join(BASE_DIR, 'risk_model')
DATA_PATH = os.path.join(PROJECT_DIR, 'A-LSTM', 'data')
PORT = 5000


app.register_blueprint(user_bp)

# ==================== 数据加载函数 ====================

@lru_cache(maxsize=64)
def _load_stock_data_cached(stock_code: str, days: int) -> tuple:
    """内部缓存函数：返回 tuple 以支持 lru_cache"""
    try:
        file_path = os.path.join(DATA_PATH, f"{stock_code}.csv")
        if not os.path.exists(file_path):
            return None
        df = pd.read_csv(file_path)
        df = df.tail(days)
        if 'Date' not in df.columns:
            df['Date'] = pd.date_range(start=datetime.now() - timedelta(days=days), periods=len(df))
        return tuple(df.values.tolist()), tuple(df.columns), tuple(df['Date'].astype(str).tolist())
    except Exception:
        return None

def load_stock_data(stock_code: str, days: int = 500) -> pd.DataFrame:
    """
    加载股票数据（带缓存）
    
    Args:
        stock_code: 股票代码，如 "000001.SZ"
        days: 要加载的天数
    
    Returns:
        包含 'Date' 和 'Close' 列的 DataFrame
    """
    cached = _load_stock_data_cached(stock_code, min(days, 500))
    if cached:
        data, cols, dates = cached
        df = pd.DataFrame(data, columns=cols)
        return df.reset_index(drop=True)
    return generate_mock_data(stock_code, days)


def generate_mock_data(stock_code: str, days: int = 500) -> pd.DataFrame:
    """
    生成模拟股票数据（用于演示）
    
    Args:
        stock_code: 股票代码
        days: 生成的天数
    
    Returns:
        包含 'Date' 和 'Close' 列的 DataFrame
    """
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    
    # 生成基于随机游走的价格数据
    base_price = 100
    prices = [base_price]
    
    for _ in range(1, days):
        change = np.random.normal(0.1, 1.5)
        new_price = prices[-1] + change
        new_price = max(80, min(120, new_price))  # 限制价格范围
        prices.append(new_price)
    
    df = pd.DataFrame({
        'Date': dates,
        'Close': prices
    })
    
    return df


# ==================== 特征生成函数 ====================

def generate_technical_features(prices: np.ndarray, window_sizes: list = [5, 10, 20]) -> np.ndarray:
    """
    基于价格数据生成技术指标特征（MA, 动量等）
    
    Args:
        prices: 价格数列 (N,)
        window_sizes: 移动平均窗口列表
    
    Returns:
        特征矩阵 (N, num_features)，第一列是close价格
    """
    features = []
    n = len(prices)
    
    # 第1列：close价格本身
    features.append(prices)
    
    # 动量指标
    if len(prices) > 1:
        momentum = np.diff(prices, prepend=prices[0])
        features.append(momentum)
    
    # 各种窗口的移动平均
    for window in window_sizes:
        if n >= window:
            ma = pd.Series(prices).rolling(window=window, min_periods=1).mean().values
            features.append(ma)
    
    # 价格相对于移动平均的偏差
    for window in [5, 10]:
        if n >= window:
            ma = pd.Series(prices).rolling(window=window, min_periods=1).mean().values
            ratio = prices / (ma + 1e-10)
            features.append(ratio)
    
    # 波动率（标准差）
    if n >= 20:
        volatility = pd.Series(prices).rolling(window=20, min_periods=1).std().values
        features.append(volatility)
    
    # 日收益率
    if n > 1:
        returns = np.diff(prices) / (prices[:-1] + 1e-10)
        returns = np.concatenate([[0], returns])  # 先填充一个0
        features.append(returns)
    
    # 变化幅度
    for window in [5, 10]:
        if n >= window:
            change = pd.Series(prices).pct_change(window).fillna(0).values
            features.append(change)
    
    # 堆叠为矩阵 (N, num_features)
    feature_matrix = np.column_stack(features)
    
    # 处理NaN和Inf
    feature_matrix = np.nan_to_num(feature_matrix, nan=0.0, posinf=0.0, neginf=0.0)
    
    # 如果特征数不足34，通过复制或补全来达到
    if feature_matrix.shape[1] < 34:
        # 通过重复最后一列来补足
        needed = 34 - feature_matrix.shape[1]
        for _ in range(needed):
            feature_matrix = np.column_stack([feature_matrix, feature_matrix[:, -1]])
    elif feature_matrix.shape[1] > 34:
        # 如果超过34，只取前34列
        feature_matrix = feature_matrix[:, :34]
    
    return feature_matrix
    """
    数据标准化
    
    Args:
        data: 输入数据
        method: 标准化方法 ('minmax' 或 'zscore')
    
    Returns:
        标准化后的数据和参数（用于反标准化）
    """
    if method == 'minmax':
        data_min = np.min(data)
        data_max = np.max(data)
        normalized = (data - data_min) / (data_max - data_min + 1e-10)
        return normalized, {'min': data_min, 'max': data_max}
    
    elif method == 'zscore':
        mean = np.mean(data)
        std = np.std(data)
        normalized = (data - mean) / (std + 1e-10)
        return normalized, {'mean': mean, 'std': std}


def denormalize_data(data: np.ndarray, params: dict, method: str = 'minmax') -> np.ndarray:
    """
    数据反标准化
    """
    if method == 'minmax':
        return data * (params['max'] - params['min']) + params['min']
    
    elif method == 'zscore':
        return data * params['std'] + params['mean']


def create_sequences(data: np.ndarray, seq_length: int):
    """
    创建时间序列样本
    
    Args:
        data: 输入数据
        seq_length: 序列长度
    
    Returns:
        数据序列数组
    """
    sequences = []
    for i in range(len(data) - seq_length):
        sequences.append(data[i:i + seq_length])
    return np.array(sequences)


# ==================== 模型预测函数 ====================

def predict_with_gru(data: np.ndarray, predict_days: int, stock_code: str = None, hidden_size: int = 64):
    """
    使用 GRU 模型进行预测
    
    Args:
        data: 输入时间序列数据（close价格）
        predict_days: 预测天数
        stock_code: 股票代码，用于加载对应的预训练模型（如 "000001.SZ"）
        hidden_size: GRU 隐藏层大小
    
    Returns:
        预测结果数组
    """
    try:
        import torch
        import torch.nn as nn
        
        # 生成多变量特征
        feature_matrix = generate_technical_features(data)  # (N, 34)
        print(f"[GRU] 特征矩阵形状: {feature_matrix.shape}")
        
        # 标准化特征
        feature_min = feature_matrix.min(axis=0, keepdims=True)
        feature_max = feature_matrix.max(axis=0, keepdims=True)
        normalized_features = (feature_matrix - feature_min) / (feature_max - feature_min + 1e-10)
        
        # close价格标准化参数（用于反标准化预测结果）
        close_min = feature_min[0, 0]
        close_max = feature_max[0, 0]
        
        # 使用真实的LSTM_GRU混合模型架构
        class LSTM_GRU_Model(nn.Module):
            def __init__(
                self,
                input_size=34,
                lstm_hidden_size=64,
                lstm_layers=1,
                gru_hidden_size=64,
                gru_layers=1,
                dropout=0.1,
                output_size=1,
                output_window=10,
            ):
                super().__init__()
                self.output_window = output_window
                self.lstm = nn.LSTM(
                    input_size,
                    lstm_hidden_size,
                    lstm_layers,
                    batch_first=True,
                    dropout=dropout if lstm_layers > 1 else 0.0,
                )
                self.gru = nn.GRU(
                    lstm_hidden_size,
                    gru_hidden_size,
                    gru_layers,
                    batch_first=True,
                    dropout=dropout if gru_layers > 1 else 0.0,
                )
                self.fc = nn.Linear(gru_hidden_size, output_size * output_window)

            def forward(self, x):
                lstm_out, _ = self.lstm(x)
                gru_out, _ = self.gru(lstm_out)
                last_output = gru_out[:, -1, :]
                output = self.fc(last_output)
                return output.view(x.size(0), self.output_window, -1)
        
        # 创建模型
        model = LSTM_GRU_Model(
            input_size=34,
            lstm_hidden_size=64,
            lstm_layers=1,
            gru_hidden_size=64,
            gru_layers=1,
            dropout=0.1,
            output_size=1,
            output_window=10,
        )
        
        # 如果提供了股票代码，尝试加载对应的模型权重
        if stock_code:
            model_file = os.path.join(MODEL_PATH.get('gru', ''), f"{stock_code}.pth")
            if os.path.exists(model_file):
                try:
                    checkpoint = torch.load(model_file, map_location='cpu')
                    # 兼容不同的保存格式
                    if isinstance(checkpoint, dict) and 'state_dict' in checkpoint:
                        state = checkpoint['state_dict']
                    elif isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
                        state = checkpoint['model_state_dict']
                    else:
                        state = checkpoint
                    
                    # 加载权重
                    if isinstance(state, dict):
                        missing, unexpected = model.load_state_dict(state, strict=False)
                        print(f"[GRU] 已加载模型 {stock_code}，missing={len(missing)}, unexpected={len(unexpected)}")
                    else:
                        print(f"[GRU] 模型文件格式不识别，将使用随机初始化")
                except Exception as e:
                    print(f"[GRU] 加载模型权重失败: {e}，将使用随机初始化")
        
        model.eval()
        
        # 生成预测
        predictions = []
        input_window = 64
        current_features = normalized_features[-input_window:]  # (64, 34)
        
        for step in range(predict_days):
            with torch.no_grad():
                input_tensor = torch.FloatTensor(current_features).unsqueeze(0)  # (1, 64, 34)
                output = model(input_tensor)  # (1, 10, 1)
                next_pred_normalized = output[0, 0, 0].item()  # 取第一个输出
            
            # 反标准化预测值（只用close列的标准化参数）
            next_pred = next_pred_normalized * (close_max - close_min) + close_min
            predictions.append(next_pred)
            
            # 更新特征：将预测的close价格作为新的close，特征向量向前移动
            # 为简化，我们只更新第一列（close价格）
            new_close = next_pred
            # 生成新的特征向量（简化的方式：复制最后一行）
            new_feature_row = current_features[-1:].copy()
            new_feature_row[0, 0] = next_pred_normalized  # 更新close列的标准化值
            
            current_features = np.vstack([current_features[1:], new_feature_row])
        
        return predictions
    
    except Exception as e:
        print(f"GRU prediction error: {e}")
        import traceback
        traceback.print_exc()
        # 返回简单的趋势预测作为备选
        last_price = data[-1]
        trend = (data[-1] - data[-10]) / 10 if len(data) >= 10 else 0
        return [last_price + trend * (i + 1) for i in range(predict_days)]


def predict_with_transformer(data: np.ndarray, predict_days: int, stock_code: str = None, num_heads: int = 8):
    """
    使用 Transformer 模型进行预测
    
    Args:
        data: 输入时间序列数据（close价格）
        predict_days: 预测天数
        stock_code: 股票代码，用于加载对应的预训练模型（如 "000001.SZ"）
        num_heads: 注意力头数
    
    Returns:
        预测结果数组
    """
    try:
        import torch
        import torch.nn as nn
        import math
        
        # 生成多变量特征
        feature_matrix = generate_technical_features(data)  # (N, 34)
        print(f"[Transformer] 特征矩阵形状: {feature_matrix.shape}")
        
        # 标准化特征
        feature_min = feature_matrix.min(axis=0, keepdims=True)
        feature_max = feature_matrix.max(axis=0, keepdims=True)
        normalized_features = (feature_matrix - feature_min) / (feature_max - feature_min + 1e-10)
        
        # close价格标准化参数（用于反标准化预测结果）
        close_min = feature_min[0, 0]
        close_max = feature_max[0, 0]
        
        # 位置编码模块
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
        
        # LSTM + Transformer 融合模型
        class MultiVariateLSTM_Transformer(nn.Module):
            def __init__(self, input_size=34, lstm_hidden_size=64, lstm_layers=2,
                         trans_layers=2, trans_heads=4, trans_ffn_hidden=128, 
                         dropout=0.1, output_size=1, output_window=10):
                super(MultiVariateLSTM_Transformer, self).__init__()
                self.lstm_hidden_size = lstm_hidden_size
                self.lstm_layers = lstm_layers
                self.output_window = output_window
                
                # LSTM 层：提取局部时序特征
                self.lstm = nn.LSTM(input_size, lstm_hidden_size, lstm_layers, 
                                   batch_first=True, dropout=dropout if lstm_layers > 1 else 0.0)
                
                # 位置编码
                self.pos_encoder = PositionalEncoding(d_model=lstm_hidden_size, dropout=dropout)
                
                # Transformer Encoder 层
                encoder_layer = nn.TransformerEncoderLayer(
                    d_model=lstm_hidden_size, 
                    nhead=trans_heads,
                    dim_feedforward=trans_ffn_hidden, 
                    dropout=dropout,
                    batch_first=False  # Transformer expects (seq_len, batch, features)
                )
                self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=trans_layers)
                
                # 输出层
                self.fc = nn.Linear(lstm_hidden_size, output_size * output_window)
            
            def forward(self, x):
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
        
        # 创建模型
        model = MultiVariateLSTM_Transformer(
            input_size=34,
            lstm_hidden_size=64,
            lstm_layers=2,
            trans_layers=2,
            trans_heads=4,
            trans_ffn_hidden=128,
            dropout=0.1,
            output_size=1,
            output_window=10,
        )
        
        # 如果提供了股票代码，尝试加载对应的模型权重
        if stock_code:
            model_file = os.path.join(MODEL_PATH.get('transformer', ''), f"{stock_code}.pth")
            if os.path.exists(model_file):
                try:
                    checkpoint = torch.load(model_file, map_location='cpu')
                    # 兼容不同的保存格式
                    if isinstance(checkpoint, dict) and 'state_dict' in checkpoint:
                        state = checkpoint['state_dict']
                    elif isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
                        state = checkpoint['model_state_dict']
                    else:
                        state = checkpoint
                    
                    # 加载权重
                    if isinstance(state, dict):
                        missing, unexpected = model.load_state_dict(state, strict=False)
                        print(f"[Transformer] 已加载模型 {stock_code}，missing={len(missing)}, unexpected={len(unexpected)}")
                    else:
                        print(f"[Transformer] 模型文件格式不识别，将使用随机初始化")
                except Exception as e:
                    print(f"[Transformer] 加载模型权重失败: {e}，将使用随机初始化")
        
        model.eval()
        
        # 生成预测
        predictions = []
        input_window = 64
        current_features = normalized_features[-input_window:]  # (64, 34)
        
        for step in range(predict_days):
            with torch.no_grad():
                input_tensor = torch.FloatTensor(current_features).unsqueeze(0)  # (1, 64, 34)
                output = model(input_tensor)  # (1, 10, 1)
                next_pred_normalized = output[0, 0, 0].item()  # 取第一个输出
            
            # 反标准化预测值（只用close列的标准化参数）
            next_pred = next_pred_normalized * (close_max - close_min) + close_min
            predictions.append(next_pred)
            
            # 更新特征：将预测的close价格作为新的close，特征向量向前移动
            new_feature_row = current_features[-1:].copy()
            new_feature_row[0, 0] = next_pred_normalized  # 更新close列的标准化值
            
            current_features = np.vstack([current_features[1:], new_feature_row])
        
        return predictions
    
    except Exception as e:
        print(f"Transformer prediction error: {e}")
        import traceback
        traceback.print_exc()
        # 返回简单的趋势预测作为备选
        last_price = data[-1]
        trend = (data[-1] - data[-10]) / 10 if len(data) >= 10 else 0
        return [last_price + trend * (i + 1) for i in range(predict_days)]



# ==================== 评估指标函数 ====================

def calculate_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict:
    """
    计算预测性能指标
    
    Args:
        actual: 真实值
        predicted: 预测值
    
    Returns:
        包含各种指标的字典
    """
    # 确保长度相同
    min_len = min(len(actual), len(predicted))
    actual = actual[:min_len]
    predicted = predicted[:min_len]
    
    # 计算指标
    mae = np.mean(np.abs(actual - predicted))
    mse = np.mean((actual - predicted) ** 2)
    rmse = np.sqrt(mse)
    
    # MAPE (百分比绝对错误)
    mape = np.mean(np.abs((actual - predicted) / (actual + 1e-10))) * 100
    
    # R² 评分
    ss_res = np.sum((actual - predicted) ** 2)
    ss_tot = np.sum((actual - np.mean(actual)) ** 2)
    r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
    
    return {
        'mae': float(mae),
        'rmse': float(rmse),
        'mape': float(mape),
        'r2': float(r2)
    }


def normalize_vector(values: np.ndarray, mode: str = 'zscore') -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return values
    if mode == 'minmax':
        min_v = np.min(values)
        max_v = np.max(values)
        return (values - min_v) / (max_v - min_v + 1e-10)
    mean_v = np.mean(values)
    std_v = np.std(values) + 1e-10
    z = (values - mean_v) / std_v
    z_min = np.min(z)
    z_max = np.max(z)
    return (z - z_min) / (z_max - z_min + 1e-10)


def get_available_stocks() -> list:
    """
    获取可用股票列表
    优先从数据库获取（适用于云服务器部署），否则从本地文件系统读取
    """
    # 1. 优先从数据库获取（云服务器部署场景）
    try:
        db_stocks = get_supported_stocks()
        if db_stocks and len(db_stocks) > 0:
            print(f"从数据库获取到 {len(db_stocks)} 只股票")
            return db_stocks
    except Exception as e:
        print(f"从数据库获取股票列表失败: {e}")
    
    # 2. 兜底：从本地文件系统读取（本地开发场景）
    if not os.path.exists(DATA_PATH):
        print(f"警告: 数据路径不存在 {DATA_PATH}，且数据库中也没有股票数据")
        return []
    stocks = [filename.replace('.csv', '') for filename in os.listdir(DATA_PATH) if filename.endswith('.csv')]
    print(f"从本地文件系统获取到 {len(stocks)} 只股票")
    return sorted(stocks)


def get_stocks_by_prediction_models(selected_models: list = None, mode: str = 'any') -> tuple:
    """
    根据预测模型文件返回可用股票。

    Args:
        selected_models: 指定模型列表（gru / transformer），为空时默认全部
        mode: any=并集, all=交集

    Returns:
        (stocks, stocks_by_model)
    """
    model_names = [name for name in MODEL_PATH.keys()]
    if selected_models:
        selected = [m for m in selected_models if m in MODEL_PATH]
        if selected:
            model_names = selected

    stocks_by_model = {}
    available_sets = []

    for model_name in model_names:
        model_dir = MODEL_PATH.get(model_name)
        model_stocks = []

        if model_dir and os.path.exists(model_dir):
            model_stocks = sorted([
                filename[:-4]
                for filename in os.listdir(model_dir)
                if filename.endswith('.pth')
            ])

        stocks_by_model[model_name] = model_stocks
        available_sets.append(set(model_stocks))

    if not available_sets:
        return [], stocks_by_model

    if mode == 'all':
        result = sorted(set.intersection(*available_sets)) if available_sets else []
    else:
        merged = set()
        for current in available_sets:
            merged.update(current)
        result = sorted(merged)

    return result, stocks_by_model


def parse_holdings(holdings_text: str, fallback: list) -> list:
    if not holdings_text:
        return fallback[:5]
    stocks = [item.strip() for item in holdings_text.split(',') if item.strip()]
    if not stocks:
        return fallback[:5]
    return stocks


def load_prices_from_database(stock: str, lookback: int, end_date: Optional[date] = None) -> Optional[np.ndarray]:
    """
    从数据库加载股票价格数据
    
    Args:
        stock: 股票代码，如 "000001.SZ"
        lookback: 需要的数据条数
    
    Returns:
        价格数组，如果加载失败则返回 None
    """
    try:
        manager = get_user_manager(required=False)
        if manager is None or manager.cursor is None:
            return None
        
        # 尝试直接使用股票代码作为表名（用反引号括起来）
        table_name = f"`{stock}`"
        if end_date:
            query = f"""
                SELECT close FROM {table_name}
                WHERE close IS NOT NULL AND trade_date <= %s
                ORDER BY trade_date DESC
                LIMIT %s
            """
            manager.cursor.execute(query, (end_date.strftime('%Y-%m-%d'), lookback * 2))
        else:
            query = f"""
                SELECT close FROM {table_name}
                WHERE close IS NOT NULL
                ORDER BY trade_date DESC
                LIMIT %s
            """
            manager.cursor.execute(query, (lookback * 2,))  # 多取一些以防数据不足
        rows = manager.cursor.fetchall()
        
        if not rows:
            return None
        
        # 反转数据（从旧到新）并转换为数组
        prices = np.array([float(row[0]) for row in reversed(rows)])
        
        # 返回最近的 lookback 条数据
        return prices[-lookback:] if len(prices) >= lookback else prices
    
    except Exception as e:
        print(f"从数据库加载股票 {stock} 价格数据失败: {e}")
        return None


def parse_prediction_start_date(raw_value: str) -> date:
    raw = str(raw_value or '').strip()
    if not raw:
        return datetime.now().date()
    try:
        return datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError as exc:
        raise ValueError('predict_start_date 格式必须为 YYYY-MM-DD') from exc


def resolve_prediction_start_date(params: dict) -> tuple[date, bool, bool]:
    """Resolve start date and enforce auth for custom date selection."""
    today = datetime.now().date()
    has_custom_date = 'predict_start_date' in (params or {}) and str(params.get('predict_start_date', '')).strip() != ''
    start_date = parse_prediction_start_date(params.get('predict_start_date', ''))

    if has_custom_date:
        username = get_current_username()
        if not username:
            raise PermissionError('仅登录用户可选择开始预测日期，请先登录')

        manager = get_user_manager(required=False)
        if manager is None:
            raise PermissionError('用户校验失败，请稍后重试')

        ok, _, _ = manager.get_user_info(username)
        if not ok:
            raise PermissionError('仅注册用户可选择开始预测日期')

    return start_date, (start_date < today), has_custom_date


def load_stock_prices_with_dates(stock: str, end_date: Optional[date] = None) -> Optional[pd.DataFrame]:
    """Load stock close series with trade dates from DB first, local file as fallback."""
    try:
        manager = get_user_manager(required=False)
        if manager is not None and manager.cursor is not None:
            table_name = f"`{stock}`"
            if end_date:
                query = f"""
                    SELECT trade_date, close FROM {table_name}
                    WHERE trade_date <= %s
                    ORDER BY trade_date ASC
                """
                manager.cursor.execute(query, (end_date.strftime('%Y-%m-%d'),))
            else:
                query = f"""
                    SELECT trade_date, close FROM {table_name}
                    ORDER BY trade_date ASC
                """
                manager.cursor.execute(query)

            rows = manager.cursor.fetchall()
            if rows:
                df = pd.DataFrame(rows, columns=['Date', 'Close'])
                df['Date'] = pd.to_datetime(df['Date'])
                df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
                # 保留所有行（包含NaN），然后进行forward fill再backward fill
                df = df.sort_values('Date').reset_index(drop=True)
                df['Close'] = df['Close'].ffill().bfill()
                df = df.dropna(subset=['Close']).reset_index(drop=True)
                return df if not df.empty else None
    except Exception as e:
        print(f"从数据库按日期加载股票 {stock} 失败: {e}")

    try:
        file_path = os.path.join(DATA_PATH, f'{stock}.csv')
        if not os.path.exists(file_path):
            return None

        df = pd.read_csv(file_path)
        close_col = None
        for candidate in ['Close', 'close', '收盘价', 'Adj Close', 'adj_close']:
            if candidate in df.columns:
                close_col = candidate
                break
        if close_col is None:
            return None

        date_col = None
        for candidate in ['Date', 'date', 'trade_date', '日期']:
            if candidate in df.columns:
                date_col = candidate
                break

        if date_col is None:
            # Fallback: synthetic calendar dates if source has no date column.
            dates = pd.date_range(end=datetime.now(), periods=len(df), freq='D')
            out = pd.DataFrame({'Date': dates, 'Close': pd.to_numeric(df[close_col], errors='coerce')})
        else:
            out = pd.DataFrame({
                'Date': pd.to_datetime(df[date_col], errors='coerce'),
                'Close': pd.to_numeric(df[close_col], errors='coerce')
            })

        out = out.dropna(subset=['Date']).sort_values('Date').reset_index(drop=True)
        # 进行forward fill再backward fill来填充缺失的价格数据
        out['Close'] = out['Close'].ffill().bfill()
        if end_date:
            out = out[out['Date'].dt.date <= end_date].reset_index(drop=True)
        out = out.dropna(subset=['Close']).reset_index(drop=True)
        return out if not out.empty else None
    except Exception as e:
        print(f"从本地按日期加载股票 {stock} 失败: {e}")
        return None


def load_prices_for_stock(stock: str, lookback: int, end_date: Optional[date] = None) -> np.ndarray:
    """
    加载股票价格数据
    优先从数据库加载（云服务器部署场景），否则从本地文件加载
    """
    # 1. 优先从数据库加载
    db_prices = load_prices_from_database(stock, lookback, end_date=end_date)
    if db_prices is not None and len(db_prices) >= 20:
        print(f"从数据库加载股票 {stock} 价格数据，共 {len(db_prices)} 条")
        return db_prices
    
    # 2. 兜底：从本地文件加载
    file_path = os.path.join(DATA_PATH, f'{stock}.csv')
    if not os.path.exists(file_path):
        print(f"警告: 股票 {stock} 数据不存在，使用模拟数据")
        mock = generate_mock_data(stock, lookback)
        return mock['Close'].values
    
    df = pd.read_csv(file_path)
    price_column = None
    for candidate in ['Close', 'close', '收盘价', 'Adj Close', 'adj_close']:
        if candidate in df.columns:
            price_column = candidate
            break
    if price_column is None:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if not numeric_cols:
            mock = generate_mock_data(stock, lookback)
            return mock['Close'].values
        price_column = numeric_cols[-1]
    if end_date is not None:
        date_col = None
        for candidate in ['Date', 'date', 'trade_date', '日期']:
            if candidate in df.columns:
                date_col = candidate
                break
        if date_col is not None:
            parsed_date = pd.to_datetime(df[date_col], errors='coerce')
            df = df[parsed_date.dt.date <= end_date]

    series = df[price_column].dropna().astype(float).tail(lookback).values
    if len(series) < 20:
        mock = generate_mock_data(stock, lookback)
        return mock['Close'].values
    print(f"从本地文件加载股票 {stock} 价格数据，共 {len(series)} 条")
    return series


def build_returns_matrix(holdings: list, lookback: int, end_date: Optional[date] = None) -> np.ndarray:
    price_list = []
    min_len = None
    for stock in holdings:
        prices = load_prices_for_stock(stock, lookback, end_date=end_date)
        min_len = len(prices) if min_len is None else min(min_len, len(prices))
        price_list.append(prices)

    trimmed = [series[-min_len:] for series in price_list]
    prices_mat = np.vstack(trimmed).T
    returns = np.diff(prices_mat, axis=0) / (prices_mat[:-1] + 1e-10)
    returns = np.nan_to_num(returns, nan=0.0, posinf=0.0, neginf=0.0)
    return returns


def load_matrix_or_default(file_path: str, fallback: np.ndarray) -> np.ndarray:
    if not os.path.exists(file_path):
        return fallback
    loaded = np.load(file_path, allow_pickle=True)
    if loaded.ndim == 3:
        loaded = loaded[-1]
    loaded = np.asarray(loaded, dtype=float)
    if loaded.shape[0] != loaded.shape[1]:
        return fallback
    return loaded


def solve_markowitz_weights(mu_vec: np.ndarray, sigma: np.ndarray, gamma: float = 1.0) -> np.ndarray:
    mu_vec = np.asarray(mu_vec, dtype=float)
    sigma = np.asarray(sigma, dtype=float)
    n = mu_vec.shape[0]
    if n == 0:
        return np.array([])
    if n == 1:
        return np.array([1.0])

    if sigma.ndim == 0:
        sigma = np.eye(n) * float(sigma)
    if sigma.ndim == 1:
        sigma = np.diag(sigma)

    sigma = np.nan_to_num(sigma, nan=0.0, posinf=0.0, neginf=0.0)
    sigma = 0.5 * (sigma + sigma.T)
    sigma[np.diag_indices(n)] += 1e-8

    A = np.block([
        [gamma * sigma, np.ones((n, 1))],
        [np.ones((1, n)), np.zeros((1, 1))],
    ])
    b = np.concatenate([mu_vec, np.array([1.0])])
    try:
        x = np.linalg.solve(A, b)
        w = x[:n]
    except np.linalg.LinAlgError:
        w = np.ones(n) / n

    w = np.maximum(w, 0)
    s = float(w.sum())
    if s <= 0:
        w = np.ones(n) / n
    else:
        w = w / s
    return w


def build_risk_modeling_result(params: dict) -> dict:
    start_date, _, _ = resolve_prediction_start_date(params)
    methods = [str(item).strip().lower() for item in params.get('methods', ['gcn'])]
    methods = [item for item in methods if item in {'gcn', 'coefficient', 'convex'}]
    if not methods:
        raise ValueError('请至少选择一种风险建模方法')

    lookback = int(params.get('lookback', 500))
    lookback = max(60, min(1200, lookback))
    risk_horizon = int(params.get('risk_horizon', 20))
    risk_horizon = max(1, min(90, risk_horizon))
    edge_threshold = float(params.get('edge_threshold', 0.18))
    edge_threshold = max(0.0, min(1.0, edge_threshold))
    topk = int(params.get('topk', 6))
    topk = max(1, min(20, topk))
    convex_lambda = float(params.get('convex_lambda', 0.6))
    convex_lambda = max(0.0, min(1.0, convex_lambda))
    normalize_mode = str(params.get('normalize_mode', 'zscore')).lower()
    if normalize_mode not in {'zscore', 'minmax'}:
        normalize_mode = 'zscore'

    all_stocks = get_available_stocks()
    holdings = parse_holdings(params.get('holdings', ''), all_stocks)
    holdings = [stock for stock in holdings if stock in all_stocks]
    if len(holdings) < 2:
        holdings = all_stocks[:5]
    if len(holdings) < 2:
        raise ValueError('有效股票数量不足，无法建模')

    returns = build_returns_matrix(holdings, lookback, end_date=start_date)
    n = len(holdings)
    vol = np.std(returns, axis=0) * np.sqrt(252)
    corr = np.corrcoef(returns, rowvar=False)
    corr = np.nan_to_num(corr, nan=0.0, posinf=0.0, neginf=0.0)
    np.fill_diagonal(corr, 0.0)

    stock_to_index = {stock: index for index, stock in enumerate(all_stocks)}
    holding_indices = [stock_to_index[stock] for stock in holdings]

    gcn_default = np.abs(corr)
    gcn_matrix_all = load_matrix_or_default(
        os.path.join(RISK_MODEL_DIR, 'gcn', 'Adjacency_Matrix.npy'),
        gcn_default
    )
    if gcn_matrix_all.shape[0] >= max(holding_indices) + 1:
        gcn_matrix = np.abs(gcn_matrix_all[np.ix_(holding_indices, holding_indices)])
    else:
        gcn_matrix = gcn_default

    coef_default = np.abs(np.cov(returns, rowvar=False))
    coef_matrix_all = load_matrix_or_default(
        os.path.join(RISK_MODEL_DIR, 'coefficient', 'covariance_matrices.npy'),
        coef_default
    )
    if coef_matrix_all.shape[0] >= max(holding_indices) + 1:
        coef_matrix = np.abs(coef_matrix_all[np.ix_(holding_indices, holding_indices)])
    else:
        coef_matrix = coef_default

    np.fill_diagonal(gcn_matrix, 0.0)
    np.fill_diagonal(coef_matrix, 0.0)

    vol_norm = normalize_vector(vol, normalize_mode)
    method_scores = {}
    method_graph_mats = {}

    if 'gcn' in methods:
        gcn_strength = normalize_vector(np.mean(gcn_matrix, axis=1), normalize_mode)
        method_scores['gcn'] = 0.55 * vol_norm + 0.45 * gcn_strength
        method_graph_mats['gcn'] = gcn_matrix

    if 'coefficient' in methods:
        coef_strength = normalize_vector(np.mean(coef_matrix, axis=1), normalize_mode)
        method_scores['coefficient'] = 0.50 * vol_norm + 0.50 * coef_strength
        coef_norm_mat = coef_matrix / (np.max(coef_matrix) + 1e-10)
        method_graph_mats['coefficient'] = coef_norm_mat

    if 'convex' in methods:
        corr_strength = normalize_vector(np.mean(np.abs(corr), axis=1), normalize_mode)
        method_scores['convex'] = convex_lambda * vol_norm + (1.0 - convex_lambda) * corr_strength
        method_graph_mats['convex'] = np.abs(corr)

    stacked_scores = np.vstack([method_scores[method] for method in methods])
    ensemble_scores = np.mean(stacked_scores, axis=0)
    graph_base_method = methods[0]
    graph_matrix = method_graph_mats[graph_base_method]

    links = []
    used_pairs = set()
    for i in range(n):
        ranking = np.argsort(-graph_matrix[i])
        keep = 0
        for j in ranking:
            if i == j:
                continue
            weight = float(graph_matrix[i, j])
            if weight < edge_threshold:
                continue
            pair = tuple(sorted((i, int(j))))
            if pair in used_pairs:
                continue
            used_pairs.add(pair)
            links.append({
                'source': holdings[pair[0]],
                'target': holdings[pair[1]],
                'value': weight
            })
            keep += 1
            if keep >= topk:
                break

    nodes = []
    for idx, stock in enumerate(holdings):
        score = float(ensemble_scores[idx])
        if score >= 0.66:
            color = '#ef4444'
        elif score >= 0.33:
            color = '#f59e0b'
        else:
            color = '#667eea'
        nodes.append({
            'id': stock,
            'name': stock,
            'risk': score,
            'color': color
        })

    max_index = int(np.argmax(ensemble_scores))
    method_series = [
        {
            'method': method,
            'scores': [float(value) for value in method_scores[method]]
        }
        for method in methods
    ]

    return {
        'graph': {
            'nodes': nodes,
            'links': links,
            'base_method': graph_base_method
        },
        'bar': {
            'stocks': holdings,
            'method_series': method_series
        },
        'metrics': {
            'mean_risk': float(np.mean(ensemble_scores)),
            'max_risk_stock': holdings[max_index],
            'max_risk_score': float(ensemble_scores[max_index]),
            'edge_count': len(links),
            'risk_horizon': risk_horizon
        },
        'params': {
            'methods': methods,
            'lookback': lookback,
            'risk_horizon': risk_horizon,
            'predict_start_date': start_date.strftime('%Y-%m-%d'),
            'edge_threshold': edge_threshold,
            'topk': topk,
            'convex_lambda': convex_lambda,
            'normalize_mode': normalize_mode,
            'holdings': holdings
        },
        'timestamp': datetime.now().isoformat()
    }


def build_backtest_result(params: dict) -> dict:
    start_date, _, _ = resolve_prediction_start_date(params)
    all_stocks = get_available_stocks()
    holdings = parse_holdings(params.get('holdings', ''), all_stocks)
    holdings = [stock for stock in holdings if stock in all_stocks]
    if len(holdings) < 2:
        holdings = all_stocks[:5]
    if len(holdings) < 2:
        raise ValueError('有效股票数量不足，无法回测')

    lookback = int(params.get('lookback', 520))
    lookback = max(120, min(2000, lookback))
    rolling_window = int(params.get('rolling_window', 60))
    rolling_window = max(20, min(240, rolling_window))
    rebalance = int(params.get('rebalance_freq', 5))
    rebalance = max(1, min(60, rebalance))
    gamma = float(params.get('gamma', 1.0))
    gamma = max(0.1, min(10.0, gamma))
    risk_model = str(params.get('risk_model', 'coefficient')).lower()
    if risk_model not in {'coefficient', 'gcn', 'convex'}:
        risk_model = 'coefficient'
    initial_capital = float(params.get('initial_capital', 1.0))
    initial_capital = max(0.0001, initial_capital)

    series_list = []
    min_len = None
    for stock in holdings:
        prices = load_prices_for_stock(stock, lookback + 20, end_date=start_date)
        min_len = len(prices) if min_len is None else min(min_len, len(prices))
        series_list.append(prices)

    if min_len is None or min_len <= rolling_window + 5:
        raise ValueError('可用于回测的价格数据长度不足')

    trimmed = [series[-min_len:] for series in series_list]
    prices_mat = np.vstack(trimmed).T
    prices_mat = np.nan_to_num(prices_mat, nan=0.0, posinf=0.0, neginf=0.0)
    prices_mat[prices_mat <= 0] = np.nan
    prices_mat = pd.DataFrame(prices_mat).ffill().bfill().values

    log_returns = np.log((prices_mat[1:] + 1e-10) / (prices_mat[:-1] + 1e-10))
    log_returns = np.nan_to_num(log_returns, nan=0.0, posinf=0.0, neginf=0.0)
    steps = log_returns.shape[0]
    if steps <= rolling_window + 1:
        raise ValueError('回测步数不足，请增大回看窗口')

    dates = pd.date_range(end=start_date, periods=min_len, freq='D')
    date_labels = [d.strftime('%Y-%m-%d') for d in dates]

    rebalance_counter = 0
    current_w = np.ones(len(holdings)) / len(holdings)
    previous_w = current_w.copy()
    turnovers = []
    weight_rows = []

    strategy_log = []
    benchmark_log = []
    strategy_dates = []
    rolling_forecast_points = []

    for t in range(rolling_window, steps):
        hist = log_returns[t - rolling_window:t]
        mu_hist = np.nanmean(hist, axis=0)
        momentum = np.nanmean(log_returns[max(0, t - 5):t], axis=0)
        mu_vec = 0.65 * mu_hist + 0.35 * momentum

        sigma = np.cov(hist, rowvar=False)
        sigma = np.asarray(sigma, dtype=float)
        if sigma.ndim == 0:
            sigma = np.eye(len(holdings)) * float(sigma)
        if sigma.ndim == 1:
            sigma = np.diag(sigma)
        sigma = np.nan_to_num(sigma, nan=0.0, posinf=0.0, neginf=0.0)

        corr = np.corrcoef(hist, rowvar=False)
        corr = np.nan_to_num(corr, nan=0.0, posinf=0.0, neginf=0.0)
        corr_abs = np.abs(corr)

        if risk_model == 'gcn':
            sigma = sigma * (0.70 + 0.30 * corr_abs)
        elif risk_model == 'convex':
            diag_sigma = np.diag(np.diag(sigma))
            sigma = 0.50 * sigma + 0.50 * diag_sigma

        need_rebalance = (rebalance_counter % rebalance == 0)
        if need_rebalance:
            current_w = solve_markowitz_weights(mu_vec, sigma, gamma=gamma)
            turnover = float(np.sum(np.abs(current_w - previous_w)))
            turnovers.append(turnover)
            previous_w = current_w.copy()

        rebalance_counter += 1
        day_ret_vec = log_returns[t]
        port_log = float(np.dot(current_w, day_ret_vec))
        bench_log = float(np.mean(day_ret_vec))

        strategy_log.append(port_log)
        benchmark_log.append(bench_log)
        strategy_dates.append(date_labels[t + 1])
        weight_rows.append(current_w.tolist())

        exp_ann_ret = float(np.dot(current_w, mu_vec) * 252)
        exp_ann_vol = float(np.sqrt(max(np.dot(current_w, np.dot(sigma, current_w)) * 252, 0.0)))
        rolling_forecast_points.append([exp_ann_vol, exp_ann_ret])

    strategy_log_arr = np.array(strategy_log, dtype=float)
    benchmark_log_arr = np.array(benchmark_log, dtype=float)

    strategy_nav = (initial_capital * np.exp(np.cumsum(strategy_log_arr))).tolist()
    benchmark_nav = (initial_capital * np.exp(np.cumsum(benchmark_log_arr))).tolist()

    nav_arr = np.array(strategy_nav, dtype=float)
    peak = np.maximum.accumulate(nav_arr)
    drawdown = ((nav_arr - peak) / (peak + 1e-10)).tolist()

    arith_ret = np.exp(strategy_log_arr) - 1.0
    cumulative_return = float(nav_arr[-1] / initial_capital - 1.0)
    mean_log = float(np.mean(strategy_log_arr)) if len(strategy_log_arr) else 0.0
    std_log = float(np.std(strategy_log_arr, ddof=1)) if len(strategy_log_arr) > 1 else 0.0
    ann_ret = float(np.exp(mean_log * 252) - 1.0)
    ann_vol = float(std_log * np.sqrt(252))
    sharpe = float(ann_ret / ann_vol) if ann_vol > 1e-12 else 0.0
    downside = np.minimum(arith_ret, 0.0)
    downside_std = float(np.std(downside, ddof=1)) if len(downside) > 1 else 0.0
    sortino = float((np.mean(arith_ret) * 252) / (downside_std * np.sqrt(252))) if downside_std > 1e-12 else 0.0
    max_dd = float(np.min(drawdown)) if drawdown else 0.0
    calmar = float(ann_ret / abs(max_dd)) if max_dd < -1e-12 else 0.0
    win_rate = float(np.mean(arith_ret > 0.0)) if len(arith_ret) else 0.0
    avg_turnover = float(np.mean(turnovers)) if turnovers else 0.0

    rolling_sharpe_window = 20
    rolling_sharpe = []
    for i in range(len(strategy_log_arr)):
        if i + 1 < rolling_sharpe_window:
            rolling_sharpe.append(None)
            continue
        seg = strategy_log_arr[i + 1 - rolling_sharpe_window:i + 1]
        seg_ann_ret = float(np.exp(np.mean(seg) * 252) - 1.0)
        seg_ann_vol = float(np.std(seg, ddof=1) * np.sqrt(252)) if len(seg) > 1 else 0.0
        rolling_sharpe.append(float(seg_ann_ret / seg_ann_vol) if seg_ann_vol > 1e-12 else 0.0)

    final_window = log_returns[-rolling_window:]
    stock_ann_ret = np.mean(final_window, axis=0) * 252
    stock_ann_vol = np.std(final_window, axis=0, ddof=1) * np.sqrt(252)
    latest_weights = np.array(weight_rows[-1], dtype=float) if weight_rows else np.ones(len(holdings)) / len(holdings)

    risk_return_points = []
    for idx, stock in enumerate(holdings):
        risk_return_points.append({
            'stock': stock,
            'ann_vol': float(stock_ann_vol[idx]),
            'ann_ret': float(stock_ann_ret[idx]),
            'weight': float(latest_weights[idx])
        })

    return {
        'metrics': {
            'cumulative_return': cumulative_return,
            'annual_return': ann_ret,
            'annual_volatility': ann_vol,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'calmar_ratio': calmar,
            'max_drawdown': max_dd,
            'win_rate': win_rate,
            'avg_turnover': avg_turnover
        },
        'series': {
            'dates': strategy_dates,
            'strategy_nav': strategy_nav,
            'benchmark_nav': benchmark_nav,
            'drawdown': drawdown,
            'rolling_sharpe': rolling_sharpe
        },
        'weights': {
            'stocks': holdings,
            'dates': strategy_dates,
            'matrix': weight_rows
        },
        'risk_return': {
            'points': risk_return_points,
            'frontier': rolling_forecast_points
        },
        'params': {
            'holdings': holdings,
            'lookback': lookback,
            'predict_start_date': start_date.strftime('%Y-%m-%d'),
            'rolling_window': rolling_window,
            'rebalance_freq': rebalance,
            'gamma': gamma,
            'risk_model': risk_model,
            'initial_capital': initial_capital
        },
        'timestamp': datetime.now().isoformat()
    }


# ==================== Flask 路由 ====================

@app.route('/')
def index():
    """提供首页"""
    return send_from_directory(BASE_DIR, 'index.html')


@app.route('/index.html')
def index_page():
    """提供首页"""
    return send_from_directory(BASE_DIR, 'index.html')


@app.route('/login.html')
def login_page():
    """提供登录页面"""
    return send_from_directory(BASE_DIR, 'login.html')


@app.route('/register.html')
def register_page():
    """提供注册页面"""
    return send_from_directory(BASE_DIR, 'register.html')


@app.route('/predict.html')
def predict_page():
    """提供预测页面"""
    return send_from_directory(BASE_DIR, 'predict.html')


@app.route('/risk.html')
def risk_page():
    """提供风险建模页面"""
    return send_from_directory(BASE_DIR, 'risk.html')


@app.route('/backtest.html')
def backtest_page():
    """提供回测页面"""
    return send_from_directory(BASE_DIR, 'backtest.html')


@app.route('/holdings.html')
def holdings_page():
    """提供持股管理页面"""
    return send_from_directory(BASE_DIR, 'holdings.html')


@app.route('/style.css')
def style():
    """提供 CSS 文件"""
    return send_from_directory(BASE_DIR, 'style.css')


@app.route('/css/<path:filename>')
def css_files(filename):
    """提供 CSS 文件夹下的文件"""
    return send_from_directory(os.path.join(BASE_DIR, 'css'), filename)


@app.route('/js/<path:filename>')
def js_files(filename):
    """提供 JS 文件夹下的文件"""
    return send_from_directory(os.path.join(BASE_DIR, 'js'), filename)


@app.route('/api/predict', methods=['POST'])
def predict():
    """
    预测 API 端点
    
    POST 请求格式:
    {
        "stock": "000001.SZ",
        "predict_days": 30,
        "history_days": 60,
        "confidence": 0.7,
        "gru_hidden": 64,
        "transformer_heads": 8,
        "seasonality": 20,
        "ma_period": 5,
        "models": ["gru", "transformer"]
    }
    """
    try:
        params = request.json
        
        if not params or not isinstance(params, dict):
            error_msg = '请求体为空或不是JSON格式'
            print(f"参数验证失败: {error_msg}")
            return jsonify({'error': error_msg}), 400
        
        # 启用详细日志
        print(f"预测请求参数: {params}")
        
        # 验证参数
        required_params = ['stock', 'predict_days', 'history_days', 'models']
        missing = [p for p in required_params if p not in params]
        if missing:
            error_msg = f'缺少必要参数: {", ".join(missing)}'
            print(f"参数验证失败: {error_msg}")
            return jsonify({'error': error_msg}), 400
        
        stock = params['stock']
        if not stock or not isinstance(stock, str) or stock.strip() == '':
            error_msg = '股票代码不能为空'
            print(f"参数验证失败: {error_msg}")
            return jsonify({'error': error_msg}), 400
        
        # 参数类型转换
        try:
            predict_days = min(int(params['predict_days']), 100)
            history_days = int(params['history_days'])
            if predict_days <= 0 or history_days <= 0:
                raise ValueError("天数必须大于0")
        except (ValueError, TypeError, KeyError) as e:
            error_msg = f'predict_days 或 history_days 无效: {str(e)}'
            print(f"参数验证失败: {error_msg}")
            return jsonify({'error': error_msg}), 400
        
        models = params.get('models', ['gru', 'transformer'])
        if not models or not isinstance(models, list) or len(models) == 0:
            error_msg = 'models 必须是非空列表'
            print(f"参数验证失败: {error_msg}")
            return jsonify({'error': error_msg}), 400
        
        try:
            gru_hidden = int(params.get('gru_hidden', 64))
            transformer_heads = int(params.get('transformer_heads', 8))
            ma_period = int(params.get('ma_period', 5))
        except (ValueError, TypeError) as e:
            error_msg = f'数值参数类型错误: {str(e)}'
            print(f"参数验证失败: {error_msg}")
            return jsonify({'error': error_msg}), 400
        
        prediction_start_date, historical_mode, _ = resolve_prediction_start_date(params)

        # 按“开始预测日期”加载历史窗口数据
        source_df = load_stock_prices_with_dates(stock, end_date=prediction_start_date)
        if source_df is None or source_df.empty:
            return jsonify({'error': '未找到可用历史数据'}), 400

        df = source_df.tail(history_days).reset_index(drop=True)
        
        if df.empty or len(df) < 20:
            return jsonify({'error': '可用数据不足，请选择更晚的时间节点或增加历史回溯期'}), 400
        
        actual_history_len = len(df)
        prices = df['Close'].values
        
        # 确保数据完整：采用更激进的缺失值处理策略
        # 步骤1: 转换为 pandas Series 以便使用 ffill/bfill
        prices_series = pd.Series(prices)
        
        # 步骤2: forward fill（从左往右）处理缺失
        prices_series = prices_series.ffill()
        
        # 步骤3: backward fill（从右往左）处理仍然残留的 NaN
        prices_series = prices_series.bfill()
        
        # 步骤4: 如果仍有 NaN（比如全是缺失），用简单线性插值
        if prices_series.isna().any():
            prices_series.interpolate(method='linear', inplace=True)
            prices_series.bfill(inplace=True)
        
        prices = prices_series.values
        
        # 应用移动平均，使用min_periods确保即使数据少也能计算
        prices_smooth = pd.Series(prices).rolling(ma_period, center=True, min_periods=1).mean().values
        
        # 历史标签使用真实交易日期
        hist_dates = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d').tolist()
        
        # 生成预测数据
        predictions_gru = None
        predictions_transformer = None
        
        if 'gru' in models:
            predictions_gru = predict_with_gru(prices_smooth, predict_days, stock_code=stock, hidden_size=gru_hidden)
        
        if 'transformer' in models:
            predictions_transformer = predict_with_transformer(prices_smooth, predict_days, stock_code=stock, num_heads=transformer_heads)
        
        # 合并历史和预测数据
        actual_data = list(prices_smooth)
        
        # 预测数据：历史部分为None，预测部分为预测值
        # 选择第一个可用的模型预测作为主预测线
        predicted_data = [None] * len(prices_smooth)
        if predictions_gru:
            predicted_data.extend(predictions_gru)
        elif predictions_transformer:
            predicted_data.extend(predictions_transformer)
        else:
            predicted_data.extend([None] * predict_days)
        
        # 生成预测标签
        future_dates = pd.date_range(start=prediction_start_date + timedelta(days=1), periods=predict_days, freq='D')
        future_labels = [d.strftime('%Y-%m-%d') for d in future_dates]

        future_actual = [None] * predict_days
        if historical_mode:
            all_future_df = load_stock_prices_with_dates(stock, end_date=None)
            if all_future_df is not None and not all_future_df.empty:
                all_future_df = all_future_df[all_future_df['Date'].dt.date > prediction_start_date]
                all_future_df = all_future_df.sort_values('Date').head(predict_days)
                actual_map = {
                    pd.to_datetime(row['Date']).strftime('%Y-%m-%d'): float(row['Close'])
                    for _, row in all_future_df.iterrows()
                }
                future_actual = [actual_map.get(lbl) for lbl in future_labels]

        actual_data.extend(future_actual)
        
        all_labels = hist_dates + future_labels
        
        # 计算评估指标
        metrics = {}
        if predictions_gru and historical_mode:
            pairs = [
                (pred, actual)
                for pred, actual in zip(predictions_gru, future_actual)
                if actual is not None
            ]
            if pairs:
                pred_vals = np.array([p[0] for p in pairs], dtype=float)
                actual_vals = np.array([p[1] for p in pairs], dtype=float)
                metrics = calculate_metrics(actual_vals, pred_vals)
        
        return jsonify({
            'labels': all_labels,
            'actual': actual_data,
            'predicted': predicted_data,
            'future_actual': future_actual,
            'historical_mode': historical_mode,
            'predict_start_date': prediction_start_date.strftime('%Y-%m-%d'),
            'metrics': metrics,
            'stock': stock,
            'timestamp': datetime.now().isoformat()
        })
    
    except PermissionError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        print(f"Prediction error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/stocks', methods=['GET'])
def get_stocks():
    """获取可用的股票列表"""
    try:
        return jsonify({'stocks': get_available_stocks()})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stocks/supported', methods=['GET'])
def get_supported_stocks_api():
    """获取支持分析的股票列表（已训练模型的股票）"""
    try:
        stocks = get_supported_stocks()
        return jsonify({
            'code': 0,
            'message': '获取支持的股票列表成功',
            'data': stocks
        })
    except Exception as e:
        return jsonify({
            'code': 1,
            'message': f'获取股票列表失败: {str(e)}',
            'data': []
        }), 500


@app.route('/api/predict/stocks/by-model', methods=['GET'])
def get_predict_stocks_by_model():
    """按预测模型文件获取股票列表。"""
    try:
        models_param = str(request.args.get('models', '')).strip().lower()
        mode = str(request.args.get('mode', 'any')).strip().lower()
        if mode not in {'any', 'all'}:
            mode = 'any'

        selected_models = []
        if models_param:
            selected_models = [
                item.strip() for item in models_param.split(',')
                if item.strip() in MODEL_PATH
            ]

        stocks, stocks_by_model = get_stocks_by_prediction_models(selected_models, mode)

        return jsonify({
            'code': 0,
            'message': '获取模型股票列表成功',
            'data': {
                'stocks': stocks,
                'stocks_by_model': stocks_by_model,
                'selected_models': selected_models if selected_models else list(MODEL_PATH.keys()),
                'mode': mode,
                'total': len(stocks)
            }
        })
    except Exception as e:
        return jsonify({
            'code': 1,
            'message': f'获取模型股票列表失败: {str(e)}',
            'data': {
                'stocks': [],
                'stocks_by_model': {},
                'selected_models': [],
                'mode': 'any',
                'total': 0
            }
        }), 500


@app.route('/health', methods=['GET'])
def health():
    """健康检查端点"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})


@app.route('/api/risk/modeling', methods=['POST'])
def risk_modeling():
    """风险建模 API：支持 gcn / coefficient / convex 三种方法"""
    try:
        params = request.json or {}
        result = build_risk_modeling_result(params)
        return jsonify(result)

    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    except PermissionError as e:
        return jsonify({'error': str(e)}), 401

    except Exception as e:
        print(f"Risk modeling error: {e}")
        return jsonify({'error': f'风险建模失败: {str(e)}'}), 500


@app.route('/api/risk/export', methods=['POST'])
def export_risk_result():
    """风险结果导出 API：支持 csv/json"""
    try:
        params = request.json or {}
        export_format = str(params.get('format', 'csv')).lower()
        if export_format not in {'csv', 'json'}:
            return jsonify({'error': 'format 仅支持 csv 或 json'}), 400

        result = build_risk_modeling_result(params)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')

        if export_format == 'json':
            payload = json.dumps(result, ensure_ascii=False, indent=2)
            response = make_response(payload)
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            response.headers['Content-Disposition'] = f'attachment; filename=risk_result_{ts}.json'
            return response

        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(['section', 'field', 'value'])

        for key, value in result['params'].items():
            writer.writerow(['params', key, json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value])

        for key, value in result['metrics'].items():
            writer.writerow(['metrics', key, value])

        writer.writerow(['', '', ''])
        writer.writerow(['nodes', 'stock', 'risk'])
        for node in result['graph']['nodes']:
            writer.writerow(['nodes', node['name'], node['risk']])

        writer.writerow(['', '', ''])
        writer.writerow(['links', 'source->target', 'weight'])
        for link in result['graph']['links']:
            writer.writerow(['links', f"{link['source']}->{link['target']}", link['value']])

        writer.writerow(['', '', ''])
        writer.writerow(['method_scores', 'method', 'stock:score list'])
        for series in result['bar']['method_series']:
            score_pairs = [f"{stock}:{score}" for stock, score in zip(result['bar']['stocks'], series['scores'])]
            writer.writerow(['method_scores', series['method'], '; '.join(score_pairs)])

        response = make_response(csv_buffer.getvalue())
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename=risk_result_{ts}.csv'
        return response

    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    except PermissionError as e:
        return jsonify({'error': str(e)}), 401

    except Exception as e:
        print(f"Risk export error: {e}")
        return jsonify({'error': f'风险导出失败: {str(e)}'}), 500


@app.route('/api/backtest/run', methods=['POST'])
def run_backtest_api():
    """回测 API：融合预测收益信号与风险控制进行动态权重回测"""
    try:
        params = request.json or {}
        result = build_backtest_result(params)
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except PermissionError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        print(f"Backtest error: {e}")
        return jsonify({'error': f'回测失败: {str(e)}'}), 500


if __name__ == '__main__':
    # In debug reloader mode, only start scheduler in the child process.
    is_reloader_child = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    if not app.debug or is_reloader_child:
        start_daily_update_scheduler(BASE_DIR)

    # app.run(host='0.0.0.0', port=PORT, debug=True)
    app.run(host='0.0.0.0', port=5000, debug=True)  # host 必须为 0.0.0.0