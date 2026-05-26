# Evaluate official employer-origin career sources defensively.
#
# Defensive spike:
# - one configured URL per employer target
# - no detail pages
# - no database writes
# - short timeout
# - simple HTML/text signal extraction only
#
# Usage:
#   python -m scripts.evaluate_employer_origin_sources

from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from typing import Iterable

import requests


TIMEOUT_SECONDS = 20

SEARCH_TERMS = [
    "Data Engineer",
    "Analytics Engineer",
    "Data Platform",
    "Data Warehouse",
    "Big Data",
    "Python SQL",
    "Data Analytics",
    "Business Intelligence",
]

ATS_HINTS = {
    "personio": ["personio"],
    "greenhouse": ["greenhouse.io", "boards.greenhouse"],
    "smartrecruiters": ["smartrecruiters"],
    "workday": ["myworkdayjobs", "workday"],
    "successfactors": ["successfactors", "sap"],
    "softgarden": ["softgarden"],
    "rexx": ["rexx-systems", "rexx"],
    "talentlink": ["talentlink"],
    "onlyfy": ["onlyfy"],
}


@dataclass(frozen=True)
class EmployerOriginTarget:
    key: str
    company_name: str
    source_family_candidate: str
    source_type_candidate: str
    url: str
    validation_reason: str


TARGETS = [
    EmployerOriginTarget(
        key="hdi",
        company_name="HDI Group",
        source_family_candidate="employer_origin:hdi",
        source_type_candidate="employer_origin_career_site",
        url="https://careers.hdi.group/en/your_career_opportunities/job_board",
        validation_reason="cross-source signal in Silver and strong target-domain relevance",
    ),
    EmployerOriginTarget(
        key="rossmann",
        company_name="Dirk Rossmann GmbH",
        source_family_candidate="employer_origin:rossmann",
        source_type_candidate="employer_origin_career_site",
        url="https://jobs.rossmann.de/jobsuche.html",
        validation_reason="repeated Silver signal from Bundesagentur and Hannover-region relevance",
    ),
    EmployerOriginTarget(
        key="finanz-informatik",
        company_name="Finanz Informatik GmbH & Co. KG",
        source_family_candidate="employer_origin:finanz_informatik",
        source_type_candidate="employer_origin_career_site",
        url="https://www.f-i.de/stellen-finden",
        validation_reason="repeated Silver signal and strong IT/Data domain fit",
    ),
    EmployerOriginTarget(
        key="wertgarantie",
        company_name="WERTGARANTIE Group",
        source_family_candidate="employer_origin:wertgarantie",
        source_type_candidate="employer_origin_career_site",
        url="https://wertgarantie-group.com/karriere/stellenangebote",
        validation_reason="StepStone-only signal; useful aggregator-vs-origin validation case",
    ),
]


def strip_html(html: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>", " ", html)
    text = re.sub(r"(?is)<style.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def find_matched_terms(text: str, terms: Iterable[str]) -> list[str]:
    text_lower = text.lower()
    return [term for term in terms if term.lower() in text_lower]


def detect_ats_hints(html: str, text: str) -> list[str]:
    haystack = f"{html}\n{text}".lower()
    matches: list[str] = []

    for ats_name, needles in ATS_HINTS.items():
        if any(needle.lower() in haystack for needle in needles):
            matches.append(ats_name)

    return sorted(set(matches))


def extract_title(html: str) -> str:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    if not match:
        return ""

    return re.sub(r"\s+", " ", unescape(match.group(1))).strip()


def count_possible_job_cards(text: str) -> int:
    # This is intentionally rough. It is not a parser contract.
    job_words = [
        "m/w/d",
        "w/m/d",
        "all genders",
        "vollzeit",
        "teilzeit",
        "hannover",
        "remote",
        "data",
        "engineer",
    ]

    lowered = text.lower()
    return sum(lowered.count(word) for word in job_words)


def evaluate_target(target: EmployerOriginTarget) -> dict[str, object]:
    headers = {
        "User-Agent": "job-application-pipeline-source-validation/0.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    response = requests.get(
        target.url,
        headers=headers,
        timeout=TIMEOUT_SECONDS,
    )

    text = strip_html(response.text)
    matched_terms = find_matched_terms(text, SEARCH_TERMS)
    ats_hints = detect_ats_hints(response.text, text)

    return {
        "key": target.key,
        "company_name": target.company_name,
        "source_family_candidate": target.source_family_candidate,
        "source_type_candidate": target.source_type_candidate,
        "url": target.url,
        "validation_reason": target.validation_reason,
        "status_code": response.status_code,
        "final_url": response.url,
        "html_bytes": len(response.content),
        "title": extract_title(response.text),
        "matched_terms": matched_terms,
        "ats_hints": ats_hints,
        "possible_job_signal_count": count_possible_job_cards(text),
    }


def print_table(rows: list[dict[str, object]]) -> None:
    headers = [
        "key",
        "status",
        "bytes",
        "matched_terms",
        "ats_hints",
        "job_signal",
        "recommendation",
    ]

    values = []
    for row in rows:
        matched_terms = ", ".join(row["matched_terms"]) if row["matched_terms"] else "-"
        ats_hints = ", ".join(row["ats_hints"]) if row["ats_hints"] else "-"
        status = str(row["status_code"])
        signal = int(row["possible_job_signal_count"])

        if status.startswith("2") and row["matched_terms"] and row["ats_hints"]:
            recommendation = "connector_candidate"
        elif status.startswith("2") and (row["matched_terms"] or row["ats_hints"]):
            recommendation = "manual_review"
        elif status.startswith("2"):
            recommendation = "reachable_needs_manual_review"
        else:
            recommendation = "defer_or_fix_url"

        values.append(
            [
                row["key"],
                status,
                str(row["html_bytes"]),
                matched_terms,
                ats_hints,
                str(signal),
                recommendation,
            ]
        )

    widths = [
        max(len(str(item)) for item in [header] + [row[index] for row in values])
        for index, header in enumerate(headers)
    ]

    print("=== Employer Origin Source Validation ===")
    print(" | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))

    for row in values:
        print(" | ".join(row[index].ljust(widths[index]) for index in range(len(headers))))


def print_details(rows: list[dict[str, object]]) -> None:
    print()
    print("=== Employer Origin Source Details ===")

    for row in rows:
        print()
        print(f"[{row['key']}] {row['company_name']}")
        print(f"source_family_candidate: {row['source_family_candidate']}")
        print(f"source_type_candidate:   {row['source_type_candidate']}")
        print(f"url:                     {row['url']}")
        print(f"final_url:               {row['final_url']}")
        print(f"status_code:             {row['status_code']}")
        print(f"title:                   {row['title'] or '-'}")
        print(f"matched_terms:           {', '.join(row['matched_terms']) if row['matched_terms'] else '-'}")
        print(f"ats_hints:               {', '.join(row['ats_hints']) if row['ats_hints'] else '-'}")
        print(f"possible_job_signal:     {row['possible_job_signal_count']}")
        print(f"validation_reason:       {row['validation_reason']}")


def main() -> None:
    rows: list[dict[str, object]] = []

    for target in TARGETS:
        try:
            rows.append(evaluate_target(target))
        except requests.RequestException as exc:
            rows.append(
                {
                    "key": target.key,
                    "company_name": target.company_name,
                    "source_family_candidate": target.source_family_candidate,
                    "source_type_candidate": target.source_type_candidate,
                    "url": target.url,
                    "validation_reason": target.validation_reason,
                    "status_code": "request_error",
                    "final_url": "-",
                    "html_bytes": 0,
                    "title": "-",
                    "matched_terms": [],
                    "ats_hints": [],
                    "possible_job_signal_count": 0,
                    "error": str(exc),
                }
            )

    print_table(rows)
    print_details(rows)


if __name__ == "__main__":
    main()
