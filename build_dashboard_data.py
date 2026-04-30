#!/usr/bin/env python3
"""
Build a single JSON payload for the dashboard from local crawled data files.

Sources:
- data/*_transactions.csv
- data/appreciation_analysis.json
- data/layout_mapping/*_transaction_layout_map.csv (preferred)
- data/layout_mapping/layout_reference_catalog.csv (preferred)
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from analyze import PROJECT_INFO


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
FORMAL_LAYOUT_DIR = DATA_DIR / "layout_mapping"
OUTPUT_PATH = DATA_DIR / "dashboard_data.json"
OUTPUT_JS_PATH = DATA_DIR / "dashboard_data.js"
ANALYSIS_PATH = DATA_DIR / "appreciation_analysis.json"
OFFICIAL_INDICES_PATH = DATA_DIR / "official_private_residential_indices.json"
FORMAL_REFERENCE_PATH = FORMAL_LAYOUT_DIR / "layout_reference_catalog.csv"
REGISTRY_PATH = DATA_DIR / "srx_project_registry.json"
URA_SUMMARY_PATH = DATA_DIR / "ura" / "projects_summary.json"
URA_INDEX_PATH = DATA_DIR / "ura" / "projects_index.json"

MONTH_TO_NUM = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}

MIN_CAGR_MONTH_SPAN = 12
BASE_MONTHS = 12
RECENT_WINDOW_MONTHS = 12
CONFIDENCE_WINDOW_MONTHS = 24
OWNER_POOL_BUCKETS = ("2b1b", "2b2b")
OWNER_POOL_DIRECT_2B2B_MIN_COUNT = 18
OWNER_POOL_DIRECT_MIN_COUNT = 24
OWNER_POOL_PROXY_MIN_COUNT = 24
SCORE_WEIGHTS = {
    "entry": 0.55,
    "trend": 0.45,
}

DISPLAY_NAME = {
    "alexis": "Alexis",
    "artra": "Artra",
    "avenue_south_residence": "Avenue South Residence",
    "caspian": "Caspian",
    "clavon": "Clavon",
    "clement_canopy": "Clement Canopy",
    "commonwealth_towers": "Commonwealth Towers",
    "harbour_view_gardens": "Harbour View Gardens",
    "hundred_trees": "Hundred Trees",
    "j_gateway": "J Gateway",
    "kent_ridge_hill": "Kent Ridge Hill Residences",
    "lakefront": "Lakefront Residences",
    "lakegrande": "Lake Grande",
    "lakeville": "Lakeville",
    "margaret_ville": "Margaret Ville",
    "normanton_park": "Normanton Park",
    "parc_clematis": "Parc Clematis",
    "parc_riviera": "Parc Riviera",
    "queens_peak": "Queens Peak",
    "seahill": "Seahill",
    "skysuites_anson": "Skysuites@Anson",
    "spottiswoode_suites": "Spottiswoode Suites",
    "stirling_residences": "Stirling Residences",
    "the_trilinq": "The Trilinq",
    "the_vision": "The Vision",
    "twin_vew": "Twin Vew",
    "village_pasir_panjang": "Village @ Pasir Panjang",
    "viva_vista": "Viva Vista",
    "whitehaven": "Whitehaven",
    "whistler_grand": "Whistler Grand",
    "the_lakeshore": "The Lakeshore",
}

REGION_GROUP = {
    "lakeville": "Lakeside / West",
    "lakegrande": "Lakeside / West",
    "seahill": "West / Pasir Panjang",
    "the_vision": "West / Pasir Panjang",
    "hundred_trees": "West / Clementi",
    "parc_clematis": "West / Clementi",
    "twin_vew": "West / West Coast",
    "parc_riviera": "West / Pasir Panjang",
    "whistler_grand": "West / West Coast",
    "normanton_park": "Pasir Panjang / RCR edge",
    "clement_canopy": "West / Clementi",
    "harbour_view_gardens": "HarbourFront / RCR",
    "alexis": "Queenstown / RCR",
    "viva_vista": "Pasir Panjang / RCR edge",
    "skysuites_anson": "CBD / RCR",
    "avenue_south_residence": "GSW / RCR",
    "spottiswoode_suites": "CBD fringe / RCR",
    "village_pasir_panjang": "Pasir Panjang / RCR edge",
    "margaret_ville": "Queenstown / RCR",
    "stirling_residences": "Queenstown / RCR",
    "queens_peak": "Queenstown / RCR",
    "commonwealth_towers": "Queenstown / RCR",
    "the_trilinq": "West / Clementi",
    "clavon": "West / Clementi",
    "artra": "Redhill / RCR",
    "kent_ridge_hill": "Kent Ridge / RCR edge",
    "j_gateway": "Jurong East / West",
    "whitehaven": "Pasir Panjang / RCR edge",
    "caspian": "Lakeside / West",
    "lakefront": "Lakeside / West",
    "the_lakeshore": "Lakeside / West",
}


def load_project_registry() -> dict[str, dict]:
    if not REGISTRY_PATH.exists():
        return {}
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    projects = payload.get("projects", {})
    return projects if isinstance(projects, dict) else {}


PROJECT_REGISTRY = load_project_registry()


def load_optional_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_key(value: str) -> str:
    return "".join(char for char in value.lower() if char.isalnum())

FOCUS_ORDER = ["small", "2b1b", "2b2b", "3b2b", "large", "pending"]
FOCUS_LABEL = {
    "small": "小户型",
    "2b1b": "2b1b",
    "2b2b": "2b2b",
    "3b2b": "3b2b",
    "large": "大户型",
    "pending": "待确认",
}
AREA_PROXY_ORDER = ["2b1b", "2b2b", "3b2b"]
AREA_PROXY_RANGES = {
    "2b1b": {"min_sqft": 600, "max_sqft": 699},
    "2b2b": {"min_sqft": 700, "max_sqft": 849},
    "3b2b": {"min_sqft": 850, "max_sqft": 1199},
}
LISTING_BUCKET_TO_TYPE_LABEL = {
    "2b1b": "2BR",
    "2b2b": "2BR",
    "3b2b": "3BR",
}


def parse_monthyear(value: str) -> tuple[int, int]:
    month = value[:3]
    year = int(value[3:])
    return year, MONTH_TO_NUM[month]


def format_monthyear(value: str) -> str:
    year, month = parse_monthyear(value)
    month_abbr = [abbr for abbr, num in MONTH_TO_NUM.items() if num == month][0]
    return f"{month_abbr} {year}"


def sort_monthyear_key(value: str) -> tuple[int, int]:
    return parse_monthyear(value)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_optional_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return load_json(path)


def parse_quarter_label(value: str) -> tuple[int, int]:
    year_str, quarter_str = value.split("-Q", 1)
    return int(year_str), int(quarter_str)


def quarter_sort_key_data_gov(value: str) -> tuple[int, int]:
    return parse_quarter_label(value)


def median_or_none(values: list[int]) -> float | None:
    if not values:
        return None
    return round(float(statistics.median(values)), 2)


def compute_annual_stats_from_rows(rows: list[dict]) -> dict[str, dict]:
    by_year: dict[str, list[int]] = {}
    for row in rows:
        year = str(row["year"])
        by_year.setdefault(year, []).append(int(row["psf"]))

    result: dict[str, dict] = {}
    for year in sorted(by_year.keys()):
        psf_values = sorted(by_year[year])
        result[year] = {
            "median_psf": round(float(statistics.median(psf_values)), 2),
            "count": len(psf_values),
        }
    return result


def compute_monthly_stats_from_rows(rows: list[dict]) -> dict[str, dict]:
    by_month: dict[str, list[int]] = {}
    for row in rows:
        key = f"{row['year']}-{row['month']:02d}"
        by_month.setdefault(key, []).append(int(row["psf"]))
    result: dict[str, dict] = {}
    for key in sorted(by_month.keys()):
        psf_values = sorted(by_month[key])
        result[key] = {
            "median_psf": round(float(statistics.median(psf_values)), 2),
            "count": len(psf_values),
        }
    return result


def compute_cagr_from_annual(annual_data: dict[str, dict]) -> float | None:
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


def month_span_between(start_period: tuple[int, int], end_period: tuple[int, int]) -> int:
    return (end_period[0] - start_period[0]) * 12 + (end_period[1] - start_period[1])


def compute_cagr_from_annual_over_month_span(
    annual_data: dict[str, dict],
    start_period: tuple[int, int],
    end_period: tuple[int, int],
) -> float | None:
    if len(annual_data) < 2:
        return None
    start_psf = annual_data[min(annual_data.keys())]["median_psf"]
    end_psf = annual_data[max(annual_data.keys())]["median_psf"]
    if start_psf <= 0:
        return None
    month_span = month_span_between(start_period, end_period)
    if month_span < MIN_CAGR_MONTH_SPAN:
        return None
    cagr = (end_psf / start_psf) ** (12 / month_span) - 1
    return round(cagr * 100, 2)


def _add_months(ym: tuple[int, int], n: int) -> tuple[int, int]:
    y, m = ym
    total = (y * 12 + m - 1) + n
    return total // 12, total % 12 + 1


def _ym_to_key(ym: tuple[int, int]) -> str:
    return f"{ym[0]}-{ym[1]:02d}"


def _key_to_ym(key: str) -> tuple[int, int]:
    parts = key.split("-")
    return int(parts[0]), int(parts[1])


def compute_base_psf(
    rows: list[dict], n_months: int = BASE_MONTHS
) -> tuple[float | None, str | None]:
    """Median PSF of transactions in the first *n_months*.

    Returns (base_psf, start_month_key).
    """
    if not rows:
        return None, None
    first_row = min(rows, key=lambda r: (r["year"], r["month"]))
    start_ym = (first_row["year"], first_row["month"])
    cutoff_ym = _add_months(start_ym, n_months)
    base_rows = [r for r in rows if (r["year"], r["month"]) < cutoff_ym]
    if not base_rows:
        return None, None
    return round(float(statistics.median([r["psf"] for r in base_rows])), 2), _ym_to_key(start_ym)


def compute_ttm_monthly(rows: list[dict]) -> dict[str, dict]:
    """TTM (trailing 12-month) median PSF for each month in the data range.

    Returns ``{YYYY-MM: {"median_psf": float, "count": int}}``.
    """
    if not rows:
        return {}
    by_month: dict[tuple[int, int], list[int]] = {}
    for row in rows:
        ym = (row["year"], row["month"])
        by_month.setdefault(ym, []).append(int(row["psf"]))

    all_yms = sorted(by_month.keys())
    first_ym, last_ym = all_yms[0], all_yms[-1]

    result: dict[str, dict] = {}
    current = first_ym
    while current <= last_ym:
        window_start = _add_months(current, -11)
        psf_values: list[int] = []
        scan = window_start
        while scan <= current:
            psf_values.extend(by_month.get(scan, []))
            scan = _add_months(scan, 1)
        if psf_values:
            result[_ym_to_key(current)] = {
                "median_psf": round(float(statistics.median(psf_values)), 2),
                "count": len(psf_values),
            }
        current = _add_months(current, 1)
    return result


def compute_cagr_from_base_ttm(
    base_psf: float | None,
    ttm_monthly: dict[str, dict],
    start_month_key: str | None,
) -> float | None:
    """CAGR using base PSF vs the last TTM month.

    ``span = M - BASE_MONTHS`` where *M* is the month offset from the start.
    """
    if not ttm_monthly or base_psf is None or base_psf <= 0 or not start_month_key:
        return None
    last_key = max(ttm_monthly.keys())
    last_psf = ttm_monthly[last_key]["median_psf"]
    m = month_span_between(_key_to_ym(start_month_key), _key_to_ym(last_key))
    span = m - BASE_MONTHS
    if span < MIN_CAGR_MONTH_SPAN:
        return None
    cagr = (last_psf / base_psf) ** (12 / span) - 1
    return round(cagr * 100, 2)


def build_bucket_metrics(
    rows: list[dict],
    bucket_order: list[str],
    bucket_getter,
) -> dict[str, dict]:
    metrics: dict[str, dict] = {}
    for bucket in bucket_order:
        bucket_rows = [row for row in rows if bucket_getter(row) == bucket]
        if not bucket_rows:
            continue
        annual = compute_annual_stats_from_rows(bucket_rows)
        monthly = compute_monthly_stats_from_rows(bucket_rows)
        years = sorted(annual.keys())
        latest_year = years[-1] if years else None
        latest_data = annual.get(latest_year, {}) if latest_year else {}
        first_row, latest_row, month_span = row_period_bounds(bucket_rows)
        base_psf, base_start = compute_base_psf(bucket_rows)
        ttm_monthly = compute_ttm_monthly(bucket_rows)
        cagr = compute_cagr_from_base_ttm(base_psf, ttm_monthly, base_start)
        cagr_monthly = compute_cagr_monthly(base_psf, ttm_monthly, base_start)
        rolling_3y_cagr_monthly = compute_rolling_3y_cagr_monthly(ttm_monthly)
        yoy_monthly = compute_yoy_monthly(ttm_monthly)
        metrics[bucket] = {
            "count": len(bucket_rows),
            "year_count": len(years),
            "year_range": year_range_label(years),
            "annual": annual,
            "monthly": monthly,
            "cagr": cagr,
            "all_time_cagr": cagr,
            "current_yoy": yoy_monthly[max(yoy_monthly.keys())] if yoy_monthly else compute_current_yoy(ttm_monthly),
            "base_psf": base_psf,
            "base_start": base_start,
            "ttm_monthly": ttm_monthly,
            "cagr_monthly": cagr_monthly,
            "rolling_3y_cagr_monthly": rolling_3y_cagr_monthly,
            "yoy_monthly": yoy_monthly,
            "latest_year": latest_year,
            "latest_psf": latest_data.get("median_psf"),
            "latest_n": latest_data.get("count"),
            "period_months": month_span,
            "period_label": period_label_for_rows(bucket_rows),
        }
    return metrics


def rows_in_last_n_months(
    rows: list[dict],
    n_months: int,
    anchor_ym: tuple[int, int] | None = None,
) -> list[dict]:
    if not rows:
        return []
    if anchor_ym is None:
        latest_row = max(rows, key=lambda row: (row["year"], row["month"], row["price"], row["sqft"]))
        anchor_ym = (latest_row["year"], latest_row["month"])
    start_ym = _add_months(anchor_ym, -(n_months - 1))
    return [
        row for row in rows
        if start_ym <= (row["year"], row["month"]) <= anchor_ym
    ]


def normalize_metric_key(label: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in label.lower()).strip("_")


def compute_period_cagr(rows: list[dict], period_years: int) -> float | None:
    if not rows:
        return None
    latest_row = max(rows, key=lambda row: (row["year"], row["month"], row["price"], row["sqft"]))
    anchor_ym = (latest_row["year"], latest_row["month"])
    subset = rows_in_last_n_months(rows, period_years * 12, anchor_ym)
    if not subset:
        return None
    base_psf, base_start = compute_base_psf(subset)
    ttm_monthly = compute_ttm_monthly(subset)
    return compute_cagr_from_base_ttm(base_psf, ttm_monthly, base_start)


def compute_current_yoy(ttm_monthly: dict[str, dict]) -> float | None:
    if not ttm_monthly:
        return None
    last_key = max(ttm_monthly.keys())
    prior_key = _ym_to_key(_add_months(_key_to_ym(last_key), -12))
    current_entry = ttm_monthly.get(last_key)
    prior_entry = ttm_monthly.get(prior_key)
    if not current_entry or not prior_entry:
        return None
    current_psf = current_entry.get("median_psf")
    prior_psf = prior_entry.get("median_psf")
    if current_psf is None or prior_psf in (None, 0):
        return None
    return round((current_psf / prior_psf - 1) * 100, 2)


def compute_cagr_monthly(
    base_psf: float | None,
    ttm_monthly: dict[str, dict],
    start_month_key: str | None,
) -> dict[str, float]:
    if not ttm_monthly or base_psf is None or base_psf <= 0 or not start_month_key:
        return {}
    result: dict[str, float] = {}
    for month_key in sorted(ttm_monthly.keys()):
        entry = ttm_monthly.get(month_key)
        if not entry:
            continue
        cagr = compute_cagr_from_base_ttm(base_psf, {month_key: entry}, start_month_key)
        if cagr is None:
            month_span = month_span_between(_key_to_ym(start_month_key), _key_to_ym(month_key))
            span = month_span - BASE_MONTHS
            if span < MIN_CAGR_MONTH_SPAN:
                continue
            current_psf = entry.get("median_psf")
            if current_psf is None or current_psf <= 0:
                continue
            cagr = round(((current_psf / base_psf) ** (12 / span) - 1) * 100, 2)
        result[month_key] = cagr
    return result


def compute_yoy_monthly(ttm_monthly: dict[str, dict]) -> dict[str, float]:
    if not ttm_monthly:
        return {}
    result: dict[str, float] = {}
    for month_key in sorted(ttm_monthly.keys()):
        current_entry = ttm_monthly.get(month_key)
        prior_key = _ym_to_key(_add_months(_key_to_ym(month_key), -12))
        prior_entry = ttm_monthly.get(prior_key)
        if not current_entry or not prior_entry:
            continue
        current_psf = current_entry.get("median_psf")
        prior_psf = prior_entry.get("median_psf")
        if current_psf is None or prior_psf in (None, 0):
            continue
        result[month_key] = round((current_psf / prior_psf - 1) * 100, 2)
    return result


def compute_rolling_3y_cagr_monthly(ttm_monthly: dict[str, dict]) -> dict[str, float]:
    if not ttm_monthly:
        return {}
    result: dict[str, float] = {}
    for month_key in sorted(ttm_monthly.keys()):
        current_entry = ttm_monthly.get(month_key)
        prior_key = _ym_to_key(_add_months(_key_to_ym(month_key), -36))
        prior_entry = ttm_monthly.get(prior_key)
        if not current_entry or not prior_entry:
            continue
        current_psf = current_entry.get("median_psf")
        prior_psf = prior_entry.get("median_psf")
        if current_psf is None or current_psf <= 0 or prior_psf is None or prior_psf <= 0:
            continue
        result[month_key] = round(((current_psf / prior_psf) ** (1 / 3) - 1) * 100, 2)
    return result


def summarize_row_set(rows: list[dict], provenance: str, label: str) -> dict:
    annual = compute_annual_stats_from_rows(rows)
    monthly = compute_monthly_stats_from_rows(rows)
    years = sorted(annual.keys())
    latest_year = years[-1] if years else None
    latest_year_data = annual.get(latest_year, {}) if latest_year else {}
    first_row, latest_row, month_span = row_period_bounds(rows)
    base_psf, base_start = compute_base_psf(rows)
    ttm_monthly = compute_ttm_monthly(rows)
    lifetime_cagr = compute_cagr_from_base_ttm(base_psf, ttm_monthly, base_start)
    cagr_monthly = compute_cagr_monthly(base_psf, ttm_monthly, base_start)
    rolling_3y_cagr_monthly = compute_rolling_3y_cagr_monthly(ttm_monthly)
    yoy_monthly = compute_yoy_monthly(ttm_monthly)

    current = None
    recent_24m_count = 0
    if latest_row:
        anchor_ym = (latest_row["year"], latest_row["month"])
        current_rows = rows_in_last_n_months(rows, RECENT_WINDOW_MONTHS, anchor_ym)
        recent_24m_rows = rows_in_last_n_months(rows, CONFIDENCE_WINDOW_MONTHS, anchor_ym)
        recent_24m_count = len(recent_24m_rows)
        if current_rows:
            current_prices = [row["price"] for row in current_rows]
            current_psf = [row["psf"] for row in current_rows]
            current = {
                "start_month": current_rows[-1]["date_label"],
                "end_month": current_rows[0]["date_label"],
                "median_price": round(float(statistics.median(current_prices)), 2),
                "median_psf": round(float(statistics.median(current_psf)), 2),
                "count": len(current_rows),
            }

    return {
        "key": normalize_metric_key(label),
        "label": label,
        "provenance": provenance,
        "count": len(rows),
        "year_count": len(years),
        "year_range": year_range_label(years),
        "period_months": month_span,
        "period_label": period_label_for_rows(rows),
        "annual": annual,
        "monthly": monthly,
        "base_psf": base_psf,
        "base_start": base_start,
        "ttm_monthly": ttm_monthly,
        "cagr_monthly": cagr_monthly,
        "rolling_3y_cagr_monthly": rolling_3y_cagr_monthly,
        "yoy_monthly": yoy_monthly,
        "lifetime_cagr": lifetime_cagr,
        "all_time_cagr": lifetime_cagr,
        "current_yoy": yoy_monthly[max(yoy_monthly.keys())] if yoy_monthly else compute_current_yoy(ttm_monthly),
        "cagr_3y": compute_period_cagr(rows, 3),
        "cagr_5y": compute_period_cagr(rows, 5),
        "latest_year": latest_year,
        "latest_year_psf": latest_year_data.get("median_psf"),
        "latest_year_count": latest_year_data.get("count"),
        "current": current,
        "recent_24m_count": recent_24m_count,
    }


def metric_is_qualified(metric: dict, min_count: int) -> bool:
    return (
        bool(metric)
        and metric.get("count", 0) >= min_count
        and (metric.get("period_months") or 0) >= 24
        and (metric.get("recent_24m_count") or 0) >= 4
        and metric.get("current") is not None
    )


def metric_current_psf(metric: dict) -> float | None:
    current = metric.get("current") if metric else None
    if not current:
        return None
    return current.get("median_psf")


def build_metric_snapshot(metric: dict) -> dict:
    return {
        "current_psf": metric_current_psf(metric),
        "all_time_cagr": metric.get("all_time_cagr"),
        "current_yoy": metric.get("current_yoy"),
        "recent_24m_count": metric.get("recent_24m_count"),
        "sample_count": metric.get("count"),
        "cagr_monthly": metric.get("cagr_monthly", {}),
        "rolling_3y_cagr_monthly": metric.get("rolling_3y_cagr_monthly", {}),
        "yoy_monthly": metric.get("yoy_monthly", {}),
    }


def select_owner_pool_metric(
    direct_2b2b: dict,
    owner_pool_direct: dict,
    area_proxy_owner_pool: dict,
    overall_reference: dict,
) -> dict:
    if metric_is_qualified(direct_2b2b, OWNER_POOL_DIRECT_2B2B_MIN_COUNT):
        return direct_2b2b
    if metric_is_qualified(owner_pool_direct, OWNER_POOL_DIRECT_MIN_COUNT):
        return owner_pool_direct
    if metric_is_qualified(area_proxy_owner_pool, OWNER_POOL_PROXY_MIN_COUNT):
        return area_proxy_owner_pool
    return overall_reference


def percentile_position(value: float | None, samples: list[float]) -> float | None:
    clean = sorted(sample for sample in samples if sample is not None)
    if value is None or not clean:
        return None
    if len(clean) == 1:
        return 0.5
    less_or_equal = sum(sample <= value for sample in clean)
    return (less_or_equal - 1) / (len(clean) - 1)


def average_or_none(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return round(sum(clean) / len(clean), 2)


def confidence_label(score: float) -> str:
    if score >= 75:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def year_range_label(years: list[str]) -> str:
    if not years:
        return "-"
    if len(years) == 1:
        return f"{years[0]} only"
    return f"{years[0]}-{years[-1]}"


def month_span_label(month_span: int) -> str:
    if month_span <= 0:
        return "-"
    return f"{month_span}个月"


def row_period_bounds(rows: list[dict]) -> tuple[dict | None, dict | None, int | None]:
    if not rows:
        return None, None, None
    first_row = min(rows, key=lambda row: (row["year"], row["month"], row["price"], row["sqft"]))
    latest_row = max(rows, key=lambda row: (row["year"], row["month"], row["price"], row["sqft"]))
    month_span = month_span_between(
        (first_row["year"], first_row["month"]),
        (latest_row["year"], latest_row["month"]),
    )
    return first_row, latest_row, month_span


def period_label_for_rows(rows: list[dict]) -> str:
    first_row, latest_row, month_span = row_period_bounds(rows)
    if not first_row or not latest_row or month_span is None:
        return "-"
    return f"{first_row['date_label']} → {latest_row['date_label']} · {month_span_label(month_span)}"


def slug_to_name(slug: str) -> str:
    if slug in PROJECT_REGISTRY and PROJECT_REGISTRY[slug].get("name"):
        return PROJECT_REGISTRY[slug]["name"]
    return DISPLAY_NAME.get(slug, slug.replace("_", " ").title())


def load_transaction_rows(csv_path: Path) -> list[dict]:
    rows: list[dict] = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            year, month = parse_monthyear(row["date"])
            rows.append(
                {
                    "date": row["date"],
                    "date_label": format_monthyear(row["date"]),
                    "year": year,
                    "month": month,
                    "sqft": int(row["sqft"]),
                    "psf": int(row["psf"]),
                    "price": int(row["price"]),
                }
            )
    rows.sort(key=lambda row: (row["year"], row["month"], row["price"], row["sqft"]), reverse=True)
    return rows


def normalize_source_entries(primary_source: dict, secondary_sources: list[dict] | None = None) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    entries: list[dict] = []
    for item in [primary_source, *(secondary_sources or [])]:
        source_kind = str(item.get("source_kind", ""))
        source_csv = str(item.get("source_csv", ""))
        if source_kind == "srx_csv" and source_csv and "/" not in source_csv:
            source_csv = f"srx/{source_csv}"
        source_label = item.get("source_label")
        source_url = str(item.get("source_url", ""))
        key = (source_kind, source_csv, source_url)
        if key in seen:
            continue
        seen.add(key)
        entries.append(
            {
                "source_kind": source_kind,
                "source_label": source_label,
                "source_url": item.get("source_url"),
                "source_csv": source_csv,
                "record_count": item.get("record_count"),
            }
        )
    return entries


def has_source_kind(summary: dict, source_kind: str) -> bool:
    if summary.get("source_kind") == source_kind:
        return True
    return has_secondary_source_kind(summary, source_kind)


def has_secondary_source_kind(summary: dict, source_kind: str) -> bool:
    return any(source.get("source_kind") == source_kind for source in summary.get("secondary_sources", []))


def detect_layout_mapping_source() -> str:
    if FORMAL_REFERENCE_PATH.exists():
        return "formal"
    return "missing"


def parse_layout_options(value: str) -> list[str]:
    options: list[str] = []
    for part in (value or "").split("|"):
        cleaned = part.strip()
        if not cleaned:
            continue
        options.append(cleaned.split(" ", 1)[0].strip())
    return options


def load_layout_catalogs() -> dict[str, list[dict]]:
    if FORMAL_REFERENCE_PATH.exists():
        catalogs: dict[str, list[dict]] = {}
        with FORMAL_REFERENCE_PATH.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                row["reference_area_sqft"] = int(row["reference_area_sqft"])
                catalogs.setdefault(row["project_slug"], []).append(row)
        return catalogs
    return {}


def bucket_from_normalized_type(normalized_type: str) -> str:
    if normalized_type in {"studio1b", "1b1b"}:
        return "small"
    if normalized_type == "2b1b":
        return "2b1b"
    if normalized_type == "2b2b":
        return "2b2b"
    if normalized_type == "3b2b":
        return "3b2b"
    return "large"


def infer_focus_bucket(mapping_row: dict, catalog_rows: list[dict]) -> tuple[str, str]:
    status = mapping_row["mapping_status"]
    sqft = int(mapping_row["sqft"])

    if status == "matched" and mapping_row.get("resolved_layout"):
        return bucket_from_normalized_type(mapping_row["resolved_layout"]), "direct_match"

    if status == "ambiguous":
        candidate_types = parse_layout_options(mapping_row.get("layout_options", ""))
        buckets = {bucket_from_normalized_type(layout_type) for layout_type in candidate_types if layout_type}
        if len(buckets) == 1:
            return next(iter(buckets)), "ambiguous_same_bucket"
        return "pending", "ambiguous_multi_bucket"

    ref_candidates = []
    for ref in catalog_rows:
        gap = abs(int(ref["reference_area_sqft"]) - sqft)
        layout_options = [ref.get("resolved_layout")] if ref.get("resolved_layout") else parse_layout_options(ref.get("layout_options", ""))
        buckets = {bucket_from_normalized_type(layout_type) for layout_type in layout_options if layout_type}
        if len(buckets) == 1:
            ref_candidates.append((gap, next(iter(buckets))))
    ref_candidates.sort(key=lambda item: item[0])

    if ref_candidates:
        min_gap = ref_candidates[0][0]
        nearby = [bucket for gap, bucket in ref_candidates if gap <= min_gap + 12 and gap <= 25]
        if nearby and len(set(nearby)) == 1:
            return nearby[0], "nearest_same_bucket"

    if sqft < 600:
        return "small", "boundary_small"
    if sqft > 1200:
        return "large", "boundary_large"
    return "pending", "needs_more_layout_data"


def infer_area_proxy_bucket(sqft: int) -> str | None:
    for bucket in AREA_PROXY_ORDER:
        bounds = AREA_PROXY_RANGES[bucket]
        if bounds["min_sqft"] <= sqft <= bounds["max_sqft"]:
            return bucket
    return None


def load_focus_mapping_rows(slug: str, catalog_rows: list[dict]) -> list[dict]:
    formal_csv_path = FORMAL_LAYOUT_DIR / f"{slug}_transaction_layout_map.csv"
    rows: list[dict] = []

    if not formal_csv_path.exists():
        return rows

    with formal_csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            bucket, bucket_reason = infer_focus_bucket(row, catalog_rows)
            rows.append(
                {
                    "date": row["date"],
                    "date_label": format_monthyear(row["date"]),
                    "year": parse_monthyear(row["date"])[0],
                    "month": parse_monthyear(row["date"])[1],
                    "sqft": int(row["sqft"]),
                    "psf": int(row["psf"]),
                    "price": int(row["price"]),
                    "mapping_status": row["mapping_status"],
                    "resolved_layout": row["resolved_layout"],
                    "layout_options": row["layout_options"] or row["resolved_layout"],
                    "focus_bucket": bucket,
                    "focus_bucket_label": FOCUS_LABEL[bucket],
                    "bucket_reason": bucket_reason,
                    "mapping_confidence": row["mapping_confidence"],
                    "evidence_urls": row["evidence_urls"],
                    "evidence_notes": row["evidence_notes"],
                }
            )
    rows.sort(key=lambda row: (row["year"], row["month"], row["price"], row["sqft"]), reverse=True)
    return rows


def build_focus_project(slug: str, catalog_by_project: dict[str, list[dict]]) -> dict:
    rows = load_focus_mapping_rows(slug, catalog_by_project.get(slug, []))
    registry_info = PROJECT_REGISTRY.get(slug, {})
    info = {**PROJECT_INFO.get(slug, {}), **registry_info}

    summary = []
    recent_by_bucket: dict[str, list[dict]] = {}
    annual_by_bucket: dict[str, dict] = {}
    for bucket in FOCUS_ORDER:
        bucket_rows = [row for row in rows if row["focus_bucket"] == bucket]
        recent_rows = bucket_rows[:8]
        if bucket_rows:
            annual = compute_annual_stats_from_rows(bucket_rows)
            annual_by_bucket[bucket] = annual
            summary.append(
                {
                    "bucket": bucket,
                    "label": FOCUS_LABEL[bucket],
                    "count": len(bucket_rows),
                    "median_psf": median_or_none([row["psf"] for row in bucket_rows]),
                    "median_price": median_or_none([row["price"] for row in bucket_rows]),
                    "latest_date": recent_rows[0]["date_label"],
                    "latest_psf": recent_rows[0]["psf"],
                    "latest_price": recent_rows[0]["price"],
                }
            )
            recent_by_bucket[bucket] = [
                {
                    "date_label": row["date_label"],
                    "sqft": row["sqft"],
                    "price": row["price"],
                    "psf": row["psf"],
                    "mapping_status": row["mapping_status"],
                    "resolved_layout": row["resolved_layout"],
                    "layout_options": row["layout_options"],
                    "bucket_reason": row["bucket_reason"],
                }
                for row in recent_rows
            ]

    typed_bucket_metrics = build_bucket_metrics(
        rows,
        AREA_PROXY_ORDER,
        lambda row: row["focus_bucket"],
    )

    mapped_rows = [row for row in rows if row["mapping_status"] == "matched"]
    focus_rows = [row for row in rows if row["focus_bucket"] in {"2b1b", "2b2b", "3b2b"}]
    owner_pool_direct_rows = [row for row in rows if row["focus_bucket"] in OWNER_POOL_BUCKETS]
    owner_pool_2b2b_rows = [row for row in rows if row["focus_bucket"] == "2b2b"]

    type_breakout = {
        bucket: summarize_row_set(
            [row for row in rows if row["focus_bucket"] == bucket],
            provenance=f"direct_{bucket}",
            label=bucket,
        )
        for bucket in OWNER_POOL_BUCKETS
    }
    owner_pool_direct = summarize_row_set(
        owner_pool_direct_rows,
        provenance="direct_owner_pool",
        label="自住池(2b1b+2b2b)",
    )
    owner_pool_area_proxy = owner_pool_direct
    owner_pool_2b2b = summarize_row_set(
        owner_pool_2b2b_rows,
        provenance="direct_2b2b",
        label="2b2b",
    )

    provenance = select_owner_pool_metric(
        owner_pool_2b2b,
        owner_pool_direct,
        owner_pool_direct,
        owner_pool_direct,
    )
    confidence_score = round(
        min(100.0, (len(mapped_rows) / len(rows) * 100 if rows else 0.0) * 0.7 + min(owner_pool_direct.get("recent_24m_count", 0) * 4, 30)),
        1,
    )

    return {
        "slug": slug,
        "name": slug_to_name(slug),
        "region_group": registry_info.get("region_group", REGION_GROUP.get(slug, "Other")),
        "top_year": info.get("top_year"),
        "tenure": info.get("tenure"),
        "units": info.get("units"),
        "row_count": len(rows),
        "matched_count": len(mapped_rows),
        "focus_count": len(focus_rows),
        "coverage_pct": round(len(mapped_rows) / len(rows) * 100, 1) if rows else 0.0,
        "focus_summary": summary,
        "annual_by_bucket": annual_by_bucket,
        "typed_bucket_metrics": typed_bucket_metrics,
        "recent_by_bucket": recent_by_bucket,
        "owner_pool_direct": owner_pool_direct,
        "owner_pool_area_proxy": owner_pool_area_proxy,
        "owner_pool_filled": provenance,
        "type_breakout": type_breakout,
        "overall_reference": summarize_row_set(rows, provenance="overall_reference", label="全项目"),
        "data_confidence": {
            "coverage_pct": round(len(mapped_rows) / len(rows) * 100, 1) if rows else 0.0,
            "recent_24m_count": owner_pool_direct.get("recent_24m_count", 0),
            "score": confidence_score,
            "label": confidence_label(confidence_score),
            "provenance": provenance.get("provenance"),
        },
    }


def build_project_summary(slug: str, analysis: dict, rows: list[dict]) -> dict:
    size_counts = Counter(row["sqft"] for row in rows)
    first_row = min(rows, key=lambda row: (row["year"], row["month"], row["price"], row["sqft"]))
    latest_row = max(rows, key=lambda row: (row["year"], row["month"], row["price"], row["sqft"]))
    registry_info = PROJECT_REGISTRY.get(slug, {})
    info = {**PROJECT_INFO.get(slug, {}), **registry_info}
    source_csv = f"{slug}_transactions.csv"
    source_kind = registry_info.get("source_kind", "propertyforsale_csv")
    source_label = registry_info.get("source_label", "propertyforsale.com.sg resale CSV")
    source_url = registry_info.get("source_url")
    secondary_sources = registry_info.get("secondary_sources", [])
    if not isinstance(secondary_sources, list):
        secondary_sources = []
    all_sources = normalize_source_entries(
        {
            "source_kind": source_kind,
            "source_label": source_label,
            "source_url": source_url,
            "source_csv": source_csv,
            "record_count": len(rows),
        },
        secondary_sources,
    )
    overall = compute_annual_stats_from_rows(rows)
    overall_monthly = compute_monthly_stats_from_rows(rows)
    overall_years = sorted(overall.keys())
    latest_overall_year = overall_years[-1] if overall_years else None
    latest_overall = overall.get(latest_overall_year, {}) if latest_overall_year else {}
    overall_month_span = month_span_between(
        (first_row["year"], first_row["month"]),
        (latest_row["year"], latest_row["month"]),
    )
    overall_period_label = period_label_for_rows(rows)
    overall_base_psf, overall_base_start = compute_base_psf(rows)
    overall_ttm_monthly = compute_ttm_monthly(rows)
    overall_cagr = compute_cagr_from_base_ttm(
        overall_base_psf, overall_ttm_monthly, overall_base_start,
    )
    overall_pk_included = len(overall_years) >= 2 and overall_cagr is not None
    public_window_pk_included = source_kind == "propertyforsale_csv" and overall_pk_included
    focus_rows = [row for row in rows if infer_area_proxy_bucket(row["sqft"]) is not None]
    owner_pool_proxy_rows = [row for row in rows if infer_area_proxy_bucket(row["sqft"]) in OWNER_POOL_BUCKETS]
    focus_annual = compute_annual_stats_from_rows(focus_rows)
    focus_years = sorted(focus_annual.keys())
    latest_focus_year = max(focus_annual.keys()) if focus_annual else None
    latest_focus = focus_annual.get(latest_focus_year, {}) if latest_focus_year else {}
    focus_first_row, focus_latest_row, focus_month_span = row_period_bounds(focus_rows)
    focus_period_label = period_label_for_rows(focus_rows)
    focus_base_psf, focus_base_start = compute_base_psf(focus_rows)
    focus_ttm_monthly = compute_ttm_monthly(focus_rows)
    focus_cagr = compute_cagr_from_base_ttm(
        focus_base_psf, focus_ttm_monthly, focus_base_start,
    )
    pk_included = len(focus_years) >= 2 and focus_cagr is not None
    area_proxy_bucket_metrics = build_bucket_metrics(
        rows,
        AREA_PROXY_ORDER,
        lambda row: infer_area_proxy_bucket(row["sqft"]),
    )
    area_proxy_pk_included = any(
        metric.get("count") for metric in area_proxy_bucket_metrics.values()
    )
    overall_reference = summarize_row_set(rows, provenance="overall_reference", label="全项目")
    owner_pool_direct = summarize_row_set([], provenance="direct_owner_pool", label="自住池(2b1b+2b2b)")
    owner_pool_area_proxy = summarize_row_set(
        owner_pool_proxy_rows,
        provenance="area_proxy",
        label="自住池(2b1b+2b2b)",
    )
    owner_pool_filled = owner_pool_area_proxy
    if not metric_is_qualified(owner_pool_filled, OWNER_POOL_PROXY_MIN_COUNT):
        owner_pool_filled = overall_reference

    type_breakout = {}
    for bucket in OWNER_POOL_BUCKETS:
        bucket_rows = [row for row in rows if infer_area_proxy_bucket(row["sqft"]) == bucket]
        type_breakout[bucket] = summarize_row_set(
            bucket_rows,
            provenance="area_proxy",
            label=bucket,
        )

    owner_pool_pk_included = owner_pool_filled.get("current") is not None and (
        owner_pool_filled.get("cagr_3y") is not None or owner_pool_filled.get("cagr_5y") is not None
    )
    confidence_score = round(
        min(
            100.0,
            min(owner_pool_filled.get("recent_24m_count", 0) * 4, 60)
            + (35 if owner_pool_filled.get("provenance") == "area_proxy" else 20),
        ),
        1,
    )

    return {
        "slug": slug,
        "name": slug_to_name(slug),
        "region_group": registry_info.get("region_group", REGION_GROUP.get(slug, "Other")),
        "csv_file": source_csv,
        "source_csv": source_csv,
        "record_count": len(rows),
        "first_date": first_row["date_label"],
        "latest_date": latest_row["date_label"],
        "year_range": f"{first_row['year']}-{latest_row['year']}",
        "unique_sqft_count": len(size_counts),
        "top_sizes": [{"sqft": sqft, "count": count} for sqft, count in size_counts.most_common(6)],
        "top_year": info.get("top_year"),
        "tenure": info.get("tenure"),
        "units": info.get("units"),
        "overall_cagr": overall_cagr,
        "overall_base_psf": overall_base_psf,
        "overall_base_start": overall_base_start,
        "overall_ttm_monthly": overall_ttm_monthly,
        "overall_year_count": len(overall_years),
        "overall_latest_year": latest_overall_year,
        "overall_latest_psf": latest_overall.get("median_psf"),
        "overall_latest_n": latest_overall.get("count"),
        "overall_annual": overall,
        "overall_monthly": overall_monthly,
        "overall_year_range": year_range_label(overall_years),
        "overall_period_months": overall_month_span,
        "overall_period_label": overall_period_label,
        "overall_pk_included": overall_pk_included,
        "public_window_pk_included": public_window_pk_included,
        "focus_cagr": focus_cagr,
        "focus_year_count": len(focus_years),
        "focus_latest_year": latest_focus_year,
        "focus_latest_psf": latest_focus.get("median_psf"),
        "focus_latest_n": latest_focus.get("count"),
        "focus_annual": focus_annual,
        "focus_period_months": focus_month_span,
        "focus_period_label": focus_period_label,
        "source": source_label,
        "source_kind": source_kind,
        "source_url": source_url,
        "secondary_sources": secondary_sources,
        "all_sources": all_sources,
        "all_source_count": len(all_sources),
        "pk_included": pk_included,
        "pk_scope": "600-1199 sqft proxy for 2b1b / 2b2b / 3b2b",
        "area_proxy_bucket_metrics": area_proxy_bucket_metrics,
        "area_proxy_pk_included": area_proxy_pk_included,
        "area_proxy_scope": "2b1b 600-699 sqft · 2b2b 700-849 sqft · 3b2b 850-1199 sqft",
        "owner_pool_direct": owner_pool_direct,
        "owner_pool_area_proxy": owner_pool_area_proxy,
        "owner_pool_filled": owner_pool_filled,
        "type_breakout": type_breakout,
        "overall_reference": overall_reference,
        "owner_pool_pk_included": owner_pool_pk_included,
        "data_confidence": {
            "coverage_pct": 0.0,
            "recent_24m_count": owner_pool_filled.get("recent_24m_count", 0),
            "score": confidence_score,
            "label": confidence_label(confidence_score),
            "provenance": owner_pool_filled.get("provenance"),
        },
        "has_detailed_csv": (DATA_DIR / "detailed" / f"{slug}_transactions_detailed.csv").exists(),
        "has_layout_mapping": (FORMAL_LAYOUT_DIR / f"{slug}_transaction_layout_map.csv").exists(),
    }


def build_ura_browser_projects(project_summaries: list[dict]) -> list[dict]:
    ura_summary = load_optional_json(URA_SUMMARY_PATH)
    ura_index = load_optional_json(URA_INDEX_PATH)
    if not ura_summary or not ura_index:
        return []

    local_by_canonical = {canonical_key(project["slug"]): project for project in project_summaries}
    browser_projects: list[dict] = []

    for ura_slug, summary in ura_summary.items():
        details = ura_index.get(ura_slug, {})
        local_match = local_by_canonical.get(canonical_key(ura_slug))
        latest_transactions = details.get("transactions", [])[-5:]
        latest_rental_median = details.get("rentalMedian", [])[-6:]
        latest_rental_contracts = details.get("rentalContracts", [])[-6:]

        browser_projects.append(
            {
                "slug": ura_slug,
                "name": summary.get("project"),
                "street": summary.get("street"),
                "districts": summary.get("districts", []),
                "coords": summary.get("coords"),
                "transactionCount": summary.get("transactionCount", 0),
                "transactionDateRange": summary.get("transactionDateRange"),
                "rentalMedianCount": summary.get("rentalMedianCount", 0),
                "rentalMedianRange": summary.get("rentalMedianRange"),
                "rentalContractCount": summary.get("rentalContractCount", 0),
                "rentalContractRange": summary.get("rentalContractRange"),
                "latestTransactions": latest_transactions,
                "latestRentalMedian": latest_rental_median,
                "latestRentalContracts": latest_rental_contracts,
                "localComparison": {
                    "matched": bool(local_match),
                    "slug": local_match.get("slug") if local_match else None,
                    "name": local_match.get("name") if local_match else None,
                    "region_group": local_match.get("region_group") if local_match else None,
                    "record_count": local_match.get("record_count") if local_match else None,
                    "first_date": local_match.get("first_date") if local_match else None,
                    "latest_date": local_match.get("latest_date") if local_match else None,
                    "latest_psf": local_match.get("overall_latest_psf") if local_match else None,
                    "latest_n": local_match.get("overall_latest_n") if local_match else None,
                    "overall_cagr": local_match.get("overall_cagr") if local_match else None,
                    "overall_period_label": local_match.get("overall_period_label") if local_match else None,
                    "source": local_match.get("source") if local_match else None,
                    "source_csv": local_match.get("source_csv") if local_match else None,
                    "transaction_count_gap": (
                        summary.get("transactionCount", 0) - local_match.get("record_count", 0)
                        if local_match
                        else None
                    ),
                },
            }
        )

    browser_projects.sort(
        key=lambda item: (
            0 if item["localComparison"]["matched"] else 1,
            -item["transactionCount"],
            item["name"] or "",
        )
    )
    return browser_projects


URA_RENTAL_PROJECTS = {
    "lakeville": "LAKEVILLE",
    "lake_grande": "LAKE GRANDE",
}

RENTAL_TYPE_RULES: dict[str, dict[tuple[str, str], str]] = {
    "LAKEVILLE": {
        ("2", "600-700"): "2b1b",
        ("2", "700-800"): "2b2b",
        ("2", "800-900"): "2b2b",
        ("3", "900-1000"): "3b2b",
    },
    "LAKE GRANDE": {
        ("2", "500-600"): "2b1b",
        ("2", "600-700"): "2b1b",
        ("2", "800-900"): "2b2b",
        ("3", "900-1000"): "3b2b",
    },
}

RENTAL_TYPE_RULES_SQM: dict[str, dict[tuple[str, str, str], str]] = {
    "LAKE GRANDE": {
        ("2", "700-800", "70-80"): "2b2b",
        ("2", "700-800", "60-70"): "2b2b",
    },
}


def classify_rental_contract(project_name: str, contract: dict) -> str | None:
    bedrooms = contract.get("noOfBedRoom", "")
    area_sqft = contract.get("areaSqft", "")
    area_sqm = contract.get("areaSqm", "")

    rules = RENTAL_TYPE_RULES.get(project_name, {})
    result = rules.get((bedrooms, area_sqft))
    if result:
        return result

    sqm_rules = RENTAL_TYPE_RULES_SQM.get(project_name, {})
    result = sqm_rules.get((bedrooms, area_sqft, area_sqm))
    if result:
        return result

    return None


def normalize_ura_quarter(ref_period: str) -> str:
    """Convert '21q1' -> '2021Q1' or pass through '2023Q1' unchanged."""
    if len(ref_period) == 4 and "q" in ref_period:
        yy, q = ref_period.split("q")
        return f"20{yy}Q{q}"
    return ref_period


def quarter_sort_key(quarter: str) -> tuple[int, int]:
    year = int(quarter[:4])
    q = int(quarter[-1])
    return (year, q)


RENTAL_SLUG_TO_FOCUS_SLUG = {
    "lakeville": "lakeville",
    "lake_grande": "lakegrande",
}

TRAILING_QUARTERS = 4


def _month_to_quarter(year: int, month: int) -> str:
    q = (month - 1) // 3 + 1
    return f"{year}Q{q}"


def _prev_quarters(quarter: str, n: int) -> list[str]:
    """Return *n* quarters ending at (and including) *quarter*."""
    year = int(quarter[:4])
    q = int(quarter[-1])
    result = []
    for _ in range(n):
        result.append(f"{year}Q{q}")
        q -= 1
        if q == 0:
            q = 4
            year -= 1
    return result


def _load_price_by_quarter_bucket(
    focus_slug: str,
    catalog_by_project: dict[str, list[dict]],
) -> dict[str, dict[str, list[int]]]:
    """Return {bucket: {quarter: [prices]}} from layout-mapped transactions."""
    rows = load_focus_mapping_rows(focus_slug, catalog_by_project.get(focus_slug, []))
    price_map: dict[str, dict[str, list[int]]] = {
        "2b1b": defaultdict(list),
        "2b2b": defaultdict(list),
        "3b2b": defaultdict(list),
    }
    for row in rows:
        bucket = row["focus_bucket"]
        if bucket not in price_map:
            continue
        q = _month_to_quarter(int(row["year"]), int(row["month"]))
        price_map[bucket][q].append(row["price"])
    return price_map


def _trailing_median_price(
    price_by_quarter: dict[str, list[int]],
    quarter: str,
    window: int = TRAILING_QUARTERS,
) -> tuple[float | None, int]:
    """Median price over a trailing window of quarters. Returns (median, count)."""
    qs = _prev_quarters(quarter, window)
    prices: list[int] = []
    for q in qs:
        prices.extend(price_by_quarter.get(q, []))
    if not prices:
        return None, 0
    return round(float(statistics.median(prices))), len(prices)


def build_decision_rental_yield(rental_trends: dict) -> dict:
    """Summarise gross-yield series and implied-fair-PSF matrix per focus project/bucket.

    Consumes the rental_trends already computed by build_rental_trends.
    """
    required_yields = [0.030, 0.035, 0.040, 0.045]  # net of property tax / mgmt / vacancy
    rent_growth_rates = [0.000, 0.010, 0.015, 0.020]  # long-run rental growth g
    buckets = ("2b1b", "2b2b", "3b2b")
    out: dict = {
        "required_yields": required_yields,
        "rent_growth_rates": rent_growth_rates,
        "assumptions_note": (
            "Gordon growth: fair_psf = psf_rent_annual / (required_yield - g). "
            "当前实现分子使用 gross annual rent，因此 required_yield 更应先读作 gross yield proxy；若要看净收益率，需先把年租改成净租。"
        ),
        "projects": {},
    }
    for project_slug, by_bucket in rental_trends.items():
        project_out: dict = {}
        for bucket in buckets:
            series = by_bucket.get(bucket) or []
            yields = [pt.get("gross_yield") for pt in series if pt.get("gross_yield") is not None]
            latest = next((pt for pt in reversed(series) if pt.get("gross_yield") is not None), None)
            hist_mean = round(sum(yields) / len(yields), 2) if yields else None
            current_yield = latest.get("gross_yield") if latest else None
            current_psf_rent = None
            current_psf_sale = None
            if latest:
                # median_rent is monthly SGD; median_price here is a bucket median SGD price,
                # so we convert via bucket typical sqft if possible. Skip if no sqft anchor.
                # Simpler: keep raw inputs; frontend or user does the fair-psf maths.
                current_psf_rent = latest.get("median_rent")
                current_psf_sale = latest.get("median_price")
            fair_matrix = None
            if current_psf_rent:
                # rental_trends stores monthly rent in SGD per unit, and median_price is per-unit
                # sale price. Convert to per-sqft yield using implicit sqft ratio via gross_yield
                # so we can do: rent_annual_psf = gross_yield * psf_sale.
                # We stick to a simpler formulation: compute fair monthly-rent multiplier
                # m = annual_rent / (required_yield - g); fair price = m (in SGD per unit),
                # then fair psf = fair price / implied sqft.
                annual_rent = current_psf_rent * 12
                fair_matrix = []
                for ry in required_yields:
                    row = []
                    for g in rent_growth_rates:
                        if ry - g <= 0:
                            row.append(None)
                        else:
                            fair_price = annual_rent / (ry - g)
                            row.append(round(fair_price))
                    fair_matrix.append(row)
            project_out[bucket] = {
                "series": series,
                "latest_quarter": latest.get("quarter") if latest else None,
                "latest_gross_yield": current_yield,
                "latest_median_rent": current_psf_rent,
                "latest_median_price": current_psf_sale,
                "historical_mean_yield": hist_mean,
                "yield_deviation_vs_mean": (
                    round(current_yield - hist_mean, 2)
                    if current_yield is not None and hist_mean is not None
                    else None
                ),
                "fair_price_matrix": fair_matrix,
            }
        out["projects"][project_slug] = project_out
    return out


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def _rolling_cagr_stats(series: list[dict], quarters: int) -> dict:
    if len(series) <= quarters:
        return {}
    values: list[float] = []
    points: list[dict] = []
    years = quarters / 4
    for idx in range(quarters, len(series)):
        start = series[idx - quarters]["index"]
        end = series[idx]["index"]
        if start <= 0 or end <= 0:
            continue
        cagr = (end / start) ** (1 / years) - 1
        values.append(cagr)
        points.append({
            "quarter": series[idx]["quarter"],
            "cagr": round(cagr, 6),
        })
    if not values:
        return {}
    return {
        "window_years": years,
        "current": round(values[-1], 6),
        "mean": round(sum(values) / len(values), 6),
        "median": round(statistics.median(values), 6),
        "p25": round(_percentile(values, 0.25), 6),
        "p75": round(_percentile(values, 0.75), 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
        "points": points,
    }


def build_market_rent_benchmarks() -> dict:
    payload = load_optional_json(OFFICIAL_INDICES_PATH)
    if not payload:
        return {}
    series_map = payload.get("series") or {}
    ocr_series = sorted(series_map.get("non_landed_ocr") or [], key=lambda item: quarter_sort_key_data_gov(item["quarter"]))
    whole_island_series = sorted(
        series_map.get("non_landed_whole_island") or [],
        key=lambda item: quarter_sort_key_data_gov(item["quarter"]),
    )
    if not ocr_series and not whole_island_series:
        return {}
    return {
        "source": payload.get("source") or {},
        "series": {
            "ocr_non_landed": ocr_series,
            "whole_island_non_landed": whole_island_series,
        },
        "stats": {
            "ocr_non_landed": {
                "rolling_5y": _rolling_cagr_stats(ocr_series, 20),
                "rolling_10y": _rolling_cagr_stats(ocr_series, 40),
            },
            "whole_island_non_landed": {
                "rolling_5y": _rolling_cagr_stats(whole_island_series, 20),
                "rolling_10y": _rolling_cagr_stats(whole_island_series, 40),
            },
        },
        "notes": {
            "coverage": "Official URA rental index for non-landed private residential; OCR and whole-island series cover 2004Q1 to 2025Q4.",
            "interpretation": "Use rolling 10Y CAGR as a long-run anchor for g; use project/type gross-yield history as the observable market anchor for required_yield.",
        },
    }


def resolve_listing_local_cagr(project_analysis: dict, bucket: str) -> float:
    by_type = project_analysis.get("by_type_cagr") or {}
    type_label = LISTING_BUCKET_TO_TYPE_LABEL.get(bucket)
    if type_label and by_type.get(type_label) is not None:
        return by_type[type_label] / 100
    overall = project_analysis.get("overall_cagr")
    return (overall / 100) if overall is not None else 0.02


def build_listing_valuation_data(layout_catalogs: dict[str, list[dict]], analysis: dict) -> dict:
    out = {
        "default_window_months": RECENT_WINDOW_MONTHS,
        "projects": {},
    }
    for slug in ("lakeville", "lakegrande"):
        rows = load_focus_mapping_rows(slug, layout_catalogs.get(slug, []))
        project_analysis = analysis.get(slug, {})
        project_out = {
            "latest_date": None,
            "latest_date_label": None,
            "buckets": {},
        }
        latest_date = None
        for bucket in AREA_PROXY_ORDER:
            bucket_rows = [
                row
                for row in rows
                if row["mapping_status"] == "matched" and row["resolved_layout"] == bucket
            ]
            transactions = [
                {
                    "date": row["date"],
                    "date_label": row["date_label"],
                    "sqft": row["sqft"],
                    "psf": row["psf"],
                    "price": row["price"],
                }
                for row in bucket_rows
            ]
            if transactions:
                bucket_latest = max((row["date"] for row in bucket_rows), key=sort_monthyear_key)
                latest_date = (
                    bucket_latest
                    if latest_date is None or sort_monthyear_key(bucket_latest) > sort_monthyear_key(latest_date)
                    else latest_date
                )
            project_out["buckets"][bucket] = {
                "local_cagr": resolve_listing_local_cagr(project_analysis, bucket),
                "transactions": transactions,
            }
        if latest_date is not None:
            project_out["latest_date"] = latest_date
            project_out["latest_date_label"] = format_monthyear(latest_date)
        out["projects"][slug] = project_out
    return out


def build_rental_trends(layout_catalogs: dict[str, list[dict]]) -> dict:
    ura_index = load_optional_json(URA_INDEX_PATH)
    if not ura_index:
        return {}

    price_caches: dict[str, dict[str, dict[str, list[int]]]] = {}
    for rental_slug, focus_slug in RENTAL_SLUG_TO_FOCUS_SLUG.items():
        price_caches[rental_slug] = _load_price_by_quarter_bucket(
            focus_slug, layout_catalogs,
        )

    result: dict[str, dict[str, list[dict]]] = {}

    for local_slug, project_name in URA_RENTAL_PROJECTS.items():
        ura_slug = local_slug
        details = ura_index.get(ura_slug, {})
        contracts = details.get("rentalContracts", [])

        buckets: dict[str, dict[str, list[int]]] = {
            "2b1b": defaultdict(list),
            "2b2b": defaultdict(list),
            "3b2b": defaultdict(list),
        }

        for contract in contracts:
            unit_type = classify_rental_contract(project_name, contract)
            if not unit_type:
                continue
            quarter = normalize_ura_quarter(contract.get("refPeriod", ""))
            rent = contract.get("rent")
            if rent and quarter:
                buckets[unit_type][quarter].append(rent)

        project_price_cache = price_caches.get(local_slug, {})

        project_trends: dict[str, list[dict]] = {}
        for unit_type in ("2b1b", "2b2b", "3b2b"):
            quarter_data = buckets[unit_type]
            sorted_quarters = sorted(quarter_data.keys(), key=quarter_sort_key)
            price_by_q = project_price_cache.get(unit_type, {})
            trend: list[dict] = []
            for quarter in sorted_quarters:
                rents = quarter_data[quarter]
                median_rent = round(statistics.median(rents))
                median_price, price_count = _trailing_median_price(price_by_q, quarter)
                gross_yield = None
                if median_price and median_price > 0:
                    gross_yield = round(median_rent * 12 / median_price * 100, 2)
                trend.append({
                    "quarter": quarter,
                    "median_rent": median_rent,
                    "count": len(rents),
                    "median_price": median_price,
                    "price_txn_count": price_count,
                    "gross_yield": gross_yield,
                })
            project_trends[unit_type] = trend

        result[local_slug] = project_trends

    return result


def merge_focus_metrics(summary: dict, focus_project: dict | None) -> dict:
    if not focus_project:
        return summary
    merged = dict(summary)
    merged["owner_pool_direct"] = focus_project["owner_pool_direct"]
    merged["owner_pool_area_proxy"] = summary["owner_pool_area_proxy"]
    merged["owner_pool_filled"] = select_owner_pool_metric(
        focus_project["type_breakout"].get("2b2b", {}),
        focus_project["owner_pool_direct"],
        summary["owner_pool_area_proxy"],
        summary["overall_reference"],
    )
    merged["type_breakout"] = {
        **summary.get("type_breakout", {}),
        **focus_project.get("type_breakout", {}),
    }
    merged["overall_reference"] = focus_project["overall_reference"]
    merged["data_confidence"] = focus_project["data_confidence"]
    merged["owner_pool_pk_included"] = merged["owner_pool_filled"].get("current") is not None and (
        merged["owner_pool_filled"].get("cagr_3y") is not None or merged["owner_pool_filled"].get("cagr_5y") is not None
    )
    return merged


def build_comparison_scores(projects: list[dict]) -> list[dict]:
    if not projects:
        return []

    history_positions: dict[str, float | None] = {}
    region_peer_positions: dict[str, float | None] = {}
    region_groups = {project.get("region_group") for project in projects}

    for project in projects:
        current_psf = metric_current_psf(project["owner_pool_filled"])
        ttm_series = [
            item["median_psf"] for key, item in sorted(project["owner_pool_filled"].get("ttm_monthly", {}).items())
        ]
        history_positions[project["slug"]] = percentile_position(current_psf, ttm_series)

        peer_samples = [
            metric_current_psf(peer["owner_pool_filled"])
            for peer in projects
            if peer.get("region_group") == project.get("region_group")
        ]
        if len([sample for sample in peer_samples if sample is not None]) < 3:
            peer_samples = [metric_current_psf(peer["owner_pool_filled"]) for peer in projects]
        region_peer_positions[project["slug"]] = percentile_position(current_psf, peer_samples)

    trend_3y_values = [project["owner_pool_filled"].get("cagr_3y") for project in projects]
    trend_5y_values = [project["owner_pool_filled"].get("cagr_5y") for project in projects]
    recent_counts = [project["data_confidence"].get("recent_24m_count") for project in projects]
    coverage_values = [project["data_confidence"].get("coverage_pct") for project in projects]

    scored = []
    for project in projects:
        history_score = history_positions[project["slug"]]
        peer_score = region_peer_positions[project["slug"]]
        scored.append(
            {
                **project,
                "history_position_pct": round((history_score or 0) * 100, 1) if history_score is not None else None,
                "peer_position_pct": round((peer_score or 0) * 100, 1) if peer_score is not None else None,
                "trend_5y_percentile": round((percentile_position(project["owner_pool_filled"].get("cagr_5y"), trend_5y_values) or 0) * 100, 1)
                if percentile_position(project["owner_pool_filled"].get("cagr_5y"), trend_5y_values) is not None else None,
                "trend_all_time_percentile": round((percentile_position(project["owner_pool_filled"].get("lifetime_cagr"), [peer["owner_pool_filled"].get("lifetime_cagr") for peer in projects]) or 0) * 100, 1)
                if percentile_position(project["owner_pool_filled"].get("lifetime_cagr"), [peer["owner_pool_filled"].get("lifetime_cagr") for peer in projects]) is not None else None,
                "recent_24m_count_percentile": round((percentile_position(project["data_confidence"].get("recent_24m_count"), recent_counts) or 0) * 100, 1)
                if percentile_position(project["data_confidence"].get("recent_24m_count"), recent_counts) is not None else None,
                "coverage_percentile": round((percentile_position(project["data_confidence"].get("coverage_pct"), coverage_values) or 0) * 100, 1)
                if percentile_position(project["data_confidence"].get("coverage_pct"), coverage_values) is not None else None,
            }
        )

    scored.sort(
        key=lambda item: (
            item["history_position_pct"] if item["history_position_pct"] is not None else 1000,
            item["peer_position_pct"] if item["peer_position_pct"] is not None else 1000,
            item["name"],
        )
    )
    return scored


def build_payload() -> dict:
    analysis = load_json(ANALYSIS_PATH)
    layout_catalogs = load_layout_catalogs()
    transaction_paths = sorted(DATA_DIR.glob("*_transactions.csv"))

    project_summaries = []
    overall_comparison_projects = []
    area_proxy_comparison_projects = []

    for csv_path in transaction_paths:
        slug = csv_path.name.replace("_transactions.csv", "")
        rows = load_transaction_rows(csv_path)
        summary = build_project_summary(slug, analysis[slug], rows)
        project_summaries.append(summary)

        if (
            summary["source_kind"] == "propertyforsale_csv"
            and summary["overall_year_count"] >= 2
            and summary["overall_cagr"] is not None
        ):
            overall_metric = summary["overall_reference"]
            overall_comparison_projects.append(
                {
                    "slug": slug,
                    "name": summary["name"],
                    "region_group": summary["region_group"],
                    "top_year": summary["top_year"],
                    "tenure": summary["tenure"],
                    "units": summary["units"],
                    "overall_cagr": summary["overall_cagr"],
                    "overall_base_psf": summary["overall_base_psf"],
                    "overall_base_start": summary["overall_base_start"],
                    "overall_ttm_monthly": summary["overall_ttm_monthly"],
                    "overall_annual": summary["overall_annual"],
                    "overall_monthly": summary["overall_monthly"],
                    "overall_latest_year": summary["overall_latest_year"],
                    "overall_latest_psf": summary["overall_latest_psf"],
                    "overall_latest_n": summary["overall_latest_n"],
                    "record_count": summary["record_count"],
                    "year_range": summary["overall_year_range"],
                    "overall_period_label": summary["overall_period_label"],
                    "overall_period_months": summary["overall_period_months"],
                    "source_kind": summary["source_kind"],
                    "source_label": summary["source"],
                    "source_csv": summary["source_csv"],
                    "source_url": summary["source_url"],
                    **build_metric_snapshot(overall_metric),
                }
            )

        if summary["area_proxy_pk_included"]:
            area_proxy_metric = summary["owner_pool_area_proxy"]
            area_proxy_comparison_projects.append(
                {
                    "slug": slug,
                    "name": summary["name"],
                    "region_group": summary["region_group"],
                    "top_year": summary["top_year"],
                    "tenure": summary["tenure"],
                    "units": summary["units"],
                    "record_count": summary["record_count"],
                    "source_kind": summary["source_kind"],
                    "source_label": summary["source"],
                    "source_csv": summary["source_csv"],
                    "source_url": summary["source_url"],
                    "area_proxy_scope": summary["area_proxy_scope"],
                    "area_proxy_bucket_metrics": summary["area_proxy_bucket_metrics"],
                    "owner_pool_area_proxy": area_proxy_metric,
                    **build_metric_snapshot(area_proxy_metric),
                }
            )

    focus_projects = {
        slug: build_focus_project(slug, layout_catalogs)
        for slug in ("lakeville", "lakegrande")
    }
    project_summaries = [
        merge_focus_metrics(summary, focus_projects.get(summary["slug"]))
        for summary in project_summaries
    ]
    project_summaries.sort(key=lambda item: item["record_count"], reverse=True)
    overall_comparison_projects = sorted(
        overall_comparison_projects,
        key=lambda item: (item["all_time_cagr"] is not None, item["all_time_cagr"] or float("-inf"), item["name"]),
        reverse=True,
    )
    area_proxy_comparison_projects = sorted(
        area_proxy_comparison_projects,
        key=lambda item: (item["all_time_cagr"] is not None, item["all_time_cagr"] or float("-inf"), item["name"]),
        reverse=True,
    )
    comparison_projects = build_comparison_scores(
        [
            {
                "slug": summary["slug"],
                "name": summary["name"],
                "region_group": summary["region_group"],
                "top_year": summary["top_year"],
                "tenure": summary["tenure"],
                "units": summary["units"],
                "record_count": summary["record_count"],
                "source_kind": summary["source_kind"],
                "source_label": summary["source"],
                "source_csv": summary["source_csv"],
                "source_url": summary["source_url"],
                "owner_pool_direct": summary["owner_pool_direct"],
                "owner_pool_filled": summary["owner_pool_filled"],
                "type_breakout": summary["type_breakout"],
                "overall_reference": summary["overall_reference"],
                "data_confidence": summary["data_confidence"],
                **build_metric_snapshot(summary["owner_pool_filled"]),
            }
            for summary in project_summaries
            if summary["owner_pool_pk_included"]
        ]
    )
    comparison_projects = sorted(
        comparison_projects,
        key=lambda item: (item["all_time_cagr"] is not None, item["all_time_cagr"] or float("-inf"), item["name"]),
        reverse=True,
    )
    ura_browser_projects = build_ura_browser_projects(project_summaries)
    rental_trends = build_rental_trends(layout_catalogs)
    layout_comparison_projects = sorted(
        [
            {
                "slug": project["slug"],
                "name": project["name"],
                "region_group": project.get("region_group"),
                "coverage_pct": project["coverage_pct"],
                "row_count": project["row_count"],
                "type_breakout": project["type_breakout"],
                "typed_bucket_metrics": project["typed_bucket_metrics"],
                "owner_pool_direct": project["owner_pool_direct"],
                "owner_pool_filled": project["owner_pool_filled"],
                "data_confidence": project["data_confidence"],
                **build_metric_snapshot(project["owner_pool_direct"]),
            }
            for project in focus_projects.values()
            if project["owner_pool_direct"].get("current") is not None
        ],
        key=lambda item: (item["all_time_cagr"] is not None, item["all_time_cagr"] or float("-inf"), item["name"]),
        reverse=True,
    )

    total_records = sum(project["record_count"] for project in project_summaries)
    detailed_count = sum(1 for project in project_summaries if project["has_detailed_csv"])
    primary_propertyforsale_count = sum(
        1 for project in project_summaries if project["source_kind"] == "propertyforsale_csv"
    )
    primary_ura_resale_count = sum(
        1 for project in project_summaries if project["source_kind"] == "ura_resale_csv"
    )
    primary_srx_count = sum(
        1 for project in project_summaries if project["source_kind"] == "srx_csv"
    )
    secondary_srx_count = sum(
        1 for project in project_summaries if has_secondary_source_kind(project, "srx_csv")
    )
    ura_matched_count = sum(1 for project in ura_browser_projects if project["localComparison"]["matched"])

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "meta": {
            "project_count": len(project_summaries),
            "total_records": total_records,
            "detailed_project_count": detailed_count,
            "pk_project_count": len(comparison_projects),
            "propertyforsale_project_count": primary_propertyforsale_count,
            "ura_resale_project_count": primary_ura_resale_count,
            "ura_project_count": primary_propertyforsale_count,
            "srx_project_count": primary_srx_count,
            "srx_backup_project_count": secondary_srx_count,
            "overall_comparison_project_count": len(overall_comparison_projects),
            "area_proxy_comparison_project_count": len(area_proxy_comparison_projects),
            "layout_comparison_project_count": len(layout_comparison_projects),
            "layout_mapping_source": detect_layout_mapping_source(),
            "ura_browser_project_count": len(ura_browser_projects),
            "ura_matched_project_count": ura_matched_count,
            "focus_projects": list(focus_projects),
        },
        "projects": project_summaries,
        "comparison_projects": comparison_projects,
        "overall_comparison_projects": overall_comparison_projects,
        "area_proxy_comparison_projects": area_proxy_comparison_projects,
        "layout_comparison_projects": layout_comparison_projects,
        "focus_projects": focus_projects,
        "ura_browser_projects": ura_browser_projects,
        "rental_trends": rental_trends,
        "market_rent_benchmarks": build_market_rent_benchmarks(),
        "decision_rental_yield": build_decision_rental_yield(rental_trends),
        "listing_valuation": build_listing_valuation_data(layout_catalogs, analysis),
    }


def attach_sensitivity(payload: dict) -> dict:
    """Shell out to node to compute wealth-model sensitivity sweep and merge."""
    import subprocess

    # Need dashboard_data.js to exist already with focus_projects for the node script.
    # Write a stub first if missing; otherwise run against the freshly written file.
    try:
        result = subprocess.run(
            ["node", str(BASE_DIR / "scripts" / "build_sensitivity.mjs")],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(BASE_DIR),
        )
        sensitivity = json.loads(result.stdout).get("sensitivity")
        if sensitivity:
            payload["sensitivity"] = sensitivity
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"warning: sensitivity sweep failed: {exc}")
    return payload


def main() -> None:
    payload = build_payload()
    # Write once without sensitivity (so the node script can read focus_projects),
    # compute sensitivity, then rewrite with it merged in.
    json_text = json.dumps(payload, indent=2, ensure_ascii=False)
    OUTPUT_PATH.write_text(json_text, encoding="utf-8")
    OUTPUT_JS_PATH.write_text(
        "window.__DASHBOARD_DATA__ = " + json_text + ";\n",
        encoding="utf-8",
    )
    payload = attach_sensitivity(payload)
    json_text = json.dumps(payload, indent=2, ensure_ascii=False)
    OUTPUT_PATH.write_text(json_text, encoding="utf-8")
    OUTPUT_JS_PATH.write_text(
        "window.__DASHBOARD_DATA__ = " + json_text + ";\n",
        encoding="utf-8",
    )
    print(
        f"dashboard data written to {OUTPUT_PATH} and {OUTPUT_JS_PATH} "
        f"({payload['meta']['project_count']} real CSV projects, "
        f"{payload['meta']['overall_comparison_project_count']} overall-reference PK projects, "
        f"{payload['meta']['ura_resale_project_count']} URA resale fallback projects, "
        f"{payload['meta']['srx_project_count']} legacy SRX primary projects, "
        f"{payload['meta']['pk_project_count']} owner-pool PK projects, "
        f"{payload['meta']['area_proxy_comparison_project_count']} area-proxy PK projects, "
        f"{payload['meta']['layout_comparison_project_count']} typed-layout PK projects, "
        f"{payload['meta']['ura_browser_project_count']} URA browser projects, "
        f"{payload['meta']['total_records']} crawled rows)"
    )


if __name__ == "__main__":
    main()
