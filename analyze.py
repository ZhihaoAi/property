#!/usr/bin/env python3
from __future__ import annotations

"""
Property appreciation analysis for multiple projects.
Reads transaction CSVs, groups by unit type and year, computes median PSF, Q1/Q3/min/max for box plot, and CAGR.
"""

import csv
import json
import statistics
from pathlib import Path

# Month abbreviation to number for date parsing
MONTH_MAP = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

MIN_CAGR_MONTH_SPAN = 12

# Project metadata: top_year, tenure, units (units may be None if unknown)
BASE_PROJECT_INFO = {
    "lakeville": {"top_year": 2018, "tenure": "99yr", "units": 696},
    "lakegrande": {"top_year": 2018, "tenure": "99yr", "units": 374},
    "seahill": {"top_year": 2011, "tenure": "99yr", "units": 478},
    "the_vision": {"top_year": 2015, "tenure": "99yr", "units": 295},
    "hundred_trees": {"top_year": 2013, "tenure": "Freehold", "units": 396},
    "parc_clematis": {"top_year": 2023, "tenure": "99yr", "units": 1468},
    "twin_vew": {"top_year": 2022, "tenure": "99yr", "units": 520},
    "parc_riviera": {"top_year": 2020, "tenure": "99yr", "units": 752},
    "whistler_grand": {"top_year": 2022, "tenure": "99yr", "units": 716},
    "normanton_park": {"top_year": 2023, "tenure": "99yr", "units": 1862},
    "clement_canopy": {"top_year": 2019, "tenure": "99yr", "units": 505},
    "harbour_view_gardens": {"top_year": 2021, "tenure": "99yr", "units": 59},
    "alexis": {"top_year": 2014, "tenure": "Freehold", "units": 293},
    "viva_vista": {"top_year": 2014, "tenure": "Freehold", "units": 259},
    "skysuites_anson": {"top_year": 2015, "tenure": "99yr", "units": 360},
    "avenue_south_residence": {"top_year": 2023, "tenure": "99yr", "units": 1074},
    "spottiswoode_suites": {"top_year": 2017, "tenure": "Freehold", "units": 183},
    "village_pasir_panjang": {"top_year": 2016, "tenure": "Freehold", "units": 148},
    "margaret_ville": {"top_year": 2021, "tenure": "99yr", "units": 309},
    "stirling_residences": {"top_year": 2022, "tenure": "99yr", "units": 1259},
    "queens_peak": {"top_year": 2020, "tenure": "99yr", "units": 700},
    "commonwealth_towers": {"top_year": 2017, "tenure": "99yr", "units": 845},
    "the_trilinq": {"top_year": 2017, "tenure": "99yr", "units": 755},
    "clavon": {"top_year": 2023, "tenure": "99yr", "units": 640},
    "artra": {"top_year": 2022, "tenure": "99yr", "units": 400},
    "kent_ridge_hill": {"top_year": 2025, "tenure": "99yr", "units": 548},
    "j_gateway": {"top_year": 2017, "tenure": "99yr", "units": 738},
    "whitehaven": {"top_year": 2017, "tenure": "Freehold", "units": 121},
    "caspian": {"top_year": 2008, "tenure": "99yr", "units": 712},
    "lakefront": {"top_year": 2010, "tenure": "99yr", "units": 629},
    "the_lakeshore": {"top_year": 2007, "tenure": "99yr", "units": 848},
}

REGISTRY_PATH = Path(__file__).resolve().parent / "data" / "srx_project_registry.json"


def load_registry_info() -> dict:
    if not REGISTRY_PATH.exists():
        return {}
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    projects = payload.get("projects", {})
    registry_info = {}
    for slug, item in projects.items():
        normalized = {}
        for key in ("top_year", "tenure", "units"):
            value = item.get(key)
            if value is not None:
                normalized[key] = value
        if normalized:
            registry_info[slug] = normalized
    return registry_info


PROJECT_INFO = {**BASE_PROJECT_INFO, **load_registry_info()}


def parse_monthyear(date_str: str) -> tuple[int, int]:
    """Parse MonthYear (e.g. Feb2026) and return (year, month)."""
    for month_abbr, month_num in MONTH_MAP.items():
        if date_str.startswith(month_abbr):
            return int(date_str[len(month_abbr):]), month_num
    raise ValueError(f"Cannot parse date: {date_str}")


def parse_year(date_str: str) -> str:
    """Parse MonthYear (e.g. Feb2026) and return year as string."""
    year, _ = parse_monthyear(date_str)
    return str(year)


def get_unit_type(sqft: float) -> str:
    """Classify unit by sqft: 1BR < 600, 2BR 600-849, 3BR 850-1199, 4BR+ >= 1200."""
    if sqft < 600:
        return "1BR"
    if sqft < 850:
        return "2BR"
    if sqft < 1200:
        return "3BR"
    return "4BR+"


def load_transactions(csv_path: Path) -> list[dict]:
    """Load transactions from CSV. Returns list of {year, sqft, psf, price, type}."""
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            date_value = r["date"].strip()
            year, month = parse_monthyear(date_value)
            sqft = int(r["sqft"])
            psf = int(r["psf"])
            price = int(r["price"])
            unit_type = get_unit_type(sqft)
            rows.append(
                {
                    "date": date_value,
                    "year": str(year),
                    "month": month,
                    "sqft": sqft,
                    "psf": psf,
                    "price": price,
                    "type": unit_type,
                }
            )
    return rows


def _quantile(sorted_list: list[float], q: float) -> float:
    """Compute quantile q (0-1) for sorted list. Uses linear interpolation."""
    if not sorted_list:
        return 0.0
    n = len(sorted_list)
    idx = (n - 1) * q
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    w = idx - lo
    return sorted_list[lo] * (1 - w) + sorted_list[hi] * w


def compute_annual_stats(transactions: list[dict], group_key: str, group_val: str | None = None) -> dict:
    """
    Group transactions by year (and optionally by unit type), compute box-plot stats.
    Returns: {"2018": {"median_psf": X, "q1": X, "q3": X, "min": X, "max": X, "count": N}, ...}
    """
    by_year: dict[str, list[int]] = {}
    for t in transactions:
        if group_key == "overall":
            include = True
        else:
            include = t["type"] == group_val
        if include:
            year = t["year"]
            if year not in by_year:
                by_year[year] = []
            by_year[year].append(t["psf"])

    result = {}
    for year in sorted(by_year.keys()):
        psf_list = sorted(by_year[year])
        n = len(psf_list)
        result[year] = {
            "median_psf": round(statistics.median(psf_list), 2),
            "q1": round(_quantile(psf_list, 0.25), 2),
            "q3": round(_quantile(psf_list, 0.75), 2),
            "min": min(psf_list),
            "max": max(psf_list),
            "count": n,
        }
    return result


def compute_cagr(annual_data: dict) -> float | None:
    """
    Compute CAGR from earliest to latest year with data.
    CAGR = (end/start)^(1/years) - 1, returned as percentage (e.g. 5.2 for 5.2%).
    """
    if len(annual_data) < 2:
        return None
    years = sorted(annual_data.keys())
    start_year, end_year = years[0], years[-1]
    start_psf = annual_data[start_year]["median_psf"]
    end_psf = annual_data[end_year]["median_psf"]
    if start_psf <= 0:
        return None
    num_years = int(end_year) - int(start_year)
    if num_years <= 0:
        return None
    cagr = (end_psf / start_psf) ** (1 / num_years) - 1
    return round(cagr * 100, 2)


def compute_cagr_over_month_span(
    annual_data: dict,
    start_period: tuple[int, int] | None,
    end_period: tuple[int, int] | None,
) -> float | None:
    """
    Compute CAGR using annual median PSF endpoints, but annualize over the
    exact month span between the earliest and latest available transactions.
    """
    if len(annual_data) < 2 or not start_period or not end_period:
        return None
    years = sorted(annual_data.keys())
    start_year, end_year = years[0], years[-1]
    start_psf = annual_data[start_year]["median_psf"]
    end_psf = annual_data[end_year]["median_psf"]
    if start_psf <= 0:
        return None
    month_span = (end_period[0] - start_period[0]) * 12 + (end_period[1] - start_period[1])
    if month_span < MIN_CAGR_MONTH_SPAN:
        return None
    cagr = (end_psf / start_psf) ** (12 / month_span) - 1
    return round(cagr * 100, 2)


def period_for_transactions(
    transactions: list[dict],
) -> tuple[dict | None, dict | None, tuple[int, int] | None, tuple[int, int] | None, int | None]:
    if not transactions:
        return None, None, None, None, None
    first_tx = min(transactions, key=lambda row: (int(row["year"]), row["month"], row["price"], row["sqft"]))
    latest_tx = max(transactions, key=lambda row: (int(row["year"]), row["month"], row["price"], row["sqft"]))
    start_period = (int(first_tx["year"]), first_tx["month"])
    end_period = (int(latest_tx["year"]), latest_tx["month"])
    month_span = (end_period[0] - start_period[0]) * 12 + (end_period[1] - start_period[1])
    return first_tx, latest_tx, start_period, end_period, month_span


def compute_annual_stats_filtered(transactions: list[dict], allowed_types: list[str]) -> dict:
    """Like compute_annual_stats but only includes transactions of specified types."""
    by_year: dict[str, list[int]] = {}
    for t in transactions:
        if t["type"] in allowed_types:
            year = t["year"]
            if year not in by_year:
                by_year[year] = []
            by_year[year].append(t["psf"])

    result = {}
    for year in sorted(by_year.keys()):
        psf_list = sorted(by_year[year])
        n = len(psf_list)
        result[year] = {
            "median_psf": round(statistics.median(psf_list), 2),
            "q1": round(_quantile(psf_list, 0.25), 2),
            "q3": round(_quantile(psf_list, 0.75), 2),
            "min": min(psf_list),
            "max": max(psf_list),
            "count": n,
        }
    return result


def analyze_project(name: str, transactions: list[dict]) -> dict:
    """Build full analysis structure for one project."""
    overall = compute_annual_stats(transactions, "overall")
    by_type = {
        "1BR": compute_annual_stats(transactions, "type", "1BR"),
        "2BR": compute_annual_stats(transactions, "type", "2BR"),
        "3BR": compute_annual_stats(transactions, "type", "3BR"),
        "4BR+": compute_annual_stats(transactions, "type", "4BR+"),
    }
    by_type = {k: v for k, v in by_type.items() if v}

    first_tx, latest_tx, start_period, end_period, month_span = period_for_transactions(transactions)
    overall_cagr = compute_cagr_over_month_span(
        overall,
        start_period,
        end_period,
    )
    by_type_cagr = {}
    by_type_period = {}
    for t, data in by_type.items():
        type_transactions = [row for row in transactions if row["type"] == t]
        type_first_tx, type_latest_tx, type_start_period, type_end_period, type_month_span = period_for_transactions(type_transactions)
        c = compute_cagr_over_month_span(data, type_start_period, type_end_period)
        if c is not None:
            by_type_cagr[t] = c
        if type_first_tx and type_latest_tx and type_month_span is not None:
            by_type_period[t] = {
                "start": type_first_tx["date"],
                "end": type_latest_tx["date"],
                "month_span": type_month_span,
            }

    # 2BR+3BR only analysis
    focus_transactions = [row for row in transactions if row["type"] in {"2BR", "3BR"}]
    only_23br = compute_annual_stats_filtered(transactions, ["2BR", "3BR"])
    focus_first_tx, focus_latest_tx, focus_start_period, focus_end_period, focus_month_span = period_for_transactions(focus_transactions)
    only_23br_cagr = compute_cagr_over_month_span(only_23br, focus_start_period, focus_end_period)

    info = PROJECT_INFO.get(name, {"top_year": None, "tenure": None, "units": None})

    return {
        "overall": overall,
        "by_type": by_type,
        "overall_cagr": overall_cagr,
        "overall_period": {
            "start": first_tx["date"],
            "end": latest_tx["date"],
            "month_span": month_span,
        },
        "by_type_cagr": by_type_cagr,
        "by_type_period": by_type_period,
        "only_23br": only_23br,
        "only_23br_cagr": only_23br_cagr,
        "only_23br_period": {
            "start": focus_first_tx["date"] if focus_first_tx else None,
            "end": focus_latest_tx["date"] if focus_latest_tx else None,
            "month_span": focus_month_span,
        },
        "info": info,
    }


def print_summary(project_name: str, data: dict):
    """Print human-readable summary to stdout."""
    print(f"\n{'='*60}")
    print(f"  {project_name.upper()}")
    print("=" * 60)

    print("\n--- Overall (all unit types) ---")
    overall = data["overall"]
    for year in sorted(overall.keys()):
        d = overall[year]
        print(f"  {year}: median PSF {d['median_psf']:,.0f} (Q1={d['q1']:,.0f}, Q3={d['q3']:,.0f}), "
              f"range [{d['min']:,.0f}-{d['max']:,.0f}], {d['count']} transactions")
    if data["overall_cagr"] is not None:
        print(f"  CAGR: {data['overall_cagr']}%")

    print("\n--- By unit type ---")
    for unit_type in ["1BR", "2BR", "3BR", "4BR+"]:
        if unit_type not in data["by_type"]:
            continue
        print(f"\n  {unit_type}:")
        for year in sorted(data["by_type"][unit_type].keys()):
            d = data["by_type"][unit_type][year]
            print(f"    {year}: median PSF {d['median_psf']:,.0f}, {d['count']} transactions")
        if unit_type in data["by_type_cagr"]:
            print(f"    CAGR: {data['by_type_cagr'][unit_type]}%")


def main():
    base = Path(__file__).resolve().parent
    data_dir = base / "data"

    project_configs = [
        (csv_path.name.replace("_transactions.csv", ""), csv_path.name)
        for csv_path in sorted(data_dir.glob("*_transactions.csv"))
    ]

    result = {}
    for key, csv_name in project_configs:
        csv_path = data_dir / csv_name
        if not csv_path.exists():
            print(f"Skipping {key}: {csv_name} not found")
            continue
        try:
            tx = load_transactions(csv_path)
            result[key] = analyze_project(key, tx)
        except Exception as e:
            print(f"Error loading {key}: {e}")
            continue

    out_path = data_dir / "appreciation_analysis.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Analysis written to {out_path} ({len(result)} projects)")

    for key, data in result.items():
        display_name = key.replace("_", " ").title()
        print_summary(display_name, data)


if __name__ == "__main__":
    main()
