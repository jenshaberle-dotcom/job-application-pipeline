"""Region Stuttgart technology-company discovery adapter."""

from __future__ import annotations

import argparse
import json
import re
from html import unescape

from src.census_sources.public_directory import (
    DirectorySource,
    fetch_text,
    seed,
)

SOURCE = DirectorySource(
    source_id="region_stuttgart_technology_directory",
    geography="STUTTGART_REGION",
    cohorts=("TECH",),
    start_url="https://www.region-stuttgart.de/type/unternehmen/",
)
TECH_HINTS = ("unternehmen", "robot", "sensor", "quant", "halbleiter", "photon")


def parse_directory(html):
    match = re.search(r"\bvar\s+dmMapData\s*=\s*", html)
    if not match:
        raise ValueError("stuttgart_directory_contract_changed")
    data, _ = json.JSONDecoder().raw_decode(html[match.end():])
    rows = data.get("companies")
    if not isinstance(rows, list) or not rows:
        raise ValueError("stuttgart_directory_empty")
    companies = {}
    for row in rows:
        if "unternehmen" not in row.get("type", []):
            continue
        name, key = row.get("title"), row.get("id")
        if not isinstance(name, str) or not name.strip() or type(key) is not int:
            raise ValueError("stuttgart_identity_invalid")
        companies[str(key)] = seed(unescape(name).strip(), SOURCE, website=row.get("url"),
                                  directory_url=row.get("permalink"), source_record_id=str(key))
    if not companies:
        raise ValueError("stuttgart_directory_no_companies")
    return {
        "schema_version": "jap.discovery.region_stuttgart_technology.v1",
        "source_id": SOURCE.source_id,
        "geography": SOURCE.geography,
        "company_count": len(companies),
        "complete": True,
        "coverage_scope": "published_company_map",
        "companies": sorted(companies.values(), key=lambda x: str(x["company_name"]).casefold()),
    }


def discover() -> dict[str, object]:
    return parse_directory(fetch_text(SOURCE.start_url))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    a = p.parse_args()
    payload = discover()
    with open(a.output, "w", encoding="utf-8") as h:
        json.dump(payload, h, ensure_ascii=False, indent=2, sort_keys=True)
        h.write("\n")
    print(json.dumps({"source": SOURCE.source_id, "companies": payload["company_count"]}))


if __name__ == "__main__":
    main()
