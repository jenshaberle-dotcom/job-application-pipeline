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
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

BASE = "https://firmen.cc.hs-hannover.de/companies/page{page}/"
TECH_FIELDS = frozenset(
    {
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
    }
)
SOCIAL_FIELDS = frozenset(
    {
        "Gesundheit & Soziale Dienste",
        "Bildung, Erziehung, Pädagogik",
        "Sozialwesen",
        "Psychologie",
    }
)
REGION_MARKERS = (
    " hannover",
    " langenhagen",
    " laatzen",
    " garbsen",
    " isernhagen",
    " burgwedel",
    " wedemark",
    " neustadt",
    " springe",
    " seelze",
    " gehrden",
    " barsinghausen",
    " lehrte",
    " burgdorf",
    " uetze",
    " pattensen",
    " ronnenberg",
    " sehnde",
    " wennigsen",
    " wunstorf",
    " hemmingen",
)


DIRECTORY_ORIGIN = "https://firmen.cc.hs-hannover.de"
SECTION_LABELS = {"Berufsfeld(er)", "Anschrift", "Beschreibung", "Mitarbeitende", "Homepage"}


def directory_identity(href: str) -> str | None:
    """Only an actual local company-profile link establishes a record boundary."""
    try:
        url = urlsplit(urljoin(DIRECTORY_ORIGIN, href))
        if (url.scheme not in {"http", "https"}
                or url.netloc != "firmen.cc.hs-hannover.de"
                or not re.fullmatch(r"/companies/[0-9]+/", url.path)
                or url.query or url.fragment):
            return None
    except ValueError:
        return None
    return DIRECTORY_ORIGIN + url.path


class DirectoryParser(HTMLParser):
    """Bind tab, desktop and mobile views to their common directory identity.

    A label's preceding text is NOT a company name: the real directory repeats
    labels in navigation and repeats fields after the homepage link.
    """

    def __init__(self) -> None:
        super().__init__()
        self.records: list[dict] = []
        self.record: dict | None = None
        self.name_parts: list[str] | None = None
        self.suppressed = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in {"script", "style", "template"}:
            self.suppressed += 1
        if self.suppressed or tag != "a":
            return
        identity = directory_identity(dict(attrs).get("href") or "")
        if identity:
            self.record = {"directory_url": identity, "name_parts": [], "text": []}
            self.records.append(self.record)
            self.name_parts = self.record["name_parts"]

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "template"} and self.suppressed:
            self.suppressed -= 1
        if tag == "a":
            self.name_parts = None

    def handle_data(self, data: str) -> None:
        if self.suppressed:
            return
        value = " ".join(data.split())
        if not value:
            return
        if self.name_parts is not None:
            self.name_parts.append(value)
        elif self.record is not None:
            self.record["text"].append(value)


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


def parse_company_blocks(html: str) -> list[dict[str, object]]:
    parser = DirectoryParser()
    parser.feed(html)
    parser.close()
    rows: dict[str, dict] = {}
    for record in parser.records:
        name = " ".join(record["name_parts"]).strip()
        if not name or name in SECTION_LABELS or re.match(r"(?i)(?:https?://|www\.)", name):
            continue
        fields: set[str] = set()
        addresses: set[str] = set()
        homepages: set[str] = set()
        section = ""
        section_value_seen = False
        for value in record["text"]:
            if value in SECTION_LABELS:
                section = value
                section_value_seen = False
                continue
            if value.rstrip(".") == "Keine Angabe":
                continue
            if section == "Berufsfeld(er)":
                fields.add(value)
            elif section == "Anschrift" and not section_value_seen and re.search(r"\b[0-9]{5}\b", value):
                addresses.add(value)
                section_value_seen = True
            elif section == "Homepage" and not section_value_seen and re.match(r"(?i)https?://", value):
                url = urlsplit(value)
                if url.hostname and not url.username and not url.password:
                    homepages.add(value)
                    section_value_seen = True
        # Compact table-only occurrences do not carry labelled sections. Never
        # guess those fields or copy the next company's homepage into this one.
        if not fields:
            continue
        if len(addresses) > 1 or len(homepages) > 1:
            raise ValueError("directory_record_field_conflict")
        identity = record["directory_url"]
        row = {
            "company_name": name,
            "fields": sorted(fields),
            "location": next(iter(addresses), ""),
            "website": next(iter(homepages), ""),
            "directory_url": identity,
            "source_record_id": identity,
        }
        if identity in rows and rows[identity] != row:
            raise ValueError("directory_record_identity_conflict")
        rows[identity] = row
    return list(rows.values())


def is_region(address: str) -> bool:
    value = " " + address.casefold()
    return any(marker in value for marker in REGION_MARKERS)


def is_tech(fields: list[str]) -> bool:
    return bool(TECH_FIELDS.intersection(fields))


def cohorts_for(fields: list[str]) -> list[str]:
    cohorts = []
    observed = set(fields)
    if TECH_FIELDS.intersection(observed):
        cohorts.append("TECH")
    if SOCIAL_FIELDS.intersection(observed):
        cohorts.append("SOCIAL")
    return cohorts


def discover(max_pages: int, delay: float, timeout: int) -> dict[str, object]:
    by_identity: dict[str, dict[str, object]] = {}
    pages = 0
    for page in range(1, max_pages + 1):
        html = fetch_page(page, timeout)
        pages += 1
        match = re.search(r"(\d+)\s+Firmen gefunden", html)
        rows = parse_company_blocks(html)
        if not rows:
            if match and int(match.group(1)) == 0:
                break
            raise ValueError("directory_record_identity_not_found")
        for row in rows:
            if not is_region(str(row["location"])):
                continue
            cohorts = cohorts_for(list(row["fields"]))
            if not cohorts:
                continue
            key = str(row["source_record_id"])
            by_identity[key] = {
                "company_name": row["company_name"],
                "source": "hochschule_hannover_career_center",
                "website": row["website"] or None,
                "location": row["location"] or None,
                "industry": " | ".join(row["fields"]),
                "source_record_id": row["source_record_id"],
                "directory_url": row["directory_url"],
                "cohort": cohorts[0],
                "cohorts": cohorts,
                "geography": "REGION_HANNOVER",
            }
        if match and page * 10 >= int(match.group(1)):
            break
        if delay:
            time.sleep(delay)
    companies = sorted(by_identity.values(), key=lambda row: str(row["company_name"]).casefold())
    return {
        "schema_version": "jap.discovery.hsh_career_center.v1",
        "source_url": "https://firmen.cc.hs-hannover.de/companies/",
        "cohorts": ["TECH", "SOCIAL"],
        "selection": {
            "region": "Region Hannover",
            "tech_fields": sorted(TECH_FIELDS),
            "social_fields": sorted(SOCIAL_FIELDS),
        },
        "pages_fetched": pages,
        "company_count": len(companies),
        "companies": companies,
        "boundaries": {
            "source_activation": False,
            "database_writes": False,
            "application_actions": False,
        },
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
    print(
        json.dumps(
            {
                "company_count": payload["company_count"],
                "pages_fetched": payload["pages_fetched"],
                "output": args.output,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
