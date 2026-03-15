"""
股票数据预处理与入库脚本

功能：
1. 从 TuShare 拉取单只股票 2010-01-01 至今的原始日线数据
2. 计算后续环节需要的技术指标
3. 对指标缺失值执行向后填充（bfill）
4. 保存原始数据 CSV 和最终特征数据 CSV
5. 将最终特征表写入 MySQL 数据库

支持两种输入模式：
1) 单只输入：每次处理一只，完成后由用户决定是否继续
2) 批量输入：一次输入多只，逗号分隔，统一处理
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List

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


def load_config() -> Dict[str, str]:
    load_dotenv(dotenv_path=".env")
    config = {
        "tushare_token": os.getenv("TUSHARE_TOKEN", ""),
        "host": os.getenv("host", "localhost"),
        "port": os.getenv("port", "3306"),
        "username": os.getenv("username", "root"),
        "password": os.getenv("password", ""),
        "database": os.getenv("database", "etf_scut"),
    }
    if not config["tushare_token"]:
        raise ValueError("未在 .env 中读取到 TUSHARE_TOKEN")
    return config


def init_tushare(token: str):
    ts.set_token(token)
    return ts.pro_api()


def normalize_codes(codes: List[str]) -> List[str]:
    normalized = []
    for code in codes:
        item = code.strip().upper()
        if item:
            normalized.append(item)
    return normalized


def get_stock_codes() -> List[str]:
    print("\n请选择股票输入方式：")
    print("1 - 单只依次输入（每处理一只可决定是否继续）")
    print("2 - 一次输入多只（逗号分隔）")
    mode = input("请输入模式（1/2）: ").strip()

    if mode == "1":
        codes = []
        while True:
            code = input("请输入单只股票代码（示例: 000001.SZ）: ").strip().upper()
            if code:
                codes.append(code)
            cont = input("是否继续输入下一只？(y/n): ").strip().lower()
            if cont not in {"y", "yes"}:
                break
        return normalize_codes(codes)

    raw = input("请输入多个股票代码，逗号分隔: ")
    return normalize_codes(raw.split(","))


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


def backfill_indicators(df: pd.DataFrame) -> pd.DataFrame:
    indicator_cols = [col for col in FEATURE_COLUMNS if col not in RAW_COLUMNS]
    df[indicator_cols] = df[indicator_cols].bfill()
    return df


def ensure_local_dirs() -> Dict[str, Path]:
    base = Path("A-DataBase") / "output"
    raw_dir = base / "raw"
    feature_dir = base / "features"
    raw_dir.mkdir(parents=True, exist_ok=True)
    feature_dir.mkdir(parents=True, exist_ok=True)
    return {"raw": raw_dir, "feature": feature_dir}


def save_csv(df_raw: pd.DataFrame, df_feature: pd.DataFrame, ts_code: str, paths: Dict[str, Path]):
    raw_file = paths["raw"] / f"{ts_code}_raw.csv"
    feature_file = paths["feature"] / f"{ts_code}_features.csv"
    df_raw.to_csv(raw_file, index=False, encoding="utf-8-sig")
    df_feature.to_csv(feature_file, index=False, encoding="utf-8-sig")


def get_mysql_conn(config: Dict[str, str]):
    return pymysql.connect(
        host=config["host"],
        port=int(config["port"]),
        user=config["username"],
        password=config["password"],
        database=config["database"],
        charset="utf8mb4",
        autocommit=True,
    )


def ensure_feature_table(conn):
    sql = """
    CREATE TABLE IF NOT EXISTS stock_feature_data (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        ts_code VARCHAR(16) NOT NULL,
        trade_date DATE NOT NULL,
        open DECIMAL(12,4),
        high DECIMAL(12,4),
        low DECIMAL(12,4),
        close DECIMAL(12,4),
        pre_close DECIMAL(12,4),
        change_value DECIMAL(12,4),
        pct_chg DECIMAL(10,4),
        vol DECIMAL(20,4),
        amount DECIMAL(20,4),
        mtm_5 DECIMAL(12,6),
        mtm_10 DECIMAL(12,6),
        mtm_20 DECIMAL(12,6),
        ma_5 DECIMAL(12,6),
        ma_10 DECIMAL(12,6),
        ma_20 DECIMAL(12,6),
        ema_5 DECIMAL(12,6),
        ema_10 DECIMAL(12,6),
        ema_20 DECIMAL(12,6),
        tr DECIMAL(12,6),
        atr DECIMAL(12,6),
        u DECIMAL(12,6),
        d DECIMAL(12,6),
        au DECIMAL(12,6),
        ad DECIMAL(12,6),
        rs DECIMAL(12,6),
        rsi DECIMAL(12,6),
        ma_12 DECIMAL(12,6),
        ma_26 DECIMAL(12,6),
        ema_12 DECIMAL(12,6),
        ema_26 DECIMAL(12,6),
        dif DECIMAL(12,6),
        dif_ma_9 DECIMAL(12,6),
        dea DECIMAL(12,6),
        macd DECIMAL(12,6),
        volume_change_rate DECIMAL(12,6),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY unique_code_date (ts_code, trade_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    with conn.cursor() as cursor:
        cursor.execute(sql)


def save_to_db(conn, df: pd.DataFrame):
    sql = """
    INSERT INTO stock_feature_data (
        ts_code, trade_date, open, high, low, close, pre_close, change_value, pct_chg, vol, amount,
        mtm_5, mtm_10, mtm_20, ma_5, ma_10, ma_20, ema_5, ema_10, ema_20,
        tr, atr, u, d, au, ad, rs, rsi, ma_12, ma_26, ema_12, ema_26,
        dif, dif_ma_9, dea, macd, volume_change_rate
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s
    ) ON DUPLICATE KEY UPDATE
        open=VALUES(open), high=VALUES(high), low=VALUES(low), close=VALUES(close),
        pre_close=VALUES(pre_close), change_value=VALUES(change_value), pct_chg=VALUES(pct_chg),
        vol=VALUES(vol), amount=VALUES(amount),
        mtm_5=VALUES(mtm_5), mtm_10=VALUES(mtm_10), mtm_20=VALUES(mtm_20),
        ma_5=VALUES(ma_5), ma_10=VALUES(ma_10), ma_20=VALUES(ma_20),
        ema_5=VALUES(ema_5), ema_10=VALUES(ema_10), ema_20=VALUES(ema_20),
        tr=VALUES(tr), atr=VALUES(atr), u=VALUES(u), d=VALUES(d), au=VALUES(au), ad=VALUES(ad),
        rs=VALUES(rs), rsi=VALUES(rsi), ma_12=VALUES(ma_12), ma_26=VALUES(ma_26),
        ema_12=VALUES(ema_12), ema_26=VALUES(ema_26), dif=VALUES(dif),
        dif_ma_9=VALUES(dif_ma_9), dea=VALUES(dea), macd=VALUES(macd),
        volume_change_rate=VALUES(volume_change_rate), updated_at=CURRENT_TIMESTAMP
    """

    records = []
    for row in df.itertuples(index=False):
        records.append(
            (
                row.ts_code,
                row.trade_date.date() if hasattr(row.trade_date, "date") else row.trade_date,
                row.open,
                row.high,
                row.low,
                row.close,
                row.pre_close,
                row.change,
                row.pct_chg,
                row.vol,
                row.amount,
                row.mtm_5,
                row.mtm_10,
                row.mtm_20,
                row.ma_5,
                row.ma_10,
                row.ma_20,
                row.ema_5,
                row.ema_10,
                row.ema_20,
                row.tr,
                row.atr,
                row.u,
                row.d,
                row.au,
                row.ad,
                row.rs,
                row.rsi,
                row.ma_12,
                row.ma_26,
                row.ema_12,
                row.ema_26,
                row.dif,
                row.dif_ma_9,
                row.dea,
                row.macd,
                row.volume_change_rate,
            )
        )

    with conn.cursor() as cursor:
        cursor.executemany(sql, records)


def process_one_stock(pro, conn, ts_code: str, start_date: str, end_date: str, paths: Dict[str, Path]):
    print(f"\n开始处理: {ts_code}")
    raw_df = fetch_daily_data(pro, ts_code=ts_code, start_date=start_date, end_date=end_date)
    if raw_df.empty:
        print(f"{ts_code} 未拉取到数据，已跳过")
        return

    feature_df = calculate_indicators(raw_df.copy())
    feature_df = backfill_indicators(feature_df)
    feature_df = feature_df[FEATURE_COLUMNS]

    save_csv(raw_df, feature_df, ts_code, paths)
    save_to_db(conn, feature_df)
    print(f"{ts_code} 处理完成: 原始数据 {len(raw_df)} 行，特征数据 {len(feature_df)} 行")


def main():
    config = load_config()
    pro = init_tushare(config["tushare_token"])
    codes = get_stock_codes()
    if not codes:
        print("未输入有效股票代码，程序结束")
        return

    start_date = "20100101"
    end_date = datetime.now().strftime("%Y%m%d")
    print(f"拉取区间: {start_date} ~ {end_date}")
    print(f"待处理股票数: {len(codes)}")

    paths = ensure_local_dirs()
    conn = get_mysql_conn(config)

    try:
        ensure_feature_table(conn)
        for ts_code in codes:
            process_one_stock(
                pro=pro,
                conn=conn,
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                paths=paths,
            )
    finally:
        conn.close()

    print("\n全部处理完成")


if __name__ == "__main__":
    main()