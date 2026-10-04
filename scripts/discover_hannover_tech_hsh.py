"""Discover TECH employers from the public Hochschule Hannover Career Center directory.

Network transport is intentionally explicit and read-only. The output is seed evidence for
the mass census, never employer-source activation.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from html.parser import HTMLParser
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://firmen.cc.hs-hannover.de/companies/page{page}/"
TECH_FIELDS = frozenset({
    "Informationstechnologie",
    "Softwarentwicklung/-kenntnisse",
    "Datenbank-/ Informationsmanagement",
    "Elektro-, Nachrichten- und Regeltechnik",
    "Elektroindustrie",
    "Forschung & Entwicklung",
    "Maschinenbau, Anlagenbau",
    "Automobilindustrie und Zulieferer",
    "Fahrzeug- und Schiffbau",
    "Energie & Wasserversorgung",
    "Medizin, Medizintechnik",
    "Luft- & Raumfahrt",
    "Telekommunikation",
    "Ingenieur allg.",
})
REGION_MARKERS = (
    " hannover", " langenhagen", " laatzen", " garbsen", " isernhagen",
    " burgwedel", " wedemark", " neustadt", " springe", " seelze",
    " gehrden", " barsinghausen", " lehrte", " burgdorf", " uetze",
    " pattensen", " ronnenberg", " sehnde", " wennigsen", " wunstorf",
    " hemmingen",
)


class DirectoryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if value:
            self.text.append(value)


def fetch_page(page: int, timeout: int) -> str:
    query = urlencode({"basic": "1", "orderby": "nameasc"})
    request = Request(
        BASE.format(page=page) + "?" + query,
        headers={"User-Agent": "JAP-Connector-Factory-Census/1.0 (+read-only research)"},
    )
    with urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"directory_http_status:{response.status}")
        return response.read().decode("utf-8", errors="replace")


def visible_text(html: str) -> list[str]:
    parser = DirectoryParser()
    parser.feed(html)
    return parser.text


def parse_company_blocks(html: str) -> list[dict[str, object]]:
    # TYPO3 renders each result twice: compact table and expanded detail. The expanded
    # detail has stable semantic labels; split there and dedupe later.
    text = visible_text(html)
    starts = [i for i, value in enumerate(text) if value == "Berufsfeld(er)"]
    rows: list[dict[str, object]] = []
    for start in starts:
        if start == 0:
            continue
        name = text[start - 1]
        if name in {"Name", "Sortieren nach:"}:
            continue
        end = next((i for i in range(start + 1, len(text)) if text[i] == "Berufsfeld(er)"), len(text))
        block = text[start:end]
        fields: list[str] = []
        address = ""
        homepage = ""
        section = "fields"
        for value in block[1:]:
            if value == "Anschrift":
                section = "address"
                continue
            if value == "Beschreibung":
                section = "description"
                continue
            if value == "Mitarbeitende":
                section = "employees"
                continue
            if value == "Homepage":
                section = "homepage"
                continue
            if section == "fields" and value not in {"Keine Angabe"}:
                fields.append(value)
            elif section == "address" and not address and value != "Keine Angabe":
                address = value
            elif section == "homepage" and not homepage and value != "Keine Angabe":
                homepage = value
        if fields:
            rows.append({"company_name": name, "fields": sorted(set(fields)), "location": address, "website": homepage})
    return rows


def is_region(address: str) -> bool:
    value = " " + address.casefold()
    return any(marker in value for marker in REGION_MARKERS)


def is_tech(fields: list[str]) -> bool:
    return bool(TECH_FIELDS.intersection(fields))


def discover(max_pages: int, delay: float, timeout: int) -> dict[str, object]:
    by_identity: dict[tuple[str, str], dict[str, object]] = {}
    pages = 0
    for page in range(1, max_pages + 1):
        html = fetch_page(page, timeout)
        pages += 1
        match = re.search(r"(\d+)\s+Firmen gefunden", html)
        rows = parse_company_blocks(html)
        if not rows and page > 1:
            break
        for row in rows:
            if not is_region(str(row["location"])) or not is_tech(list(row["fields"])):
                continue
            key = (str(row["company_name"]).casefold(), str(row["website"]).casefold())
            by_identity[key] = {
                "company_name": row["company_name"],
                "source": "hochschule_hannover_career_center",
                "website": row["website"] or None,
                "location": row["location"] or None,
                "industry": " | ".join(row["fields"]),
                "source_record_id": f"page:{page}:{row['company_name']}",
                "cohort": "TECH",
            }
        if match and page * 10 >= int(match.group(1)):
            break
        if delay:
            time.sleep(delay)
    companies = sorted(by_identity.values(), key=lambda row: str(row["company_name"]).casefold())
    return {
        "schema_version": "jap.discovery.hsh_career_center.v1",
        "source_url": "https://firmen.cc.hs-hannover.de/companies/",
        "cohort": "TECH",
        "selection": {"region": "Region Hannover", "tech_fields": sorted(TECH_FIELDS)},
        "pages_fetched": pages,
        "company_count": len(companies),
        "companies": companies,
        "boundaries": {"source_activation": False, "database_writes": False, "application_actions": False},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-pages", type=int, default=60)
    parser.add_argument("--delay-seconds", type=float, default=0.25)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    args = parser.parse_args()
    payload = discover(args.max_pages, args.delay_seconds, args.timeout_seconds)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({"company_count": payload["company_count"], "pages_fetched": payload["pages_fetched"], "output": args.output}, sort_keys=True))


if __name__ == "__main__":
    main()
