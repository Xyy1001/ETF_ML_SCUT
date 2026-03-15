# A-DataBase Daily Update & Data Tools

This guide covers two new scripts:
- `daily_update.py`: one-command daily incremental update to DB.
- `data_tools.py`: interactive reader/export tool.

## 1. Prerequisites

1. Configure `.env` in `A-DataBase` (copy from `.env.example`).
2. Ensure MySQL is running and tables already initialized (use `db_init.py --init` once).
3. Install dependencies (if not installed yet):

```bash
pip install pandas numpy pymysql tushare python-dotenv
```

## 2. Daily Incremental Update

Run from workspace root (`E:\ETF SCUT`) or from `A-DataBase` folder.

```bash
cd A-DataBase
python daily_update.py --env-path .env
```

What it does:
- Scans stock tables like `000001.SZ`.
- Finds latest DB date for each stock.
- Pulls recent daily bars from TuShare.
- Recomputes indicators on a rolling lookback window.
- Upserts rows into each stock table (new + corrected rows).

Useful options:

```bash
# Update specific stocks only
python daily_update.py --env-path .env --codes 000001.SZ,000002.SZ

# Adjust rolling recompute window
python daily_update.py --env-path .env --lookback-days 120

# If a table is empty, use this start date
python daily_update.py --env-path .env --default-start-date 20100101
```

## 3. Interactive Data Reader Tool

```bash
cd A-DataBase
python data_tools.py --env-path .env
```

Flow:
1. Show readable stock table list.
2. Show each table's row count and date range.
3. Select one stock by index.
4. View/select columns (attributes).
5. Input start/end date.
6. Get data preview and row count.
7. Choose whether to save CSV locally.

## 4. Suggested Daily Automation (Windows Task Scheduler)

You can create a daily scheduled task to run:

```bash
cd /d E:\ETF SCUT\A-DataBase
python daily_update.py --env-path .env
```

Set it after market close (for example 16:30) to keep DB updated.
