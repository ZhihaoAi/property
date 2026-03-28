#!/usr/bin/env python3
"""
Build formal project layout catalogs and transaction-to-layout mappings.

This formalizes the previous Lakeville / Lake Grande POC into stable outputs:
- data/layout_mapping/layout_reference_catalog.csv
- data/layout_mapping/<project>_transaction_layout_map.csv
- data/layout_mapping/summary.json
- data/layout_mapping/summary.md
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
INPUT_REFERENCE = DATA_DIR / "poc_layout" / "layout_reference_poc.csv"
OUTPUT_DIR = DATA_DIR / "layout_mapping"

PROJECTS = {
    "lakeville": DATA_DIR / "lakeville_transactions.csv",
    "lakegrande": DATA_DIR / "lakegrande_transactions.csv",
}

MATCH_TOLERANCE_SQFT = 1
CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}

CATALOG_FIELDS = [
    "project_slug",
    "reference_area_sqft",
    "catalog_status",
    "layout_options",
    "resolved_layout",
    "bedrooms",
    "bathrooms",
    "best_confidence",
    "evidence_count",
    "evidence_kinds",
    "evidence_urls",
    "evidence_notes",
]

MAP_FIELDS = [
    "project_slug",
    "date",
    "sqft",
    "psf",
    "price",
    "mapping_status",
    "resolved_layout",
    "bedrooms",
    "bathrooms",
    "layout_options",
    "reference_area_sqft",
    "area_diff_sqft",
    "match_rule",
    "mapping_confidence",
    "review_note",
    "evidence_kinds",
    "evidence_urls",
    "evidence_notes",
]


def confidence_sort_key(value: str) -> int:
    return CONFIDENCE_RANK.get(value, 0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--projects",
        nargs="*",
        default=["lakeville", "lakegrande"],
        help="Project slugs to build. Defaults to Lakeville and Lake Grande.",
    )
    return parser.parse_args()


def load_reference_rows() -> list[dict[str, str]]:
    with INPUT_REFERENCE.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def normalize_layout_option(row: dict[str, str]) -> tuple[str, str, str]:
    return row["normalized_type"], row["bedrooms"], row["bathrooms"]


def build_catalog(reference_rows: list[dict[str, str]]) -> tuple[dict[str, list[dict[str, str]]], list[dict[str, str]]]:
    grouped: dict[str, dict[int, list[dict[str, str]]]] = defaultdict(lambda: defaultdict(list))
    for row in reference_rows:
        grouped[row["project_slug"]][int(row["reference_area_sqft"])].append(row)

    catalogs_by_project: dict[str, list[dict[str, str]]] = {}
    catalog_rows: list[dict[str, str]] = []

    for project_slug, area_map in grouped.items():
        project_catalog: list[dict[str, str]] = []
        for area_sqft in sorted(area_map):
            refs = area_map[area_sqft]
            unique_layouts = sorted({normalize_layout_option(ref) for ref in refs})
            evidence_urls = " | ".join(sorted({ref["evidence_url"] for ref in refs}))
            evidence_notes = " | ".join(sorted({ref["evidence_note"] for ref in refs}))
            evidence_kinds = " | ".join(sorted({ref["evidence_kind"] for ref in refs}))
            best_confidence = max((ref["confidence"] for ref in refs), key=confidence_sort_key)
            resolved = len(unique_layouts) == 1
            chosen = unique_layouts[0] if resolved else ("", "", "")
            row = {
                "project_slug": project_slug,
                "reference_area_sqft": str(area_sqft),
                "catalog_status": "resolved" if resolved else "conflicting",
                "layout_options": " | ".join(
                    f"{layout_type} ({beds}b/{baths}ba)" for layout_type, beds, baths in unique_layouts
                ),
                "resolved_layout": chosen[0],
                "bedrooms": chosen[1],
                "bathrooms": chosen[2],
                "best_confidence": best_confidence,
                "evidence_count": str(len(refs)),
                "evidence_kinds": evidence_kinds,
                "evidence_urls": evidence_urls,
                "evidence_notes": evidence_notes,
            }
            project_catalog.append(row)
            catalog_rows.append(row)
        catalogs_by_project[project_slug] = project_catalog

    return catalogs_by_project, catalog_rows


def classify_transaction(sqft: int, catalog: list[dict[str, str]]) -> dict[str, str]:
    candidates = []
    for entry in catalog:
        area_sqft = int(entry["reference_area_sqft"])
        gap = abs(area_sqft - sqft)
        if gap <= MATCH_TOLERANCE_SQFT:
            candidates.append((gap, entry))

    if not candidates:
        return {
            "mapping_status": "unmapped",
            "resolved_layout": "",
            "bedrooms": "",
            "bathrooms": "",
            "layout_options": "",
            "reference_area_sqft": "",
            "area_diff_sqft": "",
            "match_rule": "",
            "mapping_confidence": "",
            "review_note": "No nearby reference area found within +/- 1 sqft.",
            "evidence_kinds": "",
            "evidence_urls": "",
            "evidence_notes": "",
        }

    candidates.sort(key=lambda item: (item[0], -confidence_sort_key(item[1]["best_confidence"])))
    gap, chosen = candidates[0]
    match_rule = "exact_area" if gap == 0 else f"nearest_{MATCH_TOLERANCE_SQFT}sqft"

    if chosen["catalog_status"] == "conflicting":
        return {
            "mapping_status": "ambiguous",
            "resolved_layout": "",
            "bedrooms": "",
            "bathrooms": "",
            "layout_options": chosen["layout_options"],
            "reference_area_sqft": chosen["reference_area_sqft"],
            "area_diff_sqft": str(gap),
            "match_rule": match_rule,
            "mapping_confidence": chosen["best_confidence"],
            "review_note": "Conflicting bath/layout evidence exists for this area. Keep unresolved.",
            "evidence_kinds": chosen["evidence_kinds"],
            "evidence_urls": chosen["evidence_urls"],
            "evidence_notes": chosen["evidence_notes"],
        }

    return {
        "mapping_status": "matched",
        "resolved_layout": chosen["resolved_layout"],
        "bedrooms": chosen["bedrooms"],
        "bathrooms": chosen["bathrooms"],
        "layout_options": chosen["layout_options"],
        "reference_area_sqft": chosen["reference_area_sqft"],
        "area_diff_sqft": str(gap),
        "match_rule": match_rule,
        "mapping_confidence": chosen["best_confidence"],
        "review_note": "",
        "evidence_kinds": chosen["evidence_kinds"],
        "evidence_urls": chosen["evidence_urls"],
        "evidence_notes": chosen["evidence_notes"],
    }


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_project_mappings(project_slug: str, catalog: list[dict[str, str]], tx_path: Path) -> tuple[list[dict[str, str]], dict]:
    rows: list[dict[str, str]] = []
    with tx_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for tx in reader:
            mapping = classify_transaction(int(tx["sqft"]), catalog)
            rows.append(
                {
                    "project_slug": project_slug,
                    "date": tx["date"],
                    "sqft": tx["sqft"],
                    "psf": tx["psf"],
                    "price": tx["price"],
                    **mapping,
                }
            )

    total = len(rows)
    matched = [row for row in rows if row["mapping_status"] == "matched"]
    ambiguous = [row for row in rows if row["mapping_status"] == "ambiguous"]
    unmapped = [row for row in rows if row["mapping_status"] == "unmapped"]
    layout_counts = Counter(row["resolved_layout"] for row in matched)
    unresolved_sizes = Counter(int(row["sqft"]) for row in ambiguous + unmapped).most_common(8)

    summary = {
        "project_slug": project_slug,
        "total_rows": total,
        "matched_rows": len(matched),
        "ambiguous_rows": len(ambiguous),
        "unmapped_rows": len(unmapped),
        "coverage_pct": round((len(matched) / total * 100) if total else 0.0, 1),
        "layout_counts": dict(layout_counts),
        "unresolved_sizes": [{"sqft": sqft, "count": count} for sqft, count in unresolved_sizes],
        "recent_matched_examples": matched[:5],
        "recent_ambiguous_examples": ambiguous[:5],
    }
    return rows, summary


def build_summary_markdown(summary_payload: dict) -> str:
    lines = [
        "# Project Layout Mapping Summary",
        "",
        "This formal mapping uses the manually curated 99.co evidence table as the layout reference catalog.",
        "Matching rule: exact area first, then nearest within +/- 1 sqft. Conflicting layout evidence remains ambiguous.",
        "",
    ]

    for project_slug, item in summary_payload["projects"].items():
        layout_counts = item["layout_counts"]
        unresolved_text = ", ".join(
            f"{entry['sqft']} sqft ({entry['count']})" for entry in item["unresolved_sizes"]
        ) or "none"
        lines.extend(
            [
                f"## {project_slug}",
                "",
                f"- coverage: {item['matched_rows']} / {item['total_rows']} matched ({item['coverage_pct']}%)",
                f"- ambiguous: {item['ambiguous_rows']}",
                f"- unmapped: {item['unmapped_rows']}",
                f"- matched layouts: {', '.join(f'{k}={v}' for k, v in layout_counts.items()) or 'none'}",
                f"- unresolved sizes: {unresolved_text}",
                "",
            ]
        )

        if item["recent_ambiguous_examples"]:
            lines.append("Ambiguous examples:")
            for row in item["recent_ambiguous_examples"]:
                lines.append(
                    f"- {row['date']} · {row['sqft']} sqft · options: {row['layout_options']}"
                )
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    selected_projects = [project for project in args.projects if project in PROJECTS]
    if not selected_projects:
        raise SystemExit("No valid projects selected.")

    reference_rows = load_reference_rows()
    catalogs_by_project, catalog_rows = build_catalog(reference_rows)
    write_csv(OUTPUT_DIR / "layout_reference_catalog.csv", CATALOG_FIELDS, catalog_rows)

    summary_payload = {"projects": {}}
    for project_slug in selected_projects:
        catalog = catalogs_by_project.get(project_slug, [])
        tx_rows, summary = build_project_mappings(project_slug, catalog, PROJECTS[project_slug])
        write_csv(OUTPUT_DIR / f"{project_slug}_transaction_layout_map.csv", MAP_FIELDS, tx_rows)
        summary_payload["projects"][project_slug] = summary
        print(
            f"{project_slug}: matched {summary['matched_rows']}/{summary['total_rows']} "
            f"({summary['coverage_pct']}%), ambiguous {summary['ambiguous_rows']}, unmapped {summary['unmapped_rows']}"
        )

    write_json(OUTPUT_DIR / "summary.json", summary_payload)
    (OUTPUT_DIR / "summary.md").write_text(build_summary_markdown(summary_payload), encoding="utf-8")
    print(f"wrote {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
