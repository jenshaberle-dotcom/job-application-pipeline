"""Validate employer-origin career sources defensively.

S2F is intentionally a bounded review workflow. It is not a connector and it does
not write to the database. It checks one configured public career/search URL per
employer candidate and exports review artifacts for the next source-target
decision.

Defensive boundaries:
- one configured URL per employer target
- no detail pages
- no database writes
- short timeout
- simple HTML/text signal extraction only

Usage:
    python -m scripts.evaluate_employer_origin_sources
    python -m scripts.evaluate_employer_origin_sources --export-dir exports/employer_origin_source_validation
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from html import unescape
from pathlib import Path
from typing import Any, Iterable, Protocol

import requests


DEFAULT_EXPORT_DIR = Path("exports/employer_origin_source_validation")
TIMEOUT_SECONDS = 20
USER_AGENT = "job-application-pipeline/employer-origin-source-validation"

SEARCH_TERMS = (
    "Data Engineer",
    "Analytics Engineer",
    "Data Platform",
    "Data Warehouse",
    "Big Data",
    "Python SQL",
    "Data Analytics",
    "Business Intelligence",
)

ATS_HINTS: dict[str, tuple[str, ...]] = {
    "personio": ("personio",),
    "greenhouse": ("greenhouse.io", "boards.greenhouse"),
    "smartrecruiters": ("smartrecruiters",),
    "workday": ("myworkdayjobs", "workday"),
    "successfactors": ("successfactors", "sapsf", "career5.successfactors"),
    "softgarden": ("softgarden",),
    "rexx": ("rexx-systems", "rexx"),
    "talentlink": ("talentlink",),
    "onlyfy": ("onlyfy",),
}


@dataclass(frozen=True)
class EmployerOriginTarget:
    key: str
    company_name: str
    source_family_candidate: str
    source_type_candidate: str
    url: str
    validation_reason: str


@dataclass(frozen=True)
class FetchedPage:
    status_code: int | str
    final_url: str
    html: str
    html_bytes: int
    error: str = ""


@dataclass(frozen=True)
class EmployerOriginEvaluation:
    key: str
    company_name: str
    source_family_candidate: str
    source_type_candidate: str
    url: str
    validation_reason: str
    status_code: int | str
    final_url: str
    html_bytes: int
    title: str
    matched_terms: tuple[str, ...]
    ats_hints: tuple[str, ...]
    possible_job_signal_count: int
    recommendation: str
    notes: str
    error: str


class Fetcher(Protocol):
    def __call__(self, target: EmployerOriginTarget, timeout_seconds: int) -> FetchedPage:
        ...


TARGETS: tuple[EmployerOriginTarget, ...] = (
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
)


def strip_html(html: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>", " ", html)
    text = re.sub(r"(?is)<style.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def find_matched_terms(text: str, terms: Iterable[str]) -> tuple[str, ...]:
    text_lower = text.lower()
    matches: list[str] = []

    for term in terms:
        normalized_term = term.lower().strip()
        if not normalized_term:
            continue
        if normalized_term in text_lower:
            matches.append(term)
            continue

        tokens = normalized_term.split()
        if len(tokens) > 1 and all(token in text_lower for token in tokens):
            matches.append(term)

    return tuple(matches)


def detect_ats_hints(html: str, text: str) -> tuple[str, ...]:
    haystack = f"{html}\n{text}".lower()
    matches: list[str] = []

    for ats_name, needles in ATS_HINTS.items():
        if any(needle.lower() in haystack for needle in needles):
            matches.append(ats_name)

    return tuple(sorted(set(matches)))


def extract_title(html: str) -> str:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    if not match:
        return ""

    return re.sub(r"\s+", " ", unescape(match.group(1))).strip()


def count_possible_job_cards(text: str) -> int:
    # This is intentionally rough. It is not a parser contract.
    job_words = (
        "m/w/d",
        "w/m/d",
        "all genders",
        "vollzeit",
        "teilzeit",
        "hannover",
        "remote",
        "data",
        "engineer",
    )

    lowered = text.lower()
    return sum(lowered.count(word) for word in job_words)


def recommendation_for_evidence(
    *,
    status_code: int | str,
    matched_terms: tuple[str, ...],
    ats_hints: tuple[str, ...],
    possible_job_signal_count: int,
) -> str:
    status = str(status_code)

    if not status.startswith("2"):
        return "defer_or_fix_url"
    if matched_terms and ats_hints:
        return "connector_candidate_after_manual_review"
    if ats_hints:
        return "ats_near_candidate_manual_review"
    if matched_terms:
        return "employer_origin_candidate_manual_review"
    if possible_job_signal_count > 0:
        return "reachable_needs_manual_review"
    return "reachable_low_signal_defer"


def notes_for_evidence(
    *,
    status_code: int | str,
    matched_terms: tuple[str, ...],
    ats_hints: tuple[str, ...],
    possible_job_signal_count: int,
    error: str,
) -> str:
    if error:
        return f"request_error: {error}"

    notes: list[str] = []
    if str(status_code).startswith("2"):
        notes.append("reachable")
    else:
        notes.append("not_reachable_or_unexpected_status")

    if matched_terms:
        notes.append("profile_terms_visible")
    else:
        notes.append("profile_terms_not_visible_in_static_html")

    if ats_hints:
        notes.append("ats_hint_detected")
    else:
        notes.append("no_ats_hint_detected")

    if possible_job_signal_count > 0:
        notes.append("rough_job_signal_present")
    else:
        notes.append("low_or_dynamic_static_signal")

    return "; ".join(notes)


def fetch_target(target: EmployerOriginTarget, timeout_seconds: int) -> FetchedPage:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        response = requests.get(
            target.url,
            headers=headers,
            timeout=timeout_seconds,
        )
    except requests.RequestException as exc:
        return FetchedPage(
            status_code="request_error",
            final_url="-",
            html="",
            html_bytes=0,
            error=str(exc),
        )

    return FetchedPage(
        status_code=response.status_code,
        final_url=response.url,
        html=response.text,
        html_bytes=len(response.content),
    )


def evaluate_target(
    target: EmployerOriginTarget,
    *,
    fetcher: Fetcher = fetch_target,
    timeout_seconds: int = TIMEOUT_SECONDS,
    search_terms: tuple[str, ...] = SEARCH_TERMS,
) -> EmployerOriginEvaluation:
    page = fetcher(target, timeout_seconds)
    text = strip_html(page.html)
    matched_terms = find_matched_terms(text, search_terms)
    ats_hints = detect_ats_hints(page.html, text)
    possible_job_signal_count = count_possible_job_cards(text)
    recommendation = recommendation_for_evidence(
        status_code=page.status_code,
        matched_terms=matched_terms,
        ats_hints=ats_hints,
        possible_job_signal_count=possible_job_signal_count,
    )
    notes = notes_for_evidence(
        status_code=page.status_code,
        matched_terms=matched_terms,
        ats_hints=ats_hints,
        possible_job_signal_count=possible_job_signal_count,
        error=page.error,
    )

    return EmployerOriginEvaluation(
        key=target.key,
        company_name=target.company_name,
        source_family_candidate=target.source_family_candidate,
        source_type_candidate=target.source_type_candidate,
        url=target.url,
        validation_reason=target.validation_reason,
        status_code=page.status_code,
        final_url=page.final_url,
        html_bytes=page.html_bytes,
        title=extract_title(page.html),
        matched_terms=matched_terms,
        ats_hints=ats_hints,
        possible_job_signal_count=possible_job_signal_count,
        recommendation=recommendation,
        notes=notes,
        error=page.error,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_safe_row(row: Any) -> dict[str, Any]:
    data = asdict(row) if not isinstance(row, dict) else row
    return {
        key: "; ".join(value) if isinstance(value, tuple) else value
        for key, value in data.items()
    }


def write_csv(path: Path, rows: list[Any], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(csv_safe_row(row))


def build_manifest(
    *,
    rows: list[EmployerOriginEvaluation],
    output_path: Path,
    search_terms: tuple[str, ...],
    timeout_seconds: int,
) -> dict[str, Any]:
    status_counts = Counter(str(row.status_code) for row in rows)
    recommendation_counts = Counter(row.recommendation for row in rows)
    ats_hint_counts: Counter[str] = Counter()

    for row in rows:
        ats_hint_counts.update(row.ats_hints)

    return {
        "mode": "s2f_employer_origin_source_candidate_validation",
        "database_writes": False,
        "external_requests": True,
        "detail_pages_fetched": False,
        "candidate_count": len(rows),
        "search_terms": list(search_terms),
        "timeout_seconds": timeout_seconds,
        "status_counts": dict(sorted(status_counts.items())),
        "recommendation_counts": dict(sorted(recommendation_counts.items())),
        "ats_hint_counts": dict(sorted(ats_hint_counts.items())),
        "interpretation_boundary": (
            "This validation checks one configured public career/search URL per employer. "
            "It is not a connector, does not crawl detail pages and does not prove full job coverage. "
            "Positive findings are candidates for manual review before any source-target activation."
        ),
        "output_files": {
            "validation_csv": str(output_path),
        },
        "output_sha256": {
            "validation_csv": sha256_file(output_path),
        },
    }


def run_evaluation(
    *,
    export_dir: Path,
    timeout_seconds: int,
    search_terms: tuple[str, ...],
    targets: tuple[EmployerOriginTarget, ...] = TARGETS,
    fetcher: Fetcher = fetch_target,
) -> dict[str, Any]:
    export_dir.mkdir(parents=True, exist_ok=True)

    rows = [
        evaluate_target(
            target,
            fetcher=fetcher,
            timeout_seconds=timeout_seconds,
            search_terms=search_terms,
        )
        for target in targets
    ]

    validation_path = export_dir / "employer_origin_source_validation.csv"
    manifest_path = export_dir / "employer_origin_source_validation_manifest.json"

    write_csv(
        validation_path,
        rows,
        [
            "key",
            "company_name",
            "source_family_candidate",
            "source_type_candidate",
            "url",
            "validation_reason",
            "status_code",
            "final_url",
            "html_bytes",
            "title",
            "matched_terms",
            "ats_hints",
            "possible_job_signal_count",
            "recommendation",
            "notes",
            "error",
        ],
    )

    manifest = build_manifest(
        rows=rows,
        output_path=validation_path,
        search_terms=search_terms,
        timeout_seconds=timeout_seconds,
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    print_table(rows)
    print_details(rows)
    print()
    print("Interpretation boundary:")
    print(manifest["interpretation_boundary"])
    print()
    print("Exported employer-origin validation files:")
    for path in manifest["output_files"].values():
        print(f"- {path}")
    print(f"- {manifest_path}")

    return manifest


def print_table(rows: list[EmployerOriginEvaluation]) -> None:
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
        values.append(
            [
                row.key,
                str(row.status_code),
                str(row.html_bytes),
                ", ".join(row.matched_terms) if row.matched_terms else "-",
                ", ".join(row.ats_hints) if row.ats_hints else "-",
                str(row.possible_job_signal_count),
                row.recommendation,
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


def print_details(rows: list[EmployerOriginEvaluation]) -> None:
    print()
    print("=== Employer Origin Source Details ===")

    for row in rows:
        print()
        print(f"[{row.key}] {row.company_name}")
        print(f"source_family_candidate: {row.source_family_candidate}")
        print(f"source_type_candidate:   {row.source_type_candidate}")
        print(f"url:                     {row.url}")
        print(f"final_url:               {row.final_url}")
        print(f"status_code:             {row.status_code}")
        print(f"title:                   {row.title or '-'}")
        print(f"matched_terms:           {', '.join(row.matched_terms) if row.matched_terms else '-'}")
        print(f"ats_hints:               {', '.join(row.ats_hints) if row.ats_hints else '-'}")
        print(f"possible_job_signal:     {row.possible_job_signal_count}")
        print(f"recommendation:          {row.recommendation}")
        print(f"notes:                   {row.notes}")
        print(f"validation_reason:       {row.validation_reason}")
        if row.error:
            print(f"error:                   {row.error}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate employer-origin source candidates with bounded external requests."
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=DEFAULT_EXPORT_DIR,
        help="Directory for CSV and manifest outputs.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--search-term",
        action="append",
        dest="search_terms",
        help="Search term to evaluate. Can be passed multiple times.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    search_terms = tuple(args.search_terms or SEARCH_TERMS)
    run_evaluation(
        export_dir=args.export_dir,
        timeout_seconds=args.timeout_seconds,
        search_terms=search_terms,
    )


if __name__ == "__main__":
    main()
