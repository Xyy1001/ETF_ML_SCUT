#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Background service: auto-check and incrementally update stock daily data.

This module is designed for G-Web runtime integration.
When enabled, it periodically:
1. Loads DB and Tushare config from .env
2. Checks stock tables in DB
3. Pulls latest daily bars from Tushare
4. Recomputes indicators on rolling window and upserts into DB
"""

from __future__ import annotations

import os
import re
import threading
import time
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


class DailyUpdater:
    def __init__(self, config: Dict[str, str]):
        self.config = config
        self._pro = None

    def init_tushare(self):
        token = self.config.get("tushare_token", "")
        if not token:
            raise ValueError("TUSHARE_TOKEN is missing in .env")
        ts.set_token(token)
        self._pro = ts.pro_api()

    def connect_mysql(self):
        return pymysql.connect(
            host=self.config["host"],
            port=int(self.config["port"]),
            user=self.config["username"],
            password=self.config["password"],
            database=self.config["database"],
            charset="utf8mb4",
            autocommit=True,
        )

    @staticmethod
    def list_stock_tables(conn) -> List[str]:
        sql = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = %s
        ORDER BY table_name
        """
        database_name = conn.db.decode("utf-8") if isinstance(conn.db, bytes) else conn.db
        result = []
        with conn.cursor() as cur:
            cur.execute(sql, (database_name,))
            for (table_name,) in cur.fetchall():
                table = str(table_name).upper()
                if CODE_PATTERN.match(table):
                    result.append(table)
        return result

    @staticmethod
    def get_last_trade_date(conn, table_name: str) -> Optional[datetime]:
        with conn.cursor() as cur:
            cur.execute(f"SELECT MAX(trade_date) FROM `{table_name}`")
            row = cur.fetchone()
            if not row or not row[0]:
                return None
            if isinstance(row[0], datetime):
                return row[0]
            return datetime.combine(row[0], datetime.min.time())

    def fetch_daily_data(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        df = self._pro.daily(
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

    @staticmethod
    def calculate_indicators(df: pd.DataFrame, atr_n: int = 14, rsi_n: int = 14) -> pd.DataFrame:
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

        indicator_cols = [c for c in FEATURE_COLUMNS if c not in RAW_COLUMNS]
        df[indicator_cols] = df[indicator_cols].ffill()
        return df

    @staticmethod
    def _to_sql_val(value):
        return None if pd.isna(value) else value

    def upsert_rows(self, conn, table_name: str, df: pd.DataFrame) -> int:
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
                    self._to_sql_val(item.ts_code),
                    self._to_sql_val(item.trade_date.date() if hasattr(item.trade_date, "date") else item.trade_date),
                    self._to_sql_val(item.open),
                    self._to_sql_val(item.high),
                    self._to_sql_val(item.low),
                    self._to_sql_val(item.close),
                    self._to_sql_val(item.pre_close),
                    self._to_sql_val(item.change),
                    self._to_sql_val(item.pct_chg),
                    self._to_sql_val(item.vol),
                    self._to_sql_val(item.amount),
                    self._to_sql_val(item.mtm_5),
                    self._to_sql_val(item.mtm_10),
                    self._to_sql_val(item.mtm_20),
                    self._to_sql_val(item.ma_5),
                    self._to_sql_val(item.ma_10),
                    self._to_sql_val(item.ma_20),
                    self._to_sql_val(item.ema_5),
                    self._to_sql_val(item.ema_10),
                    self._to_sql_val(item.ema_20),
                    self._to_sql_val(item.tr),
                    self._to_sql_val(item.atr),
                    self._to_sql_val(item.u),
                    self._to_sql_val(item.d),
                    self._to_sql_val(item.au),
                    self._to_sql_val(item.ad),
                    self._to_sql_val(item.rs),
                    self._to_sql_val(item.rsi),
                    self._to_sql_val(item.ma_12),
                    self._to_sql_val(item.ma_26),
                    self._to_sql_val(item.ema_12),
                    self._to_sql_val(item.ema_26),
                    self._to_sql_val(item.dif),
                    self._to_sql_val(item.dif_ma_9),
                    self._to_sql_val(item.dea),
                    self._to_sql_val(item.macd),
                    self._to_sql_val(item.volume_change_rate),
                )
            )

        with conn.cursor() as cur:
            cur.executemany(sql, rows)

        return len(rows)

    def update_one_stock(self, conn, ts_code: str, lookback_days: int, default_start_date: str, end_date: str) -> int:
        last_trade_date = self.get_last_trade_date(conn, ts_code)
        if last_trade_date is None:
            start_date = default_start_date
        else:
            start_date = (last_trade_date - timedelta(days=lookback_days)).strftime("%Y%m%d")

        raw_df = self.fetch_daily_data(ts_code=ts_code, start_date=start_date, end_date=end_date)
        if raw_df.empty:
            return 0

        feature_df = self.calculate_indicators(raw_df.copy())
        feature_df = feature_df[FEATURE_COLUMNS]

        return self.upsert_rows(conn, ts_code, feature_df)

    def run_once(self) -> int:
        if self._pro is None:
            self.init_tushare()

        end_date = datetime.now().strftime("%Y%m%d")
        lookback_days = int(self.config.get("lookback_days", "120"))
        default_start_date = self.config.get("default_start_date", "20100101")

        conn = self.connect_mysql()
        try:
            tables = self.list_stock_tables(conn)
            if not tables:
                print("[AutoUpdate] No stock tables found; skip.")
                return 0

            total_rows = 0
            for ts_code in tables:
                affected = self.update_one_stock(
                    conn=conn,
                    ts_code=ts_code,
                    lookback_days=lookback_days,
                    default_start_date=default_start_date,
                    end_date=end_date,
                )
                total_rows += affected

            print(f"[AutoUpdate] Completed. tables={len(tables)}, affected_rows={total_rows}, end_date={end_date}")
            return total_rows
        finally:
            conn.close()


def _resolve_env_path(base_dir: str, env_path: str) -> Path:
    raw = Path(env_path)
    if raw.is_absolute():
        return raw

    candidates = [
        (Path.cwd() / raw).resolve(),
        (Path(base_dir) / raw).resolve(),
        (Path(base_dir) / ".env").resolve(),
    ]
    for item in candidates:
        if item.exists():
            return item
    return candidates[-1]


def _load_config(base_dir: str) -> Dict[str, str]:
    env_path = os.getenv("AUTO_DAILY_UPDATE_ENV_PATH", ".env")
    resolved = _resolve_env_path(base_dir, env_path)

    if resolved.exists():
        load_dotenv(dotenv_path=resolved, override=True)
        print(f"[AutoUpdate] Loaded .env: {resolved}")
    else:
        print(f"[AutoUpdate] Warning: .env not found at {resolved}, using process env")

    cfg = {
        "host": os.getenv("host", "localhost"),
        "port": os.getenv("port", "3306"),
        "username": os.getenv("username", "root"),
        "password": os.getenv("password", ""),
        "database": os.getenv("database", "etf_scut"),
        "tushare_token": os.getenv("TUSHARE_TOKEN", ""),
        "lookback_days": os.getenv("AUTO_DAILY_UPDATE_LOOKBACK_DAYS", "120"),
        "default_start_date": os.getenv("AUTO_DAILY_UPDATE_DEFAULT_START_DATE", "20100101"),
    }
    return cfg


def _to_bool(value: str, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def start_daily_update_scheduler(base_dir: str) -> None:
    """Start non-blocking background loop for periodic data update."""
    enabled = _to_bool(os.getenv("AUTO_DAILY_UPDATE_ENABLED", "true"), default=True)
    if not enabled:
        print("[AutoUpdate] Disabled by AUTO_DAILY_UPDATE_ENABLED")
        return

    interval_minutes = int(os.getenv("AUTO_DAILY_UPDATE_INTERVAL_MINUTES", "60"))
    run_on_start = _to_bool(os.getenv("AUTO_DAILY_UPDATE_RUN_ON_START", "true"), default=True)

    config = _load_config(base_dir)
    updater = DailyUpdater(config)

    def _runner_loop():
        print(
            f"[AutoUpdate] Scheduler started. interval={interval_minutes}min, "
            f"run_on_start={run_on_start}"
        )

        if run_on_start:
            try:
                updater.run_once()
            except Exception as exc:
                print(f"[AutoUpdate] Initial run failed: {exc}")

        while True:
            time.sleep(max(interval_minutes, 1) * 60)
            try:
                updater.run_once()
            except Exception as exc:
                print(f"[AutoUpdate] Periodic run failed: {exc}")

    thread = threading.Thread(target=_runner_loop, daemon=True, name="daily-update-scheduler")
    thread.start()
