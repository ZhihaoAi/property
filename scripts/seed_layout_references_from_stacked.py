#!/usr/bin/env python3
"""
Seed layout reference evidence from Stacked directory brochure/floor-plan sources.

The script is intentionally conservative:
- existing manual rows are preserved;
- auto-generated rows are tagged with [auto-stacked] and replaced on rerun;
- source status is written for every root data/*_transactions.csv project;
- PDFs that cannot be text-parsed are recorded in the manifest instead of guessed.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote

import requests
from pypdf import PdfReader


BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
from build_dashboard_data import slug_to_name

DATA_DIR = BASE_DIR / "data"
REFERENCE_PATH = DATA_DIR / "poc_layout" / "layout_reference_poc.csv"
MANIFEST_PATH = DATA_DIR / "poc_layout" / "layout_source_manifest.csv"

AUTO_NOTE_PREFIX = "[auto-stacked]"
STACKED_BASE = "https://directory.stackedhomes.com/condo"
TIMEOUT_SECONDS = 20

REFERENCE_FIELDS = [
    "project_slug",
    "reference_area_sqft",
    "bedrooms",
    "bathrooms",
    "normalized_type",
    "confidence",
    "evidence_kind",
    "evidence_url",
    "evidence_note",
]

MANIFEST_FIELDS = [
    "project_slug",
    "project_name",
    "source_url",
    "source_type",
    "source_status",
    "notes",
]

STACKED_SLUG_OVERRIDES = {
    "clement_canopy": ["the-clement-canopy", "clement-canopy"],
    "hillview_peak": ["kingsford-hillview-peak", "hillview-peak"],
    "kent_ridge_hill": ["kent-ridge-hill-residences", "kent-ridge-hill"],
    "lakefront": ["lakefront-residences", "lakefront"],
    "lakegrande": ["lake-grande", "lakegrande"],
    "skysuites_anson": ["skysuites-at-anson", "skysuites-anson"],
    "village_pasir_panjang": ["village-at-pasir-panjang", "village-pasir-panjang"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--projects", nargs="*", help="Optional project slugs. Defaults to every root transaction CSV.")
    return parser.parse_args()


def discover_transaction_projects() -> list[str]:
    return sorted(path.name.removesuffix("_transactions.csv") for path in DATA_DIR.glob("*_transactions.csv"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def stacked_candidates(project_slug: str) -> list[str]:
    return STACKED_SLUG_OVERRIDES.get(project_slug, [project_slug.replace("_", "-")])


def fetch_stacked_page(project_slug: str) -> tuple[str | None, str | None]:
    for stacked_slug in stacked_candidates(project_slug):
        url = f"{STACKED_BASE}/{stacked_slug}/"
        try:
            response = requests.get(url, timeout=TIMEOUT_SECONDS)
        except requests.RequestException:
            continue
        if response.status_code == 200 and "Floor Plans" in response.text:
            return response.url, response.text
    return None, None


def extract_brochure_url(html: str) -> str | None:
    hrefs = re.findall(r'href="([^"]+)"', html)
    brochure_urls = [
        href
        for href in hrefs
        if "stacked-condo-database" in href
        and "brochure" in href.lower()
        and href.lower().endswith(".pdf")
    ]
    return unquote(brochure_urls[0]) if brochure_urls else None


def extract_floorplan_urls(html: str) -> list[str]:
    urls = []
    for attr in ("data-src", "src"):
        urls.extend(re.findall(rf'{attr}="([^"]+)"', html))
    return sorted({unquote(url) for url in urls if "stacked-condo-database" in url and "floorplan" in url.lower()})


def type_to_bedrooms(type_name: str, context: str) -> int | None:
    type_text = type_name.lower()
    numeric_type = re.search(r"type\s*\(?([0-5])", type_text)
    if numeric_type:
        return int(numeric_type.group(1))

    alpha_type = re.search(r"(?:type\s+|^s?)([abcde])", type_name, re.IGNORECASE)
    if alpha_type:
        return {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}[alpha_type.group(1).lower()]

    context_text = context.lower()
    if "studio" in context_text:
        return 0
    bedroom_match = re.search(r"([1-5])\s*[-+]?\s*bedroom", context_text)
    if bedroom_match:
        return int(bedroom_match.group(1))
    return None


def infer_bathrooms(bedrooms: int, sqft: int, type_name: str, context: str) -> int:
    text = f"{type_name} {context}".lower()
    if bedrooms <= 1:
        return 1
    if bedrooms == 2:
        if "bath 2" in text or "master bath" in text:
            return 2
        return 2 if sqft >= 600 else 1
    if bedrooms == 3:
        if "bath 3" in text or "3y" in text or "yard" in text or "wc" in text or sqft >= 1000:
            return 3
        return 2
    if bedrooms == 4:
        if "bath 4" in text or "dual" in text or sqft >= 1250:
            return 4
        return 3
    return 4


def normalized_type(bedrooms: int, bathrooms: int) -> str:
    if bedrooms == 0:
        return "studio1b"
    return f"{bedrooms}b{bathrooms}b"


def area_from_line(line: str) -> int | None:
    sqft_match = re.search(r"(\d{3,4})\s*sq\.?\s*ft\.?", line, re.IGNORECASE)
    if sqft_match:
        return int(sqft_match.group(1))
    sqm_match = re.search(r"(\d{2,3})\s*sq\.?\s*m\.?", line, re.IGNORECASE)
    if sqm_match:
        return round(int(sqm_match.group(1)) * 10.7639)
    sqm_compact_match = re.search(r"(\d{2,3})\s*sqm", line, re.IGNORECASE)
    if sqm_compact_match:
        return round(int(sqm_compact_match.group(1)) * 10.7639)
    return None


def parse_brochure_rows(project_slug: str, brochure_url: str) -> tuple[list[dict[str, str]], str]:
    response = requests.get(brochure_url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    temp_path = Path(tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name)
    temp_path.write_bytes(response.content)

    try:
        pages = PdfReader(str(temp_path)).pages
        parsed_rows: list[dict[str, str]] = []
        for page in pages:
            text = page.extract_text() or ""
            if "type" not in text.lower() and "sq ft" not in text.lower() and "sq.ft" not in text.lower():
                continue
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            for index, line in enumerate(lines):
                is_type_line = re.match(r"^type\b", line, re.IGNORECASE)
                is_stack_code_line = re.match(r"^s?[A-E][A-Za-z]*\d[A-Za-z0-9()]*$", line, re.IGNORECASE)
                if not (is_type_line or is_stack_code_line):
                    continue
                area = None
                for area_index in range(index + 1, min(len(lines), index + 12)):
                    if area_index > index + 1 and re.match(r"^type\b", lines[area_index], re.IGNORECASE):
                        break
                    area = area_from_line(lines[area_index])
                    if area is not None:
                        break
                if area is None or not 250 <= area <= 5000:
                    continue

                context = "\n".join(lines[max(0, index - 8): min(len(lines), index + 18)])
                bedrooms = type_to_bedrooms(line, context)
                if bedrooms is None:
                    continue
                bathrooms = infer_bathrooms(bedrooms, area, line, context)
                parsed_rows.append(
                    {
                        "project_slug": project_slug,
                        "reference_area_sqft": str(area),
                        "bedrooms": str(bedrooms),
                        "bathrooms": str(bathrooms),
                        "normalized_type": normalized_type(bedrooms, bathrooms),
                        "confidence": "medium",
                        "evidence_kind": "third_party_original_brochure",
                        "evidence_url": brochure_url,
                        "evidence_note": (
                            f"{AUTO_NOTE_PREFIX} Stacked-hosted original brochure text lists {line} at {area} sqft; "
                            "bedroom count comes from brochure type/category and bathroom count is inferred from floor-plan labels/standard layout convention."
                        ),
                    }
                )
        return parsed_rows, "parsed" if parsed_rows else "found_unparsed"
    except Exception as exc:  # pypdf can fail on encrypted/image-only PDFs.
        return [], f"parse_failed:{type(exc).__name__}"


def dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str, str, str]] = set()
    deduped = []
    for row in rows:
        key = (
            row["project_slug"],
            row["reference_area_sqft"],
            row["bedrooms"],
            row["bathrooms"],
            row["normalized_type"],
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def main() -> int:
    args = parse_args()
    selected_projects = sorted(args.projects or discover_transaction_projects())
    selected_set = set(selected_projects)
    existing_rows = read_csv(REFERENCE_PATH)
    existing_manifest_rows = read_csv(MANIFEST_PATH)
    manual_rows = [row for row in existing_rows if not row.get("evidence_note", "").startswith(AUTO_NOTE_PREFIX)]
    retained_auto_rows = [
        row
        for row in existing_rows
        if row.get("evidence_note", "").startswith(AUTO_NOTE_PREFIX)
        and row["project_slug"] not in selected_set
    ]
    retained_manifest_rows = [row for row in existing_manifest_rows if row["project_slug"] not in selected_set]
    manual_projects = {row["project_slug"] for row in manual_rows}

    generated_rows: list[dict[str, str]] = []
    manifest_rows: list[dict[str, str]] = []

    for project_slug in selected_projects:
        project_name = slug_to_name(project_slug)
        if project_slug in {"lakeville", "lakegrande"} and project_slug in manual_projects:
            project_rows = [row for row in manual_rows if row["project_slug"] == project_slug]
            source_url = project_rows[0].get("evidence_url", "") if project_rows else ""
            manifest_rows.append(
                {
                    "project_slug": project_slug,
                    "project_name": project_name,
                    "source_url": source_url,
                    "source_type": "developer_brochure",
                    "source_status": "existing_manual",
                    "notes": "Existing manually reviewed brochure/floor-plan evidence retained.",
                }
            )
            continue

        stacked_url, html = fetch_stacked_page(project_slug)
        if not html:
            manifest_rows.append(
                {
                    "project_slug": project_slug,
                    "project_name": project_name,
                    "source_url": "",
                    "source_type": "third_party_original_brochure",
                    "source_status": "missing",
                    "notes": "No Stacked directory page found with floor-plan content.",
                }
            )
            continue

        brochure_url = extract_brochure_url(html)
        floorplan_urls = extract_floorplan_urls(html)
        if not brochure_url:
            manifest_rows.append(
                {
                    "project_slug": project_slug,
                    "project_name": project_name,
                    "source_url": floorplan_urls[0] if floorplan_urls else stacked_url or "",
                    "source_type": "developer_floor_plan",
                    "source_status": "floorplan_images_only" if floorplan_urls else "found_no_brochure",
                    "notes": f"Stacked page found; brochure PDF unavailable. floorplan_images={len(floorplan_urls)}",
                }
            )
            continue

        rows, status = parse_brochure_rows(project_slug, brochure_url)
        generated_rows.extend(rows)
        manifest_rows.append(
            {
                "project_slug": project_slug,
                "project_name": project_name,
                "source_url": brochure_url,
                "source_type": "third_party_original_brochure",
                "source_status": status,
                "notes": f"auto_rows={len(rows)}; floorplan_images={len(floorplan_urls)}",
            }
        )
        print(f"{project_slug}: {status}, auto_rows={len(rows)}")

    final_rows = dedupe_rows(manual_rows + retained_auto_rows + generated_rows)
    final_rows.sort(key=lambda row: (row["project_slug"], int(row["reference_area_sqft"]), row["normalized_type"], row["evidence_kind"]))
    manifest_rows = retained_manifest_rows + manifest_rows
    manifest_rows.sort(key=lambda row: row["project_slug"])

    write_csv(REFERENCE_PATH, REFERENCE_FIELDS, final_rows)
    write_csv(MANIFEST_PATH, MANIFEST_FIELDS, manifest_rows)
    print(f"wrote {REFERENCE_PATH} ({len(final_rows)} rows)")
    print(f"wrote {MANIFEST_PATH} ({len(manifest_rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
