#!/usr/bin/env python3
"""
Extract Resale transaction data from propertyforsale.com.sg fetched pages.
Output: date,sqft,psf,price (CSV format)
"""

import re
import os
from pathlib import Path

# Month name to 3-letter abbreviation
MONTH_MAP = {
    "January": "Jan", "February": "Feb", "March": "Mar", "April": "Apr",
    "May": "May", "June": "Jun", "July": "Jul", "August": "Aug",
    "September": "Sep", "October": "Oct", "November": "Nov", "December": "Dec"
}

# Mapping: fetched file -> (output_csv, project_name for info)
PROJECTS = [
    ("5bc82b54-071b-4c07-afda-8977231aadae.txt", "stirling_residences_transactions.csv", "Stirling Residences"),
    ("72039a39-bbd6-4351-ba22-903af873be75.txt", "queens_peak_transactions.csv", "Queens Peak"),
    ("d4c8360a-b853-43d2-9e46-fa97f98fe4cc.txt", "commonwealth_towers_transactions.csv", "Commonwealth Towers"),
    ("0f7130d8-d32f-41dd-8ef7-9732bd336db0.txt", "the_trilinq_transactions.csv", "The Trilinq"),
    ("a9e5fa7f-0277-4989-97a3-418db9f24c29.txt", "clavon_transactions.csv", "Clavon"),
    ("defc6b6f-ebd2-4002-9267-d39cc8071196.txt", "artra_transactions.csv", "Artra"),
    ("70c05ad5-2873-496d-87d3-e15f2844117f.txt", "kent_ridge_hill_transactions.csv", "Kent Ridge Hill Residences"),
    ("ef2cd020-54ab-4fb0-83d0-cf2de0218ddc.txt", "j_gateway_transactions.csv", "J Gateway"),
]

FETCHED_DIR = Path("/Users/zhihao.ai/.cursor/projects/Users-zhihao-ai-projects-property/agent-tools")
OUTPUT_DIR = Path("/Users/zhihao.ai/projects/property/data")


def parse_date(date_str: str) -> str:
    """Convert 'February 2026' -> 'Feb2026'"""
    date_str = date_str.strip()
    for full, abbr in MONTH_MAP.items():
        if date_str.startswith(full):
            year = date_str[len(full):].strip()
            return f"{abbr}{year}"
    return date_str


def strip_commas(s: str) -> str:
    """Remove commas from number string"""
    return s.strip().replace(",", "")


def extract_resale_rows(content: str) -> list[dict]:
    """Parse markdown table and return Resale rows as {date, sqft, psf, price}"""
    lines = content.split("\n")
    rows = []
    in_table = False
    header_found = False

    for line in lines:
        if "| Date of Sale |" in line and "Type of Sale |" in line:
            in_table = True
            header_found = True
            continue
        if not in_table:
            continue
        if "| --- |" in line or "|---|" in line:
            continue
        if not line.strip().startswith("|"):
            # End of table
            break

        parts = [p.strip() for p in line.split("|")]
        # parts[0] and parts[-1] are empty due to leading/trailing |
        # Indices: 1=Date, 2=Project, 3=Street, 4=District, 5=Segment, 6=Tenure, 7=LeaseStart, 8=TypeOfSale, 9=FloorLevel, 10=FloorArea, 11=PSF, 12=SalePrice
        if len(parts) < 13:
            continue
        type_of_sale = parts[8].strip()
        if type_of_sale != "Resale":
            continue

        date_raw = parts[1]
        sqft_raw = parts[10]
        psf_raw = parts[11]
        price_raw = parts[12]

        try:
            date = parse_date(date_raw)
            sqft = strip_commas(sqft_raw)
            psf = strip_commas(psf_raw)
            price = strip_commas(price_raw)
            if sqft and psf and price and date:
                rows.append({"date": date, "sqft": sqft, "psf": psf, "price": price})
        except Exception:
            continue

    return rows


def extract_project_info(content: str) -> dict:
    """Extract TOP year, tenure, total units from page content"""
    info = {"tenure": "N/A", "top_year": "N/A", "units": "N/A"}
    # Pattern: "PROJECT is a 99 yrs lease residential property..."
    tenure_match = re.search(r"is a ([^a]+(?:lease|hold)[^.]*)\.", content, re.I)
    if tenure_match:
        info["tenure"] = tenure_match.group(1).strip()
    # Look for TOP or completion year - often in project description
    top_match = re.search(r"TOP\s*(\d{4})|completed\s*(\d{4})|(\d{4})\s*TOP", content, re.I)
    if top_match:
        info["top_year"] = next(g for g in top_match.groups() if g)
    # Units - harder to find, try "xxx units" or "xxx-unit"
    units_match = re.search(r"(\d[\d,]*)\s*units?", content, re.I)
    if units_match:
        info["units"] = units_match.group(1).replace(",", "")
    return info


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for src_file, out_csv, project_name in PROJECTS:
        src_path = FETCHED_DIR / src_file
        out_path = OUTPUT_DIR / out_csv

        if not src_path.exists():
            print(f"  {project_name}: SKIP - file not found: {src_path}")
            results.append((project_name, 0, {"tenure": "N/A", "top_year": "N/A", "units": "N/A"}))
            continue

        content = src_path.read_text(encoding="utf-8", errors="replace")
        rows = extract_resale_rows(content)
        info = extract_project_info(content)

        with open(out_path, "w", encoding="utf-8") as f:
            f.write("date,sqft,psf,price\n")
            for r in rows:
                f.write(f"{r['date']},{r['sqft']},{r['psf']},{r['price']}\n")

        results.append((project_name, len(rows), info))
        print(f"  {project_name}: {len(rows)} Resale records -> {out_path.name}")

    return results


if __name__ == "__main__":
    main()
