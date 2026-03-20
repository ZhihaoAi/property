#!/usr/bin/env python3
"""
Fetch URA private residential datasets and build a project-name index.

Usage:
  python3 scripts/fetch_ura_private_residential.py --access-key YOUR_KEY
  python3 scripts/fetch_ura_private_residential.py --access-key YOUR_KEY --project lakeville
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.parse
from pathlib import Path


BASE_DIR = Path("/Users/zhihao.ai/projects/property")
OUTPUT_DIR = BASE_DIR / "data" / "ura"

TOKEN_URL = "https://eservice.ura.gov.sg/uraDataService/insertNewToken/v1"
SERVICE_URL = "https://eservice.ura.gov.sg/uraDataService/invokeUraDS/v1"


def get_json(url: str, headers: dict[str, str]) -> dict:
    cmd = ["curl", "-sS", url]
    for key, value in headers.items():
        cmd.extend(["-H", f"{key}: {value}"])
    result = subprocess.run(cmd, check=True, capture_output=True)
    return json.loads(result.stdout.decode("utf-8", errors="replace"))


def get_token(access_key: str) -> str:
    payload = get_json(TOKEN_URL, {"AccessKey": access_key})
    if payload.get("Status") != "Success" or not payload.get("Result"):
        raise RuntimeError(f"Failed to get token: {payload}")
    return payload["Result"]


def fetch_service(access_key: str, token: str, service: str, **params: str) -> dict:
    query = {"service": service, **params}
    url = f"{SERVICE_URL}?{urllib.parse.urlencode(query)}"
    payload = get_json(url, {"AccessKey": access_key, "Token": token})
    if payload.get("Status") != "Success":
        raise RuntimeError(f"Service {service} failed: {payload}")
    return payload


def quarter_iter(start_year: int, start_quarter: int, end_year: int, end_quarter: int) -> list[str]:
    year = start_year
    quarter = start_quarter
    values: list[str] = []
    while (year, quarter) <= (end_year, end_quarter):
        values.append(f"{str(year)[2:]}q{quarter}")
        quarter += 1
        if quarter == 5:
            year += 1
            quarter = 1
    return values


def build_project_index(
    transactions_batches: list[dict],
    rental_median_payload: dict,
    rental_payloads: dict[str, dict],
) -> dict[str, dict]:
    index: dict[str, dict] = {}

    def ensure_project(project_name: str) -> dict:
        slug = slugify(project_name)
        if slug not in index:
            index[slug] = {
                "project": project_name,
                "slug": slug,
                "transactions": [],
                "rentalMedian": [],
                "rentalContracts": [],
                "street": None,
                "districts": [],
                "coords": None,
            }
        return index[slug]

    for batch_no, payload in enumerate(transactions_batches, start=1):
        for project in payload.get("Result", []):
            entry = ensure_project(project["project"])
            entry["street"] = project.get("street") or entry["street"]
            entry["coords"] = {"x": project.get("x"), "y": project.get("y")}
            districts = {tx.get("district") for tx in project.get("transaction", []) if tx.get("district")}
            entry["districts"] = sorted(set(entry["districts"]) | districts)
            for tx in project.get("transaction", []):
                entry["transactions"].append({"batch": batch_no, **tx})

    for project in rental_median_payload.get("Result", []):
        entry = ensure_project(project["project"])
        entry["street"] = project.get("street") or entry["street"]
        entry["coords"] = {"x": project.get("x"), "y": project.get("y")}
        districts = {item.get("district") for item in project.get("rentalMedian", []) if item.get("district")}
        entry["districts"] = sorted(set(entry["districts"]) | districts)
        entry["rentalMedian"].extend(project.get("rentalMedian", []))

    for ref_period, payload in rental_payloads.items():
        for project in payload.get("Result", []):
            entry = ensure_project(project["project"])
            entry["street"] = project.get("street") or entry["street"]
            entry["coords"] = {"x": project.get("x"), "y": project.get("y")}
            districts = {item.get("district") for item in project.get("rental", []) if item.get("district")}
            entry["districts"] = sorted(set(entry["districts"]) | districts)
            for rental in project.get("rental", []):
                entry["rentalContracts"].append({"refPeriod": ref_period, **rental})

    for entry in index.values():
        entry["transactions"].sort(key=lambda item: item.get("contractDate", ""))
        entry["rentalMedian"].sort(key=lambda item: item.get("refPeriod", ""))
        entry["rentalContracts"].sort(key=lambda item: (item.get("refPeriod", ""), item.get("leaseDate", "")))

    return index


def slugify(value: str) -> str:
    cleaned = []
    for char in value.lower():
        if char.isalnum():
            cleaned.append(char)
        elif cleaned and cleaned[-1] != "_":
            cleaned.append("_")
    return "".join(cleaned).strip("_")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def summarize_project(project: dict) -> dict:
    return {
        "project": project["project"],
        "slug": project["slug"],
        "street": project["street"],
        "districts": project["districts"],
        "coords": project["coords"],
        "transactionCount": len(project["transactions"]),
        "transactionDateRange": transaction_date_range(project["transactions"]),
        "rentalMedianCount": len(project["rentalMedian"]),
        "rentalMedianRange": rental_median_range(project["rentalMedian"]),
        "rentalContractCount": len(project["rentalContracts"]),
        "rentalContractRange": rental_contract_range(project["rentalContracts"]),
    }


def transaction_date_range(items: list[dict]) -> list[str] | None:
    dates = sorted({item.get("contractDate") for item in items if item.get("contractDate")})
    if not dates:
        return None
    return [dates[0], dates[-1]]


def rental_median_range(items: list[dict]) -> list[str] | None:
    dates = sorted({item.get("refPeriod") for item in items if item.get("refPeriod")})
    if not dates:
        return None
    return [dates[0], dates[-1]]


def rental_contract_range(items: list[dict]) -> list[str] | None:
    ref_periods = sorted({item.get("refPeriod") for item in items if item.get("refPeriod")})
    if not ref_periods:
        return None
    return [ref_periods[0], ref_periods[-1]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--access-key", required=True)
    parser.add_argument("--project", help="Optional project slug/name to print after fetch")
    parser.add_argument("--latest-quarter", default="26q1", help="Latest rental-contract quarter to fetch, yyqN")
    return parser.parse_args()


def latest_quarter_to_bounds(latest_quarter: str) -> tuple[int, int]:
    yy = int(latest_quarter[:2])
    quarter = int(latest_quarter[-1])
    return 2000 + yy, quarter


def main() -> int:
    args = parse_args()
    access_key = args.access_key
    latest_year, latest_quarter = latest_quarter_to_bounds(args.latest_quarter)

    token = get_token(access_key)
    print(f"Token acquired. Prefix: {token[:12]}...")

    transactions_batches: list[dict] = []
    for batch in ("1", "2", "3", "4"):
        payload = fetch_service(access_key, token, "PMI_Resi_Transaction", batch=batch)
        transactions_batches.append(payload)
        write_json(OUTPUT_DIR / f"transactions_batch_{batch}.json", payload)
        print(f"Fetched transactions batch {batch}: {len(payload.get('Result', []))} projects")

    rental_median_payload = fetch_service(access_key, token, "PMI_Resi_Rental_Median")
    write_json(OUTPUT_DIR / "rental_median.json", rental_median_payload)
    print(f"Fetched rental median: {len(rental_median_payload.get('Result', []))} projects")

    rental_payloads: dict[str, dict] = {}
    start_year = latest_year - 5
    quarters = quarter_iter(start_year, latest_quarter, latest_year, latest_quarter)
    for ref_period in quarters:
        payload = fetch_service(access_key, token, "PMI_Resi_Rental", refPeriod=ref_period)
        rental_payloads[ref_period] = payload
        write_json(OUTPUT_DIR / "rental_contracts" / f"{ref_period}.json", payload)
        print(f"Fetched rental contracts {ref_period}: {len(payload.get('Result', []))} projects")

    project_index = build_project_index(transactions_batches, rental_median_payload, rental_payloads)
    write_json(OUTPUT_DIR / "projects_index.json", project_index)

    summary = {
        slug: summarize_project(project)
        for slug, project in sorted(project_index.items())
    }
    write_json(OUTPUT_DIR / "projects_summary.json", summary)

    if args.project:
        target = slugify(args.project)
        project = project_index.get(target)
        if not project:
            print(f"Project not found: {args.project}", file=sys.stderr)
            return 2
        print(json.dumps(summarize_project(project), indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
