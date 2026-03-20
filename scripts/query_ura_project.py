#!/usr/bin/env python3
"""
Query locally cached URA private residential data by project name.

Usage:
  python3 scripts/query_ura_project.py lakeville
  python3 scripts/query_ura_project.py "Lakeville" --full
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BASE_DIR = Path("/Users/zhihao.ai/projects/property")
INDEX_PATH = BASE_DIR / "data" / "ura" / "projects_index.json"


def slugify(value: str) -> str:
    cleaned = []
    for char in value.lower():
        if char.isalnum():
            cleaned.append(char)
        elif cleaned and cleaned[-1] != "_":
            cleaned.append("_")
    return "".join(cleaned).strip("_")


def summarize(project: dict) -> dict:
    transactions = project.get("transactions", [])
    rental_median = project.get("rentalMedian", [])
    rental_contracts = project.get("rentalContracts", [])
    return {
        "project": project.get("project"),
        "slug": project.get("slug"),
        "street": project.get("street"),
        "districts": project.get("districts", []),
        "coords": project.get("coords"),
        "transactionCount": len(transactions),
        "rentalMedianCount": len(rental_median),
        "rentalContractCount": len(rental_contracts),
        "latestTransactions": transactions[-5:],
        "latestRentalMedian": rental_median[-5:],
        "latestRentalContracts": rental_contracts[-5:],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()

    if not INDEX_PATH.exists():
        print(f"Missing local index: {INDEX_PATH}", file=sys.stderr)
        return 2

    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    target = slugify(args.project)
    project = index.get(target)
    if not project:
        print(f"Project not found: {args.project}", file=sys.stderr)
        return 1

    payload = project if args.full else summarize(project)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
