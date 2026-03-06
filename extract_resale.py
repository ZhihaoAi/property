#!/usr/bin/env python3
"""
Extract Resale transactions from crawled markdown table files and save as CSV.
"""

import csv
import re
from pathlib import Path

# Full month name to abbreviation
MONTH_ABBR = {
    "January": "Jan", "February": "Feb", "March": "Mar", "April": "Apr",
    "May": "May", "June": "Jun", "July": "Jul", "August": "Aug",
    "September": "Sep", "October": "Oct", "November": "Nov", "December": "Dec",
}


def parse_date_to_monthyear(date_str: str) -> str:
    """Convert 'February 2026' to 'Feb2026'."""
    date_str = date_str.strip()
    for full, abbr in MONTH_ABBR.items():
        if date_str.startswith(full):
            year = date_str[len(full):].strip()
            return f"{abbr}{year}"
    raise ValueError(f"Cannot parse date: {date_str}")


def parse_number(s: str) -> int:
    """Remove commas and convert to int."""
    return int(s.replace(",", "").strip())


def extract_resale_from_markdown(file_path: Path) -> list[dict]:
    """
    Parse markdown table, extract rows where Type of Sale = Resale.
    Returns list of {date, sqft, psf, price}.
    """
    lines = file_path.read_text(encoding="utf-8").splitlines()
    rows = []
    in_table = False

    for line in lines:
        if not line.strip().startswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")]
        # Skip header and separator rows
        if len(parts) < 13:
            continue
        if "Date of Sale" in line or "---" in line:
            in_table = True
            continue
        # Data row: date=1, type=8, floor_area=10, psf=11, sale_price=12
        try:
            date_raw = parts[1]
            type_of_sale = parts[8]
            if type_of_sale != "Resale":
                continue
            floor_area = parse_number(parts[10])
            psf = parse_number(parts[11])
            sale_price = parse_number(parts[12])
            date_str = parse_date_to_monthyear(date_raw)
            rows.append({"date": date_str, "sqft": floor_area, "psf": psf, "price": sale_price})
        except (ValueError, IndexError) as e:
            continue  # Skip malformed rows

    return rows


def main():
    base = Path(__file__).resolve().parent
    data_dir = base / "data"
    tools_dir = Path("/Users/zhihao.ai/.cursor/projects/Users-zhihao-ai-projects-property/agent-tools")

    mappings = [
        ("15f61f1e-2cb7-40a4-b625-c728c954cbae.txt", "seahill_transactions.csv"),
        ("bc0f8956-f190-4bf6-a91e-a413641e0584.txt", "the_vision_transactions.csv"),
        ("82612131-2875-4911-b8c3-70be5c5154c0.txt", "hundred_trees_transactions.csv"),
        ("69538a84-0c38-4d93-89e9-b9c3301ddae9.txt", "parc_clematis_transactions.csv"),
    ]

    data_dir.mkdir(exist_ok=True)

    for src_id, csv_name in mappings:
        src_path = tools_dir / src_id
        if not src_path.exists():
            print(f"Skip: {src_id} not found")
            continue
        rows = extract_resale_from_markdown(src_path)
        out_path = data_dir / csv_name
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["date", "sqft", "psf", "price"])
            writer.writeheader()
            writer.writerows(rows)
        print(f"Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
