#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Split mixed ETF CSV by stock code and compute technical indicators.

Input format (example):
代码,日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率

Output format per stock (example: 000001.SZ.csv):
open,high,low,close,pre_close,change,pct_chg,vol,amount,
mtm_5,mtm_10,mtm_20,ma_5,ma_10,ma_20,ema_5,ema_10,ema_20,
tr,atr,u,d,au,ad,rs,rsi,ma_12,ma_26,ema_12,ema_26,dif,dif_ma_9,dea,volume_change_rate
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

REQUIRED_CN_COLUMNS = ["代码", "日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额"]

OUTPUT_COLUMNS = [
    "open",
    "high",
    "low",
    "close",
    "pre_close",
    "change",
    "pct_chg",
    "vol",
    "amount",
    "mtm_5",
    "mtm_10",
    "mtm_20",
    "ma_5",
    "ma_10",
    "ma_20",
    "ema_5",
    "ema_10",
    "ema_20",
    "tr",
    "atr",
    "u",
    "d",
    "au",
    "ad",
    "rs",
    "rsi",
    "ma_12",
    "ma_26",
    "ema_12",
    "ema_26",
    "dif",
    "dif_ma_9",
    "dea",
    "volume_change_rate",
]


def infer_exchange(code6: str) -> str:
    if code6.startswith(("8", "4")):
        return "BJ"
    if code6.startswith(("5", "6", "9")):
        return "SH"
    return "SZ"


def normalize_ts_code(raw_code: str) -> str:
    raw = str(raw_code).strip().upper()
    if "." in raw:
        left, right = raw.split(".", 1)
        left = left.zfill(6)
        suffix = right if right in {"SZ", "SH", "BJ"} else infer_exchange(left)
        return f"{left}.{suffix}"

    code6 = raw.zfill(6)
    return f"{code6}.{infer_exchange(code6)}"


def compute_indicators(df: pd.DataFrame, atr_n: int = 14, rsi_n: int = 14) -> pd.DataFrame:
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    vol = df["vol"].astype(float)

    df["mtm_5"] = close - close.shift(5)
    df["mtm_10"] = close - close.shift(10)
    df["mtm_20"] = close - close.shift(20)

    df["ma_5"] = close.rolling(window=5).mean()
    df["ma_10"] = close.rolling(window=10).mean()
    df["ma_20"] = close.rolling(window=20).mean()

    df["ema_5"] = close.ewm(span=5, adjust=False, min_periods=5).mean()
    df["ema_10"] = close.ewm(span=10, adjust=False, min_periods=10).mean()
    df["ema_20"] = close.ewm(span=20, adjust=False, min_periods=20).mean()

    prev_close = close.shift(1)
    hl = high - low
    hc_prev = (high - prev_close).abs()
    lc_prev = (low - prev_close).abs()
    df["tr"] = pd.concat([hl, hc_prev, lc_prev], axis=1).max(axis=1)
    df["atr"] = df["tr"].rolling(window=atr_n).mean()

    delta = close.diff()
    df["u"] = delta.clip(lower=0)
    df["d"] = (-delta).clip(lower=0)
    df["au"] = df["u"].ewm(alpha=1 / rsi_n, adjust=False, min_periods=rsi_n).mean()
    df["ad"] = df["d"].ewm(alpha=1 / rsi_n, adjust=False, min_periods=rsi_n).mean()
    df["rs"] = df["au"] / df["ad"].replace(0, np.nan)
    df["rsi"] = 100 * df["rs"] / (1 + df["rs"])

    df["ma_12"] = close.rolling(window=12).mean()
    df["ma_26"] = close.rolling(window=26).mean()
    df["ema_12"] = close.ewm(span=12, adjust=False, min_periods=12).mean()
    df["ema_26"] = close.ewm(span=26, adjust=False, min_periods=26).mean()
    df["dif"] = df["ema_12"] - df["ema_26"]
    df["dif_ma_9"] = df["dif"].rolling(window=9).mean()
    df["dea"] = df["dif"].ewm(span=9, adjust=False, min_periods=9).mean()

    df["volume_change_rate"] = vol.pct_change()

    indicator_cols = [c for c in OUTPUT_COLUMNS if c not in {"open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"}]
    df[indicator_cols] = df[indicator_cols].ffill()
    return df


def transform_one_stock(stock_df: pd.DataFrame, atr_n: int, rsi_n: int) -> pd.DataFrame:
    work = stock_df.copy()

    work["trade_date"] = pd.to_datetime(work["日期"], errors="coerce")
    work = work.dropna(subset=["trade_date"])
    work = work.sort_values("trade_date").drop_duplicates(subset=["trade_date"], keep="last").reset_index(drop=True)

    rename_map: Dict[str, str] = {
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "vol",
        "成交额": "amount",
        "涨跌额": "change",
        "涨跌幅": "pct_chg",
    }
    work = work.rename(columns=rename_map)

    for col in ["open", "close", "high", "low", "vol", "amount", "change", "pct_chg"]:
        if col in work.columns:
            work[col] = pd.to_numeric(work[col], errors="coerce")

    # Source file has no dedicated pre_close column, reconstruct from previous close.
    work["pre_close"] = work["close"].shift(1)

    # If change/pct_chg is missing in some rows, backfill by formula.
    missing_change = work["change"].isna() if "change" in work.columns else pd.Series(True, index=work.index)
    if "change" not in work.columns:
        work["change"] = np.nan
    work.loc[missing_change, "change"] = work["close"] - work["pre_close"]

    if "pct_chg" not in work.columns:
        work["pct_chg"] = np.nan
    missing_pct = work["pct_chg"].isna()
    denom = work["pre_close"].replace(0, np.nan)
    work.loc[missing_pct, "pct_chg"] = (work["change"] / denom) * 100

    work = compute_indicators(work, atr_n=atr_n, rsi_n=rsi_n)

    for col in OUTPUT_COLUMNS:
        if col not in work.columns:
            work[col] = np.nan

    return work[OUTPUT_COLUMNS]


def validate_columns(df: pd.DataFrame):
    missing = [col for col in REQUIRED_CN_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Input CSV missing required columns: {missing}")


def split_and_export(input_csv: Path, output_dir: Path, atr_n: int, rsi_n: int):
    df = pd.read_csv(input_csv, encoding="utf-8-sig")
    validate_columns(df)

    # Keep code as zero-padded string.
    df["代码"] = df["代码"].astype(str).str.strip().str.zfill(6)

    output_dir.mkdir(parents=True, exist_ok=True)

    grouped = df.groupby("代码", sort=True)
    total = 0
    for code, stock_df in grouped:
        ts_code = normalize_ts_code(code)
        out_df = transform_one_stock(stock_df, atr_n=atr_n, rsi_n=rsi_n)

        out_path = output_dir / f"{ts_code}.csv"
        out_df.to_csv(out_path, index=False, encoding="utf-8-sig")
        total += 1
        print(f"Saved: {out_path} ({len(out_df)} rows)")

    print(f"Done. Exported {total} stock files to: {output_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Split mixed ETF CSV and compute indicators per stock")
    parser.add_argument("--input", default="mid//etf_data.csv", help="Path to mixed CSV file")
    parser.add_argument("--output-dir", default="output_split", help="Directory to save per-stock CSV files")
    parser.add_argument("--atr-n", type=int, default=14, help="ATR window")
    parser.add_argument("--rsi-n", type=int, default=14, help="RSI window")
    return parser.parse_args()


def main():
    args = parse_args()
    input_csv = Path(args.input).resolve()
    output_dir = Path(args.output_dir).resolve()

    if not input_csv.exists():
        raise FileNotFoundError(f"Input file not found: {input_csv}")

    split_and_export(input_csv, output_dir, atr_n=args.atr_n, rsi_n=args.rsi_n)


if __name__ == "__main__":
    main()
