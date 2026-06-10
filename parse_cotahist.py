#!/usr/bin/env python3
"""B3 COTAHIST annual file parser.

Reads COTAHIST_AYYYY.ZIP files collected by b3_data_collector.py and writes
one Parquet file per year to data/parquet/cotahist/.

B3 COTAHIST layout (245-char, post-2001 format):
  All type-01 records (daily trade data). Header (type=00) and trailer
  (type=99) records are skipped.

Prices are stored in R$ with 2 decimal places (raw integer / 100).
FATCOT is the cotation factor; price per individual unit = price / fatcot.
For most modern equities fatcot=1, so price == price_per_unit.

Usage:
  python parse_cotahist.py                        # parse all years
  COTAHIST_YEARS=2020,2021,2022 python parse_cotahist.py
  B3_DATA_DIR=./data python parse_cotahist.py
"""

from __future__ import annotations

import io
import os
import sys
import zipfile
from pathlib import Path

import pandas as pd

DATA_DIR = Path(os.getenv("B3_DATA_DIR", "./data"))
RAW_COTAHIST = DATA_DIR / "raw" / "b3_cotahist"
OUT_DIR = DATA_DIR / "parquet" / "cotahist"

# (colname, start, end) — 0-indexed, end exclusive
COLSPECS: list[tuple[str, int, int]] = [
    ("tipreg",  0,   2),   # record type: '01'=daily data, '00'=header, '99'=trailer
    ("datpre",  2,  10),   # trade date YYYYMMDD
    ("codbdi", 10,  12),   # BDI code: '02'=spot lot, '12'=FII, '34'=ETF, etc.
    ("codneg", 12,  24),   # ticker (padded with spaces)
    ("tpmerc", 24,  27),   # market: '010'=spot, '020'=fractional, '030'=options
    ("nomres", 27,  39),   # abbreviated company name
    ("especi", 39,  49),   # paper specification: ON, PN, UNT, CI, etc.
    ("preabe", 56,  69),   # open price (integer, divide by 100 for R$)
    ("premax", 69,  82),   # high price
    ("premin", 82,  95),   # low price
    ("premed", 95, 108),   # average price
    ("preuln",108, 121),   # close price (last trade)
    ("preofc",121, 134),   # best buy offer
    ("preofv",134, 147),   # best sell offer
    ("totneg",147, 152),   # number of trades
    ("quatot",152, 170),   # total shares traded
    ("voltot",170, 188),   # total financial volume (integer, divide by 100 for R$)
    ("fatcot",210, 217),   # cotation factor (usually 1; price_per_unit = price / fatcot)
    ("codisi",230, 242),   # ISIN code
]

PRICE_COLS = {"preabe", "premax", "premin", "premed", "preuln", "preofc", "preofv", "voltot"}
INT_COLS   = {"totneg", "quatot", "fatcot"}
STR_COLS   = {"codbdi", "codneg", "tpmerc", "nomres", "especi", "codisi"}


def _find_zips(dataset_dir: Path) -> list[Path]:
    return sorted(dataset_dir.rglob("*.zip"))


def parse_year(zip_path: Path, year: int) -> pd.DataFrame | None:
    print(f"  parsing {zip_path.name} ...", flush=True)
    try:
        with zipfile.ZipFile(zip_path) as z:
            names = z.namelist()
            txt_name = next((n for n in names if n.upper().endswith(".TXT")), names[0])
            raw = z.read(txt_name).decode("latin1", errors="replace")
    except Exception as e:
        print(f"  ERROR reading zip: {e}", flush=True)
        return None

    lines = raw.splitlines()
    data_lines = [l for l in lines if len(l) == 245 and l[0:2] == "01"]
    if not data_lines:
        print(f"  WARNING: no type-01 records found", flush=True)
        return None

    buf = io.StringIO("\n".join(data_lines))
    df = pd.read_fwf(
        buf,
        colspecs=[(s, e) for _, s, e in COLSPECS],
        names=[n for n, _, _ in COLSPECS],
        dtype=str,
        header=None,
    )

    # Drop the tipreg column (always '01')
    df = df.drop(columns=["tipreg"])

    # Parse date
    df["date"] = pd.to_datetime(df["datpre"], format="%Y%m%d", errors="coerce")
    df = df.drop(columns=["datpre"])

    # Strip string columns
    for col in STR_COLS:
        df[col] = df[col].str.strip()

    # Numeric columns
    for col in PRICE_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce") / 100.0

    for col in INT_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    # Reorder columns with date first
    cols = ["date", "codneg", "codbdi", "tpmerc", "nomres", "especi",
            "preabe", "premax", "premin", "premed", "preuln",
            "preofc", "preofv", "totneg", "quatot", "voltot",
            "fatcot", "codisi"]
    df = df[[c for c in cols if c in df.columns]]

    print(f"  {len(df):,} records  date range: {df['date'].min().date()} – {df['date'].max().date()}", flush=True)
    return df


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    years_env = os.getenv("COTAHIST_YEARS", "")
    if years_env:
        target_years = {int(y.strip()) for y in years_env.split(",") if y.strip()}
    else:
        target_years = None

    total_written = 0
    errors = 0

    # Each dataset dir is named COTAHIST_AYYYY
    for dataset_dir in sorted(RAW_COTAHIST.iterdir()):
        if not dataset_dir.is_dir():
            continue
        name = dataset_dir.name
        if not name.startswith("COTAHIST_A"):
            continue
        try:
            year = int(name.removeprefix("COTAHIST_A"))
        except ValueError:
            continue

        if target_years and year not in target_years:
            continue

        zips = _find_zips(dataset_dir)
        if not zips:
            print(f"[{year}] no zip files found", flush=True)
            continue

        # Use the most recently collected zip (latest timestamp in name)
        zip_path = zips[-1]
        out_path = OUT_DIR / f"{year}.parquet"

        print(f"[{year}] {zip_path}", flush=True)
        df = parse_year(zip_path, year)
        if df is None or df.empty:
            errors += 1
            continue

        df.to_parquet(out_path, index=False, engine="pyarrow", compression="snappy")
        size_mb = out_path.stat().st_size / 1_048_576
        print(f"  → {out_path.name}  {size_mb:.1f} MB", flush=True)
        total_written += 1

    print(f"\nDone. Wrote {total_written} parquet files, {errors} errors.", flush=True)
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
