#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Forward-fill missing values for stock CSV outputs.

Supports:
1. Single CSV file.
2. A folder containing many CSV files.
3. In-place overwrite or write to another folder.

Note:
- Pure forward fill (ffill) keeps leading NaN values if a column starts with NaN.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import pandas as pd


def list_csv_files(path: Path) -> List[Path]:
    if path.is_file():
        if path.suffix.lower() != ".csv":
            raise ValueError(f"Input file is not CSV: {path}")
        return [path]

    if not path.is_dir():
        raise FileNotFoundError(f"Input path not found: {path}")

    files = sorted(path.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found under: {path}")
    return files


def ffill_csv(input_file: Path, output_file: Path, columns: List[str] | None = None) -> int:
    df = pd.read_csv(input_file, encoding="utf-8-sig")

    before_missing = int(df.isna().sum().sum())

    if columns:
        selected = [c for c in columns if c in df.columns]
        if selected:
            df[selected] = df[selected].ffill()
    else:
        df = df.ffill()

    after_missing = int(df.isna().sum().sum())

    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, index=False, encoding="utf-8-sig")

    return before_missing - after_missing


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Forward-fill missing values in CSV files")
    parser.add_argument(
        "--input",
        default="output_split",
        help="Input CSV file path or directory path (default: output_split)",
    )
    parser.add_argument(
        "--output-dir",
        default="output_ffill",
        help="Output directory when input is directory, or output folder for a single file",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite original file(s) in place",
    )
    parser.add_argument(
        "--columns",
        default="",
        help="Comma-separated columns to fill; empty means all columns",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).resolve()
    files = list_csv_files(input_path)

    cols = [c.strip() for c in args.columns.split(",") if c.strip()]
    total_filled = 0

    if args.in_place:
        for file_path in files:
            filled = ffill_csv(file_path, file_path, columns=cols if cols else None)
            total_filled += filled
            print(f"Updated: {file_path.name}, filled={filled}")
        print(f"Done (in-place). Files={len(files)}, total_filled={total_filled}")
        return

    output_dir = Path(args.output_dir).resolve()

    if input_path.is_file():
        out_file = output_dir / input_path.name
        filled = ffill_csv(input_path, out_file, columns=cols if cols else None)
        total_filled += filled
        print(f"Saved: {out_file}, filled={filled}")
        print(f"Done. Files=1, total_filled={total_filled}")
        return

    for file_path in files:
        out_file = output_dir / file_path.name
        filled = ffill_csv(file_path, out_file, columns=cols if cols else None)
        total_filled += filled
        print(f"Saved: {out_file.name}, filled={filled}")

    print(f"Done. Files={len(files)}, total_filled={total_filled}, output={output_dir}")


if __name__ == "__main__":
    main()
