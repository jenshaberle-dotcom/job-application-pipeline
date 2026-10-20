"""Munich Startup's observed public cursor API; retain only company seed fields.

The 2026 portal's own startup-list script calls /api/startups and carries the
returned cursor until hasNextPage is false. Old ?paging= links now redirect to
the same first page. Never call a repeated cursor or claim a partial list complete.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from urllib.parse import quote, urlencode, urlsplit
from pathlib import Path
from src.connectors.classic_factory_delivery import atomic_json

from src.census_sources.public_directory import DirectorySource, fetch_text, seed

SOURCE = DirectorySource("munich_startup", "MUNICH", ("TECH",),
                         "https://www.munich-startup.de/de/startups-and-ecosystem", 220)
API = "https://www.munich-startup.de/api/startups"


def parse_page(payload):
    rows = payload.get("startups")
    total, more, cursor = (payload.get(key) for key in ("totalCount", "hasNextPage", "cursor"))
    if (not isinstance(rows, list) or len(rows) > 100 or type(total) is not int or not 0 <= total <= 10000
            or type(more) is not bool or (more and (not isinstance(cursor, str)
                or not re.fullmatch(r"[0-9]{1,8}", cursor) or not rows))):
        raise ValueError("munich_cursor_contract_changed")
    companies = []
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get("id"), str)
                or not re.fullmatch(r"[0-9]{1,12}", row["id"])
                or not isinstance(row.get("slug"), str) or not re.fullmatch(r"[\w-]{1,180}", row["slug"])
                or not isinstance(row.get("title"), str) or not 1 <= len(row["title"].strip()) <= 300):
            raise ValueError("munich_company_identity_changed")
        website = row.get("website") or None
        if website is not None:
            url = urlsplit(website)
            if (url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password
                    or url.port not in {None, 80, 443} or len(website) > 2048):
                website = None  # An invalid optional link never becomes employer authority.
        companies.append(seed(row["title"], SOURCE, website=website,
            industry=row.get("industry") if isinstance(row.get("industry"), str) else None,
            directory_url=SOURCE.start_url + "/" + quote(row["slug"], safe="-_"), source_record_id=row["id"]))
    return companies, total, more, cursor


def discover(*, delay: float = 0.2, checkpoint=None) -> dict[str, object]:
    companies, pages, cursors, totals = {}, [], set(), set()
    duplicate_count = 0
    cursor, observed_total = None, None
    for _ in range(SOURCE.max_pages):
        url = API + ("?" + urlencode({"cursor": cursor}) if cursor is not None else "?")
        raw = fetch_text(url, timeout=45)
        rows, total, more, next_cursor = parse_page(json.loads(raw))
        totals.add(total)
        if observed_total is None:
            observed_total = total
        for row in rows:
            key = row["source_record_id"]
            if key in companies:
                if companies[key] != row:
                    raise ValueError("munich_company_changed_during_read")
                duplicate_count += 1
            companies[key] = row
        pages.append({"url": url, "response_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                      "count": len(rows), "reported_total": total})
        if checkpoint:
            checkpoint({"source_id": SOURCE.source_id, "companies": list(companies.values()),
                        "company_count": len(companies), "complete": False,
                        "observed_directory_total": observed_total, "pages": pages,
                        "coverage_issue": "PAGINATION_INCOMPLETE"})
        print(json.dumps({"pages_read": len(pages), "companies": len(companies),
                          "reported_total": observed_total}), flush=True)
        if not more:
            break
        if next_cursor in cursors:
            raise ValueError("munich_repeated_cursor")
        cursors.add(next_cursor)
        cursor = next_cursor
        if delay:
            time.sleep(delay)
    else:
        raise ValueError("munich_pagination_bound_exhausted")
    # Later totalCount values in the observed API decrease during pagination;
    # they are retained verbatim and never summed or treated as global totals.
    complete = observed_total == len(companies) and duplicate_count == 0
    return {"schema_version": "jap.discovery.munich_startup.v2", "source_id": SOURCE.source_id,
            "geography": SOURCE.geography, "observed_directory_total": observed_total,
            "company_count": len(companies), "complete": complete, "reported_totals": sorted(totals),
            "duplicate_count": duplicate_count, "pages": pages,
            "companies": sorted(companies.values(), key=lambda row: row["company_name"].casefold())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--delay-seconds", type=float, default=0.2)
    args = parser.parse_args()
    payload = discover(delay=args.delay_seconds,
                       checkpoint=lambda value: atomic_json(Path(args.output), value))
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({"source": SOURCE.source_id, "companies": payload["company_count"]}))


if __name__ == "__main__":
    main()
