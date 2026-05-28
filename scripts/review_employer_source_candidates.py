"""Review employer/source candidates against current pipeline visibility.

S2E is intentionally a read-only review workflow. It does not fetch employer
websites, does not call aggregators and does not write to the database. It turns
source-coverage nervousness into comparable evidence:

- expected strategic employers that should be watched for false negatives
- aggregator-discovered employer candidates from S2D
- active-source company discovery from the current hot store

Usage:
    python -m scripts.review_employer_source_candidates
    python -m scripts.review_employer_source_candidates --export-dir exports/employer_candidate_review
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from src.config import get_database_config


@dataclass(frozen=True)
class EmployerCandidate:
    key: str
    company_name: str
    candidate_group: str
    target_region: str
    candidate_origin: str
    aliases: tuple[str, ...]
    expected_source_path: str
    priority: str
    notes: str


@dataclass(frozen=True)
class CandidateHit:
    candidate_key: str
    source_name: str
    raw_job_id: int
    silver_job_id: int | None
    decision: str
    search_term: str
    raw_company_name: str
    raw_title: str
    silver_company_name: str
    silver_title: str
    source_url: str
    fetched_at: Any
    matched_aliases: tuple[str, ...]


@dataclass(frozen=True)
class CandidateSummary:
    candidate_key: str
    company_name: str
    candidate_group: str
    target_region: str
    candidate_origin: str
    expected_source_path: str
    priority: str
    raw_jobs: int
    silver_jobs: int
    source_count: int
    source_names: str
    skipped_raw_jobs: int
    included_decisions: int
    latest_seen_at: str
    matched_aliases: str
    matched_search_terms: str
    visibility_status: str
    false_negative_signal: str
    likely_gap_type: str
    recommendation: str
    notes: str


@dataclass(frozen=True)
class SourceCompanyDiscovery:
    source_name: str
    source_family: str
    company_name: str
    raw_jobs: int
    silver_jobs: int
    latest_fetched_at: str
    sample_titles: str


DEFAULT_CANDIDATES: tuple[EmployerCandidate, ...] = (
    EmployerCandidate(
        key="hdi",
        company_name="HDI Group",
        candidate_group="strategic_expected",
        target_region="Hannover / Germany / remote Germany",
        candidate_origin="known_target_market_candidate",
        aliases=("HDI", "HDI Group", "HDI Deutschland", "HDI Systeme"),
        expected_source_path="employer_origin_or_ats_path_unknown",
        priority="high",
        notes="Known Hannover/insurance target; useful false-negative check candidate.",
    ),
    EmployerCandidate(
        key="rossmann",
        company_name="Dirk Rossmann GmbH",
        candidate_group="strategic_expected",
        target_region="Burgwedel / Hannover region / Germany",
        candidate_origin="known_target_market_candidate",
        aliases=("ROSSMANN", "Rossmann", "Dirk Rossmann"),
        expected_source_path="employer_origin_or_ats_path_unknown",
        priority="high",
        notes="Regional employer with potential data/IT roles.",
    ),
    EmployerCandidate(
        key="finanz_informatik",
        company_name="Finanz Informatik GmbH & Co. KG",
        candidate_group="strategic_expected",
        target_region="Hannover / Germany",
        candidate_origin="known_target_market_candidate",
        aliases=("Finanz Informatik", "FI-TS"),
        expected_source_path="employer_origin_or_ats_path_unknown",
        priority="high",
        notes="Strong IT/data domain fit and regional relevance.",
    ),
    EmployerCandidate(
        key="wertgarantie",
        company_name="WERTGARANTIE Group",
        candidate_group="strategic_expected",
        target_region="Hannover / Germany",
        candidate_origin="known_target_market_candidate",
        aliases=("WERTGARANTIE", "Wertgarantie"),
        expected_source_path="employer_origin_or_ats_path_unknown",
        priority="medium",
        notes="Insurance/service domain candidate; useful StepStone/aggregator-vs-origin validation case.",
    ),
    EmployerCandidate(
        key="vhv",
        company_name="VHV Gruppe",
        candidate_group="strategic_expected",
        target_region="Hannover / Germany",
        candidate_origin="known_target_market_candidate",
        aliases=("VHV", "VHV Gruppe", "VHV Group"),
        expected_source_path="employer_origin_or_ats_path_unknown",
        priority="medium",
        notes="Hannover insurance target; useful false-negative check candidate.",
    ),
    EmployerCandidate(
        key="talanx",
        company_name="Talanx",
        candidate_group="strategic_expected",
        target_region="Hannover / Germany",
        candidate_origin="known_target_market_candidate",
        aliases=("Talanx",),
        expected_source_path="employer_origin_or_ats_path_unknown",
        priority="medium",
        notes="Hannover insurance group context; related but intentionally tracked separately from HDI.",
    ),
    EmployerCandidate(
        key="sumup",
        company_name="SumUp",
        candidate_group="aggregator_discovered",
        target_region="Germany / remote Germany",
        candidate_origin="s2d_aggregator_discovery",
        aliases=("SumUp",),
        expected_source_path="employer_origin_or_ats_path_unknown",
        priority="medium",
        notes="S2D signal with analytics/data roles and German locations.",
    ),
    EmployerCandidate(
        key="cordes_graefe",
        company_name="Cordes & Graefe KG",
        candidate_group="aggregator_discovered",
        target_region="Northern Germany",
        candidate_origin="s2d_aggregator_discovery",
        aliases=("Cordes & Graefe", "Cordes und Graefe", "Cordes Graefe", "Cordes & Graefe KG"),
        expected_source_path="employer_origin_or_ats_path_unknown",
        priority="high",
        notes="S2D signal for Product Owner Data Platform in Northern Germany.",
    ),
    EmployerCandidate(
        key="quantum_systems",
        company_name="Quantum-Systems GmbH",
        candidate_group="aggregator_discovered",
        target_region="Germany",
        candidate_origin="s2d_aggregator_discovery",
        aliases=("Quantum-Systems", "Quantum Systems"),
        expected_source_path="employer_origin_or_ats_path_unknown",
        priority="low",
        notes="Technically interesting S2D signal, but less aligned with Hannover/remote-Germany target.",
    ),
    EmployerCandidate(
        key="onekommafuenf",
        company_name="1KOMMA5°",
        candidate_group="aggregator_discovered_control",
        target_region="Germany",
        candidate_origin="s2d_aggregator_discovery_already_active_check",
        aliases=("1KOMMA5", "1KOMMA5°", "1KOMMA5˚", "1komma5grad", "1KOMMA5 GmbH"),
        expected_source_path="already_active_personio_target",
        priority="control",
        notes="Already active as Personio target; use as S2D coverage/control check.",
    ),
)

RAW_COMPANY_SQL = """
CASE
    WHEN rj.source_name = 'stepstone' THEN rj.raw_data #>> '{result_card,company_name}'
    WHEN rj.source_name = 'bundesagentur_fuer_arbeit' THEN rj.raw_data #>> '{job,arbeitgeber}'
    WHEN rj.source_name LIKE 'greenhouse:%%' THEN rj.raw_data #>> '{job,company_name}'
    WHEN rj.source_name LIKE 'personio:%%' THEN rj.raw_data #>> '{job,company_name}'
    ELSE NULL
END
"""

RAW_TITLE_SQL = """
CASE
    WHEN rj.source_name = 'stepstone' THEN rj.raw_data #>> '{result_card,title}'
    WHEN rj.source_name = 'bundesagentur_fuer_arbeit' THEN rj.raw_data #>> '{job,titel}'
    WHEN rj.source_name LIKE 'greenhouse:%%' THEN rj.raw_data #>> '{job,title}'
    WHEN rj.source_name LIKE 'personio:%%' THEN rj.raw_data #>> '{job,title}'
    ELSE NULL
END
"""


CANDIDATE_HIT_SQL = f"""
SELECT
    rj.id AS raw_job_id,
    rj.source_name,
    sj.id AS silver_job_id,
    COALESCE(spd.decision, '<none>') AS decision,
    COALESCE(ir.search_term, '<unknown>') AS search_term,
    COALESCE({RAW_COMPANY_SQL}, '') AS raw_company_name,
    COALESCE({RAW_TITLE_SQL}, '') AS raw_title,
    COALESCE(sj.company_name, '') AS silver_company_name,
    COALESCE(sj.title, '') AS silver_title,
    COALESCE(sj.source_url, rj.source_url, '') AS source_url,
    rj.fetched_at,
    CONCAT_WS(
        ' ',
        COALESCE({RAW_COMPANY_SQL}, ''),
        COALESCE({RAW_TITLE_SQL}, ''),
        COALESCE(sj.company_name, ''),
        COALESCE(sj.title, ''),
        COALESCE(sj.source_url, rj.source_url, ''),
        COALESCE(rj.raw_data::text, '')
    ) AS match_haystack
FROM raw_jobs rj
LEFT JOIN silver_jobs sj
    ON sj.raw_job_id = rj.id
LEFT JOIN silver_processing_decisions spd
    ON spd.raw_job_id = rj.id
LEFT JOIN ingestion_runs ir
    ON ir.id = rj.ingestion_run_id
WHERE __WHERE_CLAUSE__
ORDER BY
    rj.fetched_at DESC,
    rj.source_name,
    rj.id;
"""


SOURCE_COMPANY_DISCOVERY_SQL = f"""
WITH raw_companies AS (
    SELECT
        rj.id AS raw_job_id,
        rj.source_name,
        CASE
            WHEN POSITION(':' IN rj.source_name) > 0
            THEN SPLIT_PART(rj.source_name, ':', 1)
            ELSE rj.source_name
        END AS source_family,
        NULLIF(TRIM(COALESCE({RAW_COMPANY_SQL}, '')), '') AS company_name,
        NULLIF(TRIM(COALESCE({RAW_TITLE_SQL}, '')), '') AS title,
        rj.fetched_at,
        sj.id AS silver_job_id
    FROM raw_jobs rj
    LEFT JOIN silver_jobs sj
        ON sj.raw_job_id = rj.id
),
company_summary AS (
    SELECT
        source_name,
        source_family,
        company_name,
        COUNT(*) AS raw_jobs,
        COUNT(silver_job_id) AS silver_jobs,
        MAX(fetched_at) AS latest_fetched_at,
        STRING_AGG(DISTINCT title, ' | ' ORDER BY title)
            FILTER (WHERE title IS NOT NULL) AS sample_titles
    FROM raw_companies
    WHERE company_name IS NOT NULL
    GROUP BY
        source_name,
        source_family,
        company_name
),
ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY source_name
            ORDER BY raw_jobs DESC, company_name
        ) AS source_rank
    FROM company_summary
)
SELECT
    source_name,
    source_family,
    company_name,
    raw_jobs,
    silver_jobs,
    latest_fetched_at,
    COALESCE(sample_titles, '') AS sample_titles
FROM ranked
WHERE source_rank <= %s
ORDER BY
    source_name,
    source_rank,
    company_name;
"""


def normalize_text(value: str) -> str:
    return " ".join(value.lower().split())


def source_family(source_name: str) -> str:
    return source_name.split(":", 1)[0]


def matched_aliases_in_text(text: str, aliases: Iterable[str]) -> tuple[str, ...]:
    haystack = normalize_text(text)
    return tuple(alias for alias in aliases if normalize_text(alias) in haystack)


def build_candidate_where_clause(candidate: EmployerCandidate) -> tuple[str, list[str]]:
    fields = [
        f"COALESCE({RAW_COMPANY_SQL}, '')",
        f"COALESCE({RAW_TITLE_SQL}, '')",
        "COALESCE(sj.company_name, '')",
        "COALESCE(sj.title, '')",
        "COALESCE(sj.source_url, rj.source_url, '')",
        "COALESCE(rj.raw_data::text, '')",
    ]
    haystack = "LOWER(CONCAT_WS(' ', " + ", ".join(fields) + "))"

    predicates = [f"{haystack} LIKE LOWER(%s)" for _ in candidate.aliases]
    params = [f"%{alias}%" for alias in candidate.aliases]

    return " OR ".join(predicates), params


def load_candidate_hits(
    connection: Any,
    candidate: EmployerCandidate,
) -> list[CandidateHit]:
    where_clause, params = build_candidate_where_clause(candidate)
    sql = CANDIDATE_HIT_SQL.replace("__WHERE_CLAUSE__", where_clause)

    from psycopg.rows import dict_row

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(sql, params)
        rows = cursor.fetchall()

    hits: list[CandidateHit] = []
    for row in rows:
        haystack = str(row.pop("match_haystack"))
        matched_aliases = matched_aliases_in_text(haystack, candidate.aliases)
        if not matched_aliases:
            continue

        hits.append(
            CandidateHit(
                candidate_key=candidate.key,
                source_name=row["source_name"],
                raw_job_id=row["raw_job_id"],
                silver_job_id=row["silver_job_id"],
                decision=row["decision"],
                search_term=row["search_term"],
                raw_company_name=row["raw_company_name"],
                raw_title=row["raw_title"],
                silver_company_name=row["silver_company_name"],
                silver_title=row["silver_title"],
                source_url=row["source_url"],
                fetched_at=row["fetched_at"],
                matched_aliases=matched_aliases,
            )
        )

    return hits


def classify_visibility(raw_jobs: int, silver_jobs: int, skipped_raw_jobs: int) -> str:
    if silver_jobs > 0:
        return "visible_in_silver"
    if raw_jobs > 0 and skipped_raw_jobs > 0:
        return "raw_only_skipped_or_filtered"
    if raw_jobs > 0:
        return "raw_only_not_promoted"
    return "not_visible_current_db"


def classify_false_negative_signal(candidate: EmployerCandidate, visibility_status: str) -> str:
    if visibility_status == "visible_in_silver":
        return "low_currently_visible"

    if candidate.candidate_group == "strategic_expected":
        if visibility_status == "not_visible_current_db":
            return "high_expected_candidate_missing"
        return "medium_expected_candidate_not_silver_visible"

    if candidate.candidate_group.startswith("aggregator_discovered"):
        if visibility_status == "not_visible_current_db":
            return "medium_new_candidate_not_covered"
        return "medium_candidate_seen_but_not_silver_visible"

    return "unknown"


def infer_likely_gap_type(visibility_status: str) -> str:
    if visibility_status == "visible_in_silver":
        return "currently_visible"
    if visibility_status == "raw_only_skipped_or_filtered":
        return "silver_filter_or_relevance_gap"
    if visibility_status == "raw_only_not_promoted":
        return "silver_processing_or_transform_gap"
    return "source_coverage_or_search_term_gap"


def recommend_next_step(candidate: EmployerCandidate, visibility_status: str) -> str:
    if candidate.expected_source_path == "already_active_personio_target":
        return "already_active_source_target_check_current_coverage"

    if visibility_status == "visible_in_silver":
        return "covered_keep_in_overlap_and_source_value_monitoring"

    if candidate.candidate_group == "strategic_expected":
        return "investigate_employer_origin_path_and_search_term_gap"

    if candidate.candidate_group.startswith("aggregator_discovered"):
        return "validate_employer_origin_or_ats_path_before_connector_work"

    return "review_manually_before_source_decision"


def format_datetime(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def summarize_candidate(
    candidate: EmployerCandidate,
    hits: list[CandidateHit],
) -> CandidateSummary:
    raw_job_ids = {hit.raw_job_id for hit in hits}
    silver_job_ids = {hit.silver_job_id for hit in hits if hit.silver_job_id is not None}
    source_names = sorted({hit.source_name for hit in hits})
    skipped_raw_jobs = len({hit.raw_job_id for hit in hits if hit.decision == "skipped"})
    included_decisions = len({hit.raw_job_id for hit in hits if hit.decision == "included"})
    latest_seen_at = max((hit.fetched_at for hit in hits), default=None)
    aliases = sorted({alias for hit in hits for alias in hit.matched_aliases})
    search_terms = sorted(
        {hit.search_term for hit in hits if hit.search_term and hit.search_term != "<unknown>"}
    )

    visibility_status = classify_visibility(
        raw_jobs=len(raw_job_ids),
        silver_jobs=len(silver_job_ids),
        skipped_raw_jobs=skipped_raw_jobs,
    )

    return CandidateSummary(
        candidate_key=candidate.key,
        company_name=candidate.company_name,
        candidate_group=candidate.candidate_group,
        target_region=candidate.target_region,
        candidate_origin=candidate.candidate_origin,
        expected_source_path=candidate.expected_source_path,
        priority=candidate.priority,
        raw_jobs=len(raw_job_ids),
        silver_jobs=len(silver_job_ids),
        source_count=len(source_names),
        source_names="; ".join(source_names) or "<none>",
        skipped_raw_jobs=skipped_raw_jobs,
        included_decisions=included_decisions,
        latest_seen_at=format_datetime(latest_seen_at),
        matched_aliases="; ".join(aliases) or "<none>",
        matched_search_terms="; ".join(search_terms) or "<none>",
        visibility_status=visibility_status,
        false_negative_signal=classify_false_negative_signal(candidate, visibility_status),
        likely_gap_type=infer_likely_gap_type(visibility_status),
        recommendation=recommend_next_step(candidate, visibility_status),
        notes=candidate.notes,
    )


def load_source_company_discovery(
    connection: Any,
    limit_per_source: int,
) -> list[SourceCompanyDiscovery]:
    from psycopg.rows import dict_row

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(SOURCE_COMPANY_DISCOVERY_SQL, (limit_per_source,))
        rows = cursor.fetchall()

    return [
        SourceCompanyDiscovery(
            source_name=row["source_name"],
            source_family=row["source_family"],
            company_name=row["company_name"],
            raw_jobs=row["raw_jobs"],
            silver_jobs=row["silver_jobs"],
            latest_fetched_at=format_datetime(row["latest_fetched_at"]),
            sample_titles=" ".join(str(row["sample_titles"]).split())[:500],
        )
        for row in rows
    ]


def write_csv(path: Path, rows: list[Any], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(
    *,
    summaries: list[CandidateSummary],
    details: list[CandidateHit],
    source_companies: list[SourceCompanyDiscovery],
    summary_path: Path,
    details_path: Path,
    source_companies_path: Path,
) -> dict[str, Any]:
    visibility_counts = defaultdict(int)
    false_negative_counts = defaultdict(int)
    recommendation_counts = defaultdict(int)

    for summary in summaries:
        visibility_counts[summary.visibility_status] += 1
        false_negative_counts[summary.false_negative_signal] += 1
        recommendation_counts[summary.recommendation] += 1

    stepstone_company_rows = [
        row for row in source_companies if row.source_name == "stepstone"
    ]

    return {
        "mode": "s2e_employer_candidate_and_false_negative_review",
        "database_writes": False,
        "external_requests": False,
        "candidate_count": len(summaries),
        "candidate_detail_rows": len(details),
        "source_company_discovery_rows": len(source_companies),
        "stepstone_unique_company_rows": len(stepstone_company_rows),
        "visibility_status_counts": dict(sorted(visibility_counts.items())),
        "false_negative_signal_counts": dict(sorted(false_negative_counts.items())),
        "recommendation_counts": dict(sorted(recommendation_counts.items())),
        "interpretation_boundary": (
            "This review quantifies current pipeline visibility and false-negative risk. "
            "A missing candidate is not proof that the employer has no relevant jobs; it is "
            "a signal to inspect source coverage, search terms, fetch limits or employer-origin paths."
        ),
        "unique_company_discovery_boundary": (
            "Unique company names are source-discovery evidence only. They can suggest employer-origin "
            "follow-up candidates, but they are not canonical job evidence and do not justify aggressive "
            "aggregator expansion."
        ),
        "output_files": {
            "summary_csv": str(summary_path),
            "details_csv": str(details_path),
            "source_company_discovery_csv": str(source_companies_path),
        },
        "output_sha256": {
            "summary_csv": sha256_file(summary_path),
            "details_csv": sha256_file(details_path),
            "source_company_discovery_csv": sha256_file(source_companies_path),
        },
    }


def run_review(export_dir: Path, unique_company_limit_per_source: int) -> dict[str, Any]:
    export_dir.mkdir(parents=True, exist_ok=True)

    summaries: list[CandidateSummary] = []
    details: list[CandidateHit] = []

    import psycopg

    with psycopg.connect(**get_database_config()) as connection:
        for candidate in DEFAULT_CANDIDATES:
            hits = load_candidate_hits(connection, candidate)
            summaries.append(summarize_candidate(candidate, hits))
            details.extend(hits)

        source_companies = load_source_company_discovery(
            connection,
            unique_company_limit_per_source,
        )

    summary_path = export_dir / "employer_candidate_review_summary.csv"
    details_path = export_dir / "employer_candidate_review_details.csv"
    source_companies_path = export_dir / "source_unique_company_discovery.csv"
    manifest_path = export_dir / "employer_candidate_review_manifest.json"

    write_csv(
        summary_path,
        summaries,
        [
            "candidate_key",
            "company_name",
            "candidate_group",
            "target_region",
            "candidate_origin",
            "expected_source_path",
            "priority",
            "raw_jobs",
            "silver_jobs",
            "source_count",
            "source_names",
            "skipped_raw_jobs",
            "included_decisions",
            "latest_seen_at",
            "matched_aliases",
            "matched_search_terms",
            "visibility_status",
            "false_negative_signal",
            "likely_gap_type",
            "recommendation",
            "notes",
        ],
    )
    write_csv(
        details_path,
        details,
        [
            "candidate_key",
            "source_name",
            "raw_job_id",
            "silver_job_id",
            "decision",
            "search_term",
            "raw_company_name",
            "raw_title",
            "silver_company_name",
            "silver_title",
            "source_url",
            "fetched_at",
            "matched_aliases",
        ],
    )
    write_csv(
        source_companies_path,
        source_companies,
        [
            "source_name",
            "source_family",
            "company_name",
            "raw_jobs",
            "silver_jobs",
            "latest_fetched_at",
            "sample_titles",
        ],
    )

    manifest = build_manifest(
        summaries=summaries,
        details=details,
        source_companies=source_companies,
        summary_path=summary_path,
        details_path=details_path,
        source_companies_path=source_companies_path,
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return manifest


def print_manifest_summary(manifest: dict[str, Any]) -> None:
    print("Employer Candidate and False-Negative Review")
    print("Mode: read-only")
    print("Database writes: none")
    print("External requests: none")
    print()

    for key in [
        "candidate_count",
        "candidate_detail_rows",
        "source_company_discovery_rows",
        "stepstone_unique_company_rows",
    ]:
        print(f"{key}: {manifest[key]}")

    print("visibility_status_counts:", manifest["visibility_status_counts"])
    print("false_negative_signal_counts:", manifest["false_negative_signal_counts"])
    print("recommendation_counts:", manifest["recommendation_counts"])
    print()
    print(manifest["interpretation_boundary"])
    print()
    print("Exported employer candidate review files:")
    for path in manifest["output_files"].values():
        print(f"- {path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Review expected and discovered employers against current pipeline visibility."
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("exports/employer_candidate_review"),
        help="Directory for CSV and manifest outputs.",
    )
    parser.add_argument(
        "--unique-company-limit-per-source",
        type=int,
        default=25,
        help="Maximum unique company rows exported per source for discovery review.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = run_review(
        export_dir=args.export_dir,
        unique_company_limit_per_source=args.unique_company_limit_per_source,
    )
    print_manifest_summary(manifest)


if __name__ == "__main__":
    main()
