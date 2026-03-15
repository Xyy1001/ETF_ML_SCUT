import os
import re
import argparse
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
plt.rc("font",family='YouYuan')

def discover_tickers(returns_dir: str) -> List[str]:
    # 发现股票池：扫描收益目录中的 CSV 文件，按文件名解析股票代码（如 000001.SZ_...）
    tickers = []
    for name in os.listdir(returns_dir):
        # 仅处理预测结果 CSV 文件
        if name.endswith('.csv'):
            base = os.path.splitext(name)[0]
            # file pattern like: 000001.SZ_20250602_20251105
            code = base.split('_')[0]
            tickers.append(code)
    tickers = sorted(set(tickers))
    return tickers


def load_pred_close(returns_dir: str, tickers: List[str]) -> pd.DataFrame:
    # 读取并合并各股票的预测收盘价；日期列优先匹配 trade_date/pred_date，预测价列优先匹配 pred_close/pred_mean10
    frames = []
    for t in tickers:
        files = [f for f in os.listdir(returns_dir) if f.startswith(t) and f.lower().endswith('.csv')]
        if not files:
            continue
        path = os.path.join(returns_dir, files[0])
        df = pd.read_csv(path)
        # 清理列名中的空白字符
        cols = [c.strip() if isinstance(c, str) else c for c in df.columns]
        df.columns = cols
        date_candidates = ['trade_date', 'pred_date', 'date', '日期', '交易日期']
        price_candidates = ['pred_close', 'pred_mean10']
        date_col = next((c for c in date_candidates if c in df.columns), None)
        price_col = next((c for c in price_candidates if c in df.columns), None)
        if date_col is None:
            date_col = df.columns[0]
        if price_col is None:
            if len(df.columns) < 2:
                raise ValueError(f'文件 {path} 至少需要两列以识别日期与预测价格')
            price_col = df.columns[1]
        # 统一列名并仅保留日期与预测价两列
        df = df[[date_col, price_col]].copy()
        df.rename(columns={date_col: 'trade_date', price_col: t}, inplace=True)
        df['trade_date'] = df['trade_date'].astype(str)
        frames.append(df)
    if not frames:
        raise RuntimeError('未在收益结果目录中找到任何 CSV 文件')
    out = frames[0]
    for df in frames[1:]:
        # 按日期外连接，保证覆盖所有交易日
        out = pd.merge(out, df, on='trade_date', how='outer')
    out.sort_values('trade_date', inplace=True)
    out.reset_index(drop=True, inplace=True)
    return out


def load_actual_close(actual_dir: Optional[str], tickers: List[str]) -> Optional[pd.DataFrame]:
    if not actual_dir or not os.path.isdir(actual_dir):
        return None
    frames = []
    for t in tickers:
        # 支持文件名：000001.SZ.csv 或 000001_SZ.xlsx/xls（按前缀匹配）
        prefixes = [t, t.replace('.', '_')]
        candidates = []
        for name in os.listdir(actual_dir):
            lower = name.lower()
            if any(name.startswith(p) for p in prefixes) and (lower.endswith('.csv') or lower.endswith('.xlsx') or lower.endswith('.xls')):
                candidates.append(name)
        if not candidates:
            continue
        path = os.path.join(actual_dir, candidates[0])
        ext = os.path.splitext(path)[1].lower()
        if ext == '.csv':
            df = pd.read_csv(path)
        else:
            try:
                df = pd.read_excel(path, engine='openpyxl')
            except Exception:
                df = pd.read_excel(path)
        # 智能匹配日期/收盘列名并标准化
        cols = [c.strip() if isinstance(c, str) else c for c in df.columns]
        df.columns = cols
        date_candidates = ['trade_date', 'date', '日期', '交易日期']
        close_candidates = ['close', '收盘', '收盘价', 'Close', 'Adj Close', 'adj_close']
        date_col = next((c for c in date_candidates if c in df.columns), None)
        close_col = next((c for c in close_candidates if c in df.columns), None)
        if date_col is None or close_col is None:
            raise ValueError(f'文件 {path} 未找到日期/收盘列，现有列: {list(df.columns)}')
        df = df[[date_col, close_col]].copy()
        df.rename(columns={date_col: 'trade_date', close_col: t}, inplace=True)
        df['trade_date'] = df['trade_date'].astype(str)
        frames.append(df)
    if not frames:
        return None
    out = frames[0]
    for df in frames[1:]:
        out = pd.merge(out, df, on='trade_date', how='outer')
    out.sort_values('trade_date', inplace=True)
    out.reset_index(drop=True, inplace=True)
    return out


def compute_expected_log_returns(
    pred_close_df: pd.DataFrame,
    actual_close_df: Optional[pd.DataFrame]
) -> pd.DataFrame:
    # 计算预期对数收益率 μ：
    # 有真实价：μ_t = log(pred_close_t / actual_close_{t-1})；否则回退为 log(pred_close_t / pred_close_{t-1})
    dates = pred_close_df['trade_date']
    tickers = [c for c in pred_close_df.columns if c != 'trade_date']
    mu = pd.DataFrame({'trade_date': dates})
    if actual_close_df is not None:
        # 将真实收盘价按前一交易日对齐到当前日期
        act = actual_close_df.copy()
        act_shift = act.copy()
        act_shift[tickers] = act_shift[tickers].shift(1)
        act_shift.rename(columns={c: f'prev_{c}' for c in tickers}, inplace=True)
        merged = pd.merge(pred_close_df, act_shift, on='trade_date', how='left')
        for t in tickers:
            prev_col = f'prev_{t}'
            mu[t] = np.log(merged[t] / merged[prev_col])
    else:
        # 无真实价时，使用前一日预测价计算对数收益
        pred_shift = pred_close_df.copy()
        pred_shift[tickers] = pred_shift[tickers].shift(1)
        for t in tickers:
            mu[t] = np.log(pred_close_df[t] / pred_shift[t])
    # 将无效值置为 NaN 以便后续处理
    mu.replace([np.inf, -np.inf], np.nan, inplace=True)
    return mu


def parse_total_steps_from_report(report_path: str) -> Optional[int]:
    # 从评估报告中解析“保存的风险矩阵总步数”，用于与实际矩阵步数核对
    if not os.path.isfile(report_path):
        return None
    text = open(report_path, 'r', encoding='utf-8', errors='ignore').read()
    m = re.search(r'Total predicted matrices saved:\s*(\d+)', text)
    if m:
        return int(m.group(1))
    return None


def load_risk_matrices(risk_dir: str) -> np.ndarray:
    # 加载风险协方差矩阵并按说明文档除以 10000 还原尺度；确保形状为 (时间×股票×股票)
    npy_path = os.path.join(risk_dir, 'predicted_covariance_matrices.npy')
    arr = np.load(npy_path)
    # Rescale according to doc: values are 10000x; divide by 10000
    arr = arr / 10000.0
    # Ensure shape is (T, N, N)
    if arr.ndim == 3:
        if arr.shape[1] == arr.shape[2]:
            # assume first dim is time
            return arr
        elif arr.shape[0] == arr.shape[1]:
            # time might be last dim -> transpose axes
            return np.transpose(arr, (2, 0, 1))
    raise ValueError(f'无法识别风险矩阵形状: {arr.shape}')


def read_tickers_order(mapping_path: str) -> Optional[List[str]]:
    # 读取风险矩阵股票顺序映射文件（每行一个代码），用于从 26×26 矩阵中抽取子矩阵
    if not os.path.isfile(mapping_path):
        return None
    lines = [ln.strip() for ln in open(mapping_path, 'r', encoding='utf-8') if ln.strip()]
    return lines if lines else None


def subset_sigma_for_tickers(
    sigma_t: np.ndarray,
    tickers_order: Optional[List[str]],
    target_tickers: List[str]
) -> np.ndarray:
    # 从当期风险矩阵中按股票代码顺序抽取目标股票池的子协方差矩阵；
    # 若未提供映射且目标数等于矩阵维度，则直接使用原矩阵；否则用对角均值近似风险
    n_all = sigma_t.shape[0]
    if tickers_order is None:
        if len(target_tickers) == n_all:
            return sigma_t
        avg_var = float(np.nanmean(np.diag(sigma_t))) if sigma_t.size else 1.0
        n = len(target_tickers)
        return np.eye(n) * (avg_var if np.isfinite(avg_var) and avg_var > 0 else 1.0)
    index_map = {sym: i for i, sym in enumerate(tickers_order)}
    idx = []
    for t in target_tickers:
        if t not in index_map:
            raise ValueError(f'映射文件缺少股票代码 {t}，无法提取子矩阵')
        idx.append(index_map[t])
    sub = sigma_t[np.ix_(idx, idx)]
    return sub


def solve_markowitz_weights(mu_vec: np.ndarray, sigma: np.ndarray, gamma: float = 1.0) -> np.ndarray:
    # 均值-方差（Markowitz）权重求解：
    # 在约束 sum(w)=1 下构造 KKT 线性系统并求解；
    # 对角加入微小正则提升稳定性，失败时回退等权；
    # 最后对权重做非负投影并归一化到单纯形
    n = mu_vec.shape[0]
    # regularize
    eps = 1e-8
    sigma = sigma.copy()
    sigma[np.diag_indices(n)] += eps
    # KKT system
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
    # Optional clamp negatives then renormalize to simplex
    w = np.maximum(w, 0)
    s = w.sum()
    if s <= 0:
        w = np.ones(n) / n
    else:
        w = w / s
    return w


def main():
    # 命令行入口：解析参数并按流程执行数据读取、收益与风险计算、权重优化、回测与输出
    parser = argparse.ArgumentParser(description='基于说明文档的马科维茨投资决策')
    parser.add_argument('--returns_dir', default=os.path.join(os.getcwd(), '26个股票预测结果'), help='收益结果目录')
    parser.add_argument('--risk_dir', default=os.path.join(os.getcwd(), 'results（risk）'), help='风险结果目录')
    parser.add_argument('--actual_dir', default=os.path.join(os.getcwd(), '回测数据1'), help='实际收盘价目录（可选），文件名形如 000001.SZ.csv 或 000001_SZ.xlsx，列含 日期/收盘')
    parser.add_argument('--mapping_path', default=None, help='风险矩阵 26 支股票的顺序映射文件，每行一个股票代码')
    parser.add_argument('--gamma', type=float, default=1.0, help='风险厌恶系数 gamma，越大越保守')
    parser.add_argument('--out_dir', default=os.path.join(os.getcwd(), 'portfolio_results'), help='输出目录')
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    # Discover tickers and load predicted closes
    # 识别股票代码并合并预测收盘价
    tickers = discover_tickers(args.returns_dir)
    if not tickers:
        raise RuntimeError('收益结果目录未发现任何股票 CSV 文件')
    pred_close_df = load_pred_close(args.returns_dir, tickers)

    # Load actual closes if provided and compute expected log returns
    # 读取真实收盘价（如提供）并计算预期对数收益率 μ
    actual_df = load_actual_close(args.actual_dir, tickers)
    mu_df = compute_expected_log_returns(pred_close_df, actual_df)

    # Load risk matrices
    # 加载风险矩阵并校验与报告步数一致性（仅提示不一致）
    risk_arr = load_risk_matrices(args.risk_dir)
    steps = risk_arr.shape[0]
    # Try to read total steps from report for alignment
    total_steps = parse_total_steps_from_report(os.path.join(args.risk_dir, 'evaluation_report.txt'))
    if total_steps and total_steps != steps:
        print(f'警告：风险矩阵步数 {steps} 与报告中的 {total_steps} 不一致')

    # Build mapping
    tickers_order = None
    if args.mapping_path:
        tickers_order = read_tickers_order(args.mapping_path)

    # Align dates: use the first `steps` rows of mu_df if it is longer
    # 将收益与风险的时间长度对齐为较短者，避免外推
    available_steps = min(steps, len(mu_df))
    mu_df = mu_df.iloc[:available_steps].copy()
    risk_arr = risk_arr[:available_steps]

    # Solve weights for each date
    # 逐日根据 μ 与子协方差矩阵求解最优权重并记录
    weight_rows = []
    for i in range(available_steps):
        date = mu_df['trade_date'].iloc[i]
        mu_row = mu_df.iloc[i][tickers].astype(float).values
        sigma_t = risk_arr[i]
        sigma_sub = subset_sigma_for_tickers(sigma_t, tickers_order, tickers)
        w = solve_markowitz_weights(mu_row, sigma_sub, gamma=args.gamma)
        row = {'trade_date': date}
        for j, t in enumerate(tickers):
            row[t] = float(w[j])
        weight_rows.append(row)

    weights_df = pd.DataFrame(weight_rows)
    weights_path = os.path.join(args.out_dir, 'weights.csv')
    weights_df.to_csv(weights_path, index=False, encoding='utf-8')

    # Save a brief notes file
    # 输出简要说明文件，记录关键口径与结果位置
    notes_path = os.path.join(args.out_dir, 'README.txt')
    with open(notes_path, 'w', encoding='utf-8') as f:
        f.write('说明:\n')
        f.write('- 风险矩阵按说明文档除以 10000 进行还原。\n')
        f.write('- 预期收益使用对数收益率：有实际收盘价时用实际前一日收盘价；否则回退为使用前一日预测收盘价。\n')
        f.write(f'- 股票池: {", ".join(tickers)}\n')
        f.write('- 优化方法：带等权约束的均值-方差（KKT 问题解），再投影到非负并归一化。\n')
        f.write('- 如未提供风险矩阵股票顺序映射文件，则用对角均值作为近似风险。\n')
        f.write(f'- 输出文件: {weights_path}\n')

    print(f'已生成权重文件: {weights_path}')

    # 回测：如有真实价格则优先使用真实价，否则用预测价
    run_backtest(pred_close_df, weights_df, args.out_dir, actual_df)

def run_backtest(pred_close_df: pd.DataFrame, weights_df: pd.DataFrame, out_dir: str, actual_close_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    # 回测：使用真实价（优先）或预测价计算每日组合收益与净值，并输出指标与图形
    tickers_bt = [c for c in weights_df.columns if c != 'trade_date']
    base_df = actual_close_df if actual_close_df is not None else pred_close_df
    prices = base_df[['trade_date'] + tickers_bt].copy()
    for t in tickers_bt:
        if t not in prices.columns:
            raise ValueError(f'收益数据缺少股票 {t}')
    prices[tickers_bt] = prices[tickers_bt].astype(float)
    rets = prices[['trade_date']].copy()
    for t in tickers_bt:
        # 个股日对数收益
        rets[t + '_ret'] = np.log(prices[t] / prices[t].shift(1))
    w = weights_df[['trade_date']].copy()
    for t in tickers_bt:
        w[t + '_w'] = weights_df[t]
    merged = pd.merge(rets, w, on='trade_date', how='inner')
    port_log = []
    dates_bt = merged['trade_date'].tolist()
    for i in range(len(merged)):
        r = merged[[t + '_ret' for t in tickers_bt]].iloc[i].astype(float).values
        ww = merged[[t + '_w' for t in tickers_bt]].iloc[i].astype(float).values
        r = np.nan_to_num(r, nan=0.0, posinf=0.0, neginf=0.0)
        ww = np.nan_to_num(ww, nan=0.0, posinf=0.0, neginf=0.0)
        s = ww.sum()
        if s > 0:
            # 每日归一化权重，确保权重和为 1
            ww = ww / s
        port_log.append(float(np.dot(ww, r)))
    nav = []
    acc = 1.0
    for v in port_log:
        # 净值按对数收益累乘
        acc *= float(np.exp(v))
        nav.append(acc)
    out = pd.DataFrame({
        'trade_date': dates_bt,
        'port_ret_log': port_log,
        'port_ret_arith': [float(np.exp(v) - 1.0) for v in port_log],
        'nav': nav,
    })
    out_path = os.path.join(out_dir, 'backtest.csv')
    out.to_csv(out_path, index=False, encoding='utf-8')
    nav_arr = np.array(nav, dtype=float)
    if nav_arr.size:
        peak = np.maximum.accumulate(nav_arr)
        drawdown = (nav_arr - peak) / peak
        mdd = float(np.min(drawdown)) if drawdown.size else 0.0
        mean_log = float(np.nanmean(port_log)) if port_log else 0.0
        vol_log = float(np.nanstd(port_log, ddof=1)) if len(port_log) > 1 else 0.0
        ann_ret = float(np.exp(mean_log * 252) - 1.0)
        ann_vol = float(vol_log * np.sqrt(252))
        met_path = os.path.join(out_dir, 'backtest_metrics.txt')
        with open(met_path, 'w', encoding='utf-8') as f:
            f.write(f'样本期累计收益: {nav_arr[-1] - 1.0}\n')
            f.write(f'年化收益(基于日对数): {ann_ret}\n')
            f.write(f'年化波动(基于日对数): {ann_vol}\n')
            f.write(f'最大回撤: {mdd}\n')
        try:
            plot_df = out.copy()
            plot_df['trade_date'] = pd.to_datetime(plot_df['trade_date'])
            fig = plt.figure(figsize=(10, 4))
            plt.plot(plot_df['trade_date'], plot_df['port_ret_arith'], color='steelblue')
            plt.title('每日组合算术收益率')
            plt.xlabel('日期')
            plt.ylabel('收益率')
            plt.grid(True, alpha=0.3)
            ret_path = os.path.join(out_dir, 'backtest_returns.png')
            plt.tight_layout()
            plt.savefig(ret_path, dpi=120)
            plt.close(fig)
            fig2 = plt.figure(figsize=(10, 4))
            plt.plot(plot_df['trade_date'], plot_df['nav'], color='darkorange')
            plt.title('组合净值')
            plt.xlabel('日期')
            plt.ylabel('净值')
            plt.grid(True, alpha=0.3)
            nav_path = os.path.join(out_dir, 'backtest_nav.png')
            plt.tight_layout()
            plt.savefig(nav_path, dpi=120)
            plt.close(fig2)
            fig3 = plt.figure(figsize=(10, 4))
            plt.plot(plot_df['trade_date'], plot_df['nav'] - 1.0, color='seagreen')
            plt.title('累计收益率')
            plt.xlabel('日期')
            plt.ylabel('累计收益率')
            plt.grid(True, alpha=0.3)
            cumret_path = os.path.join(out_dir, 'backtest_cumret.png')
            plt.tight_layout()
            plt.savefig(cumret_path, dpi=120)
            plt.close(fig3)
        except Exception as e:
            try:
                err_path = os.path.join(out_dir, 'plot_error.txt')
                with open(err_path, 'w', encoding='utf-8') as fe:
                    fe.write(str(e))
            except Exception:
                pass
    return out


if __name__ == '__main__':
    main()
