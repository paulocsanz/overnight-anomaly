#!/usr/bin/env python3
"""
B3 Gap Strategy Backtester + Live Signal Generator

Usage:
  Backtest all history:
    python scripts/backtest.py --backtest --years 2025 2026

  Parameter sweep (varies gap threshold 1.5–3.5% per year):
    python scripts/backtest.py --sweep --years 2025 2026

  Generate today's live signals:
    python scripts/backtest.py --live

  Dry run (no writes):
    python scripts/backtest.py --backtest --years 2025 --dry-run

Env vars required:
  AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY  (from b3-collector)
  TRADING_API_URL  (e.g. https://backend-production-bde8.up.railway.app)
  TRADING_API_TOKEN
"""

import argparse
import io
import os
import sys
import zipfile
from collections import defaultdict

import boto3
import pandas as pd
import requests
from tqdm import tqdm

# ── S3 config ────────────────────────────────────────────────────────────────

S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "https://t3.storageapi.dev")
S3_BUCKET   = os.environ.get("S3_BUCKET",   "b3-public-data-lake-xi4emg")
S3_PREFIX   = "raw/b3_cotahist"

# ── Trading API config ────────────────────────────────────────────────────────

API_URL   = os.environ.get("TRADING_API_URL",   "https://backend-production-bde8.up.railway.app")
API_TOKEN = os.environ.get("TRADING_API_TOKEN", "")
UNBOUNDED_LIQUIDITY_CAP_BRL = 9_999_999_999.0


# ── COTAHIST parsing ──────────────────────────────────────────────────────────

def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name="auto",
    )

def latest_cotahist_key(s3, year: int) -> str | None:
    prefix = f"{S3_PREFIX}/COTAHIST_A{year}/{year}/"
    resp = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)
    if "Contents" not in resp:
        return None
    return sorted(o["Key"] for o in resp["Contents"])[-1]

def download_zip(s3, key: str) -> bytes:
    buf = io.BytesIO()
    s3.download_fileobj(S3_BUCKET, key, buf)
    return buf.getvalue()

def parse_cotahist(zip_data: bytes) -> pd.DataFrame:
    """
    Fixed-width COTAHIST layout (1-indexed positions → 0-indexed slices):
      TIPREG  0:2    record type ('01' = stock day)
      DATPRE  2:10   date YYYYMMDD
      CODBDI  10:12  BDI code ('02' = equity, '12' = ETF)
      CODNEQ  12:24  ticker (12 chars, space-padded)
      TPMERC  24:27  market type ('010' = regular)
      PREABE  56:69  opening price (int ÷ 100)
      PREMAX  69:82  max price
      PREMIN  82:95  min price
      PREMED  95:108 avg price
      PREULT  108:121 closing price (int ÷ 100)
      TOTNEG  147:152 number of trades
      VOLTOT  170:188 volume (int ÷ 100)
    """
    rows = []
    with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
        name = next(n for n in z.namelist() if not n.endswith("/"))
        with z.open(name) as f:
            for raw in f:
                line = raw.decode("latin-1").rstrip("\r\n")
                if len(line) < 188 or line[0:2] != "01":
                    continue
                if line[10:12] not in ("02", "12"):  # equity + ETFs
                    continue
                if line[24:27] != "010":              # regular market only
                    continue
                try:
                    rows.append({
                        "date":   line[2:10],
                        "ticker": line[12:24].strip(),
                        "open":   int(line[56:69]) / 100,
                        "high":   int(line[69:82]) / 100,
                        "low":    int(line[82:95]) / 100,
                        "avg":    int(line[95:108]) / 100,
                        "close":  int(line[108:121]) / 100,
                        "trades": int(line[147:152]),
                        "volume": int(line[170:188]) / 100,
                    })
                except (ValueError, IndexError):
                    continue
    return pd.DataFrame(rows)

def compute_gaps(df: pd.DataFrame) -> pd.DataFrame:
    """Compute gap + derived features needed by all strategy signal types."""
    df = df.sort_values(["ticker", "date"]).copy()
    grp = df.groupby("ticker")

    df["prev_close"]    = grp["close"].shift(1)
    df["prev_high"]     = grp["high"].shift(1)
    df["prev_low"]      = grp["low"].shift(1)
    df["prev_volume"]   = grp["volume"].shift(1)
    df["prev_close_2d"] = grp["close"].shift(2)   # for trend confirmation

    # Rolling 10-day avg volume (days t-11 to t-2, all known at signal time)
    df["avg_volume_10d"] = grp["volume"].transform(
        lambda x: x.shift(1).rolling(10, min_periods=5).mean()
    )

    df = df.dropna(subset=["prev_close"])
    df["gap_pct"] = (df["open"] - df["prev_close"]) / df["prev_close"] * 100

    # Prior-day close-to-close return (% ) — for trend confirmation strategy
    df["prev_day_return"] = (
        (df["prev_close"] - df["prev_close_2d"]) / df["prev_close_2d"] * 100
    )

    # Prior-day intraday range as % of prev_close — for tight-range breakout strategy
    df["prev_range_pct"] = (df["prev_high"] - df["prev_low"]) / df["prev_close"] * 100

    return df


# ── Strategy evaluation ───────────────────────────────────────────────────────

def fetch_strategies() -> list[dict]:
    """Pull active strategies from the trading API."""
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    r = requests.get(f"{API_URL}/api/strategies", headers=headers, timeout=10)
    r.raise_for_status()
    return [s for s in r.json() if s.get("active")]

def signals_for_day(row: pd.Series, strategies: list[dict]) -> list[dict]:
    import math
    gap = row["gap_pct"]
    gap_abs = abs(gap)
    signals = []

    for strat in strategies:
        cfg = strat.get("signal_config") or {}
        threshold  = float(cfg.get("gap_threshold", 2.0))
        direction  = cfg.get("direction", "reversal")
        tickers    = cfg.get("tickers")

        if gap_abs < threshold:
            continue
        if float(row.get("volume", 0.0)) < float(cfg.get("min_daily_volume_brl", 0.0)):
            continue
        if float(row.get("trades", 0.0)) < float(cfg.get("min_num_trades", 0.0)):
            continue
        if float(row.get("open", 0.0)) < float(cfg.get("min_price", 0.0)):
            continue
        if tickers and row["ticker"] not in tickers:
            continue

        # ── Trend confirmation filter ─────────────────────────────────────
        # Signal only fires when gap direction matches prior-day return.
        if cfg.get("require_trend_confirmation"):
            prev_ret = row.get("prev_day_return")
            if prev_ret is None or (hasattr(prev_ret, "__float__") and math.isnan(float(prev_ret))):
                continue
            prev_ret = float(prev_ret)
            if gap > 0 and prev_ret < 0:
                continue
            if gap < 0 and prev_ret > 0:
                continue

        # ── Volume multiplier filter ──────────────────────────────────────
        # Prior-day volume must exceed N × rolling 10-day average.
        vol_mult = float(cfg.get("volume_multiplier", 0.0))
        if vol_mult > 0:
            prev_vol = row.get("prev_volume")
            avg_vol  = row.get("avg_volume_10d")
            if (prev_vol is None or avg_vol is None
                    or math.isnan(float(prev_vol)) or math.isnan(float(avg_vol))
                    or float(avg_vol) <= 0
                    or float(prev_vol) < float(avg_vol) * vol_mult):
                continue

        # ── Tight prior-range filter ──────────────────────────────────────
        # Prior day must have had compressed range (volatility consolidation).
        if cfg.get("require_tight_prior_range"):
            tight_thresh = float(cfg.get("tight_range_threshold", 1.5))
            prev_range = row.get("prev_range_pct")
            if prev_range is None or math.isnan(float(prev_range)):
                continue
            if float(prev_range) > tight_thresh:
                continue

        # ── Liquidity capacity cap (non-lookahead: prior/trailing volume only) ──
        cap = float(cfg.get("max_position_brl", UNBOUNDED_LIQUIDITY_CAP_BRL))
        avg_part = float(cfg.get("max_avg_volume_participation_pct", 2.0))
        if avg_part > 0:
            avg_vol = row.get("avg_volume_10d")
            if avg_vol is None or math.isnan(float(avg_vol)) or float(avg_vol) <= 0:
                continue
            cap = min(cap, float(avg_vol) * avg_part / 100.0)
        prev_part = float(cfg.get("max_prev_volume_participation_pct", 5.0))
        if prev_part > 0:
            prev_vol = row.get("prev_volume")
            if prev_vol is None or math.isnan(float(prev_vol)) or float(prev_vol) <= 0:
                continue
            cap = min(cap, float(prev_vol) * prev_part / 100.0)

        rules    = strat.get("trading_rules") or {}
        min_pos  = float(rules.get("min_position_brl", 500.0))
        if cap < min_pos:
            continue

        # ── Signal direction ──────────────────────────────────────────────
        if direction == "momentum":
            sig_type = "LONG" if gap > 0 else "SHORT"
        else:  # reversal
            sig_type = "SHORT" if gap > 0 else "LONG"

        pos_pct  = float(rules.get("position_pct", 10.0))
        slippage = float(rules.get("slippage_bps", 5.0)) / 10000.0

        if direction == "momentum":
            gross_ret = (row["close"] - row["open"]) / row["open"]
        else:
            gross_ret = (row["open"] - row["close"]) / row["open"]

        net_ret = gross_ret - slippage

        signals.append({
            "strategy_id": strat["id"],
            "ticker":      row["ticker"],
            "signal_type": sig_type,
            "gap_pct":     round(float(gap), 4),
            "prev_close":  round(float(row["prev_close"]), 2),
            "open_price":  round(float(row["open"]), 2),
            "close_price": round(float(row["close"]), 2),
            "signal_date": f"{row['date'][:4]}-{row['date'][4:6]}-{row['date'][6:8]}",
            "gross_return_pct": round(gross_ret * 100, 4),
            "net_return_pct":   round(net_ret * 100, 4),
            "pos_pct": pos_pct,
            "liquidity_cap_brl": round(cap, 2),
            "min_position_brl": min_pos,
        })
    return signals


# ── API calls ─────────────────────────────────────────────────────────────────

def create_backtest_run(name: str, params: dict) -> str | None:
    """Create a named backtest run in the API and return its ID."""
    headers = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}
    r = requests.post(f"{API_URL}/api/backtest/create-run",
                      json={"name": name, "params": params},
                      headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()["id"]


def post_backtest_trades(signals: list[dict], dry_run=False) -> None:
    if not signals:
        print("No signals generated.")
        return
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Posting {len(signals):,} trades...")
    if dry_run:
        for s in signals[:10]:
            print(f"  {s['signal_date']} {s['ticker']:12s} {s['signal_type']:5s} "
                  f"gap={s['gap_pct']:+.2f}%  ret={s['net_return_pct']:+.2f}%")
        return

    headers = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}
    # Batch in chunks of 500
    ok = 0
    CHUNK = 500
    for i in tqdm(range(0, len(signals), CHUNK), desc="Posting"):
        chunk = signals[i:i+CHUNK]
        r = requests.post(f"{API_URL}/api/backtest/run",
                          json=chunk, headers=headers, timeout=60)
        if r.status_code == 200:
            ok += len(chunk)
        else:
            print(f"Chunk {i//CHUNK} failed: {r.status_code} {r.text[:200]}")
    print(f"OK: {ok:,}/{len(signals):,} trades inserted")

def post_live_signals(signals: list[dict], dry_run=False) -> None:
    if not signals:
        print("No live signals.")
        return
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Posting {len(signals)} live signals...")
    if dry_run:
        for s in signals:
            print(f"  {s['signal_date']} {s['ticker']} {s['signal_type']} gap={s['gap_pct']:+.2f}%")
        return

    headers = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}
    ok = 0
    for s in tqdm(signals, desc="Signals"):
        payload = {k: v for k, v in s.items()
                   if k in ("strategy_id", "ticker", "signal_type",
                            "gap_pct", "prev_close", "open_price", "signal_date")}
        r = requests.post(f"{API_URL}/api/signals", json=payload,
                          headers=headers, timeout=10)
        if r.status_code == 201:
            ok += 1
        else:
            print(f"  Failed {s['ticker']}: {r.status_code}")
    print(f"Posted {ok}/{len(signals)} signals. Scheduler executes at 13:05 UTC.")


# ── Main ──────────────────────────────────────────────────────────────────────

def _load_year_data(s3, year: int) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """Download, parse, and compute gaps for a given year. Returns (raw_df, gapped_df)."""
    key = latest_cotahist_key(s3, year)
    if not key:
        print(f"No COTAHIST data for {year}, skipping.")
        return None
    print(f"\nDownloading COTAHIST {year} ({key.split('/')[-1]})...")
    zip_data = download_zip(s3, key)
    print(f"Parsing...")
    df = parse_cotahist(zip_data)
    print(f"  {len(df):,} records | {df['date'].nunique()} trading days | {df['ticker'].nunique()} tickers")
    return df, compute_gaps(df)


def _collect_signals(gapped: pd.DataFrame, strategies: list[dict],
                     year: int, run_id: str | None) -> list[dict]:
    signals = []
    for _, row in tqdm(gapped.iterrows(), total=len(gapped), desc=str(year)):
        for sig in signals_for_day(row, strategies):
            if run_id:
                sig["run_id"] = run_id
            signals.append(sig)
    return signals


def run_backtest(years: list[int], dry_run: bool, run_name: str | None = None) -> None:
    s3 = s3_client()
    strategies = fetch_strategies()
    if not strategies:
        print("No active strategies found. Create at least one first.")
        sys.exit(1)
    print(f"Strategies: {[s['name'] for s in strategies]}")

    # Create a named run if requested (or if multi-year)
    run_id = None
    if not dry_run:
        name = run_name or f"Backtest {'-'.join(str(y) for y in years)}"
        params = {"years": years}
        run_id = create_backtest_run(name, params)
        print(f"Created run: {name} ({run_id})")

    all_signals = []
    for year in years:
        result = _load_year_data(s3, year)
        if result is None:
            continue
        raw_df, gapped = result
        signals = _collect_signals(gapped, strategies, year, run_id)
        print(f"  {len(signals):,} signals for {year}")
        all_signals.extend(signals)
        if not dry_run:
            save_parquet(s3, raw_df, year)

    print(f"\nTotal: {len(all_signals):,} signals across {years}")
    post_backtest_trades(all_signals, dry_run)


def run_sweep(years: list[int], dry_run: bool) -> None:
    """Parameter sweep: run backtest at multiple gap thresholds."""
    s3 = s3_client()
    strategies = fetch_strategies()
    if not strategies:
        print("No active strategies found.")
        sys.exit(1)

    thresholds = [1.5, 2.0, 2.5, 3.0, 3.5]
    year_range = "-".join(str(y) for y in years)

    # Pre-load all year data once (avoid re-downloading for every threshold)
    year_data: dict[int, pd.DataFrame] = {}
    for year in years:
        result = _load_year_data(s3, year)
        if result is not None:
            raw_df, gapped = result
            year_data[year] = gapped
            if not dry_run:
                save_parquet(s3, raw_df, year)

    if not year_data:
        print("No data found for any year.")
        sys.exit(1)

    for threshold in thresholds:
        run_name = f"Sweep T={threshold}% {year_range}"
        print(f"\n{'='*60}")
        print(f"Running: {run_name}")
        print(f"{'='*60}")

        # Override gap_threshold for all strategies
        modified = []
        for strat in strategies:
            s = dict(strat)
            cfg = dict(s.get("signal_config") or {})
            cfg["gap_threshold"] = threshold
            s["signal_config"] = cfg
            modified.append(s)

        run_id = None
        if not dry_run:
            run_id = create_backtest_run(run_name, {"gap_threshold": threshold, "years": years})
            print(f"Created run: {run_id}")

        all_signals: list[dict] = []
        for year, gapped in year_data.items():
            signals = _collect_signals(gapped, modified, year, run_id)
            print(f"  {len(signals):,} signals for {year}")
            all_signals.extend(signals)

        print(f"Total: {len(all_signals):,} signals at T={threshold}%")
        post_backtest_trades(all_signals, dry_run)

def save_parquet(s3, df: pd.DataFrame, year: int) -> None:
    """Save parsed OHLCV data as Parquet to S3 for fast future reads."""
    buf = io.BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow", compression="snappy")
    key = f"processed/b3_ohlcv/{year}/cotahist.parquet"
    buf.seek(0)
    s3.put_object(Bucket=S3_BUCKET, Key=key, Body=buf.getvalue())
    print(f"  Saved parquet → s3://{S3_BUCKET}/{key} ({len(buf.getvalue())//1024}KB)")

def run_live(dry_run: bool) -> None:
    """Generate signals for today (or most recent available trading day)."""
    s3 = s3_client()
    strategies = fetch_strategies()
    if not strategies:
        print("No active strategies found.")
        sys.exit(1)

    from datetime import date
    year = date.today().year
    key = latest_cotahist_key(s3, year)
    if not key:
        print(f"No COTAHIST data for {year}.")
        sys.exit(1)

    zip_data = download_zip(s3, key)
    df = parse_cotahist(zip_data)
    gapped = compute_gaps(df)

    # Latest date available
    latest_date = gapped["date"].max()
    print(f"Latest trading date in COTAHIST: {latest_date}")
    today_df = gapped[gapped["date"] == latest_date]

    signals = []
    for _, row in today_df.iterrows():
        signals.extend(signals_for_day(row, strategies))

    post_live_signals(signals, dry_run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="B3 Gap Strategy Backtester")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--backtest", action="store_true", help="Run historical backtest")
    mode.add_argument("--sweep",    action="store_true", help="Sweep gap thresholds 1.5–3.5%%")
    mode.add_argument("--live",     action="store_true", help="Generate today's signals")
    parser.add_argument("--years",    nargs="+", type=int, default=[2025, 2026],
                        help="Years to backtest (default: 2025 2026)")
    parser.add_argument("--run-name", type=str, default=None,
                        help="Name for this backtest run (auto-generated if not set)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print results without writing to API")
    args = parser.parse_args()

    if args.backtest:
        run_backtest(args.years, args.dry_run, run_name=args.run_name)
    elif args.sweep:
        run_sweep(args.years, args.dry_run)
    else:
        run_live(args.dry_run)
