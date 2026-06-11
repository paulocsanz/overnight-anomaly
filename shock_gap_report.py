#!/usr/bin/env python3
"""Generate B3 shock-gap reversal candidates and a manual trading checklist.

This is the deployable scanner for the current gap-reversal research result. It
is intentionally low-frequency: normal 5% gaps have not held up recently.

Usage:
  python3 shock_gap_report.py
  python3 shock_gap_report.py --date 2026-06-08
  python3 shock_gap_report.py --recent-days 30
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(os.getenv("B3_DATA_DIR", "./data"))
ANALYSIS_FILE = DATA_DIR / "analysis" / "liquidity_filtered_with_metrics.parquet"
TRADING_DIR = DATA_DIR / "trading"

DEFAULT_MIN_GAP_PCT = 12.0
DEFAULT_MAX_GAP_PCT = 50.0  # Larger gaps are usually corporate actions/data adjustments.
DEFAULT_MIN_ADV20_REAIS = 1_000_000.0
DEFAULT_VOL_MULTIPLE = 3.0
DEFAULT_MIN_PREV_CLOSE = 2.0
DEFAULT_SLIPPAGE_PCT = 0.10

MANUAL_CHECK_COLUMNS = [
    "news_ok",
    "corporate_action_ok",
    "borrow_available",
    "borrow_fee_ok",
    "spread_ok",
    "auction_ok",
    "opening_range_failed",
    "vwap_failed",
    "trade_decision",
    "notes",
]


def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Run analysis_overnight_anomaly.py first.")
    return pd.read_parquet(path).sort_values(["codneg", "date"]).reset_index(drop=True)


def add_trailing_filters(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    grouped = out.groupby("codneg", group_keys=False)
    out["adv20_reais"] = grouped["voltot"].transform(lambda x: x.rolling(20, min_periods=10).mean().shift(1))
    out["range20_pct"] = grouped["intraday_range_pct"].transform(
        lambda x: x.rolling(20, min_periods=10).mean().shift(1)
    )
    out["shock_ratio"] = out["gap_pct"].abs() / out["range20_pct"].clip(lower=1.0)
    return out


def build_candidates(
    df: pd.DataFrame,
    target_date: pd.Timestamp | None,
    recent_days: int,
    min_gap_pct: float,
    max_gap_pct: float,
    min_adv20_reais: float,
    vol_multiple: float,
    min_prev_close: float,
    slippage_pct: float,
) -> pd.DataFrame:
    if target_date is not None:
        scan = df[df["date"].dt.normalize() == target_date.normalize()].copy()
    elif recent_days > 1:
        dates = df["date"].dropna().drop_duplicates().sort_values().tail(recent_days)
        scan = df[df["date"].isin(dates)].copy()
    else:
        latest_date = df["date"].max()
        scan = df[df["date"] == latest_date].copy()

    eligible = (
        (scan["prev_close"] >= min_prev_close)
        & (scan["adv20_reais"] >= min_adv20_reais)
        & (scan["gap_pct"].abs() >= min_gap_pct)
        & (scan["gap_pct"].abs() <= max_gap_pct)
        & (scan["shock_ratio"] >= vol_multiple)
        & scan["preabe"].gt(0)
        & scan["preuln"].gt(0)
        & scan["premax"].gt(scan["premin"])
    )
    candidates = scan[eligible].copy()
    if candidates.empty:
        return candidates

    candidates["side"] = np.where(candidates["gap_pct"] > 0, "SHORT", "LONG")
    candidates["priority"] = np.where(
        candidates["side"] == "SHORT",
        "HIGH_IF_BORROW_AND_OPENING_FAILURE",
        "PAPER_ONLY_UNTIL_LONG_SIDE_IMPROVES",
    )

    slip = slippage_pct / 100
    candidates["entry_estimate"] = np.where(
        candidates["side"] == "SHORT",
        candidates["preabe"] * (1 - slip),
        candidates["preabe"] * (1 + slip),
    )

    # Gap-fill targets. For shorts: lower prices. For longs: higher prices.
    gap_points = candidates["preabe"] - candidates["prev_close"]
    candidates["target_30_fill"] = candidates["preabe"] - 0.30 * gap_points
    candidates["target_50_fill"] = candidates["preabe"] - 0.50 * gap_points
    candidates["target_full_fill"] = candidates["prev_close"]

    # Placeholder risk levels; actual stop should use live first-5-minute range.
    candidates["stop_reference"] = np.where(
        candidates["side"] == "SHORT",
        "above opening-range high / VWAP reclaim",
        "below opening-range low / VWAP fail",
    )
    candidates["execution_rule"] = np.where(
        candidates["side"] == "SHORT",
        "wait 5m; short only after VWAP/opening-range failure; borrow required",
        "paper only; require stabilization and VWAP reclaim",
    )

    for col in MANUAL_CHECK_COLUMNS:
        candidates[col] = ""

    columns = [
        "date",
        "codneg",
        "side",
        "priority",
        "gap_pct",
        "shock_ratio",
        "range20_pct",
        "adv20_reais",
        "prev_close",
        "preabe",
        "entry_estimate",
        "target_30_fill",
        "target_50_fill",
        "target_full_fill",
        "stop_reference",
        "execution_rule",
        *MANUAL_CHECK_COLUMNS,
    ]
    return candidates[columns].sort_values(["date", "priority", "shock_ratio"], ascending=[False, True, False])


def write_markdown(candidates: pd.DataFrame, output_path: Path, params: dict) -> None:
    lines = [
        "# Shock Gap Reversal Report",
        "",
        "## Filters",
        f"- `abs(gap) >= {params['min_gap_pct']:.1f}%`",
        f"- `abs(gap) <= {params['max_gap_pct']:.1f}%`",
        f"- `ADV20 >= R${params['min_adv20_reais']:,.0f}`",
        f"- `abs(gap) / range20 >= {params['vol_multiple']:.1f}`",
        f"- `prev_close >= R${params['min_prev_close']:.2f}`",
        "",
        "## Execution Rules",
        "- Do not enter at the auction blindly.",
        "- Wait ~5 minutes after open.",
        "- Short gap-ups only if borrow is available and price fails VWAP/opening range.",
        "- Long gap-downs are paper-only until more evidence improves the long side.",
        "- Take partial profit around 30–50% gap fill; exit all before close.",
        "",
    ]

    if candidates.empty:
        lines += ["## Candidates", "", "No candidates.", ""]
    else:
        display = candidates.copy()
        display["date"] = display["date"].dt.strftime("%Y-%m-%d")
        lines += ["## Candidates", "", display.to_markdown(index=False), ""]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def print_summary(candidates: pd.DataFrame, params: dict) -> None:
    print("SHOCK GAP REVERSAL REPORT")
    print("=" * 80)
    print(
        f"Filters: |gap| >= {params['min_gap_pct']:.1f}%, "
        f"|gap| <= {params['max_gap_pct']:.1f}%, "
        f"ADV20 >= R${params['min_adv20_reais']:,.0f}, "
        f"shock_ratio >= {params['vol_multiple']:.1f}x, "
        f"prev_close >= R${params['min_prev_close']:.2f}"
    )
    print(f"Candidates: {len(candidates)}")
    if candidates.empty:
        return

    view = candidates[[
        "date",
        "codneg",
        "side",
        "gap_pct",
        "shock_ratio",
        "range20_pct",
        "adv20_reais",
        "preabe",
        "target_30_fill",
        "target_50_fill",
        "priority",
    ]].copy()
    view["date"] = view["date"].dt.strftime("%Y-%m-%d")
    for col in ["gap_pct", "shock_ratio", "range20_pct", "preabe", "target_30_fill", "target_50_fill"]:
        view[col] = view[col].map(lambda x: f"{x:,.2f}")
    view["adv20_reais"] = view["adv20_reais"].map(lambda x: f"R${x:,.0f}")
    print(view.to_string(index=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate B3 shock-gap candidates and manual checklist.")
    parser.add_argument("--data", type=Path, default=ANALYSIS_FILE, help="Input parquet file")
    parser.add_argument("--date", type=str, help="Scan one date, YYYY-MM-DD. Default: latest date")
    parser.add_argument("--recent-days", type=int, default=1, help="Scan latest N trading dates")
    parser.add_argument("--min-gap", type=float, default=DEFAULT_MIN_GAP_PCT)
    parser.add_argument("--max-gap", type=float, default=DEFAULT_MAX_GAP_PCT)
    parser.add_argument("--min-adv20", type=float, default=DEFAULT_MIN_ADV20_REAIS)
    parser.add_argument("--vol-multiple", type=float, default=DEFAULT_VOL_MULTIPLE)
    parser.add_argument("--min-prev-close", type=float, default=DEFAULT_MIN_PREV_CLOSE)
    parser.add_argument("--slippage", type=float, default=DEFAULT_SLIPPAGE_PCT)
    parser.add_argument("--output-dir", type=Path, default=TRADING_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    target_date = pd.Timestamp(args.date) if args.date else None
    df = add_trailing_filters(load_data(args.data))
    candidates = build_candidates(
        df=df,
        target_date=target_date,
        recent_days=args.recent_days,
        min_gap_pct=args.min_gap,
        max_gap_pct=args.max_gap,
        min_adv20_reais=args.min_adv20,
        vol_multiple=args.vol_multiple,
        min_prev_close=args.min_prev_close,
        slippage_pct=args.slippage,
    )

    if target_date is not None:
        label = target_date.strftime("%Y-%m-%d")
    elif args.recent_days > 1:
        label = f"latest_{args.recent_days}_days"
    else:
        label = df["date"].max().strftime("%Y-%m-%d")

    csv_path = args.output_dir / f"shock_gap_report_{label}.csv"
    md_path = args.output_dir / f"shock_gap_report_{label}.md"
    candidates.to_csv(csv_path, index=False)
    write_markdown(
        candidates,
        md_path,
        {
            "min_gap_pct": args.min_gap,
            "max_gap_pct": args.max_gap,
            "min_adv20_reais": args.min_adv20,
            "vol_multiple": args.vol_multiple,
            "min_prev_close": args.min_prev_close,
        },
    )

    print_summary(
        candidates,
        {
            "min_gap_pct": args.min_gap,
            "max_gap_pct": args.max_gap,
            "min_adv20_reais": args.min_adv20,
            "vol_multiple": args.vol_multiple,
            "min_prev_close": args.min_prev_close,
        },
    )
    print(f"\nCSV: {csv_path}")
    print(f"Markdown: {md_path}")


if __name__ == "__main__":
    main()
