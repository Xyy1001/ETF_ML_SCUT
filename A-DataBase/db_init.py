#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库初始化与股票特征入库脚本

功能：
1. --init: 按用户输入的股票代码创建同名表，并写入该股票 2010-01-01 至今的数据
2. 指标计算：MTM / MA / EMA / TR / ATR / RSI / MACD / 成交量变动率
3. 缺失值处理：对指标列执行向后填充（bfill）
4. --reset: 删除当前数据库中的所有表（不删除数据库）
5. --hard-reset: 删除并重建数据库
6. --verify: 查看当前数据库所有表及记录数
"""

import argparse
import os
import re
import sys
from datetime import datetime
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


def load_config(env_path: str) -> Dict[str, str]:
    """从 .env 加载配置"""
    if os.path.exists(env_path):
        load_dotenv(env_path, override=True)
    else:
        print(f"警告: .env 文件未找到 ({env_path})，将使用默认配置")

    config = {
        "host": os.getenv("host", "localhost"),
        "port": os.getenv("port", "3306"),
        "username": os.getenv("username", "root"),
        "password": os.getenv("password", ""),
        "database": os.getenv("database", "etf_scut"),
        "tushare_token": os.getenv("TUSHARE_TOKEN", ""),
    }
    return config


class StockDatabaseInitializer:
    def __init__(self, config: Dict[str, str]):
        self.host = config["host"]
        self.port = int(config["port"])
        self.username = config["username"]
        self.password = config["password"]
        self.database = config["database"]
        self.tushare_token = config.get("tushare_token", "")

        self.conn = None
        self.cursor = None
        self.pro = None

    def connect(self):
        try:
            self.conn = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.username,
                password=self.password,
                charset="utf8mb4",
                autocommit=True,
            )
            self.cursor = self.conn.cursor()
            print(f"✓ 成功连接数据库服务器: {self.host}:{self.port}")
        except pymysql.Error as e:
            print(f"✗ 数据库连接失败: {e}")
            sys.exit(1)

    def create_database(self):
        try:
            self.cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{self.database}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            self.cursor.execute(f"USE `{self.database}`")
            print(f"✓ 使用数据库: {self.database}")
        except pymysql.Error as e:
            print(f"✗ 创建/切换数据库失败: {e}")
            sys.exit(1)

    def init_tushare(self):
        if not self.tushare_token:
            print("✗ 未在 .env 中读取到 TUSHARE_TOKEN")
            sys.exit(1)
        ts.set_token(self.tushare_token)
        self.pro = ts.pro_api()
        print("✓ TuShare 接口初始化成功")

    def validate_ts_code(self, ts_code: str) -> bool:
        return bool(re.match(r"^[0-9A-Z]{6}\.(SZ|SH|BJ)$", ts_code.upper()))

    def get_stock_codes(self) -> List[str]:
        print("\n请选择股票输入方式：")
        print("1 - 依次输入单只股票代码（每次处理后决定是否继续）")
        print("2 - 一次输入多只股票代码（逗号分隔）")

        mode = input("请输入模式（1/2）: ").strip()
        codes: List[str] = []

        if mode == "1":
            while True:
                code = input("请输入股票代码（示例: 000001.SZ）: ").strip().upper()
                if code:
                    if self.validate_ts_code(code):
                        codes.append(code)
                    else:
                        print(f"⚠ 股票代码格式无效，已跳过: {code}")
                cont = input("是否继续输入并处理下一只？(y/n): ").strip().lower()
                if cont not in {"y", "yes"}:
                    break
        else:
            raw = input("请输入多个股票代码，逗号分隔: ").strip()
            for item in raw.split(","):
                code = item.strip().upper()
                if not code:
                    continue
                if self.validate_ts_code(code):
                    codes.append(code)
                else:
                    print(f"⚠ 股票代码格式无效，已跳过: {code}")

        unique_codes = []
        seen = set()
        for code in codes:
            if code not in seen:
                seen.add(code)
                unique_codes.append(code)

        return unique_codes

    def create_stock_table(self, ts_code: str):
        """按股票代码创建同名表"""
        table_name = ts_code
        sql = f"""
        CREATE TABLE IF NOT EXISTS `{table_name}` (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            ts_code VARCHAR(16) NOT NULL,
            trade_date DATE NOT NULL,
            open DECIMAL(12, 4),
            high DECIMAL(12, 4),
            low DECIMAL(12, 4),
            close DECIMAL(12, 4),
            pre_close DECIMAL(12, 4),
            change_value DECIMAL(12, 4),
            pct_chg DECIMAL(12, 6),
            vol DECIMAL(20, 4),
            amount DECIMAL(20, 4),
            mtm_5 DECIMAL(16, 6),
            mtm_10 DECIMAL(16, 6),
            mtm_20 DECIMAL(16, 6),
            ma_5 DECIMAL(16, 6),
            ma_10 DECIMAL(16, 6),
            ma_20 DECIMAL(16, 6),
            ema_5 DECIMAL(16, 6),
            ema_10 DECIMAL(16, 6),
            ema_20 DECIMAL(16, 6),
            tr DECIMAL(16, 6),
            atr DECIMAL(16, 6),
            u DECIMAL(16, 6),
            d DECIMAL(16, 6),
            au DECIMAL(16, 6),
            ad DECIMAL(16, 6),
            rs DECIMAL(16, 6),
            rsi DECIMAL(16, 6),
            ma_12 DECIMAL(16, 6),
            ma_26 DECIMAL(16, 6),
            ema_12 DECIMAL(16, 6),
            ema_26 DECIMAL(16, 6),
            dif DECIMAL(16, 6),
            dif_ma_9 DECIMAL(16, 6),
            dea DECIMAL(16, 6),
            macd DECIMAL(16, 6),
            volume_change_rate DECIMAL(16, 6),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY unique_trade_date (trade_date),
            INDEX idx_trade_date (trade_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """

        self.cursor.execute(sql)
        print(f"✓ 已创建/确认表: {table_name}")

    def fetch_daily_data(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        df = self.pro.daily(
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

    def calculate_indicators(self, df: pd.DataFrame, atr_n: int = 14, rsi_n: int = 14) -> pd.DataFrame:
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

    def backfill_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """对指标列执行向前填充（用前一天值填补当前天缺失）"""
        indicator_cols = [c for c in FEATURE_COLUMNS if c not in RAW_COLUMNS]
        df[indicator_cols] = df[indicator_cols].ffill()
        return df

    def save_to_table(self, ts_code: str, df: pd.DataFrame):
        table_name = ts_code
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
            ts_code=VALUES(ts_code), open=VALUES(open), high=VALUES(high), low=VALUES(low), close=VALUES(close),
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

        def to_sql_val(val):
            """将 NaN 转为 None，其他值保持不变"""
            if pd.isna(val):
                return None
            return val

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

        with self.conn.cursor() as cur:
            cur.executemany(sql, rows)

        print(f"✓ 入库完成: {table_name} ({len(rows)} 行)")

    def process_one_stock(self, ts_code: str, start_date: str, end_date: str):
        print("\n" + "-" * 60)
        print(f"开始处理股票: {ts_code}")
        print("-" * 60)

        self.create_stock_table(ts_code)
        raw_df = self.fetch_daily_data(ts_code=ts_code, start_date=start_date, end_date=end_date)

        if raw_df.empty:
            print(f"⚠ {ts_code} 未拉取到数据，跳过")
            return

        feature_df = self.calculate_indicators(raw_df.copy())
        feature_df = self.backfill_indicators(feature_df)
        feature_df = feature_df[FEATURE_COLUMNS]

        self.save_to_table(ts_code, feature_df)
        print(f"✓ {ts_code} 处理完成")

    def initialize_by_stock_codes(self, stock_codes: List[str]):
        start_date = "20100101"
        end_date = datetime.now().strftime("%Y%m%d")

        print("\n" + "=" * 60)
        print(f"数据拉取区间: {start_date} ~ {end_date}")
        print(f"计划处理股票数量: {len(stock_codes)}")
        print("=" * 60)

        for ts_code in stock_codes:
            self.process_one_stock(ts_code=ts_code, start_date=start_date, end_date=end_date)

        print("\n✓ 初始化与入库任务全部完成")

    def reset_database(self):
        """删除当前数据库中的所有表，不删除数据库本身"""
        print("\n" + "=" * 60)
        print("正在删除当前数据库中的所有表...")
        print("=" * 60)

        try:
            self.cursor.execute(f"USE `{self.database}`")
            self.cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            self.cursor.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = %s
                ORDER BY table_name
                """,
                (self.database,),
            )
            tables = [row[0] for row in self.cursor.fetchall()]

            if not tables:
                print("当前数据库中没有表，无需删除")
            else:
                for table_name in tables:
                    self.cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")
                print(f"✓ 已删除 {len(tables)} 张表")

            self.cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            print("✓ 数据库表删除完成")
        except pymysql.Error as e:
            try:
                self.cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            except Exception:
                pass
            print(f"✗ 删除表失败: {e}")
            sys.exit(1)

    def hard_reset_database(self):
        """删除数据库并重新创建空库"""
        print("\n" + "=" * 60)
        print("正在硬重置数据库（删库重建）...")
        print("=" * 60)

        try:
            self.cursor.execute(f"DROP DATABASE IF EXISTS `{self.database}`")
            print(f"✓ 已删除数据库: {self.database}")
            self.create_database()
            print("✓ 硬重置完成（当前为空库）")
        except pymysql.Error as e:
            print(f"✗ 硬重置失败: {e}")
            sys.exit(1)

    def verify_tables(self):
        print("\n" + "=" * 60)
        print("数据库表检查")
        print("=" * 60)

        try:
            self.cursor.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = %s
                ORDER BY table_name
                """,
                (self.database,),
            )
            tables = [row[0] for row in self.cursor.fetchall()]
            print(f"当前表数量: {len(tables)}")

            for idx, table_name in enumerate(tables, 1):
                self.cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
                count = self.cursor.fetchone()[0]
                print(f"  {idx:2d}. {table_name:20s} ({count} 行)")
        except pymysql.Error as e:
            print(f"✗ 表检查失败: {e}")

    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        print("\n✓ 数据库连接已关闭")


def main():
    parser = argparse.ArgumentParser(
        description="按股票代码建表并写入特征数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  初始化并写入数据（交互输入股票代码）:
    python db_init.py --env-path .env --init

  删除当前数据库所有表:
    python db_init.py --env-path .env --reset

  硬重置（删库重建空库）:
    python db_init.py --env-path .env --hard-reset

  查看当前表和行数:
    python db_init.py --env-path .env --verify
        """,
    )

    parser.add_argument("--env-path", default=".env", help="环境配置文件路径")
    parser.add_argument("--init", action="store_true", help="初始化并写入股票数据")
    parser.add_argument("--reset", action="store_true", help="删除当前数据库中的所有表")
    parser.add_argument("--hard-reset", action="store_true", help="删除数据库并重新创建")
    parser.add_argument("--verify", action="store_true", help="查看数据库中的表和行数")

    args = parser.parse_args()

    config = load_config(args.env_path)

    print("\n" + "=" * 60)
    print("股票数据初始化工具")
    print("=" * 60)
    print(f"数据库主机: {config['host']}:{config['port']}")
    print(f"数据库名称: {config['database']}")
    print(f"数据库用户: {config['username']}")
    print("=" * 60)

    initializer = StockDatabaseInitializer(config)

    try:
        initializer.connect()
        initializer.create_database()

        if args.hard_reset:
            initializer.hard_reset_database()
        elif args.reset:
            initializer.reset_database()
        elif args.verify:
            initializer.verify_tables()
        elif args.init:
            initializer.init_tushare()
            stock_codes = initializer.get_stock_codes()
            if not stock_codes:
                print("⚠ 未输入有效股票代码，任务结束")
                return
            initializer.initialize_by_stock_codes(stock_codes)
            initializer.verify_tables()
        else:
            parser.print_help()
    finally:
        initializer.close()


if __name__ == "__main__":
    main()
