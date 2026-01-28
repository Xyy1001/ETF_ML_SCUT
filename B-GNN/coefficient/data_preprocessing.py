import os
import glob
import pickle
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import yaml
from sklearn.preprocessing import StandardScaler


def _read_yaml_config(path: str) -> Dict:
    """读取 YAML 配置文件为字典。"""
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def _ensure_dir(path: str) -> None:
    """确保路径所在目录存在。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _extract_features_and_target(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    """从DataFrame中提取特征和目标变量。
    
    Args:
        df: 包含股票数据的DataFrame
        
    Returns:
        features: 形状为 [T, 36] 的特征矩阵（第3-38列，36个特征）
        log_returns: 形状为 [T] 的对数收益率向量（第38列）
    """
    # 第3-38列为特征指标（36个特征）
    # 特征：第3-38列（36维特征）
    features = df.iloc[:, 2:38].values.astype(np.float64)  # 第3-38列（索引2-37，共36列）
    
    # 提取对数收益率（第38列）
    log_returns = df.iloc[:, 37].values.astype(np.float64)  # 第38列（索引37）
    
    print(f"提取特征形状: {features.shape}, 对数收益率形状: {log_returns.shape}")
    return features, log_returns


def _load_single_xlsx(path: str) -> pd.DataFrame:
    """读取单只股票 XLSX 文件，确保所有交易日数据都被读取。"""
    try:
        # 读取数据，header=0表示第一行是列名，从第二行开始是数据
        df = pd.read_excel(path, header=0)
        print(f"读取文件 {path}，数据形状: {df.shape}")
        print(f"列名: {list(df.columns)}")
        
        # 检查是否有空行或无效数据
        original_rows = len(df)
        df = df.dropna(how='all')  # 删除完全为空的行
        if len(df) != original_rows:
            print(f"删除了 {original_rows - len(df)} 个空行")
        
        print(f"最终数据形状: {df.shape}")
        return df
    except Exception as e:
        raise ValueError(f"无法读取文件 {path}: {e}")


def _split_data(features_list: List[np.ndarray], log_returns_list: List[np.ndarray],
                train_days: int = 3688, test_days: int = 205) -> Tuple[List[np.ndarray], List[np.ndarray], 
                                                   List[np.ndarray], List[np.ndarray]]:
    """将数据按时间顺序切分为训练集和测试集。
    
    Args:
        features_list: 每只股票的特征矩阵列表
        log_returns_list: 每只股票的对数收益率列表
        train_days: 训练集天数（前3688行）
        test_days: 测试集天数（第3589-3793行，共205天）
        
    Returns:
        train_features, train_returns, test_features, test_returns
    """
    # 假设所有股票的数据长度相同
    total_days = features_list[0].shape[0]
    
    # 测试集起始位置（从第3589行开始，索引为3588）
    test_start = 3588  # 第3589行的索引
    test_end = test_start + test_days  # 第3793行的索引+1
    
    # 验证数据长度
    if total_days < train_days:
        print(f"警告：数据长度不足训练集要求。期望{train_days}天，实际{total_days}天")
        train_days = total_days
    
    if total_days < test_end:
        print(f"警告：数据长度不足测试集要求。期望到第{test_end}行，实际{total_days}行")
        test_end = total_days
        test_days = test_end - test_start
    
    print(f"总交易日数: {total_days}")
    print(f"训练集: 前{train_days}天（第1-{train_days}行）")
    print(f"测试集: 第{test_start+1}-{test_end}行，共{test_days}天")
    
    train_features = [features[:train_days] for features in features_list]
    train_returns = [returns[:train_days] for returns in log_returns_list]
    test_features = [features[test_start:test_end] for features in features_list]
    test_returns = [returns[test_start:test_end] for returns in log_returns_list]
    
    return train_features, train_returns, test_features, test_returns


def _build_samples(features_list: List[np.ndarray], log_returns_list: List[np.ndarray],
                  lookback: int = 100, horizon: int = 10) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """构造样本：110天滑动窗口（前100天特征+后10天目标）。
    
    如果无法计算相关系数，则跳过样本。

    Args:
        features_list: 每只股票的特征矩阵列表 [T, 36]
        log_returns_list: 每只股票的对数收益率列表 [T]
        lookback: 回溯天数（100天）
        horizon: 预测天数（10天）
        
    Returns:
        node_features: [n_samples, n_stocks, 36, lookback] 节点特征
        edge_features: [n_samples, n_stocks, n_stocks] 边特征（相关系数矩阵）
        targets: [n_samples, n_stocks, n_stocks] 目标（未来10天相关系数矩阵）
    """
    n_stocks = len(features_list)
    T = features_list[0].shape[0]
    window_size = lookback + horizon  # 110天
    
    max_samples = T - window_size + 1
    if max_samples <= 0:
        raise ValueError(f"数据长度不足，无法构造样本。需要至少{window_size}天数据，当前只有{T}天")

    print(f"最多可构造 {max_samples} 个样本，每个样本使用 {window_size} 天数据")

    # 初始化列表以存储有效样本
    node_features_list = []
    edge_features_list = []
    targets_list = []
    
    successful_samples = 0
    skipped_samples = 0
    
    # 滑动窗口构造样本
    for i in range(max_samples):
        start_idx = i
        lookback_end = start_idx + lookback
        horizon_end = lookback_end + horizon
        
        # 1. 构造边特征：前100天各股票对数收益率的相关系数平方矩阵
        lookback_returns = np.stack([
            log_returns_list[stock_idx][start_idx:lookback_end]
            for stock_idx in range(n_stocks)
        ], axis=0)  # [n_stocks, 100]

        # 检查是否存在任何股票的收益率在窗口期内是恒定的
        if np.any(np.std(lookback_returns, axis=1) < 1e-8):
            # print(f"样本 {i}: 无法计算边特征（历史收益率恒定），跳过该样本。")
            skipped_samples += 1
            continue

        try:
            corr_matrix = np.corrcoef(lookback_returns)
            edge_matrix = np.nan_to_num(corr_matrix)  # 直接使用相关系数矩阵
        except Exception as e:
            # print(f"样本 {i}: 计算边特征时发生未知错误，跳过该样本。错误: {e}")
            skipped_samples += 1
            continue

        # 2. 构造目标：后10天各股票对数收益率的相关系数矩阵
        future_returns = np.stack([
            log_returns_list[stock_idx][lookback_end:horizon_end]
            for stock_idx in range(n_stocks)
        ], axis=0)  # [n_stocks, 10]

        if np.any(np.std(future_returns, axis=1) < 1e-9):
            # print(f"样本 {i}: 无法计算目标矩阵（未来收益率恒定），跳过该样本。")
            skipped_samples += 1
            continue

        try:
            target_corr = np.corrcoef(future_returns)
            target_corr = np.nan_to_num(target_corr)
        except Exception as e:
            # print(f"样本 {i}: 计算目标矩阵时发生未知错误，跳过该样本。错误: {e}")
            skipped_samples += 1
            continue

        # 3. 构造节点特征
        current_node_features = np.zeros((n_stocks, 36, lookback), dtype=np.float64)
        for stock_idx in range(n_stocks):
            stock_features = features_list[stock_idx][start_idx:lookback_end]
            current_node_features[stock_idx] = stock_features.T
        
        node_features_list.append(current_node_features)
        edge_features_list.append(edge_matrix.astype(np.float64))
        targets_list.append(target_corr.astype(np.float64))
        successful_samples += 1

    if successful_samples > 0:
        node_features = np.stack(node_features_list, axis=0)
        edge_features = np.stack(edge_features_list, axis=0)
        targets = np.stack(targets_list, axis=0)
    else:
        node_features = np.empty((0, n_stocks, 36, lookback), dtype=np.float64)
        edge_features = np.empty((0, n_stocks, n_stocks), dtype=np.float64)
        targets = np.empty((0, n_stocks, n_stocks), dtype=np.float64)

    print(f"\n样本构造完成:")
    print(f"  成功构造样本数量: {successful_samples}")
    print(f"  因无法计算相关性而放弃的样本数量: {skipped_samples}")
    print(f"  节点特征形状: {node_features.shape}")
    print(f"  边特征形状: {edge_features.shape}")
    print(f"  目标形状: {targets.shape}")
    
    return node_features, edge_features, targets


def _standardize_features_per_sample(train_node_features: np.ndarray, test_node_features: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """对每个样本的节点特征进行标准化处理。
    
    对于每个样本的26个节点特征矩阵 [26, 36, 100]，分别对每个节点的特征矩阵按列（特征维度）进行标准化。
    即对每个节点的 [36, 100] 矩阵，按36个特征维度分别标准化。
    
    Args:
        train_node_features: 训练集节点特征 [n_train_samples, 26, 36, 100]
        test_node_features: 测试集节点特征 [n_test_samples, 26, 36, 100]
        
    Returns:
        标准化后的训练集特征、测试集特征
    """
    print("开始按样本进行特征标准化...")
    
    # 获取形状信息
    n_train_samples, n_stocks, n_features, lookback = train_node_features.shape
    n_test_samples = test_node_features.shape[0]
    
    # 初始化输出数组
    train_normalized = np.zeros_like(train_node_features)
    test_normalized = np.zeros_like(test_node_features)
    
    # 对每个训练样本进行标准化
    for sample_idx in range(n_train_samples):
        for stock_idx in range(n_stocks):
            # 获取该样本该股票的特征矩阵 [36, 100]
            stock_features = train_node_features[sample_idx, stock_idx]  # [36, 100]
            
            # 对每个特征维度（36维）分别进行标准化
            normalized_features = np.zeros_like(stock_features)
            for feature_idx in range(n_features):
                feature_values = stock_features[feature_idx, :]  # [100]
                
                # 计算该特征的均值和标准差
                mean_val = np.mean(feature_values)
                std_val = np.std(feature_values)
                
                # 避免除零错误，设置极小的默认标准差
                if std_val < 1e-8:
                    std_val = 1e-8  # 设置极小的默认值
                normalized_features[feature_idx, :] = (feature_values - mean_val) / std_val
            
            train_normalized[sample_idx, stock_idx] = normalized_features
    
    # 对每个测试样本进行标准化
    for sample_idx in range(n_test_samples):
        for stock_idx in range(n_stocks):
            # 获取该样本该股票的特征矩阵 [36, 100]
            stock_features = test_node_features[sample_idx, stock_idx]  # [36, 100]
            
            # 对每个特征维度（36维）分别进行标准化
            normalized_features = np.zeros_like(stock_features)
            for feature_idx in range(n_features):
                feature_values = stock_features[feature_idx, :]  # [100]
                
                # 计算该特征的均值和标准差
                mean_val = np.mean(feature_values)
                std_val = np.std(feature_values)
                
                # 避免除零错误，设置极小的默认标准差
                if std_val < 1e-8:
                    std_val = 1e-8  # 设置极小的默认值
                normalized_features[feature_idx, :] = (feature_values - mean_val) / std_val
            
            test_normalized[sample_idx, stock_idx] = normalized_features
    
    print(f"按样本特征标准化完成，处理了{n_train_samples}个训练样本和{n_test_samples}个测试样本")
    print(f"每个样本包含{n_stocks}只股票，每只股票有{n_features}个特征维度")
    return train_normalized, test_normalized


def preprocess(config_path: str = "configs/variables.yaml") -> None:
    """主入口：读取XLSX文件 → 数据切分 → 样本构造 → 标准化 → 保存。
    
    Args:
        config_path: 配置文件路径
    """
    print("=== 开始数据预处理 ===")
    
    # 读取配置文件
    cfg = _read_yaml_config(config_path)
    
    # 1. 读取XLSX文件
    raw_dir = "data/raw"
    xlsx_files = sorted(glob.glob(os.path.join(raw_dir, "*.xlsx")))
    
    if len(xlsx_files) == 0:
        raise FileNotFoundError(f"未在 {raw_dir} 下发现任何 XLSX 文件")
    
    print(f"找到 {len(xlsx_files)} 个XLSX文件: {xlsx_files}")
    
    # 2. 加载所有股票数据
    all_features = []
    all_log_returns = []
    
    for xlsx_file in xlsx_files:
        df = _load_single_xlsx(xlsx_file)
        features, log_returns = _extract_features_and_target(df)
        all_features.append(features)
        all_log_returns.append(log_returns)
    
    # 3. 数据切分（从配置文件读取参数，如果没有则使用默认值0.7）
    train_ratio = cfg.get('gnn_training', {}).get('train_ratio', 0.7)
    print(f"使用固定训练天数: 3688天，测试天数: 205天")
    train_features, train_returns, test_features, test_returns = _split_data(
        all_features, all_log_returns, train_days=3688, test_days=205
    )
    
    # 4. 构造训练样本
    print("\n构造训练样本...")
    train_node_features, train_edge_features, train_targets = _build_samples(
        train_features, train_returns, lookback=100, horizon=10
    )
    
    # 5. 构造测试样本
    print("\n构造测试样本...")
    test_node_features, test_edge_features, test_targets = _build_samples(
        test_features, test_returns, lookback=100, horizon=10
    )
    
    # 6. 特征标准化（按样本进行）
    print("\n进行特征标准化...")
    train_node_normalized, test_node_normalized = _standardize_features_per_sample(
        train_node_features, test_node_features
    )
    
    # 7. 保存数据
    print("\n保存处理后的数据...")
    
    # 确保输出目录存在
    output_dir = "data"
    _ensure_dir(os.path.join(output_dir, "dummy.txt"))
    
    # 保存训练集
    np.save(os.path.join(output_dir, "train_node_features_raw.npy"), train_node_features)
    np.save(os.path.join(output_dir, "train_node_features_norm.npy"), train_node_normalized)
    np.save(os.path.join(output_dir, "train_edge_features.npy"), train_edge_features)
    np.save(os.path.join(output_dir, "train_targets.npy"), train_targets)
    
    # 保存测试集
    np.save(os.path.join(output_dir, "test_node_features_raw.npy"), test_node_features)
    np.save(os.path.join(output_dir, "test_node_features_norm.npy"), test_node_normalized)
    np.save(os.path.join(output_dir, "test_edge_features.npy"), test_edge_features)
    np.save(os.path.join(output_dir, "test_targets.npy"), test_targets)
    
    # 注意：由于采用按样本标准化，不再保存全局标准化器
    
    # 打印总结信息
    print("\n=== 数据预处理完成 ===")
    print(f"训练集样本数: {train_node_features.shape[0]}")
    print(f"测试集样本数: {test_node_features.shape[0]}")
    print(f"股票数量: {train_node_features.shape[1]}")
    print(f"特征维度: {train_node_features.shape[2]}")
    print(f"回溯天数: {train_node_features.shape[3]}")
    print(f"边特征维度: {train_edge_features.shape[1]}x{train_edge_features.shape[2]}")
    print(f"目标维度: {train_targets.shape[1]}x{train_targets.shape[2]}")
    
    print("\n保存的文件:")
    for filename in ["train_node_features_raw.npy", "train_node_features_norm.npy", 
                     "train_edge_features.npy", "train_targets.npy",
                     "test_node_features_raw.npy", "test_node_features_norm.npy",
                     "test_edge_features.npy", "test_targets.npy"]:
        print(f"  - {os.path.join(output_dir, filename)}")
    print("\n注意：采用按样本标准化方式，每个样本独立标准化，不保存全局标准化器")
    
    print("\n数据预处理流程完成！")


if __name__ == '__main__':
    preprocess()


