#!/usr/bin/env python3
"""
POC: classify resale transactions by bed/bath using manually curated 99.co
listing evidence for Lakeville and Lake Grande.

This script is intentionally conservative:
- exact area match preferred
- otherwise nearest reference within +/- 1 sqft
- if candidates conflict, keep the row ambiguous instead of forcing a label
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path


BASE_DIR = Path("/Users/zhihao.ai/projects/property")
DATA_DIR = BASE_DIR / "data"
POC_DIR = DATA_DIR / "poc_layout"
REFERENCE_CSV = POC_DIR / "layout_reference_poc.csv"

PROJECTS = [
    ("lakeville", DATA_DIR / "lakeville_transactions.csv"),
    ("lakegrande", DATA_DIR / "lakegrande_transactions.csv"),
]

MATCH_TOLERANCE_SQFT = 1
CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}

OUTPUT_FIELDS = [
    "project_slug",
    "date",
    "sqft",
    "psf",
    "price",
    "layout_status",
    "normalized_type",
    "bedrooms",
    "bathrooms",
    "reference_area_sqft",
    "area_diff_sqft",
    "match_rule",
    "mapping_confidence",
    "evidence_kind",
    "evidence_urls",
    "evidence_notes",
]


def load_references() -> dict[str, list[dict[str, str | int]]]:
    grouped: dict[str, list[dict[str, str | int]]] = {}
    with REFERENCE_CSV.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row["reference_area_sqft"] = int(row["reference_area_sqft"])
            row["bedrooms"] = int(row["bedrooms"])
            row["bathrooms"] = int(row["bathrooms"])
            grouped.setdefault(str(row["project_slug"]), []).append(row)
    return grouped


def confidence_sort_key(value: str) -> int:
    return CONFIDENCE_RANK.get(value, 0)


def classify_row(
    project_slug: str,
    sqft: int,
    references: list[dict[str, str | int]],
) -> dict[str, str]:
    candidates: list[dict[str, str | int]] = []
    for ref in references:
        gap = abs(int(ref["reference_area_sqft"]) - sqft)
        if gap <= MATCH_TOLERANCE_SQFT:
            candidates.append(ref)

    if not candidates:
        return {
            "layout_status": "unmapped",
            "normalized_type": "",
            "bedrooms": "",
            "bathrooms": "",
            "reference_area_sqft": "",
            "area_diff_sqft": "",
            "match_rule": "",
            "mapping_confidence": "",
            "evidence_kind": "",
            "evidence_urls": "",
            "evidence_notes": "",
        }

    candidates.sort(
        key=lambda ref: (
            abs(int(ref["reference_area_sqft"]) - sqft),
            -confidence_sort_key(str(ref["confidence"])),
        )
    )

    unique_layouts = {
        (
            str(ref["normalized_type"]),
            int(ref["bedrooms"]),
            int(ref["bathrooms"]),
        )
        for ref in candidates
    }

    if len(unique_layouts) > 1:
        candidate_types = sorted(layout[0] for layout in unique_layouts)
        evidence_urls = sorted({str(ref["evidence_url"]) for ref in candidates})
        evidence_notes = sorted({str(ref["evidence_note"]) for ref in candidates})
        return {
            "layout_status": "ambiguous",
            "normalized_type": " | ".join(candidate_types),
            "bedrooms": "",
            "bathrooms": "",
            "reference_area_sqft": "",
            "area_diff_sqft": "",
            "match_rule": "conflicting_nearby_refs",
            "mapping_confidence": "",
            "evidence_kind": " | ".join(sorted({str(ref["evidence_kind"]) for ref in candidates})),
            "evidence_urls": " | ".join(evidence_urls),
            "evidence_notes": " | ".join(evidence_notes),
        }

    chosen = candidates[0]
    reference_area_sqft = int(chosen["reference_area_sqft"])
    gap = abs(reference_area_sqft - sqft)
    match_rule = "exact_area" if gap == 0 else f"nearest_{MATCH_TOLERANCE_SQFT}sqft"

    same_layout_refs = [
        ref
        for ref in candidates
        if str(ref["normalized_type"]) == str(chosen["normalized_type"])
        and int(ref["bedrooms"]) == int(chosen["bedrooms"])
        and int(ref["bathrooms"]) == int(chosen["bathrooms"])
    ]

    evidence_urls = " | ".join(sorted({str(ref["evidence_url"]) for ref in same_layout_refs}))
    evidence_notes = " | ".join(sorted({str(ref["evidence_note"]) for ref in same_layout_refs}))
    evidence_kind = " | ".join(sorted({str(ref["evidence_kind"]) for ref in same_layout_refs}))
    mapping_confidence = max(
        (str(ref["confidence"]) for ref in same_layout_refs),
        key=confidence_sort_key,
    )

    return {
        "layout_status": "matched",
        "normalized_type": str(chosen["normalized_type"]),
        "bedrooms": str(chosen["bedrooms"]),
        "bathrooms": str(chosen["bathrooms"]),
        "reference_area_sqft": str(reference_area_sqft),
        "area_diff_sqft": str(gap),
        "match_rule": match_rule,
        "mapping_confidence": mapping_confidence,
        "evidence_kind": evidence_kind,
        "evidence_urls": evidence_urls,
        "evidence_notes": evidence_notes,
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def build_summary(project_rows: dict[str, list[dict[str, str]]]) -> str:
    lines = [
        "# Layout Mapping POC Summary",
        "",
        "Sources: manually curated 99.co listing snippets captured via search-engine cache on 2026-03-12.",
        "Matching rule: exact area first, then nearest within +/- 1 sqft if there is no conflicting nearby reference.",
        "",
    ]

    for project_slug in sorted(project_rows):
        rows = project_rows[project_slug]
        total = len(rows)
        matched = sum(1 for row in rows if row["layout_status"] == "matched")
        ambiguous = sum(1 for row in rows if row["layout_status"] == "ambiguous")
        unmapped = total - matched - ambiguous
        exact = sum(1 for row in rows if row["match_rule"] == "exact_area")
        nearest = sum(1 for row in rows if row["match_rule"].startswith("nearest_"))
        coverage = (matched / total * 100) if total else 0.0

        unmapped_sizes = Counter(
            int(row["sqft"])
            for row in rows
            if row["layout_status"] != "matched"
        ).most_common(8)
        mapped_types = Counter(
            row["normalized_type"]
            for row in rows
            if row["layout_status"] == "matched"
        )

        lines.extend(
            [
                f"## {project_slug}",
                "",
                f"- total rows: {total}",
                f"- matched rows: {matched} ({coverage:.1f}%)",
                f"- ambiguous rows: {ambiguous}",
                f"- unmapped rows: {unmapped}",
                f"- exact matches: {exact}",
                f"- nearest +/-1 sqft matches: {nearest}",
                f"- mapped types: {', '.join(f'{k}={v}' for k, v in mapped_types.items()) or 'none'}",
                f"- top unmapped sizes: {', '.join(f'{sqft} sqft ({count})' for sqft, count in unmapped_sizes) or 'none'}",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    POC_DIR.mkdir(parents=True, exist_ok=True)
    references_by_project = load_references()
    project_rows: dict[str, list[dict[str, str]]] = {}

    for project_slug, csv_path in PROJECTS:
        refs = references_by_project.get(project_slug, [])
        rows: list[dict[str, str]] = []
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for source_row in reader:
                sqft = int(source_row["sqft"])
                classification = classify_row(project_slug, sqft, refs)
                rows.append(
                    {
                        "project_slug": project_slug,
                        "date": source_row["date"],
                        "sqft": source_row["sqft"],
                        "psf": source_row["psf"],
                        "price": source_row["price"],
                        **classification,
                    }
                )

        out_path = POC_DIR / f"{project_slug}_transactions_layout_poc.csv"
        write_csv(out_path, rows)
        project_rows[project_slug] = rows
        print(f"{project_slug}: wrote {len(rows)} rows -> {out_path}")

    summary_path = POC_DIR / "summary.md"
    summary_path.write_text(build_summary(project_rows), encoding="utf-8")
    print(f"summary: wrote {summary_path}")


if __name__ == "__main__":
    main()
