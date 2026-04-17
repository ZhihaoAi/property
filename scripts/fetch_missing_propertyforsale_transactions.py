#!/usr/bin/env python3
"""
Refresh the repo's default transaction CSVs.

Default behavior is `resale-only`:

- Existing propertyforsale markdown caches are rebuilt into resale CSVs.
- Existing propertyforsale HTML caches are reused when available.
- Stale propertyforsale captcha/register HTML caches are automatically refetched
  unless `--offline` is set.
- When propertyforsale resale rows are unavailable, local URA resale rows are used
  as the default fallback.
- Existing SRX CSVs are preserved under data/srx/ as secondary sources.

Use `--sale-scope all` only for explicit requests that need New Sale / Sub Sale.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import shutil
import time
import urllib.request
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path("/Users/zhihao.ai/projects/property")
DATA_DIR = ROOT_DIR / "data"
SRX_BACKUP_DIR = DATA_DIR / "srx"
LEGACY_PROPERTYFORSALE_RESALE_DIR = DATA_DIR / "propertyforsale_resale_backup"
PROPERTYFORSALE_PRIMARY_BACKUP_DIR = DATA_DIR / "propertyforsale_primary_backup"
HTML_CACHE_DIR = DATA_DIR / "propertyforsale_html"
URA_INDEX_PATH = DATA_DIR / "ura" / "projects_index.json"
LEGACY_MARKDOWN_DIR = Path(
    "/Users/zhihao.ai/.cursor/projects/Users-zhihao-ai-projects-property/agent-tools"
)
REGISTRY_PATH = DATA_DIR / "srx_project_registry.json"

USER_AGENT = "Mozilla/5.0"
VALID_SALE_TYPES = {"New Sale", "Sub Sale", "Resale"}
DEFAULT_SALE_TYPES = frozenset({"Resale"})
MONTH_MAP = {
    "January": "Jan",
    "February": "Feb",
    "March": "Mar",
    "April": "Apr",
    "May": "May",
    "June": "Jun",
    "July": "Jul",
    "August": "Aug",
    "September": "Sep",
    "October": "Oct",
    "November": "Nov",
    "December": "Dec",
}
MONTH_NUM_TO_ABBR = {
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
PRIMARY_PROPERTYFORSALE_RESALE_LABEL = "propertyforsale.com.sg resale CSV"
PRIMARY_PROPERTYFORSALE_ALL_SALES_LABEL = "propertyforsale.com.sg all-sales CSV"
PRIMARY_URA_RESALE_LABEL = "URA PMI resale CSV"
PRIMARY_URA_RESALE_URL = "https://eservice.ura.gov.sg/uraDataService/invokeUraDS/v1?service=PMI_Resi_Transaction"
URA_RESALE_TYPE_CODE = "3"
SQM_TO_SQFT = 10.7639
CAPTCHA_PATTERNS = ("recaptcha", "g-recaptcha", "captcha")
REGISTER_PATTERNS = (
    "sign up for free",
    "propertyforsale member benefits",
    "wishlist (0)",
)

PROJECTS = [
    {"slug": "seahill", "markdown_id": "15f61f1e-2cb7-40a4-b625-c728c954cbae.txt"},
    {"slug": "the_vision", "markdown_id": "bc0f8956-f190-4bf6-a91e-a413641e0584.txt"},
    {"slug": "hundred_trees", "markdown_id": "82612131-2875-4911-b8c3-70be5c5154c0.txt"},
    {"slug": "parc_clematis", "markdown_id": "69538a84-0c38-4d93-89e9-b9c3301ddae9.txt"},
    {"slug": "stirling_residences", "markdown_id": "5bc82b54-071b-4c07-afda-8977231aadae.txt"},
    {"slug": "queens_peak", "markdown_id": "72039a39-bbd6-4351-ba22-903af873be75.txt"},
    {"slug": "commonwealth_towers", "markdown_id": "d4c8360a-b853-43d2-9e46-fa97f98fe4cc.txt"},
    {"slug": "the_trilinq", "markdown_id": "0f7130d8-d32f-41dd-8ef7-9732bd336db0.txt"},
    {"slug": "clavon", "markdown_id": "a9e5fa7f-0277-4989-97a3-418db9f24c29.txt"},
    {"slug": "artra", "markdown_id": "defc6b6f-ebd2-4002-9267-d39cc8071196.txt"},
    {"slug": "kent_ridge_hill", "markdown_id": "70c05ad5-2873-496d-87d3-e15f2844117f.txt"},
    {"slug": "j_gateway", "markdown_id": "ef2cd020-54ab-4fb0-83d0-cf2de0218ddc.txt"},
    {"slug": "whitehaven", "markdown_id": "faf51c66-bda4-42fd-b65c-8be0bec3abd5.txt"},
    {"slug": "caspian", "markdown_id": "ec8484a2-5986-4320-9dbe-3c2c88ddc8b4.txt"},
    {"slug": "lakefront", "markdown_id": "2ed034c7-7c99-4d75-977b-a1cc527ed201.txt"},
    {"slug": "twin_vew", "markdown_id": "0fbe5408-9a94-4a79-9c21-2267f7105344.txt"},
    {"slug": "clement_canopy", "markdown_id": "11147a51-0984-453d-b65f-9a74ab2f7235.txt"},
    {"slug": "harbour_view_gardens", "markdown_id": "11952ad5-356a-4e25-a5f9-0241f63d14c5.txt"},
    {"slug": "village_pasir_panjang", "markdown_id": "19b1de90-0184-474d-aca1-84a0502bdfec.txt"},
    {"slug": "spottiswoode_suites", "markdown_id": "39d6deae-e330-4f05-9c4f-11a0066bb84c.txt"},
    {"slug": "skysuites_anson", "markdown_id": "41d33546-d887-48f7-8854-2679ac7c8ff9.txt"},
    {"slug": "lakeville", "markdown_id": "42b4f4b9-740b-4a57-9e41-73e5e6f5dd03.txt"},
    {"slug": "margaret_ville", "markdown_id": "5f8890c8-6711-4dd7-9218-a2c2240e2336.txt"},
    {"slug": "parc_riviera", "markdown_id": "7259f6cd-6748-4cec-b440-a954531c9e3d.txt"},
    {"slug": "lakegrande", "markdown_id": "8113f800-087a-4898-b247-8d8476799bbc.txt"},
    {"slug": "avenue_south_residence", "markdown_id": "8f4eee87-e0f8-4481-a44f-1c80edf84ce9.txt"},
    {"slug": "alexis", "markdown_id": "999cfb1f-3077-4c86-adfc-7e01cf8cf020.txt"},
    {"slug": "normanton_park", "markdown_id": "a51705e8-c3a0-4b5d-95a3-f1101ab0940b.txt"},
    {"slug": "viva_vista", "markdown_id": "b6bff152-6e5e-4b91-8ef0-a0657981f3cb.txt"},
    {"slug": "whistler_grand", "markdown_id": "c1f7496d-a285-42e2-8403-810d3141e820.txt"},
    {"slug": "the_skywoods", "page_slug": "the-skywoods"},
    {"slug": "the_botany_at_dairy_farm", "page_slug": "the-botany-at-dairy-farm"},
    {"slug": "sol_acres", "page_slug": "sol-acres"},
    {"slug": "eco_sanctuary", "page_slug": "eco-sanctuary"},
    {"slug": "foresque_residences", "page_slug": "foresque-residences"},
    {"slug": "gem_residences", "page_slug": "gem-residences"},
    {"slug": "the_hillier", "page_slug": "the-hillier"},
    {"slug": "the_tre_ver", "page_slug": "the-tre-ver"},
    {"slug": "hillview_peak", "page_slug": "kingsford-hillview-peak"},
    {"slug": "tree_house", "page_slug": "tree-house"},
    {"slug": "hillsta", "page_slug": "hillsta"},
    {"slug": "hillion_residences", "page_slug": "hillion-residences"},
    {"slug": "midwood", "page_slug": "midwood"},
    {"slug": "eight_riversuites", "page_slug": "eight-riversuites"},
    {"slug": "the_tennery", "page_slug": "the-tennery"},
    {"slug": "dairy_farm_residences", "page_slug": "dairy-farm-residences"},
    {"slug": "le_quest", "page_slug": "le-quest"},
    {"slug": "daintree_residence", "page_slug": "daintree-residence"},
    {"slug": "the_myst", "page_slug": "the-myst"},
    {"slug": "the_sen", "page_slug": "the-sen"},
    {"slug": "the_lakeshore", "page_slug": "the-lakeshore"},
]


class PropertyForSaleCaptchaError(RuntimeError):
    pass


class PropertyForSaleBlockedError(RuntimeError):
    pass


class PropertyForSaleNoMatchingRowsError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("projects", nargs="*", help="Optional project slugs to refresh")
    parser.add_argument(
        "--sale-scope",
        choices=("resale", "all"),
        default="resale",
        help="Default is resale-only. Use all only for explicit New Sale/Sub Sale work.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use local markdown / HTML / URA caches only and skip network fetches.",
    )
    return parser.parse_args()


def selected_projects(filters: list[str]) -> list[dict]:
    filters = set(filters)
    if not filters:
        return PROJECTS
    return [project for project in PROJECTS if project["slug"] in filters]


def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        return {"generated_at": "", "projects": {}}
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if "projects" not in payload or not isinstance(payload["projects"], dict):
        payload["projects"] = {}
    return payload


def save_registry(payload: dict) -> None:
    payload["generated_at"] = datetime.now().isoformat(timespec="seconds")
    REGISTRY_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def build_url(page_slug: str) -> str:
    return f"https://www.propertyforsale.com.sg/{page_slug}/sales-transactions"


def selected_sale_types(sale_scope: str) -> frozenset[str]:
    return DEFAULT_SALE_TYPES if sale_scope == "resale" else frozenset(VALID_SALE_TYPES)


def propertyforsale_label_for_scope(sale_scope: str) -> str:
    if sale_scope == "resale":
        return PRIMARY_PROPERTYFORSALE_RESALE_LABEL
    return PRIMARY_PROPERTYFORSALE_ALL_SALES_LABEL


def fetch_html(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


def normalize_html(raw_html: str) -> str:
    return raw_html.replace("</<td>", "</td>").replace("</<th>", "</th>")


def looks_like_captcha_block(page_html: str) -> bool:
    lowered = page_html.lower()
    return any(pattern in lowered for pattern in CAPTCHA_PATTERNS)


def looks_like_register_block(page_html: str) -> bool:
    lowered = page_html.lower()
    return any(pattern in lowered for pattern in REGISTER_PATTERNS)


def parse_month_year(value: str) -> str:
    value = value.strip()
    for full, short in MONTH_MAP.items():
        if value.startswith(full):
            year = value[len(full):].strip()
            return f"{short}{year}"
    raise ValueError(f"Unsupported month/year value: {value}")


def parse_int(value: str) -> int:
    digits = re.sub(r"[^\d]", "", value)
    if not digits:
        raise ValueError(f"Cannot parse integer from {value!r}")
    return int(digits)


def strip_tags(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def sort_rows(rows: list[dict]) -> list[dict]:
    return sorted(
        rows,
        key=lambda row: (
            int(str(row["date"])[-4:]),
            list(MONTH_NUM_TO_ABBR.values()).index(str(row["date"])[:3]) + 1,
            int(row["price"]),
            int(row["sqft"]),
        ),
    )


def parse_html_table_rows(page_html: str, sale_types: frozenset[str]) -> list[dict]:
    table_match = re.search(
        r'<table id="records_list".*?<tbody>(.*?)</tbody>',
        page_html,
        flags=re.S,
    )
    if not table_match:
        if looks_like_captcha_block(page_html):
            raise PropertyForSaleCaptchaError("propertyforsale returned a reCAPTCHA page")
        if looks_like_register_block(page_html):
            raise PropertyForSaleBlockedError("propertyforsale redirected to registration page")
        raise ValueError("records_list table not found")

    rows: list[dict] = []
    for row_html in re.findall(r"<tr>(.*?)</tr>", table_match.group(1), flags=re.S):
        cell_chunks = row_html.split("<td")[1:]
        if len(cell_chunks) < 11:
            continue

        cells_raw = []
        for chunk in cell_chunks:
            content = chunk.split(">", 1)[1] if ">" in chunk else chunk
            if "</td>" in content:
                content = content.split("</td>", 1)[0]
            cells_raw.append(strip_tags(content))

        cells = [c for c in cells_raw if c] if len(cells_raw) > 12 else cells_raw

        sale_type_idx = None
        for idx, val in enumerate(cells):
            if val in VALID_SALE_TYPES:
                sale_type_idx = idx
                break
        if sale_type_idx is None or sale_type_idx + 4 > len(cells):
            continue

        date_raw = cells[0]
        sale_type = cells[sale_type_idx]
        sqft_raw = cells[sale_type_idx + 2]
        psf_raw = cells[sale_type_idx + 3]
        price_raw = cells[sale_type_idx + 4]

        if sale_type not in sale_types:
            continue

        try:
            rows.append(
                {
                    "date": parse_month_year(date_raw),
                    "sqft": parse_int(sqft_raw),
                    "psf": parse_int(psf_raw),
                    "price": parse_int(price_raw),
                }
            )
        except ValueError:
            continue

    if not rows:
        raise PropertyForSaleNoMatchingRowsError("no matching sale rows parsed from propertyforsale HTML")

    return sort_rows(rows)


def parse_markdown_rows(markdown_text: str, sale_types: frozenset[str]) -> list[dict]:
    rows: list[dict] = []
    in_table = False

    for line in markdown_text.splitlines():
        if "| Date of Sale |" in line and "Type of Sale |" in line:
            in_table = True
            continue
        if not in_table:
            continue
        if "| --- |" in line or "|---|" in line:
            continue
        if not line.strip().startswith("|"):
            break

        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 12:
            continue

        date_raw = sqft_raw = psf_raw = price_raw = sale_type = None
        if len(parts) >= 13 and parts[8] in VALID_SALE_TYPES:
            date_raw = parts[1]
            sale_type = parts[8]
            sqft_raw = parts[10]
            psf_raw = parts[11]
            price_raw = parts[12]
        elif parts[7] in VALID_SALE_TYPES:
            date_raw = parts[1]
            sale_type = parts[7]
            sqft_raw = parts[9]
            psf_raw = parts[10]
            price_raw = parts[11]

        if sale_type not in sale_types:
            continue

        try:
            rows.append(
                {
                    "date": parse_month_year(date_raw),
                    "sqft": parse_int(sqft_raw),
                    "psf": parse_int(psf_raw),
                    "price": parse_int(price_raw),
                }
            )
        except ValueError:
            continue

    if not rows:
        raise PropertyForSaleNoMatchingRowsError("no matching sale rows parsed from propertyforsale markdown")

    return sort_rows(rows)


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "sqft", "psf", "price"])
        writer.writeheader()
        writer.writerows(rows)


def count_csv_rows(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def read_csv_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_legacy_propertyforsale_resale_rows(slug: str) -> list[dict] | None:
    backup_csv = LEGACY_PROPERTYFORSALE_RESALE_DIR / f"{slug}_transactions.csv"
    if not backup_csv.exists():
        return None
    return read_csv_rows(backup_csv)


def backup_existing_propertyforsale_csv(slug: str, current_registry_entry: dict) -> Path | None:
    if current_registry_entry.get("source_kind") != "propertyforsale_csv":
        return None
    primary_csv = DATA_DIR / f"{slug}_transactions.csv"
    if not primary_csv.exists():
        return None
    backup_csv = PROPERTYFORSALE_PRIMARY_BACKUP_DIR / primary_csv.name
    if backup_csv.exists():
        return backup_csv
    shutil.copy2(primary_csv, backup_csv)
    return backup_csv


def backup_existing_srx_csv(slug: str, current_registry_entry: dict) -> Path | None:
    if current_registry_entry.get("source_kind") != "srx_csv":
        return None
    primary_csv = DATA_DIR / f"{slug}_transactions.csv"
    if not primary_csv.exists():
        return None
    backup_csv = SRX_BACKUP_DIR / primary_csv.name
    if backup_csv.exists():
        return backup_csv
    shutil.copy2(primary_csv, backup_csv)
    return backup_csv


def dedupe_secondary_sources(existing: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for item in existing:
        normalized = dict(item)
        source_kind = str(normalized.get("source_kind", ""))
        source_csv = str(normalized.get("source_csv", ""))
        if source_kind == "srx_csv" and source_csv and "/" not in source_csv:
            normalized["source_csv"] = f"srx/{Path(source_csv).name}"
        key = (
            str(normalized.get("source_kind", "")),
            str(normalized.get("source_csv", "")),
            str(normalized.get("source_url", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def update_registry_for_primary_propertyforsale(
    registry_payload: dict,
    slug: str,
    propertyforsale_url: str | None,
    record_count: int,
    source_label: str,
) -> None:
    projects = registry_payload["projects"]
    current = dict(projects.get(slug, {}))

    secondary_sources = list(current.get("secondary_sources", []))
    backup_csv = SRX_BACKUP_DIR / f"{slug}_transactions.csv"
    if current.get("source_kind") == "srx_csv" and backup_csv.exists():
        secondary_sources.insert(
            0,
            {
                "source_kind": "srx_csv",
                "source_label": current.get("source_label", "SRX last-transacted-prices"),
                "source_url": current.get("source_url"),
                "source_csv": f"srx/{slug}_transactions.csv",
                "record_count": current.get("record_count"),
            },
        )

    existing_propertyforsale_url = (
        current.get("source_url") if current.get("source_kind") == "propertyforsale_csv" else None
    )
    current.update(
        {
            "slug": slug,
            "source_kind": "propertyforsale_csv",
            "source_label": source_label,
            "source_url": propertyforsale_url or existing_propertyforsale_url,
            "source_csv": f"{slug}_transactions.csv",
            "record_count": record_count,
            "secondary_sources": dedupe_secondary_sources(secondary_sources),
        }
    )
    current.pop("propertyforsale_blocked_url", None)
    current.pop("propertyforsale_blocked_reason", None)
    projects[slug] = current


def update_registry_for_primary_ura(
    registry_payload: dict,
    slug: str,
    record_count: int,
    propertyforsale_url: str | None,
    propertyforsale_reason: str | None,
) -> None:
    projects = registry_payload["projects"]
    current = dict(projects.get(slug, {}))
    secondary_sources = list(current.get("secondary_sources", []))
    backup_csv = SRX_BACKUP_DIR / f"{slug}_transactions.csv"
    if current.get("source_kind") == "srx_csv" and backup_csv.exists():
        secondary_sources.insert(
            0,
            {
                "source_kind": "srx_csv",
                "source_label": current.get("source_label", "SRX last-transacted-prices"),
                "source_url": current.get("source_url"),
                "source_csv": f"srx/{slug}_transactions.csv",
                "record_count": current.get("record_count"),
            },
        )

    current.update(
        {
            "slug": slug,
            "source_kind": "ura_resale_csv",
            "source_label": PRIMARY_URA_RESALE_LABEL,
            "source_url": PRIMARY_URA_RESALE_URL,
            "source_csv": f"{slug}_transactions.csv",
            "record_count": record_count,
            "secondary_sources": dedupe_secondary_sources(secondary_sources),
        }
    )
    if propertyforsale_url:
        current["propertyforsale_blocked_url"] = propertyforsale_url
    else:
        current.pop("propertyforsale_blocked_url", None)
    if propertyforsale_reason:
        current["propertyforsale_blocked_reason"] = propertyforsale_reason
    else:
        current.pop("propertyforsale_blocked_reason", None)
    projects[slug] = current


def update_registry_for_resale_unavailable(
    registry_payload: dict,
    slug: str,
    propertyforsale_url: str | None,
    reason: str | None,
) -> None:
    projects = registry_payload["projects"]
    current = dict(projects.get(slug, {}))
    secondary_sources = list(current.get("secondary_sources", []))
    backup_csv = SRX_BACKUP_DIR / f"{slug}_transactions.csv"
    if current.get("source_kind") == "srx_csv" and backup_csv.exists():
        secondary_sources.insert(
            0,
            {
                "source_kind": "srx_csv",
                "source_label": current.get("source_label", "SRX last-transacted-prices"),
                "source_url": current.get("source_url"),
                "source_csv": f"srx/{slug}_transactions.csv",
                "record_count": current.get("record_count"),
            },
        )

    current.update(
        {
            "slug": slug,
            "source_kind": "resale_unavailable",
            "source_label": "No resale rows in local propertyforsale/URA cache",
            "source_url": propertyforsale_url,
            "source_csv": None,
            "record_count": 0,
            "secondary_sources": dedupe_secondary_sources(secondary_sources),
        }
    )
    if propertyforsale_url:
        current["propertyforsale_blocked_url"] = propertyforsale_url
    else:
        current.pop("propertyforsale_blocked_url", None)
    if reason:
        current["propertyforsale_blocked_reason"] = reason
    else:
        current.pop("propertyforsale_blocked_reason", None)
    projects[slug] = current


def year_range(rows: list[dict]) -> str:
    years = sorted({int(str(row["date"])[-4:]) for row in rows})
    if not years:
        return "-"
    if len(years) == 1:
        return str(years[0])
    return f"{years[0]}-{years[-1]}"


def parse_ura_contract_month(value: str) -> str:
    digits = re.sub(r"[^\d]", "", value)
    if len(digits) != 4:
        raise ValueError(f"Unsupported URA contract month: {value!r}")
    month = int(digits[:2])
    year = 2000 + int(digits[2:])
    return f"{MONTH_NUM_TO_ABBR[month]}{year}"


def parse_ura_resale_rows(slug: str, ura_index: dict[str, dict]) -> list[dict]:
    project = ura_index.get(slug)
    if not project:
        return []

    rows: list[dict] = []
    for tx in project.get("transactions", []):
        if str(tx.get("typeOfSale")) != URA_RESALE_TYPE_CODE:
            continue
        area_text = str(tx.get("area", "")).strip()
        price_text = str(tx.get("price", "")).strip()
        contract_date = str(tx.get("contractDate", "")).strip()
        if not area_text or not price_text or not contract_date:
            continue
        try:
            sqft = max(1, round(float(area_text) * SQM_TO_SQFT))
            price = int(price_text)
            psf = max(1, round(price / sqft))
            units = max(1, int(str(tx.get("noOfUnits", "1")).strip() or "1"))
            row = {
                "date": parse_ura_contract_month(contract_date),
                "sqft": sqft,
                "psf": psf,
                "price": price,
            }
            rows.extend([row.copy() for _ in range(units)])
        except (KeyError, ValueError):
            continue

    return sort_rows(rows)


def load_project_rows(
    project: dict,
    sale_types: frozenset[str],
    offline: bool,
) -> tuple[list[dict], str | None]:
    slug = project["slug"]
    if "markdown_id" in project:
        if sale_types == DEFAULT_SALE_TYPES:
            cached_rows = load_legacy_propertyforsale_resale_rows(slug)
            if cached_rows is not None:
                return cached_rows, None
        markdown_path = LEGACY_MARKDOWN_DIR / project["markdown_id"]
        if not markdown_path.exists():
            raise FileNotFoundError(f"legacy markdown not found: {markdown_path}")
        return parse_markdown_rows(
            markdown_path.read_text(encoding="utf-8", errors="replace"),
            sale_types,
        ), None

    url = build_url(project["page_slug"])
    html_cache = HTML_CACHE_DIR / f"{slug}.html"
    if html_cache.exists():
        cached_html = normalize_html(html_cache.read_text(encoding="utf-8", errors="replace"))
        try:
            return parse_html_table_rows(cached_html, sale_types), url
        except (PropertyForSaleBlockedError, PropertyForSaleCaptchaError, PropertyForSaleNoMatchingRowsError, ValueError):
            if offline:
                raise
    if offline:
        raise FileNotFoundError(f"local propertyforsale HTML cache not found: {html_cache}")
    raw_html = fetch_html(url)
    html_cache.write_text(raw_html, encoding="utf-8")
    return parse_html_table_rows(normalize_html(raw_html), sale_types), url


def remove_primary_csv(slug: str) -> None:
    primary_csv = DATA_DIR / f"{slug}_transactions.csv"
    if primary_csv.exists():
        primary_csv.unlink()


def refresh_project(
    project: dict,
    registry_payload: dict,
    sale_scope: str,
    offline: bool,
    ura_index: dict[str, dict],
) -> tuple[str, int | None, str | None]:
    slug = project["slug"]
    current_registry_entry = registry_payload["projects"].get(slug, {})
    backup_existing_propertyforsale_csv(slug, current_registry_entry)
    backup_existing_srx_csv(slug, current_registry_entry)

    sale_types = selected_sale_types(sale_scope)
    propertyforsale_url = None
    propertyforsale_reason = None

    try:
        rows, propertyforsale_url = load_project_rows(project, sale_types, offline)
        write_csv(DATA_DIR / f"{slug}_transactions.csv", rows)
        update_registry_for_primary_propertyforsale(
            registry_payload=registry_payload,
            slug=slug,
            propertyforsale_url=propertyforsale_url,
            record_count=len(rows),
            source_label=propertyforsale_label_for_scope(sale_scope),
        )
        if "page_slug" in project and not offline:
            time.sleep(1)
        return "propertyforsale", len(rows), propertyforsale_url
    except (PropertyForSaleBlockedError, PropertyForSaleCaptchaError, PropertyForSaleNoMatchingRowsError, FileNotFoundError) as exc:
        propertyforsale_reason = str(exc)
        if sale_scope != "resale":
            raise

    ura_rows = parse_ura_resale_rows(slug, ura_index)
    if ura_rows:
        write_csv(DATA_DIR / f"{slug}_transactions.csv", ura_rows)
        update_registry_for_primary_ura(
            registry_payload=registry_payload,
            slug=slug,
            record_count=len(ura_rows),
            propertyforsale_url=propertyforsale_url,
            propertyforsale_reason=propertyforsale_reason,
        )
        return "ura", len(ura_rows), propertyforsale_url

    remove_primary_csv(slug)
    update_registry_for_resale_unavailable(
        registry_payload=registry_payload,
        slug=slug,
        propertyforsale_url=propertyforsale_url,
        reason=propertyforsale_reason,
    )
    return "unavailable", None, propertyforsale_url


def main() -> int:
    args = parse_args()
    registry_payload = load_registry()
    ura_index = json.loads(URA_INDEX_PATH.read_text(encoding="utf-8")) if URA_INDEX_PATH.exists() else {}
    SRX_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    PROPERTYFORSALE_PRIMARY_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    HTML_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    selected = selected_projects(args.projects)
    if not selected:
        print("no matching projects selected")
        return 1

    failures: list[tuple[str, str]] = []
    for index, project in enumerate(selected, start=1):
        slug = project["slug"]
        try:
            source_type, count, propertyforsale_url = refresh_project(
                project=project,
                registry_payload=registry_payload,
                sale_scope=args.sale_scope,
                offline=args.offline,
                ura_index=ura_index,
            )
            if source_type == "unavailable":
                print(
                    f"[{index}/{len(selected)}] {slug}: no default resale rows "
                    "in local propertyforsale/URA cache; removed from default CSV set"
                )
                continue

            rows = read_csv_rows(DATA_DIR / f"{slug}_transactions.csv")
            year_label = year_range(rows)
            if source_type == "propertyforsale":
                print(
                    f"[{index}/{len(selected)}] {slug}: wrote {slug}_transactions.csv "
                    f"({count} {args.sale_scope} rows, {year_label})"
                    + (
                        f" from {propertyforsale_url}"
                        if propertyforsale_url
                        else " from local propertyforsale resale cache"
                    )
                )
            else:
                print(
                    f"[{index}/{len(selected)}] {slug}: wrote {slug}_transactions.csv "
                    f"({count} resale rows, {year_label}) from local URA fallback"
                )
        except Exception as exc:
            failures.append((slug, str(exc)))
            print(f"  ERROR {slug}: {exc}")

    save_registry(registry_payload)
    print(f"updated registry: {REGISTRY_PATH}")

    if failures:
        print("failures:")
        for slug, message in failures:
            print(f"  - {slug}: {message}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
