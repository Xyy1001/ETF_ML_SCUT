#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interactive data reader tool for stock tables in MySQL.

Features:
1. Show readable stock list with date coverage and row count.
2. Show available columns/attributes for selected stock table.
3. Filter by date range and selected columns.
4. Return query result to console.
5. Optionally save result to local CSV.
"""

import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import pymysql
from dotenv import load_dotenv

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

    candidates.append((script_dir / ".env").resolve())

    for item in candidates:
        if item.exists():
            return item

    return (script_dir / raw.name).resolve() if raw.name else (script_dir / ".env").resolve()


def load_config(env_path: str) -> Dict[str, str]:
    resolved_env = resolve_env_path(env_path)
    if resolved_env.exists():
        load_dotenv(dotenv_path=resolved_env, override=True)
        print(f"Loaded .env: {resolved_env}")
    else:
        print(f"Warning: .env file not found at {resolved_env}, using defaults/env vars")

    return {
        "host": os.getenv("host", "localhost"),
        "port": os.getenv("port", "3306"),
        "username": os.getenv("username", "root"),
        "password": os.getenv("password", ""),
        "database": os.getenv("database", "etf_scut"),
    }


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


def get_table_profile(conn, table_name: str) -> Tuple[int, str, str]:
    sql = f"""
    SELECT COUNT(*) AS cnt,
           DATE_FORMAT(MIN(trade_date), '%Y-%m-%d') AS start_date,
           DATE_FORMAT(MAX(trade_date), '%Y-%m-%d') AS end_date
    FROM `{table_name}`
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        row = cur.fetchone()
        return int(row[0] or 0), str(row[1] or "-"), str(row[2] or "-")


def get_columns(conn, table_name: str) -> List[str]:
    sql = """
    SELECT column_name
    FROM information_schema.columns
    WHERE table_schema = %s AND table_name = %s
    ORDER BY ordinal_position
    """
    database_name = conn.db.decode("utf-8") if isinstance(conn.db, bytes) else conn.db

    with conn.cursor() as cur:
        cur.execute(sql, (database_name, table_name))
        return [str(row[0]) for row in cur.fetchall()]


def ask_choice(prompt: str, min_value: int, max_value: int) -> int:
    while True:
        raw = input(prompt).strip()
        if not raw.isdigit():
            print("Please input a valid number.")
            continue
        value = int(raw)
        if value < min_value or value > max_value:
            print(f"Please input number in range [{min_value}, {max_value}].")
            continue
        return value


def ask_date(prompt: str, default_val: str) -> str:
    while True:
        raw = input(f"{prompt} (YYYY-MM-DD, default {default_val}): ").strip()
        if not raw:
            return default_val
        try:
            date.fromisoformat(raw)
            return raw
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")


def ask_columns(all_columns: List[str]) -> List[str]:
    print("\nAvailable columns:")
    print(", ".join(all_columns))
    raw = input(
        "Input columns separated by comma, or press Enter for all columns: "
    ).strip()
    if not raw:
        return all_columns

    requested = [x.strip() for x in raw.split(",") if x.strip()]
    invalid = [c for c in requested if c not in all_columns]
    if invalid:
        print(f"Invalid columns ignored: {', '.join(invalid)}")
    chosen = [c for c in requested if c in all_columns]
    if not chosen:
        print("No valid columns selected, using all columns.")
        return all_columns
    return chosen


def query_data(
    conn,
    table_name: str,
    columns: List[str],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    col_clause = ", ".join([f"`{c}`" for c in columns])
    sql = f"""
    SELECT {col_clause}
    FROM `{table_name}`
    WHERE trade_date BETWEEN %s AND %s
    ORDER BY trade_date ASC
    """
    return pd.read_sql(sql, conn, params=[start_date, end_date])


def maybe_save_csv(df: pd.DataFrame, default_name: str):
    save = input("Save to CSV? (y/n, default n): ").strip().lower()
    if save not in {"y", "yes"}:
        print("CSV export skipped.")
        return

    default_path = Path.cwd() / default_name
    out_path = input(f"Output path (default {default_path}): ").strip()
    target = Path(out_path) if out_path else default_path
    target.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(target, index=False, encoding="utf-8-sig")
    print(f"Saved: {target}")


def run_interactive(conn):
    tables = list_stock_tables(conn)
    if not tables:
        print("No readable stock tables found in database.")
        return

    print("\nReadable stock tables:")
    profiles = []
    for table_name in tables:
        cnt, start_date, end_date = get_table_profile(conn, table_name)
        profiles.append((table_name, cnt, start_date, end_date))

    for idx, (table_name, cnt, start_date, end_date) in enumerate(profiles, 1):
        print(f"{idx:>4d}. {table_name:<12s} rows={cnt:<8d} range={start_date} ~ {end_date}")

    choice = ask_choice("\nChoose stock by index: ", 1, len(profiles))
    table_name, _, start_default, end_default = profiles[choice - 1]

    all_columns = get_columns(conn, table_name)
    columns = ask_columns(all_columns)

    start_date = ask_date("Start date", start_default if start_default != "-" else "2010-01-01")
    end_date = ask_date("End date", end_default if end_default != "-" else date.today().isoformat())

    df = query_data(conn, table_name, columns, start_date, end_date)
    print("\nQuery finished")
    print(f"Table : {table_name}")
    print(f"Rows  : {len(df)}")
    print(f"Cols  : {len(df.columns)}")

    if df.empty:
        print("No data in selected range.")
        return

    print("\nPreview (first 20 rows):")
    with pd.option_context("display.max_columns", None, "display.width", 200):
        print(df.head(20))

    default_name = f"{table_name}_{start_date}_to_{end_date}.csv".replace(":", "-")
    maybe_save_csv(df, default_name)


def parse_args():
    parser = argparse.ArgumentParser(description="Interactive stock data reader tool")
    parser.add_argument(
        "--env-path",
        default=".env",
        help="Path to .env (supports absolute/relative; defaults to smart lookup)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    cfg = load_config(args.env_path)

    try:
        conn = connect_mysql(cfg)
    except pymysql.Error as exc:
        print(f"MySQL connection failed: {exc}")
        sys.exit(1)

    try:
        print("=" * 72)
        print("Stock Data Reader Tool")
        print(f"Database: {cfg['database']} @ {cfg['host']}:{cfg['port']}")
        print("=" * 72)
        run_interactive(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
