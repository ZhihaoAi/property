#!/usr/bin/env python3
"""
Extract richer resale transaction data from cached propertyforsale markdown pages.

Outputs:
- Per-project detailed CSVs under data/detailed/
- One combined CSV at data/resale_transactions_detailed.csv
"""

from __future__ import annotations

import csv
import re
from pathlib import Path


FETCHED_DIR = Path("/Users/zhihao.ai/.cursor/projects/Users-zhihao-ai-projects-property/agent-tools")
OUTPUT_DIR = Path("/Users/zhihao.ai/projects/property/data")
DETAILED_DIR = OUTPUT_DIR / "detailed"

MONTH_MAP = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}

MONTH_ABBR = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}

# Current cached project pages available locally.
PROJECTS = [
    ("5bc82b54-071b-4c07-afda-8977231aadae.txt", "stirling_residences"),
    ("72039a39-bbd6-4351-ba22-903af873be75.txt", "queens_peak"),
    ("d4c8360a-b853-43d2-9e46-fa97f98fe4cc.txt", "commonwealth_towers"),
    ("0f7130d8-d32f-41dd-8ef7-9732bd336db0.txt", "the_trilinq"),
    ("a9e5fa7f-0277-4989-97a3-418db9f24c29.txt", "clavon"),
    ("defc6b6f-ebd2-4002-9267-d39cc8071196.txt", "artra"),
    ("70c05ad5-2873-496d-87d3-e15f2844117f.txt", "kent_ridge_hill"),
    ("ef2cd020-54ab-4fb0-83d0-cf2de0218ddc.txt", "j_gateway"),
    ("15f61f1e-2cb7-40a4-b625-c728c954cbae.txt", "seahill"),
    ("bc0f8956-f190-4bf6-a91e-a413641e0584.txt", "the_vision"),
    ("82612131-2875-4911-b8c3-70be5c5154c0.txt", "hundred_trees"),
    ("69538a84-0c38-4d93-89e9-b9c3301ddae9.txt", "parc_clematis"),
    ("faf51c66-bda4-42fd-b65c-8be0bec3abd5.txt", "whitehaven"),
    ("ec8484a2-5986-4320-9dbe-3c2c88ddc8b4.txt", "caspian"),
    ("2ed034c7-7c99-4d75-977b-a1cc527ed201.txt", "lakefront"),
]

OUTPUT_FIELDS = [
    "project_slug",
    "project_name",
    "sale_period",
    "sale_month_year",
    "sale_year_month",
    "sale_year",
    "sale_month",
    "street_name",
    "district",
    "market_segment",
    "tenure",
    "lease_start",
    "floor_range",
    "floor_low",
    "floor_high",
    "floor_area_sqft",
    "psf_sgd",
    "sale_price_sgd",
    "source_site",
    "source_file",
]

HEADER_MAP = {
    "date of sale": "date_of_sale",
    "project name": "project_name",
    "street name": "street_name",
    "district": "district",
    "market segment": "market_segment",
    "tenure": "tenure",
    "lease start": "lease_start",
    "type of sale": "type_of_sale",
    "floor level": "floor_level",
    "floor area (sqft)": "floor_area_sqft",
    "psf (s$)": "psf_sgd",
    "sale price (s$)": "sale_price_sgd",
}


def strip_markdown_links(text: str) -> str:
    return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text).strip()


def parse_markdown_row(line: str) -> list[str]:
    line = line.strip()
    if not line.startswith("|"):
        return []
    parts = [strip_markdown_links(cell.strip()) for cell in line.strip("|").split("|")]
    return parts


def is_separator_row(cells: list[str]) -> bool:
    if not cells:
        return False
    return all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


def parse_sale_period(text: str) -> tuple[str, str, int, int]:
    text = text.strip()
    for month_name, month_num in MONTH_MAP.items():
        if text.startswith(month_name):
            year = int(text[len(month_name):].strip())
            return (
                text,
                f"{MONTH_ABBR[month_num]}{year}",
                year,
                month_num,
            )
    raise ValueError(f"Unsupported sale period: {text}")


def parse_int(text: str) -> str:
    cleaned = text.replace(",", "").strip()
    if not cleaned:
        return ""
    if cleaned.isdigit():
        return cleaned
    raise ValueError(f"Unsupported integer field: {text}")


def parse_floor_range(text: str) -> tuple[str, str]:
    match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", text.strip())
    if not match:
        return "", ""
    return match.group(1), match.group(2)


def canonicalize_headers(cells: list[str]) -> list[str]:
    return [HEADER_MAP.get(cell.strip().lower(), cell.strip().lower()) for cell in cells]


def extract_table_rows(content: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    headers: list[str] | None = None
    in_table = False

    for line in content.splitlines():
        cells = parse_markdown_row(line)
        if not cells:
            if in_table and headers:
                break
            continue

        if "Date of Sale" in line and "Type of Sale" in line:
            headers = canonicalize_headers(cells)
            in_table = True
            continue

        if not in_table or not headers or is_separator_row(cells):
            continue

        if len(cells) == len(headers) - 1 and "lease_start" in headers:
            lease_start_idx = headers.index("lease_start")
            cells = cells[:lease_start_idx] + [""] + cells[lease_start_idx:]

        if len(cells) != len(headers):
            continue

        rows.append(dict(zip(headers, cells)))

    return rows


def normalize_row(project_slug: str, source_file: str, row: dict[str, str]) -> dict[str, str] | None:
    if row.get("type_of_sale") != "Resale":
        return None

    sale_period, sale_month_year, sale_year, sale_month = parse_sale_period(row["date_of_sale"])
    floor_low, floor_high = parse_floor_range(row.get("floor_level", ""))

    return {
        "project_slug": project_slug,
        "project_name": row.get("project_name", ""),
        "sale_period": sale_period,
        "sale_month_year": sale_month_year,
        "sale_year_month": f"{sale_year:04d}-{sale_month:02d}",
        "sale_year": str(sale_year),
        "sale_month": str(sale_month),
        "street_name": row.get("street_name", ""),
        "district": row.get("district", ""),
        "market_segment": row.get("market_segment", ""),
        "tenure": row.get("tenure", ""),
        "lease_start": row.get("lease_start", ""),
        "floor_range": row.get("floor_level", ""),
        "floor_low": floor_low,
        "floor_high": floor_high,
        "floor_area_sqft": parse_int(row.get("floor_area_sqft", "")),
        "psf_sgd": parse_int(row.get("psf_sgd", "")),
        "sale_price_sgd": parse_int(row.get("sale_price_sgd", "")),
        "source_site": "propertyforsale.com.sg",
        "source_file": source_file,
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAILED_DIR.mkdir(parents=True, exist_ok=True)

    combined_rows: list[dict[str, str]] = []

    for source_file, project_slug in PROJECTS:
        source_path = FETCHED_DIR / source_file
        if not source_path.exists():
            print(f"skip {project_slug}: missing {source_path}")
            continue

        content = source_path.read_text(encoding="utf-8", errors="replace")
        project_rows: list[dict[str, str]] = []
        for raw_row in extract_table_rows(content):
            normalized = normalize_row(project_slug, source_file, raw_row)
            if normalized is not None:
                project_rows.append(normalized)

        project_rows.sort(
            key=lambda row: (
                row["sale_year_month"],
                row["sale_price_sgd"],
                row["floor_area_sqft"],
            ),
            reverse=True,
        )

        combined_rows.extend(project_rows)
        out_path = DETAILED_DIR / f"{project_slug}_transactions_detailed.csv"
        write_csv(out_path, project_rows)
        print(f"{project_slug}: wrote {len(project_rows)} rows -> {out_path}")

    combined_rows.sort(
        key=lambda row: (
            row["project_slug"],
            row["sale_year_month"],
            row["sale_price_sgd"],
            row["floor_area_sqft"],
        ),
        reverse=True,
    )
    combined_path = OUTPUT_DIR / "resale_transactions_detailed.csv"
    write_csv(combined_path, combined_rows)
    print(f"combined: wrote {len(combined_rows)} rows -> {combined_path}")


if __name__ == "__main__":
    main()
