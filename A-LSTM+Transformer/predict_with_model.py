#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
predict_with_model.py

通过已训练的模型预测指定股票在给定历史区间后的未来 n 天 close。

用法示例：
python predict_with_model.py --ts_code 000001.SZ --start_date 20240101 --end_date 20251031 --predict_days 10

说明：
- 会尝试从环境变量 TUSHARE_TOKEN 读取 tushare token，也可以在运行时输入。
- 默认会尝试加载模型路径 Advanced/Models/{ts_code}.pth
- 预测过程使用训练时的缩放（来自数据集样本返回的 scaler），在 scaled 空间迭代预测，再反标准化输出。
"""
import os
import argparse
import sys
from datetime import datetime
import numpy as np
import pandas as pd
import torch

try:
    import tushare as ts
except Exception:
    ts = None

# 尝试从同一目录导入训练脚本中定义的工具类/函数
try:
    from TrainingModel import preprocess_data, StockTimeSeriesDataset, MultiVariateLSTM_Transformer
except Exception as e:
    print("无法从 TrainingModel 导入必要组件，请确保本文件与 TrainingModel.py 在同一目录下，或调整 PYTHONPATH.")
    raise


def fetch_history(ts_token, ts_code, start_date, end_date):
    if ts is None:
        raise RuntimeError("tushare 未安装，请先 pip install tushare")
    if not ts_token:
        raise ValueError("需要提供 tushare token（环境变量 TUSHARE_TOKEN 或命令行参数）")
    ts.set_token(ts_token)
    pro = ts.pro_api()

    # tushare 的日期格式通常是 YYYYMMDD
    df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    if df is None or df.shape[0] == 0:
        raise ValueError(f"未从 tushare 获取到 {ts_code} 在 {start_date}~{end_date} 的历史日线，请检查代码或日期范围")

    # 按交易日升序排列
    df = df.sort_values('trade_date')
    df = df.reset_index(drop=True)

    # 将 trade_date 放到第一列并修改列名为常见字段
    # 保留常见 OHLC + vol + amount + pct_chg 等，其他列按原样保留
    return df


def infer_output_window_from_state(state_dict):
    # state_dict 中查找 fc.weight 的形状以推断 output_window
    # 形如: fc.weight -> (output_size * output_window, lstm_hidden_size)
    for k, v in state_dict.items():
        if k.endswith('fc.weight') or k == 'fc.weight':
            rows = v.shape[0]
            # 假设 output_size == 1
            return int(rows)
    return None


def predict(ts_token, ts_code, start_date, end_date, model_path=None, input_window=100, predict_days=10, device='cpu'):
    # 1) 抓取历史数据
    df = fetch_history(ts_token, ts_code, start_date, end_date)

    # 2) 预处理（使用 TrainingModel.preprocess_data）
    df_proc = preprocess_data(df.copy())

    # 3) 准备模型 checkpoint 并尝试从 checkpoint 推断模型的 input_size / output_window
    # 这里先尝试使用模型保存文件名提供的路径，否则在 Advanced/Models 下查找
    if model_path is None:
        model_path = os.path.join(os.path.dirname(__file__), 'Models', f"{ts_code}.pth")

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"模型文件不存在: {model_path}")

    # 读取 checkpoint（checkpoint 可能是直接的 state_dict，也可能是一个包含 state_dict 的 dict）
    raw_state = torch.load(model_path, map_location='cpu')
    # 兼容常见保存格式
    if isinstance(raw_state, dict) and ('state_dict' in raw_state or 'model_state_dict' in raw_state):
        state = raw_state.get('state_dict', raw_state.get('model_state_dict'))
    else:
        state = raw_state

    # 如果 state 仍非 dict，则无法处理
    if not isinstance(state, dict):
        raise RuntimeError(f"无法识别的 checkpoint 格式: {type(raw_state)}")

    # 从 lstm.weight_ih_l0 推断 input_size（列数），并从 fc.weight 推断 output_window（行数）
    inferred_input_size = None
    for k, v in state.items():
        if k.endswith('lstm.weight_ih_l0') or 'lstm.weight_ih_l0' in k:
            inferred_input_size = v.shape[1]
            break

    inferred_output_window = None
    for k, v in state.items():
        if k.endswith('fc.weight') or k == 'fc.weight' or k.endswith('.fc.weight'):
            # 假设 output_size == 1
            inferred_output_window = int(v.shape[0])
            break

    # 如果无法从 checkpoint 推断 input_size，则使用数据集最后一个滑窗来推断
    ds_try = StockTimeSeriesDataset(df_proc, input_window=input_window, output_window=1)
    if len(ds_try) <= 0:
        raise ValueError(f"历史数据样本不足，无法构建长度为 {input_window} 的输入窗口，请扩大 start_date 或缩小 input_window。当前可用行数: {len(df_proc)}")
    sample_input_scaled, _, _, target_scaler = ds_try[len(ds_try) - 1]

    if inferred_input_size is None:
        input_size = sample_input_scaled.shape[-1]
        print(f"未从 checkpoint 推断到 input_size，使用数据样本推断 input_size={input_size}")
    else:
        input_size = inferred_input_size
        print(f"从 checkpoint 推断到 input_size={input_size}")

    if inferred_output_window is None:
        inferred_output_window = 20
        print("无法从 checkpoint 推断 output_window，使用默认 output_window=20")
    else:
        print(f"从 checkpoint 推断到 output_window={inferred_output_window}")

    # 5) 构建模型并加载权重（非严格模式）
    model = MultiVariateLSTM_Transformer(
        input_size=input_size,
        lstm_hidden_size=64,
        lstm_layers=2,
        trans_layers=2,
        trans_heads=4,
        trans_ffn_hidden=128,
        dropout=0.1,
        output_size=1,
        output_window=inferred_output_window,
    )

    try:
        missing, unexpected = model.load_state_dict(state, strict=False)
        print(f"加载模型完成（非严格模式），missing keys: {len(missing)}, unexpected keys: {len(unexpected)}")
    except Exception as e:
        # 如果严格加载仍然报错，打印错误并继续（模型会保持随机初始化）
        print(f"加载模型 state_dict 失败，错误: {e}")

    model.to(device)
    model.eval()

    # 6) 在 scaled 空间做迭代式预测
    input_scaled_np = sample_input_scaled.cpu().numpy()  # (input_window, input_size)

    # 检查模型期望的 input_size 与样本实际的列数是否匹配
    # LSTM 模块记录了其 input_size
    expected_input_size = getattr(model.lstm, 'input_size', None)
    current_input_size = input_scaled_np.shape[1]
    if expected_input_size is None:
        print(f"无法从模型获取期望的 input_size，使用样本的 input_size={current_input_size}")
        expected_input_size = current_input_size

    if current_input_size != expected_input_size:
        print(f"警告: 模型期望 input_size={expected_input_size}，但样本 input_size={current_input_size}。将尝试自动调整输入维度以匹配模型。")
        if current_input_size < expected_input_size:
            # 通过复制最后一列和填充0来扩展（更稳妥的做法是保存训练时的 feature 列）
            pad_cols = expected_input_size - current_input_size
            # 复制最后一列作为填充值，如果没有特征列则用0填充
            if current_input_size > 0:
                last_col = input_scaled_np[:, -1:].repeat(pad_cols, axis=1)
            else:
                last_col = np.zeros((input_scaled_np.shape[0], pad_cols), dtype=input_scaled_np.dtype)
            input_scaled_np = np.concatenate([input_scaled_np, last_col], axis=1)
            print(f"已通过复制最后一列/0 填充 {pad_cols} 列。注意：这只是临时兼容，预测结果可能受影响。")
        else:
            # 如果样本列更多，则截断多余列
            input_scaled_np = input_scaled_np[:, :expected_input_size]
            print(f"已截断样本特征列到前 {expected_input_size} 列。请确认截断不会丢失重要特征。")

    feature_dim = input_scaled_np.shape[1] - 1

    remaining = predict_days
    preds_original = []
    preds_scaled_all = []

    with torch.no_grad():
        while remaining > 0:
            x = torch.FloatTensor(input_scaled_np).unsqueeze(0).to(device)  # (1, input_window, input_size)
            out = model(x)  # (1, output_window, 1)
            out = out.squeeze(0).squeeze(-1).cpu().numpy()  # (output_window,)

            take_k = min(remaining, out.shape[0])
            out_part = out[:take_k]

            # 反标准化
            try:
                out_orig = target_scaler.inverse_transform(out_part.reshape(-1, 1)).flatten()
            except Exception:
                # 如果 scaler 无法使用（极端情况），直接把 scaled 当作原值输出
                out_orig = out_part

            preds_original.extend(out_orig.tolist())
            preds_scaled_all.extend(out_part.tolist())

            # 更新 input_scaled_np：把预测的 scaled 值 append 到 target 列，features 使用最后一行重复
            target_col = input_scaled_np[:, 0]
            feature_matrix = input_scaled_np[:, 1:]

            # 扩展 target_col 与 feature_matrix
            new_target_seq = np.concatenate([target_col, out_part])
            # 对 feature 部分，重复最后一行 take_k 次
            last_feat = feature_matrix[-1:, :] if feature_dim > 0 else np.empty((1, 0))
            if feature_dim > 0:
                new_feat_seq = np.vstack([feature_matrix, np.repeat(last_feat, take_k, axis=0)])
            else:
                new_feat_seq = np.empty((new_target_seq.shape[0], 0))

            # 取最后 input_window 条作为新的输入
            new_target_col_trim = new_target_seq[-input_scaled_np.shape[0]:]
            new_feat_trim = new_feat_seq[-input_scaled_np.shape[0]:, :] if feature_dim > 0 else np.empty((input_scaled_np.shape[0], 0))

            input_scaled_np = np.column_stack([new_target_col_trim.reshape(-1, 1), new_feat_trim])

            remaining -= take_k

    # 7) 输出结果并保存到 CSV
    now = datetime.now().strftime('%Y%m%d%H%M%S')
    out_dir = os.path.join(os.path.dirname(__file__), 'predictions')
    os.makedirs(out_dir, exist_ok=True)
    out_csv = os.path.join(out_dir, f"{ts_code}_predictions_{start_date}_{end_date}_{now}.csv")

    df_out = pd.DataFrame({
        'ts_code': ts_code,
        'pred_index': list(range(1, len(preds_original) + 1)),
        'pred_close': preds_original,
        'pred_scaled': preds_scaled_all,
    })
    df_out.to_csv(out_csv, index=False)
    print(f"预测完成，已保存到: {out_csv}")
    # 额外输出：结合十天均值和输入最后一天的对应数据比值进行收益率预测（仅打印到终端）
    # 计算历史最后10天的均值（如果样本少于10天则取可用天数）
    try:
        if 'close' in df_proc.columns:
            last_n = min(10, len(df_proc))
            ten_day_mean = df_proc['close'].iloc[-last_n:].mean()
            last_input_close = df_proc['close'].iloc[-1]
        elif 'close' in df.columns:
            last_n = min(10, len(df))
            ten_day_mean = df['close'].iloc[-last_n:].mean()
            last_input_close = df['close'].iloc[-1]
        else:
            ten_day_mean = None
            last_input_close = None
    except Exception:
        ten_day_mean = None
        last_input_close = None

    print("\n=== 基于十天均值和最后一天收盘价的收益率预测（仅终端输出） ===")
    if ten_day_mean is None or last_input_close is None:
        print("无法找到历史 close 列，无法计算十天均值或最后一天收盘价。")
    else:
        print(f"历史最后 {last_n} 天均值: {ten_day_mean:.6f}, 最后一天收盘价: {last_input_close:.6f}\n")
        # 为每个预测值计算比值与收益率
        for idx, row in df_out.iterrows():
            pred_close = float(row['pred_close'])
            # 比值
            ratio_vs_10ma = pred_close / ten_day_mean if ten_day_mean != 0 else float('nan')
            ratio_vs_last = pred_close / last_input_close if last_input_close != 0 else float('nan')
            # 收益率（百分比）
            ret_vs_10ma = (ratio_vs_10ma - 1.0) * 100.0
            ret_vs_last = (ratio_vs_last - 1.0) * 100.0
            print(f"pred_index={int(row['pred_index'])}: pred_close={pred_close:.6f}, vs_10day_mean={ratio_vs_10ma:.6f} (ret {ret_vs_10ma:.3f}%), vs_last_day={ratio_vs_last:.6f} (ret {ret_vs_last:.3f}%)")

    return df_out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ts_code', required=True, help='股票代码，例如 000001.SZ')
    parser.add_argument('--start_date', required=True, help='历史起始日期，格式 YYYYMMDD')
    parser.add_argument('--end_date', required=True, help='历史结束日期，格式 YYYYMMDD')
    parser.add_argument('--predict_days', type=int, default=10, help='要预测的未来天数')
    parser.add_argument('--input_window', type=int, default=100, help='滑动窗口长度')
    parser.add_argument('--model_path', default=None, help='模型路径，默认 Advanced/Models/{ts_code}.pth')
    parser.add_argument('--tushare_token', default=os.environ.get('TUSHARE_TOKEN', None), help='tushare token，可用环境变量 TUSHARE_TOKEN')
    args = parser.parse_args()

    df_res = predict(
        ts_token=args.tushare_token,
        ts_code=args.ts_code,
        start_date=args.start_date,
        end_date=args.end_date,
        model_path=args.model_path,
        input_window=args.input_window,
        predict_days=args.predict_days,
    )

    print(df_res.head())


if __name__ == '__main__':
    main()
