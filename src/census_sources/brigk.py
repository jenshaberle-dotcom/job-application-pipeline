"""Published startup logo directory. Domain candidates are not invented company names."""
import argparse
import json
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

from src.census_sources.public_directory import DirectorySource, fetch_text, seed

SOURCE = DirectorySource("ingolstadt_digital_ecosystem", "INGOLSTADT", ("TECH",),
                         "https://www.brigk.digital/en/about-brigk/")


class Logos(HTMLParser):
    def __init__(self):
        super().__init__()
        self.href = None
        self.rows = {}
        self.unidentified = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            self.href = attrs.get("href")
        elif tag == "img":
            url = urlsplit(self.href or "")
            if url.scheme != "https" or not url.hostname or url.username or url.password:
                self.unidentified += 1
                return
            host = url.hostname.removeprefix("www.")
            self.rows[host] = dict(seed(host, SOURCE, website=self.href,
                                       directory_url=SOURCE.start_url, source_record_id=host),
                                   identity_kind="DOMAIN_ONLY", company_name_verified=False)

    def handle_endtag(self, tag):
        if tag == "a":
            self.href = None


def parse_directory(html):
    if "Overview of our" not in html:
        raise ValueError("brigk_directory_contract_changed")
    section = html.split("Overview of our", 1)[1]
    # The following h2 starts the building description, not more startups.
    boundary = re.search(r"<h2\b", section)
    if not boundary:
        raise ValueError("brigk_directory_boundary_missing")
    parser = Logos()
    parser.feed(section[:boundary.start()])
    if not parser.rows:
        raise ValueError("brigk_directory_empty")
    return dict(source_id=SOURCE.source_id, companies=list(parser.rows.values()),
                company_count=len(parser.rows), complete=parser.unidentified == 0,
                unidentified_logos=parser.unidentified,
                coverage_scope="published_startup_logos",
                coverage_issue="UNIDENTIFIED_LOGOS" if parser.unidentified else None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = parse_directory(fetch_text(SOURCE.start_url))
    with open(args.output, "w", encoding="utf8") as stream:
        json.dump(result, stream, ensure_ascii=False)


if __name__ == "__main__":
    main()
