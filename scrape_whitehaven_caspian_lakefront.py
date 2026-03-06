#!/usr/bin/env python3
"""
Scrape Resale transaction data from propertyforsale.com.sg for:
- Whitehaven, Caspian, The Lakefront Residences

Output: date,sqft,psf,price (CSV format)
Only Resale records, exclude New Sale and Sub Sale.
"""

import re
from pathlib import Path

# Month name to 3-letter abbreviation
MONTH_MAP = {
    "January": "Jan", "February": "Feb", "March": "Mar", "April": "Apr",
    "May": "May", "June": "Jun", "July": "Jul", "August": "Aug",
    "September": "Sep", "October": "Oct", "November": "Nov", "December": "Dec"
}

# Fetched content files (from mcp_web_fetch) -> (output_csv, project_name)
PROJECTS = [
    ("faf51c66-bda4-42fd-b65c-8be0bec3abd5.txt", "whitehaven_transactions.csv", "Whitehaven"),
    ("ec8484a2-5986-4320-9dbe-3c2c88ddc8b4.txt", "caspian_transactions.csv", "Caspian"),
    ("2ed034c7-7c99-4d75-977b-a1cc527ed201.txt", "lakefront_transactions.csv", "The Lakefront Residences"),
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

    for line in lines:
        if "| Date of Sale |" in line and "Type of Sale |" in line:
            in_table = True
            continue
        if not in_table:
            continue
        if "| --- |" in line or "|---|" in line:
            continue
        if not line.strip().startswith("|"):
            break

        parts = [p.strip() for p in line.split("|")]
        # parts[0] and parts[-1] are empty due to leading/trailing |
        # Freehold: 1=Date, 2=Project, 3=Street, 4=District, 5=Segment, 6=Tenure, 7=TypeOfSale, 8=FloorLevel, 9=FloorArea, 10=PSF, 11=SalePrice
        # 99yrs:    1=Date, 2=Project, 3=Street, 4=District, 5=Segment, 6=Tenure, 7=LeaseStart, 8=TypeOfSale, 9=FloorLevel, 10=FloorArea, 11=PSF, 12=SalePrice
        if len(parts) < 12:
            continue

        type_of_sale = None
        date_raw = sqft_raw = psf_raw = price_raw = None

        if parts[7] == "Resale":
            # Freehold: no Lease Start column
            type_of_sale = "Resale"
            date_raw = parts[1]
            sqft_raw = parts[9]
            psf_raw = parts[10]
            price_raw = parts[11]
        elif len(parts) >= 13 and parts[8] == "Resale":
            # 99 yrs lease
            type_of_sale = "Resale"
            date_raw = parts[1]
            sqft_raw = parts[10]
            psf_raw = parts[11]
            price_raw = parts[12]

        if type_of_sale != "Resale":
            continue

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
    # Pattern: "PROJECT is a 99 yrs lease residential property..." or "Freehold residential property"
    tenure_match = re.search(r"is a ([^a]+(?:lease|hold)[^.]*)\.", content, re.I)
    if tenure_match:
        info["tenure"] = tenure_match.group(1).strip()
    # Lease Start = TOP year for 99 yrs lease (e.g., "2008", "2010")
    lease_match = re.search(r"\|\s*(\d{4})\s*\|\s*Resale\s*\|", content)
    if lease_match:
        info["top_year"] = lease_match.group(1)
    # For Freehold, try to find from description
    if info["top_year"] == "N/A":
        top_match = re.search(r"TOP\s*(\d{4})|completed\s*(\d{4})|(\d{4})\s*TOP", content, re.I)
        if top_match:
            info["top_year"] = next(g for g in top_match.groups() if g)
    # Units - try "xxx units"
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
