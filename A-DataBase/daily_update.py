#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Daily incremental updater for stock daily bars and technical indicators.

What it does:
1. Connects to MySQL and TuShare.
2. Finds stock tables (e.g. 000001.SZ) or uses user-specified stock codes.
3. For each stock, fetches recent market data, recalculates indicators, and upserts rows.
4. Extends data to latest available date with one command.
"""

import argparse
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import pymysql
import tushare as ts
from dotenv import load_dotenv

RAW_COLUMNS = [
    "ts_code",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "pre_close",
    "change",
    "pct_chg",
    "vol",
    "amount",
]

FEATURE_COLUMNS = RAW_COLUMNS + [
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
    "macd",
    "volume_change_rate",
]

CODE_PATTERN = re.compile(r"^[0-9A-Z]{6}\.(SZ|SH|BJ)$")


def resolve_env_path(env_path: str) -> Path:
    """Resolve .env path robustly for both cwd launch and script-dir launch."""
    raw = Path(env_path)
    script_dir = Path(__file__).resolve().parent

    candidates = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.append((Path.cwd() / raw).resolve())
        candidates.append((script_dir / raw).resolve())

    # Common fallback when caller keeps default ".env".
    candidates.append((script_dir / ".env").resolve())

    for item in candidates:
        if item.exists():
            return item

    # Return a stable default path for error message.
    return (script_dir / raw.name).resolve() if raw.name else (script_dir / ".env").resolve()


def load_config(env_path: str) -> Dict[str, str]:
    resolved_env = resolve_env_path(env_path)
    if resolved_env.exists():
        load_dotenv(dotenv_path=resolved_env, override=True)
        print(f"Loaded .env: {resolved_env}")
    else:
        print(f"Warning: .env file not found at {resolved_env}, using defaults/env vars")

    cfg = {
        "host": os.getenv("host", "localhost"),
        "port": os.getenv("port", "3306"),
        "username": os.getenv("username", "root"),
        "password": os.getenv("password", ""),
        "database": os.getenv("database", "etf_scut"),
        "tushare_token": os.getenv("TUSHARE_TOKEN", ""),
    }
    if not cfg["tushare_token"]:
        raise ValueError("TUSHARE_TOKEN is missing. Please set it in .env")
    return cfg


def init_tushare(token: str):
    ts.set_token(token)
    return ts.pro_api()


def connect_mysql(cfg: Dict[str, str]):
    try:
        return pymysql.connect(
            host=cfg["host"],
            port=int(cfg["port"]),
            user=cfg["username"],
            password=cfg["password"],
            database=cfg["database"],
            charset="utf8mb4",
            autocommit=True,
        )
    except RuntimeError as exc:
        if "cryptography" in str(exc).lower():
            raise RuntimeError(
                "MySQL auth requires package 'cryptography'. Install it with: pip install cryptography"
            ) from exc
        raise


def normalize_codes(raw_codes: List[str]) -> List[str]:
    cleaned = []
    seen = set()
    for item in raw_codes:
        code = item.strip().upper()
        if not code:
            continue
        if not CODE_PATTERN.match(code):
            print(f"Skip invalid code: {code}")
            continue
        if code not in seen:
            seen.add(code)
            cleaned.append(code)
    return cleaned


def list_stock_tables(conn) -> List[str]:
    sql = """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = %s
    ORDER BY table_name
    """
    database_name = conn.db.decode("utf-8") if isinstance(conn.db, bytes) else conn.db

    tables: List[str] = []
    with conn.cursor() as cur:
        cur.execute(sql, (database_name,))
        for (table_name,) in cur.fetchall():
            if CODE_PATTERN.match(str(table_name).upper()):
                tables.append(str(table_name).upper())
    return tables


def get_last_trade_date(conn, table_name: str) -> Optional[datetime]:
    with conn.cursor() as cur:
        cur.execute(f"SELECT MAX(trade_date) FROM `{table_name}`")
        row = cur.fetchone()
        if not row or not row[0]:
            return None
        if isinstance(row[0], datetime):
            return row[0]
        return datetime.combine(row[0], datetime.min.time())


def fetch_daily_data(pro, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    df = pro.daily(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        fields=",".join(RAW_COLUMNS),
    )
    if df.empty:
        return df
    df = df.sort_values("trade_date").reset_index(drop=True)
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    return df


def calculate_indicators(df: pd.DataFrame, atr_n: int = 14, rsi_n: int = 14) -> pd.DataFrame:
    if df.empty:
        return df

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
    df["macd"] = 2 * (df["dif"] - df["dea"])

    df["volume_change_rate"] = vol.pct_change()
    return df


def ffill_indicators(df: pd.DataFrame) -> pd.DataFrame:
    indicator_cols = [c for c in FEATURE_COLUMNS if c not in RAW_COLUMNS]
    df[indicator_cols] = df[indicator_cols].ffill()
    return df


def to_sql_val(value):
    return None if pd.isna(value) else value


def upsert_rows(conn, table_name: str, df: pd.DataFrame) -> int:
    if df.empty:
        return 0

    sql = f"""
    INSERT INTO `{table_name}` (
        ts_code, trade_date, open, high, low, close, pre_close, change_value, pct_chg, vol, amount,
        mtm_5, mtm_10, mtm_20, ma_5, ma_10, ma_20,
        ema_5, ema_10, ema_20, tr, atr,
        u, d, au, ad, rs, rsi,
        ma_12, ma_26, ema_12, ema_26, dif, dif_ma_9, dea, macd,
        volume_change_rate
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s, %s,
        %s
    )
    ON DUPLICATE KEY UPDATE
        ts_code=VALUES(ts_code),
        open=VALUES(open), high=VALUES(high), low=VALUES(low), close=VALUES(close),
        pre_close=VALUES(pre_close), change_value=VALUES(change_value), pct_chg=VALUES(pct_chg),
        vol=VALUES(vol), amount=VALUES(amount),
        mtm_5=VALUES(mtm_5), mtm_10=VALUES(mtm_10), mtm_20=VALUES(mtm_20),
        ma_5=VALUES(ma_5), ma_10=VALUES(ma_10), ma_20=VALUES(ma_20),
        ema_5=VALUES(ema_5), ema_10=VALUES(ema_10), ema_20=VALUES(ema_20),
        tr=VALUES(tr), atr=VALUES(atr),
        u=VALUES(u), d=VALUES(d), au=VALUES(au), ad=VALUES(ad), rs=VALUES(rs), rsi=VALUES(rsi),
        ma_12=VALUES(ma_12), ma_26=VALUES(ma_26), ema_12=VALUES(ema_12), ema_26=VALUES(ema_26),
        dif=VALUES(dif), dif_ma_9=VALUES(dif_ma_9), dea=VALUES(dea), macd=VALUES(macd),
        volume_change_rate=VALUES(volume_change_rate),
        updated_at=CURRENT_TIMESTAMP
    """

    rows = []
    for item in df.itertuples(index=False):
        rows.append(
            (
                to_sql_val(item.ts_code),
                to_sql_val(item.trade_date.date() if hasattr(item.trade_date, "date") else item.trade_date),
                to_sql_val(item.open),
                to_sql_val(item.high),
                to_sql_val(item.low),
                to_sql_val(item.close),
                to_sql_val(item.pre_close),
                to_sql_val(item.change),
                to_sql_val(item.pct_chg),
                to_sql_val(item.vol),
                to_sql_val(item.amount),
                to_sql_val(item.mtm_5),
                to_sql_val(item.mtm_10),
                to_sql_val(item.mtm_20),
                to_sql_val(item.ma_5),
                to_sql_val(item.ma_10),
                to_sql_val(item.ma_20),
                to_sql_val(item.ema_5),
                to_sql_val(item.ema_10),
                to_sql_val(item.ema_20),
                to_sql_val(item.tr),
                to_sql_val(item.atr),
                to_sql_val(item.u),
                to_sql_val(item.d),
                to_sql_val(item.au),
                to_sql_val(item.ad),
                to_sql_val(item.rs),
                to_sql_val(item.rsi),
                to_sql_val(item.ma_12),
                to_sql_val(item.ma_26),
                to_sql_val(item.ema_12),
                to_sql_val(item.ema_26),
                to_sql_val(item.dif),
                to_sql_val(item.dif_ma_9),
                to_sql_val(item.dea),
                to_sql_val(item.macd),
                to_sql_val(item.volume_change_rate),
            )
        )

    with conn.cursor() as cur:
        cur.executemany(sql, rows)

    return len(rows)


def update_one_stock(
    conn,
    pro,
    ts_code: str,
    lookback_days: int,
    default_start_date: str,
    end_date: str,
) -> int:
    last_trade_date = get_last_trade_date(conn, ts_code)

    if last_trade_date is None:
        start_date = default_start_date
    else:
        recompute_start = last_trade_date - timedelta(days=lookback_days)
        start_date = recompute_start.strftime("%Y%m%d")

    raw_df = fetch_daily_data(pro=pro, ts_code=ts_code, start_date=start_date, end_date=end_date)
    if raw_df.empty:
        print(f"[{ts_code}] No rows returned from TuShare in {start_date}~{end_date}")
        return 0

    feature_df = calculate_indicators(raw_df.copy())
    feature_df = ffill_indicators(feature_df)
    feature_df = feature_df[FEATURE_COLUMNS]

    affected = upsert_rows(conn, ts_code, feature_df)
    last_date = feature_df["trade_date"].max().strftime("%Y-%m-%d")
    print(f"[{ts_code}] upserted {affected} rows (latest: {last_date})")
    return affected


def parse_args():
    parser = argparse.ArgumentParser(
        description="Incrementally update stock daily data and indicators.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python daily_update.py --env-path .env
  python daily_update.py --env-path .env --codes 000001.SZ,000002.SZ
  python daily_update.py --env-path .env --lookback-days 120
        """,
    )
    parser.add_argument(
        "--env-path",
        default=".env",
        help="Path to .env (supports absolute/relative; defaults to smart lookup)",
    )
    parser.add_argument(
        "--codes",
        default="",
        help="Comma-separated ts_code list. If omitted, all stock tables are updated.",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=120,
        help="Recompute window in days before the latest date in DB (default: 120)",
    )
    parser.add_argument(
        "--default-start-date",
        default="20100101",
        help="Start date when table has no data (default: 20100101)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        cfg = load_config(args.env_path)
    except ValueError as exc:
        print(f"Config error: {exc}")
        sys.exit(1)

    end_date = datetime.now().strftime("%Y%m%d")
    pro = init_tushare(cfg["tushare_token"])
    try:
        conn = connect_mysql(cfg)
    except Exception as exc:
        print(f"MySQL connection failed: {exc}")
        sys.exit(1)

    try:
        if args.codes.strip():
            stock_codes = normalize_codes(args.codes.split(","))
        else:
            stock_codes = list_stock_tables(conn)

        if not stock_codes:
            print("No stock tables/codes found to update.")
            return

        print("=" * 72)
        print("Daily Stock Data Incremental Updater")
        print(f"Database   : {cfg['database']} @ {cfg['host']}:{cfg['port']}")
        print(f"End date   : {end_date}")
        print(f"Lookback   : {args.lookback_days} days")
        print(f"Stock count: {len(stock_codes)}")
        print("=" * 72)

        total_rows = 0
        for ts_code in stock_codes:
            total_rows += update_one_stock(
                conn=conn,
                pro=pro,
                ts_code=ts_code,
                lookback_days=args.lookback_days,
                default_start_date=args.default_start_date,
                end_date=end_date,
            )

        print("=" * 72)
        print(f"Done. Total upserted rows: {total_rows}")
        print("=" * 72)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
