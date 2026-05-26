# Preview known jobs for employer-origin evidence validation.
#
# Defensive read-only script:
# - reads known Silver jobs for selected employer-origin candidates
# - performs no HTTP requests
# - performs no database writes
# - prepares manual origin evidence validation
#
# Usage:
#   python -m scripts.preview_origin_reconciliation_candidates

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import psycopg

from src.config import get_database_config


@dataclass(frozen=True)
class OriginCandidate:
    key: str
    decision_label: str
    company_pattern: str
    origin_target_url: str
    source_family_candidate: str
    source_target_candidate: str
    source_type_candidate: str
    validation_reason: str


@dataclass(frozen=True)
class KnownJob:
    decision_label: str
    origin_key: str
    origin_target_url: str
    source_family_candidate: str
    source_target_candidate: str
    source_type_candidate: str
    validation_reason: str
    normalized_company_name: str
    source_name: str
    title: str
    normalized_title: str
    city: str | None
    normalized_location: str | None
    publication_date: str | None
    external_job_id: str | None
    source_url: str | None
    canonical_key_candidate: str | None


ORIGIN_CANDIDATES = [
    OriginCandidate(
        key="hdi",
        decision_label="HDI / HDI Group",
        company_pattern="%hdi%",
        origin_target_url="https://careers.hdi.group/en/your_career_opportunities/job_board",
        source_family_candidate="employer_origin",
        source_target_candidate="hdi",
        source_type_candidate="employer_origin_career_site",
        validation_reason="cross-source signal in Silver and strong target-domain relevance",
    ),
    OriginCandidate(
        key="rossmann",
        decision_label="Dirk Rossmann GmbH",
        company_pattern="%rossmann%",
        origin_target_url="https://jobs.rossmann.de/jobsuche.html",
        source_family_candidate="employer_origin",
        source_target_candidate="rossmann",
        source_type_candidate="employer_origin_career_site",
        validation_reason="repeated Silver signal from Bundesagentur and Hannover-region relevance",
    ),
    OriginCandidate(
        key="finanz-informatik",
        decision_label="Finanz Informatik GmbH & Co. KG",
        company_pattern="%finanz informatik%",
        origin_target_url="https://www.f-i.de/stellen-finden",
        source_family_candidate="employer_origin",
        source_target_candidate="finanz_informatik",
        source_type_candidate="employer_origin_career_site",
        validation_reason="repeated Silver signal and strong IT/Data domain fit",
    ),
    OriginCandidate(
        key="wertgarantie",
        decision_label="WERTGARANTIE Group",
        company_pattern="%wertgarantie%",
        origin_target_url="https://wertgarantie-group.com/karriere/stellenangebote",
        source_family_candidate="employer_origin",
        source_target_candidate="wertgarantie",
        source_type_candidate="employer_origin_career_site",
        validation_reason="StepStone-only signal; useful aggregator-vs-origin validation case",
    ),
]


TITLE_SIGNAL_TERMS = [
    "data engineer",
    "data scientist",
    "analytics",
    "business intelligence",
    "bi",
    "reporting",
    "data integration",
    "governance",
    "data platform",
    "data warehouse",
    "etl",
    "ai",
    "ki",
    "sas",
    "power bi",
]


def source_family_from_source_name(source_name: str) -> str:
    if ":" in source_name:
        return source_name.split(":", 1)[0]

    return source_name


def source_target_from_source_name(source_name: str) -> str:
    if ":" in source_name:
        return source_name.split(":", 1)[1]

    return source_name


def find_title_signals(title: str, normalized_title: str) -> list[str]:
    haystack = f"{title} {normalized_title}".lower()

    return [
        signal
        for signal in TITLE_SIGNAL_TERMS
        if signal.lower() in haystack
    ]


def reconciliation_intent(source_name: str, source_count_for_company: int) -> str:
    source_family = source_family_from_source_name(source_name)

    if source_count_for_company > 1:
        return "cross_source_origin_confirmation"

    if source_name == "stepstone":
        return "aggregator_only_origin_check"

    if source_name == "bundesagentur_fuer_arbeit":
        return "public_platform_origin_confirmation"

    if source_family in {"personio", "greenhouse"}:
        return "employer_near_ats_recheck"

    return "manual_origin_evidence_check"


def reason_hint(source_name: str, source_count_for_company: int) -> str:
    source_family = source_family_from_source_name(source_name)

    if source_count_for_company > 1:
        return "Known from multiple sources; check whether employer origin confirms the candidate."

    if source_name == "stepstone":
        return "Known only from aggregator; check for origin confirmation, expiry or aggregator-only posting."

    if source_name == "bundesagentur_fuer_arbeit":
        return "Known from public platform; check whether employer origin confirms the listing."

    if source_family in {"personio", "greenhouse"}:
        return "Known from employer-near ATS source; check whether it should be treated as origin evidence."

    return "Manual review required."


def fetch_known_jobs() -> list[KnownJob]:
    config = get_database_config()

    values_sql = ",\n        ".join(
        ["(%s, %s, %s, %s, %s, %s, %s, %s)"] * len(ORIGIN_CANDIDATES)
    )

    params: list[str] = []
    for candidate in ORIGIN_CANDIDATES:
        params.extend(
            [
                candidate.company_pattern,
                candidate.decision_label,
                candidate.key,
                candidate.origin_target_url,
                candidate.source_family_candidate,
                candidate.source_target_candidate,
                candidate.source_type_candidate,
                candidate.validation_reason,
            ]
        )

    query = f"""
        WITH target_companies(
            pattern,
            decision_label,
            origin_key,
            origin_target_url,
            source_family_candidate,
            source_target_candidate,
            source_type_candidate,
            validation_reason
        ) AS (
            VALUES
                {values_sql}
        )
        SELECT
            tc.decision_label,
            tc.origin_key,
            tc.origin_target_url,
            tc.source_family_candidate,
            tc.source_target_candidate,
            tc.source_type_candidate,
            tc.validation_reason,
            s.normalized_company_name,
            s.source_name,
            s.title,
            s.normalized_title,
            s.city,
            s.normalized_location,
            s.publication_date::text,
            s.external_job_id,
            s.source_url,
            s.canonical_key_candidate
        FROM silver_jobs s
        JOIN target_companies tc
            ON s.normalized_company_name ILIKE tc.pattern
        WHERE s.normalized_company_name IS NOT NULL
        ORDER BY
            tc.decision_label,
            s.normalized_company_name,
            s.source_name,
            s.normalized_title,
            s.publication_date DESC NULLS LAST;
    """

    with psycopg.connect(**config) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

    return [
        KnownJob(
            decision_label=row[0],
            origin_key=row[1],
            origin_target_url=row[2],
            source_family_candidate=row[3],
            source_target_candidate=row[4],
            source_type_candidate=row[5],
            validation_reason=row[6],
            normalized_company_name=row[7],
            source_name=row[8],
            title=row[9],
            normalized_title=row[10],
            city=row[11],
            normalized_location=row[12],
            publication_date=row[13],
            external_job_id=row[14],
            source_url=row[15],
            canonical_key_candidate=row[16],
        )
        for row in rows
    ]


def company_source_counts(jobs: Iterable[KnownJob]) -> dict[str, int]:
    sources_by_company: dict[str, set[str]] = {}

    for job in jobs:
        sources_by_company.setdefault(job.decision_label, set()).add(job.source_name)

    return {
        company: len(sources)
        for company, sources in sources_by_company.items()
    }


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    if not rows:
        print("No rows.")
        return

    widths = [
        max(len(str(item)) for item in [header] + [row[index] for row in rows])
        for index, header in enumerate(headers)
    ]

    print(" | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))

    for row in rows:
        print(" | ".join(row[index].ljust(widths[index]) for index in range(len(headers))))


def print_summary(jobs: list[KnownJob]) -> None:
    print("=== Origin Evidence Validation Preview ===")
    print(f"known_jobs: {len(jobs)}")

    company_counts: dict[str, int] = {}
    source_families_by_company: dict[str, set[str]] = {}

    for job in jobs:
        company_counts[job.decision_label] = company_counts.get(job.decision_label, 0) + 1
        source_families_by_company.setdefault(job.decision_label, set()).add(
            source_family_from_source_name(job.source_name)
        )

    rows: list[list[str]] = []
    for company in sorted(company_counts):
        rows.append(
            [
                company,
                str(company_counts[company]),
                ", ".join(sorted(source_families_by_company[company])),
            ]
        )

    print()
    print("=== Known Jobs by Origin Candidate ===")
    print_table(
        headers=["origin_candidate", "known_jobs", "known_source_families"],
        rows=rows,
    )


def print_reconciliation_matrix(jobs: list[KnownJob]) -> None:
    counts = company_source_counts(jobs)

    rows: list[list[str]] = []
    for job in jobs:
        source_count = counts[job.decision_label]
        title_signals = find_title_signals(job.title, job.normalized_title)

        rows.append(
            [
                job.decision_label,
                job.source_name,
                source_family_from_source_name(job.source_name),
                source_target_from_source_name(job.source_name),
                job.title,
                job.city or "-",
                job.publication_date or "-",
                ", ".join(title_signals) if title_signals else "-",
                reconciliation_intent(job.source_name, source_count),
                "pending_manual_origin_check",
            ]
        )

    print()
    print("=== Reconciliation Matrix ===")
    print_table(
        headers=[
            "origin_candidate",
            "known_source",
            "source_family",
            "source_target",
            "known_title",
            "city",
            "publication_date",
            "title_signals",
            "reconciliation_intent",
            "evidence_status",
        ],
        rows=rows,
    )


def print_details(jobs: list[KnownJob]) -> None:
    counts = company_source_counts(jobs)

    print()
    print("=== Manual Evidence Check Details ===")

    current_company = None
    for job in jobs:
        if current_company != job.decision_label:
            current_company = job.decision_label
            print()
            print(f"## {job.decision_label}")
            print(f"origin_key:              {job.origin_key}")
            print(f"origin_target_url:       {job.origin_target_url}")
            print(f"source_family_candidate: {job.source_family_candidate}")
            print(f"source_target_candidate: {job.source_target_candidate}")
            print(f"source_type_candidate:   {job.source_type_candidate}")
            print(f"validation_reason:       {job.validation_reason}")

        source_count = counts[job.decision_label]
        print()
        print(f"- known_title:           {job.title}")
        print(f"  known_source:          {job.source_name}")
        print(f"  known_source_family:   {source_family_from_source_name(job.source_name)}")
        print(f"  normalized_company:    {job.normalized_company_name}")
        print(f"  normalized_title:      {job.normalized_title}")
        print(f"  location:              {job.normalized_location or job.city or '-'}")
        print(f"  publication_date:      {job.publication_date or '-'}")
        print(f"  title_signals:         {', '.join(find_title_signals(job.title, job.normalized_title)) or '-'}")
        print(f"  reconciliation_intent: {reconciliation_intent(job.source_name, source_count)}")
        print(f"  evidence_status:       pending_manual_origin_check")
        print(f"  reason_hint:           {reason_hint(job.source_name, source_count)}")
        print(f"  source_url:            {job.source_url or '-'}")
        print(f"  canonical_key:         {job.canonical_key_candidate or '-'}")


def main() -> None:
    jobs = fetch_known_jobs()

    print_summary(jobs)
    print_reconciliation_matrix(jobs)
    print_details(jobs)


if __name__ == "__main__":
    main()
