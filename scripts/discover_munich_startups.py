"""Read the migrated Munich Startup directory without inventing pagination.

The public portal now uses /en/startups-and-ecosystem. The old WordPress
/startups/?paging=... traversal is retired. This adapter preserves the first
visible page and verified profile headings; Load-more completeness is withheld.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

from src.search_intelligence.public_directory_discovery import (
    DirectorySource,
    discovery_failure,
    fetch_text,
    links,
    seed,
    unique_page_heading,
)

SOURCE = DirectorySource(
    source_id="munich_startup",
    geography="MUNICH",
    cohorts=("TECH",),
    start_url="https://www.munich-startup.de/en/startups-and-ecosystem",
    max_pages=1,
)
PROFILE_PATH = re.compile(r"/en/startups-and-ecosystem/[a-z0-9][a-z0-9_-]*/?")


def profile_urls(html: str) -> list[str]:
    """Accept only exact profile paths on the observed public portal origin."""
    result = set()
    for href, _ in links(html, SOURCE.start_url):
        try:
            parsed = urlsplit(href)
        except ValueError:
            continue
        if (parsed.scheme == "https" and parsed.netloc == "www.munich-startup.de"
                and PROFILE_PATH.fullmatch(parsed.path)
                and not parsed.query and not parsed.fragment):
            result.add("https://www.munich-startup.de" + parsed.path.rstrip("/"))
    return sorted(result)


def discover(*, delay: float = 0.2, max_profiles: int = 24) -> dict[str, object]:
    if not 1 <= max_profiles <= 24 or not 0 <= delay <= 1:
        raise ValueError("directory_probe_bounds_invalid")
    urls = profile_urls(fetch_text(SOURCE.start_url, timeout=8))
    if not urls:
        raise ValueError("directory_record_identity_not_found")
    companies = []
    failures = []
    for index, url in enumerate(urls[:max_profiles]):
        if index and delay:
            time.sleep(delay)
        try:
            name = unique_page_heading(fetch_text(url, timeout=8))
            companies.append(seed(name, SOURCE, directory_url=url, source_record_id=url))
        except (HTTPError, URLError, OSError, ValueError) as exc:
            failures.append({"source_record_id": url, **discovery_failure(exc)})
    return {
        "schema_version": "jap.discovery.munich_startup.v1",
        "source_id": SOURCE.source_id,
        "source_url": SOURCE.start_url,
        "geography": SOURCE.geography,
        "observed_directory_total": None,
        "company_count": len(companies),
        "companies": sorted(companies, key=lambda row: str(row["company_name"]).casefold()),
        "pages_fetched": 1,
        "visible_profile_count": len(urls),
        "profile_request_count": min(len(urls), max_profiles),
        "profile_failures": failures,
        "complete": False,
        "pagination_status": "UNQUALIFIED_LOAD_MORE",
        "selection_basis": "BROAD_STARTUP_BENCHMARK_NOT_VERIFIED_TECH_CLASSIFICATION",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--delay-seconds", type=float, default=0.2)
    args = parser.parse_args()
    payload = discover(delay=args.delay_seconds)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({"source": SOURCE.source_id, "companies": payload["company_count"],
                      "complete": False}))


if __name__ == "__main__":
    main()
