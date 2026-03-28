#!/usr/bin/env python3
"""
Build a single JSON payload for the dashboard from local crawled data files.

Sources:
- data/*_transactions.csv
- data/appreciation_analysis.json
- data/layout_mapping/*_transaction_layout_map.csv (preferred)
- data/layout_mapping/layout_reference_catalog.csv (preferred)
- data/poc_layout/*_transactions_layout_poc.csv (legacy fallback)
- data/poc_layout/layout_reference_poc.csv (legacy fallback)
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
LEGACY_LAYOUT_DIR = DATA_DIR / "poc_layout"
FORMAL_LAYOUT_DIR = DATA_DIR / "layout_mapping"
OUTPUT_PATH = DATA_DIR / "dashboard_data.json"
OUTPUT_JS_PATH = DATA_DIR / "dashboard_data.js"
ANALYSIS_PATH = DATA_DIR / "appreciation_analysis.json"
LEGACY_REFERENCE_PATH = LEGACY_LAYOUT_DIR / "layout_reference_poc.csv"
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
        years = sorted(annual.keys())
        latest_year = years[-1] if years else None
        latest_data = annual.get(latest_year, {}) if latest_year else {}
        metrics[bucket] = {
            "count": len(bucket_rows),
            "year_count": len(years),
            "year_range": year_range_label(years),
            "annual": annual,
            "cagr": compute_cagr_from_annual(annual),
            "latest_year": latest_year,
            "latest_psf": latest_data.get("median_psf"),
            "latest_n": latest_data.get("count"),
        }
    return metrics


def year_range_label(years: list[str]) -> str:
    if not years:
        return "-"
    if len(years) == 1:
        return f"{years[0]} only"
    return f"{years[0]}-{years[-1]}"


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
    if LEGACY_REFERENCE_PATH.exists():
        return "legacy_poc"
    return "missing"


def parse_layout_options(value: str) -> list[str]:
    options: list[str] = []
    for part in (value or "").split("|"):
        cleaned = part.strip()
        if not cleaned:
            continue
        options.append(cleaned.split(" ", 1)[0].strip())
    return options


def build_legacy_layout_catalogs() -> dict[str, list[dict]]:
    grouped: dict[str, dict[int, list[dict]]] = defaultdict(lambda: defaultdict(list))
    with LEGACY_REFERENCE_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            grouped[row["project_slug"]][int(row["reference_area_sqft"])].append(row)

    catalogs: dict[str, list[dict]] = {}
    for project_slug, area_map in grouped.items():
        project_catalog: list[dict] = []
        for area_sqft in sorted(area_map):
            refs = area_map[area_sqft]
            unique_layouts = sorted({ref["normalized_type"] for ref in refs if ref.get("normalized_type")})
            project_catalog.append(
                {
                    "project_slug": project_slug,
                    "reference_area_sqft": area_sqft,
                    "catalog_status": "resolved" if len(unique_layouts) == 1 else "conflicting",
                    "resolved_layout": unique_layouts[0] if len(unique_layouts) == 1 else "",
                    "layout_options": " | ".join(unique_layouts),
                }
            )
        catalogs[project_slug] = project_catalog
    return catalogs


def load_layout_catalogs() -> dict[str, list[dict]]:
    if FORMAL_REFERENCE_PATH.exists():
        catalogs: dict[str, list[dict]] = {}
        with FORMAL_REFERENCE_PATH.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                row["reference_area_sqft"] = int(row["reference_area_sqft"])
                catalogs.setdefault(row["project_slug"], []).append(row)
        return catalogs
    if LEGACY_REFERENCE_PATH.exists():
        return build_legacy_layout_catalogs()
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
    legacy_csv_path = LEGACY_LAYOUT_DIR / f"{slug}_transactions_layout_poc.csv"
    rows: list[dict] = []

    if formal_csv_path.exists():
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

    with legacy_csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            compat_row = {
                "mapping_status": row["layout_status"],
                "resolved_layout": row["normalized_type"] if row["layout_status"] == "matched" else "",
                "layout_options": row["normalized_type"],
                "sqft": row["sqft"],
            }
            bucket, bucket_reason = infer_focus_bucket(compat_row, catalog_rows)
            rows.append(
                {
                    "date": row["date"],
                    "date_label": format_monthyear(row["date"]),
                    "year": parse_monthyear(row["date"])[0],
                    "month": parse_monthyear(row["date"])[1],
                    "sqft": int(row["sqft"]),
                    "psf": int(row["psf"]),
                    "price": int(row["price"]),
                    "mapping_status": row["layout_status"],
                    "resolved_layout": row["normalized_type"] if row["layout_status"] == "matched" else "",
                    "layout_options": row["normalized_type"],
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

    return {
        "slug": slug,
        "name": slug_to_name(slug),
        "row_count": len(rows),
        "matched_count": len(mapped_rows),
        "focus_count": len(focus_rows),
        "coverage_pct": round(len(mapped_rows) / len(rows) * 100, 1) if rows else 0.0,
        "focus_summary": summary,
        "annual_by_bucket": annual_by_bucket,
        "typed_bucket_metrics": typed_bucket_metrics,
        "recent_by_bucket": recent_by_bucket,
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
    overall = analysis.get("overall", {})
    overall_years = sorted(overall.keys())
    latest_overall_year = overall_years[-1] if overall_years else None
    latest_overall = overall.get(latest_overall_year, {}) if latest_overall_year else {}
    overall_pk_included = len(overall_years) >= 2 and analysis.get("overall_cagr") is not None
    public_window_pk_included = source_kind == "propertyforsale_csv" and overall_pk_included
    only_23br = analysis.get("only_23br", {})
    latest_focus_year = max(only_23br.keys()) if only_23br else None
    latest_focus = only_23br.get(latest_focus_year, {}) if latest_focus_year else {}
    pk_included = len(only_23br) >= 2 and analysis.get("only_23br_cagr") is not None
    area_proxy_bucket_metrics = build_bucket_metrics(
        rows,
        AREA_PROXY_ORDER,
        lambda row: infer_area_proxy_bucket(row["sqft"]),
    )
    area_proxy_pk_included = any(
        metric.get("count") for metric in area_proxy_bucket_metrics.values()
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
        "overall_cagr": analysis.get("overall_cagr"),
        "overall_year_count": len(overall_years),
        "overall_latest_year": latest_overall_year,
        "overall_latest_psf": latest_overall.get("median_psf"),
        "overall_latest_n": latest_overall.get("count"),
        "overall_annual": overall,
        "overall_year_range": year_range_label(overall_years),
        "overall_pk_included": overall_pk_included,
        "public_window_pk_included": public_window_pk_included,
        "focus_cagr": analysis.get("only_23br_cagr"),
        "focus_year_count": len(only_23br),
        "focus_latest_year": latest_focus_year,
        "focus_latest_psf": latest_focus.get("median_psf"),
        "focus_latest_n": latest_focus.get("count"),
        "focus_annual": only_23br,
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
        "has_detailed_csv": (DATA_DIR / "detailed" / f"{slug}_transactions_detailed.csv").exists(),
        "has_layout_mapping": (
            (FORMAL_LAYOUT_DIR / f"{slug}_transaction_layout_map.csv").exists()
            or (LEGACY_LAYOUT_DIR / f"{slug}_transactions_layout_poc.csv").exists()
        ),
        "has_layout_poc": (LEGACY_LAYOUT_DIR / f"{slug}_transactions_layout_poc.csv").exists(),
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


def build_payload() -> dict:
    analysis = load_json(ANALYSIS_PATH)
    layout_catalogs = load_layout_catalogs()
    transaction_paths = sorted(DATA_DIR.glob("*_transactions.csv"))

    project_summaries = []
    comparison_projects = []
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
            overall_comparison_projects.append(
                {
                    "slug": slug,
                    "name": summary["name"],
                    "region_group": summary["region_group"],
                    "top_year": summary["top_year"],
                    "tenure": summary["tenure"],
                    "units": summary["units"],
                    "overall_cagr": summary["overall_cagr"],
                    "overall_annual": summary["overall_annual"],
                    "overall_latest_year": summary["overall_latest_year"],
                    "overall_latest_psf": summary["overall_latest_psf"],
                    "overall_latest_n": summary["overall_latest_n"],
                    "record_count": summary["record_count"],
                    "year_range": summary["overall_year_range"],
                    "source_kind": summary["source_kind"],
                    "source_label": summary["source"],
                    "source_csv": summary["source_csv"],
                    "source_url": summary["source_url"],
                }
            )

        if summary["focus_year_count"] >= 2 and summary["focus_cagr"] is not None:
            comparison_projects.append(
                {
                    "slug": slug,
                    "name": summary["name"],
                    "region_group": summary["region_group"],
                    "top_year": summary["top_year"],
                    "tenure": summary["tenure"],
                    "units": summary["units"],
                    "focus_cagr": summary["focus_cagr"],
                    "focus_annual": summary["focus_annual"],
                    "focus_latest_year": summary["focus_latest_year"],
                    "focus_latest_psf": summary["focus_latest_psf"],
                    "focus_latest_n": summary["focus_latest_n"],
                    "record_count": summary["record_count"],
                    "year_range": summary["year_range"],
                    "source_kind": summary["source_kind"],
                    "source_label": summary["source"],
                    "source_csv": summary["source_csv"],
                    "source_url": summary["source_url"],
                    "pk_scope": summary["pk_scope"],
                }
            )

        if summary["area_proxy_pk_included"]:
            area_proxy_comparison_projects.append(
                {
                    "slug": slug,
                    "name": summary["name"],
                    "region_group": summary["region_group"],
                    "record_count": summary["record_count"],
                    "source_kind": summary["source_kind"],
                    "source_label": summary["source"],
                    "source_csv": summary["source_csv"],
                    "source_url": summary["source_url"],
                    "area_proxy_scope": summary["area_proxy_scope"],
                    "area_proxy_bucket_metrics": summary["area_proxy_bucket_metrics"],
                }
            )

    project_summaries.sort(key=lambda item: item["record_count"], reverse=True)
    comparison_projects = sorted(
        comparison_projects,
        key=lambda item: item["focus_cagr"],
        reverse=True,
    )
    overall_comparison_projects = sorted(
        overall_comparison_projects,
        key=lambda item: item["overall_cagr"],
        reverse=True,
    )
    area_proxy_comparison_projects = sorted(
        area_proxy_comparison_projects,
        key=lambda item: item["name"],
    )

    focus_projects = {
        slug: build_focus_project(slug, layout_catalogs)
        for slug in ("lakeville", "lakegrande")
    }
    ura_browser_projects = build_ura_browser_projects(project_summaries)
    layout_comparison_projects = sorted(
        [
            {
                "slug": project["slug"],
                "name": project["name"],
                "coverage_pct": project["coverage_pct"],
                "row_count": project["row_count"],
                "typed_bucket_metrics": project["typed_bucket_metrics"],
            }
            for project in focus_projects.values()
            if any(project["typed_bucket_metrics"].get(bucket, {}).get("count") for bucket in ("2b1b", "2b2b", "3b2b"))
        ],
        key=lambda item: item["name"],
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
    }


def main() -> None:
    payload = build_payload()
    json_text = json.dumps(payload, indent=2, ensure_ascii=False)
    OUTPUT_PATH.write_text(json_text, encoding="utf-8")
    OUTPUT_JS_PATH.write_text(
        "window.__DASHBOARD_DATA__ = " + json_text + ";\n",
        encoding="utf-8",
    )
    print(
        f"dashboard data written to {OUTPUT_PATH} and {OUTPUT_JS_PATH} "
        f"({payload['meta']['project_count']} real CSV projects, "
        f"{payload['meta']['overall_comparison_project_count']} propertyforsale resale PK projects, "
        f"{payload['meta']['ura_resale_project_count']} URA resale fallback projects, "
        f"{payload['meta']['srx_project_count']} legacy SRX primary projects, "
        f"{payload['meta']['area_proxy_comparison_project_count']} area-proxy PK projects, "
        f"{payload['meta']['layout_comparison_project_count']} typed-layout PK projects, "
        f"{payload['meta']['ura_browser_project_count']} URA browser projects, "
        f"{payload['meta']['total_records']} crawled rows)"
    )


if __name__ == "__main__":
    main()
