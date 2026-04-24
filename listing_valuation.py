#!/usr/bin/env python3
"""Listing valuation (Model B): comp-band analysis for a specific listing.

Given a project + sqft + listing price (optionally floor/facing), compute where the
listing's psf falls against a recency-adjusted distribution of comparable same-project,
same-layout transactions. Missing floor/facing info simply widens the comparable pool.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LAYOUT_DIR = DATA_DIR / "layout_mapping"
APPRECIATION_PATH = DATA_DIR / "appreciation_analysis.json"

MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def parse_month_label(label: str) -> date | None:
    if not label or len(label) < 6:
        return None
    mon = MONTHS.get(label[:3])
    try:
        year = int(label[3:])
    except ValueError:
        return None
    if not mon:
        return None
    return date(year, mon, 1)


def sqft_bucket(sqft: float) -> str:
    # Ranges align with build_dashboard_data.py: 2b1b 600-699, 2b2b 700-849, 3b2b 850-1199.
    if 600 <= sqft <= 699:
        return "2b1b"
    if 700 <= sqft <= 849:
        return "2b2b"
    if 850 <= sqft <= 1199:
        return "3b2b"
    return "other"


def load_layout_map(project_slug: str) -> dict[tuple[str, int], str]:
    path = LAYOUT_DIR / f"{project_slug}_transaction_layout_map.csv"
    if not path.exists():
        return {}
    result: dict[tuple[str, int], str] = {}
    with path.open() as f:
        for row in csv.DictReader(f):
            if row.get("mapping_status") != "matched":
                continue
            layout = row.get("resolved_layout")
            if not layout:
                continue
            try:
                sqft = int(row["sqft"])
            except (TypeError, ValueError):
                continue
            result[(row["date"], sqft)] = layout
    return result


def load_transactions(project_slug: str) -> list[dict]:
    path = DATA_DIR / f"{project_slug}_transactions.csv"
    if not path.exists():
        raise SystemExit(f"transactions file not found: {path}")
    rows: list[dict] = []
    with path.open() as f:
        for row in csv.DictReader(f):
            try:
                rows.append({
                    "date_label": row["date"],
                    "date": parse_month_label(row["date"]),
                    "sqft": int(row["sqft"]),
                    "psf": int(row["psf"]),
                    "price": int(row["price"]),
                })
            except (KeyError, ValueError):
                continue
    return [r for r in rows if r["date"]]


def load_local_cagr(project_slug: str, unit_type: str) -> float:
    data = json.loads(APPRECIATION_PATH.read_text())
    proj = data.get(project_slug)
    if not proj:
        return 0.02  # fallback
    by_type = proj.get("by_type_cagr") or {}
    label = {"2b1b": "2BR", "2b2b": "2BR", "3b2b": "3BR"}.get(unit_type)
    if label and label in by_type and by_type[label] is not None:
        return by_type[label] / 100
    overall = proj.get("overall_cagr")
    return (overall / 100) if overall is not None else 0.02


def months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return float("nan")
    values = sorted(values)
    k = (len(values) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (k - lo)


def main() -> None:
    ap = argparse.ArgumentParser(description="Listing comp-band valuation")
    ap.add_argument("--project", required=True, help="project slug, e.g. lakegrande")
    ap.add_argument("--sqft", type=int, required=True, help="listing size in sqft")
    ap.add_argument("--price", type=int, required=True, help="listing asking price (SGD)")
    ap.add_argument("--window-months", type=int, default=12, help="lookback window for comps (default 12)")
    ap.add_argument("--as-of", default=None, help="reference month YYYY-MM, default latest txn")
    args = ap.parse_args()

    bucket = sqft_bucket(args.sqft)
    if bucket == "other":
        raise SystemExit(
            f"sqft {args.sqft} does not fall into 2b1b (600-699) / 2b2b (700-849) / 3b2b (850-1199) buckets"
        )

    txns = load_transactions(args.project)
    if not txns:
        raise SystemExit(f"no transactions loaded for {args.project}")

    layout_map = load_layout_map(args.project)
    # Filter to same bucket. Prefer explicit layout map hit; fall back to sqft range if layout-mapping is absent.
    same_bucket: list[dict] = []
    for t in txns:
        label = layout_map.get((t["date_label"], t["sqft"]))
        if label == bucket:
            same_bucket.append(t)
        elif not layout_map and sqft_bucket(t["sqft"]) == bucket:
            same_bucket.append(t)

    if not same_bucket:
        raise SystemExit(f"no comparable {bucket} transactions found in {args.project}")

    latest_date = max(t["date"] for t in txns)
    if args.as_of:
        y, m = args.as_of.split("-")
        ref_date = date(int(y), int(m), 1)
    else:
        ref_date = latest_date

    # Recent window
    cutoff = date(
        ref_date.year - (1 if ref_date.month <= args.window_months % 12 and args.window_months >= 12 else 0),
        ref_date.month,
        1,
    )
    # Simpler cutoff: subtract window_months month-by-month.
    y, m = ref_date.year, ref_date.month - args.window_months
    while m <= 0:
        m += 12
        y -= 1
    cutoff = date(y, m, 1)

    recent = [t for t in same_bucket if t["date"] >= cutoff]
    if not recent:
        print(f"warning: no transactions in the last {args.window_months} months; widening to all-time")
        recent = same_bucket

    cagr = load_local_cagr(args.project, bucket)
    adjusted_psfs: list[float] = []
    for t in recent:
        months = months_between(t["date"], ref_date)
        factor = (1 + cagr) ** (months / 12)
        adjusted_psfs.append(t["psf"] * factor)

    target_psf = args.price / args.sqft
    pcts = [10, 25, 50, 75, 90]
    quantiles = {p: percentile(adjusted_psfs, p / 100) for p in pcts}
    # Rank target within distribution
    rank_pos = sum(1 for v in adjusted_psfs if v <= target_psf)
    rank_pct = rank_pos / len(adjusted_psfs) * 100
    p50 = quantiles[50]
    vs_p50 = (target_psf - p50) / p50 * 100

    print(f"\nProject:        {args.project}")
    print(f"Listing:        {args.sqft} sqft @ ${args.price:,} → psf ${target_psf:,.0f}")
    print(f"Comp pool:      {len(recent)} {bucket} txns in last {args.window_months}m (cutoff {cutoff})")
    print(f"Time-adjust:    {cagr*100:.2f}% local CAGR, ref date {ref_date}")
    print("\nAdjusted comp PSF distribution (SGD/sqft):")
    for p in pcts:
        print(f"  P{p:<3}: ${quantiles[p]:,.0f}")
    print(f"\nTarget psf vs pool:")
    print(f"  Target psf:   ${target_psf:,.0f}")
    print(f"  Rank:         ~P{rank_pct:.0f}")
    print(f"  vs P50:       {vs_p50:+.1f}% ({'premium' if vs_p50 > 0 else 'discount'})")

    # Heuristic verdict
    if target_psf < quantiles[25]:
        verdict = "BARGAIN (below P25)"
    elif target_psf < quantiles[50]:
        verdict = "FAIR-CHEAP (P25–P50)"
    elif target_psf < quantiles[75]:
        verdict = "FAIR-RICH (P50–P75)"
    elif target_psf < quantiles[90]:
        verdict = "RICH (P75–P90)"
    else:
        verdict = "OVERPRICED (above P90)"
    print(f"  Verdict:      {verdict}")


if __name__ == "__main__":
    main()
