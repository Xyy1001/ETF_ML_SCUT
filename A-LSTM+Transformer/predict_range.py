#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
predict_range.py

根据用户输入的历史区间 a-b（格式 YYYYMMDD）作为模型输入数据量，基于 tushare 抓取对应股票数据，
然后预测并输出指定日期区间 c-d（交易日）的预测 close。

示例：
python predict_range.py --ts_code 000001.SZ --hist_start 20240101 --hist_end 20250101 --pred_start 20250102 --pred_end 20250115 --tushare_token YOUR_TOKEN

说明：
- 历史区间 a-b 将被用于准备输入。如果它包含的行数多于模型 input_window，则使用其最近的 input_window 行；
  如果少于 input_window，会自动填充（复制最后一行或填 0）以兼容模型（并打印警告）。
- 目标预测区间 c-d 会通过 tushare daily API 确认交易日，脚本将为这些交易日生成预测并打印到终端。
"""

import os
import argparse
import numpy as np
import pandas as pd
import torch
from datetime import datetime

try:
    import tushare as ts
except Exception:
    ts = None

try:
    from TrainingModel import preprocess_data, StockTimeSeriesDataset, MultiVariateLSTM_Transformer
except Exception:
    raise ImportError("请确保 predict_range.py 与 TrainingModel.py 位于同一目录，且 TrainingModel.py 可被导入")


def fetch_history(ts_token, ts_code, start_date, end_date):
    if ts is None:
        raise RuntimeError("tushare 未安装，请先 pip install tushare")
    ts.set_token(ts_token)
    pro = ts.pro_api()
    df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    if df is None or df.shape[0] == 0:
        raise ValueError(f"未获取到历史数据: {ts_code} {start_date}~{end_date}")
    df = df.sort_values('trade_date').reset_index(drop=True)
    return df


def fetch_pred_trading_dates(ts_token, ts_code, pred_start, pred_end):
    # 返回按升序排列的交易日 list（YYYYMMDD）
    if ts is None:
        raise RuntimeError("tushare 未安装，请先 pip install tushare")
    ts.set_token(ts_token)
    pro = ts.pro_api()
    df = pro.daily(ts_code=ts_code, start_date=pred_start, end_date=pred_end)
    if df is None or df.shape[0] == 0:
        raise ValueError(f"在预测区间未找到交易日: {pred_start}~{pred_end}")
    df = df.sort_values('trade_date').reset_index(drop=True)
    return df['trade_date'].tolist()


def infer_state_from_checkpoint(model_path):
    raw = torch.load(model_path, map_location='cpu')
    if isinstance(raw, dict) and ('state_dict' in raw or 'model_state_dict' in raw):
        state = raw.get('state_dict', raw.get('model_state_dict'))
    else:
        state = raw
    if not isinstance(state, dict):
        raise RuntimeError('无法解析 checkpoint 格式')
    # 推断 lstm input_size
    inferred_input_size = None
    inferred_output_window = None
    for k, v in state.items():
        if 'lstm.weight_ih_l0' in k:
            inferred_input_size = v.shape[1]
        if k.endswith('fc.weight') or k == 'fc.weight' or k.endswith('.fc.weight'):
            inferred_output_window = int(v.shape[0])
    return state, inferred_input_size, inferred_output_window


def predict_for_dates(ts_token, ts_code, hist_start, hist_end, pred_start, pred_end, model_path=None, input_window=100, device='cpu'):
    # 1) 检索历史与预测目标交易日
    hist_df = fetch_history(ts_token, ts_code, hist_start, hist_end)
    pred_dates = fetch_pred_trading_dates(ts_token, ts_code, pred_start, pred_end)
    n_pred = len(pred_dates)

    # 2) 预处理历史数据
    hist_proc = preprocess_data(hist_df.copy())

    # 3) 初始化 checkpoint 与模型
    if model_path is None:
        model_path = os.path.join(os.path.dirname(__file__), 'Models', f"{ts_code}.pth")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"模型文件不存在: {model_path}")

    state, inferred_input_size, inferred_output_window = infer_state_from_checkpoint(model_path)

    # 4) 准备最后一个滑窗作为输入
    ds = StockTimeSeriesDataset(hist_proc, input_window=input_window, output_window=1)
    if len(ds) == 0:
        raise ValueError('历史区间样本不足以构建输入窗口，请扩大历史区间')
    sample_input_scaled, _, _, target_scaler = ds[len(ds) - 1]
    input_np = sample_input_scaled.cpu().numpy()

    # 5) 判断并调整 input_size
    if inferred_input_size is None:
        inferred_input_size = input_np.shape[1]
    if input_np.shape[1] != inferred_input_size:
        print(f"警告: checkpoint input_size={inferred_input_size}, 样本 input_size={input_np.shape[1]}，将自动 pad/trim")
        if input_np.shape[1] < inferred_input_size:
            pad = inferred_input_size - input_np.shape[1]
            last_col = input_np[:, -1:].repeat(pad, axis=1) if input_np.shape[1] > 0 else np.zeros((input_np.shape[0], pad))
            input_np = np.concatenate([input_np, last_col], axis=1)
        else:
            input_np = input_np[:, :inferred_input_size]

    # 6) 构建模型
    model = MultiVariateLSTM_Transformer(
        input_size=inferred_input_size,
        lstm_hidden_size=64,
        lstm_layers=2,
        trans_layers=2,
        trans_heads=4,
        trans_ffn_hidden=128,
        dropout=0.1,
        output_size=1,
        output_window=(inferred_output_window or 20),
    )
    try:
        model.load_state_dict(state, strict=False)
    except Exception as e:
        print(f"加载 checkpoint 时发生异常（已忽略）：{e}")
    model.to(device).eval()

    # 7) 迭代生成 n_pred 个预测（按模型 output_window 分批）
    preds = []
    scaled_preds = []
    remaining = n_pred
    current_input = input_np.copy()
    with torch.no_grad():
        while remaining > 0:
            x = torch.FloatTensor(current_input).unsqueeze(0).to(device)
            out = model(x)  # (1, output_window, 1)
            out = out.squeeze(0).squeeze(-1).cpu().numpy()
            take = min(remaining, out.shape[0])
            part = out[:take]
            # 反标准化
            try:
                part_orig = target_scaler.inverse_transform(part.reshape(-1, 1)).flatten()
            except Exception:
                part_orig = part
            preds.extend(part_orig.tolist())
            scaled_preds.extend(part.tolist())

            # 更新 current_input（把预测 scaled 值 append 到 target 列，feature 部分复制最后一行）
            target_col = current_input[:, 0]
            feat = current_input[:, 1:]
            last_feat = feat[-1:, :] if feat.shape[0] > 0 else np.empty((1, 0))
            last_feat_rep = np.repeat(last_feat, take, axis=0) if last_feat.size else np.empty((take, 0))
            new_target = np.concatenate([target_col, part])
            new_feat = np.vstack([feat, last_feat_rep]) if last_feat_rep.size else np.empty((new_target.shape[0], 0))
            trimmed_target = new_target[-current_input.shape[0]:]
            trimmed_feat = new_feat[-current_input.shape[0]:, :] if new_feat.size else np.empty((current_input.shape[0], 0))
            current_input = np.column_stack([trimmed_target.reshape(-1, 1), trimmed_feat])

            remaining -= take

    # 8) 将预测结果与 pred_dates 对齐并打印到终端
    if len(preds) != n_pred:
        print(f"警告：生成的预测数量 {len(preds)} 与目标交易日数量 {n_pred} 不匹配")

    print(f"\n预测结果: {ts_code} 在 {pred_start}~{pred_end} 的预测 ({n_pred} 个交易日):")
    print("trade_date,pred_close,pred_scaled")
    for dt, p, sp in zip(pred_dates, preds, scaled_preds):
        print(f"{dt},{p},{sp}")

    return pd.DataFrame({'trade_date': pred_dates, 'pred_close': preds, 'pred_scaled': scaled_preds})



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ts_code', required=True)
    parser.add_argument('--hist_start', required=True)
    parser.add_argument('--hist_end', required=True)
    parser.add_argument('--pred_start', required=True)
    parser.add_argument('--pred_end', required=True)
    parser.add_argument('--model_path', default=None)
    parser.add_argument('--input_window', type=int, default=100)
    parser.add_argument('--tushare_token', default=os.environ.get('TUSHARE_TOKEN', None))
    args = parser.parse_args()

    df = predict_for_dates(
        ts_token=args.tushare_token,
        ts_code=args.ts_code,
        hist_start=args.hist_start,
        hist_end=args.hist_end,
        pred_start=args.pred_start,
        pred_end=args.pred_end,
        model_path=args.model_path,
        input_window=args.input_window,
    )

    # 可选：保存结果到 CSV 文件
    # 询问是否保存结果到 CSV 文件
    save_to_csv = input("是否保存结果到 CSV 文件？(y/n) ")
    if save_to_csv.lower() == 'y':
        # 保存到文件
        # 指定目录
        folder_path = "predictions" # 相对于终端目录下的路径
        os.makedirs(folder_path, exist_ok=True)
        # 保存到文件
        file_path = os.path.join(folder_path, f"{args.ts_code}_{args.pred_start}_{args.pred_end}.csv")
        df.to_csv(file_path, index=False)
        print(f"预测结果已保存到文件: {file_path}")
    else:
        print("预测结果已打印到终端，请自行保存到文件")


if __name__ == '__main__':
    main()
