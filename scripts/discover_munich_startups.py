"""Munich Startup mass discovery adapter.

The official portal exposes a paginated startup directory. This adapter intentionally
collects the broad startup population; downstream cohort/fingerprint stages determine
technical relevance instead of prematurely throwing away useful ML examples.
"""
from __future__ import annotations
import argparse, json, re, time
from src.search_intelligence.public_directory_discovery import DirectorySource, fetch_text, links, seed

SOURCE = DirectorySource(
    source_id="munich_startup",
    geography="MUNICH",
    cohorts=("TECH",),
    start_url="https://www.munich-startup.de/startups/?ecosystem_type=startup",
    max_pages=220,
)
SKIP = {"Mehr Startups laden", "Startup eintragen", "Zur Gründerberatung", "Insights"}


def discover(*, delay: float = .2) -> dict[str, object]:
    companies: dict[str, dict[str, object]] = {}
    observed_total = None
    empty = 0
    for page in range(1, SOURCE.max_pages + 1):
        url = SOURCE.start_url + f"&paging={page}"
        html = fetch_text(url)
        if observed_total is None:
            m = re.search(r"(\d+)\s+Suchergebnisse", html)
            if m:
                observed_total = int(m.group(1))
        page_count = 0
        for href, text in links(html, url):
            if text in SKIP or len(text) < 2:
                continue
            if "/startups/" not in href or "paging=" in href or "tags=" in href or "letter=" in href:
                continue
            key = href.split("?", 1)[0].rstrip("/")
            if key == "https://www.munich-startup.de/startups":
                continue
            companies.setdefault(key, seed(text, SOURCE, website=key, source_record_id=key))
            page_count += 1
        empty = empty + 1 if page_count == 0 else 0
        if empty >= 2 or (observed_total and len(companies) >= observed_total):
            break
        if delay:
            time.sleep(delay)
    return {
        "schema_version": "jap.discovery.munich_startup.v1",
        "source_id": SOURCE.source_id,
        "geography": SOURCE.geography,
        "observed_directory_total": observed_total,
        "company_count": len(companies),
        "companies": sorted(companies.values(), key=lambda x: str(x["company_name"]).casefold()),
    }


def main():
    p=argparse.ArgumentParser(); p.add_argument("--output", required=True); p.add_argument("--delay-seconds", type=float, default=.2)
    a=p.parse_args(); payload=discover(delay=a.delay_seconds)
    with open(a.output,"w",encoding="utf-8") as h: json.dump(payload,h,ensure_ascii=False,indent=2,sort_keys=True); h.write("\n")
    print(json.dumps({"source":SOURCE.source_id,"companies":payload["company_count"]}))


if __name__ == "__main__": main()
