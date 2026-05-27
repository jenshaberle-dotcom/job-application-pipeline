# Validate selected Greenhouse board candidates defensively.
#
# Defensive S1C validation:
# - one Greenhouse boards API request per explicit board token
# - no database writes
# - no detail-page fetching
# - local multi-term matching using the same simple matching semantics as ingestion
# - optional CSV export for review
#
# Usage:
#   python -m scripts.validate_greenhouse_board_candidates
#   python -m scripts.validate_greenhouse_board_candidates --include-reserve
#   python -m scripts.validate_greenhouse_board_candidates --candidate contentful --candidate commercetools

from __future__ import annotations

import argparse
import csv
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm
from src.connectors.greenhouse import GreenhouseConnector
from src.ingestion.post_fetch_filter import get_matching_search_terms


DEFAULT_SEARCH_TERMS = [
    "Data Engineer",
    "Analytics Engineer",
    "ETL",
    "Data Platform",
    "Data Warehouse",
    "Big Data",
    "Python SQL",
]


@dataclass(frozen=True)
class GreenhouseBoardCandidate:
    board_token: str
    selection_status: str
    rationale: str


@dataclass(frozen=True)
class MatchedJobPreview:
    external_job_id: str
    title: str
    location: str
    absolute_url: str
    matched_terms: tuple[str, ...]


@dataclass(frozen=True)
class GreenhouseBoardValidationResult:
    board_token: str
    source_name: str
    selection_status: str
    requested_url: str
    status: str
    total_jobs: int
    total_matching_jobs: int
    matching_jobs: tuple[MatchedJobPreview, ...]
    matched_term_counts: dict[str, int]
    recommendation: str
    rationale: str
    error: str = ""


CANDIDATES = {
    "contentful": GreenhouseBoardCandidate(
        board_token="contentful",
        selection_status="batch_1_candidate",
        rationale=(
            "Technology platform with Germany/Berlin relevance; selected as a controlled "
            "Greenhouse contrast to stripe."
        ),
    ),
    "commercetools": GreenhouseBoardCandidate(
        board_token="commercetools",
        selection_status="batch_1_candidate",
        rationale=(
            "Technology/product-platform employer with Germany/Berlin relevance; selected "
            "as second controlled Greenhouse board candidate."
        ),
    ),
    "celonis": GreenhouseBoardCandidate(
        board_token="celonis",
        selection_status="batch_1_reserve",
        rationale=(
            "Strong process-intelligence/data-domain fit; reserve candidate if a primary "
            "Greenhouse board fails validation."
        ),
    ),
}


CSV_FIELDS = [
    "board_token",
    "source_name",
    "selection_status",
    "requested_url",
    "status",
    "total_jobs",
    "total_matching_jobs",
    "exported_matching_jobs",
    "matched_terms",
    "recommendation",
    "rationale",
    "error",
]


MATCH_CSV_FIELDS = [
    "board_token",
    "external_job_id",
    "title",
    "location",
    "absolute_url",
    "matched_terms",
]


def make_validation_profile(board_token: str) -> SearchProfile:
    return SearchProfile(
        id=0,
        profile_name=f"greenhouse_{board_token}_validation_preview",
        source_name=f"greenhouse:{board_token}",
        search_location="global",
        search_radius_km=0,
        offer_type=None,
        page_size=100,
    )


def make_search_terms(terms: Iterable[str]) -> list[SearchTerm]:
    return [
        SearchTerm(id=index, search_term=term)
        for index, term in enumerate(terms, start=1)
    ]


def normalize_location(job_data: dict[str, Any]) -> str:
    offices = job_data.get("offices")

    if isinstance(offices, list):
        names = [
            str(office.get("name", "")).strip()
            for office in offices
            if isinstance(office, dict) and str(office.get("name", "")).strip()
        ]
        if names:
            return ", ".join(names)

    location = job_data.get("location")
    if isinstance(location, dict):
        value = str(location.get("name", "")).strip()
        if value:
            return value

    if isinstance(location, str) and location.strip():
        return location.strip()

    return ""


def build_match_preview(
    record: RawJobRecord,
    matched_terms: list[SearchTerm],
) -> MatchedJobPreview:
    job_data = record.raw_data.get("job", {})
    if not isinstance(job_data, dict):
        job_data = {}

    return MatchedJobPreview(
        external_job_id=record.external_job_id or "",
        title=str(job_data.get("title", "")).strip(),
        location=normalize_location(job_data),
        absolute_url=record.source_url,
        matched_terms=tuple(search_term.search_term for search_term in matched_terms),
    )


def summarize_matched_terms(matches: Sequence[MatchedJobPreview]) -> dict[str, int]:
    counts: Counter[str] = Counter()

    for match in matches:
        counts.update(match.matched_terms)

    return dict(sorted(counts.items()))


def classify_recommendation(
    status: str,
    total_jobs: int,
    matching_jobs: Sequence[MatchedJobPreview],
) -> str:
    if status != "reachable":
        return "defer_source_request_failed"

    if total_jobs == 0:
        return "defer_empty_board"

    if matching_jobs:
        return "candidate_for_controlled_profile_activation"

    return "reachable_no_current_matches"


def validate_candidate(
    candidate: GreenhouseBoardCandidate,
    search_terms: Sequence[SearchTerm],
    match_limit: int,
) -> GreenhouseBoardValidationResult:
    connector = GreenhouseConnector(board_token=candidate.board_token)
    profile = make_validation_profile(board_token=candidate.board_token)

    try:
        records, requested_url = connector.fetch_jobs(
            profile=profile,
            search_term=SearchTerm(search_term="*", id=None),
        )
    except Exception as exc:  # noqa: BLE001 - defensive validation should continue per target.
        requested_url = f"{connector.BASE_URL}/{candidate.board_token}/jobs"
        return GreenhouseBoardValidationResult(
            board_token=candidate.board_token,
            source_name=connector.source_name,
            selection_status=candidate.selection_status,
            requested_url=requested_url,
            status="request_failed",
            total_jobs=0,
            total_matching_jobs=0,
            matching_jobs=(),
            matched_term_counts={},
            recommendation="defer_source_request_failed",
            rationale=candidate.rationale,
            error=f"{type(exc).__name__}: {exc}",
        )

    matches: list[MatchedJobPreview] = []

    for record in records:
        matched_terms = get_matching_search_terms(
            record=record,
            search_terms=list(search_terms),
        )

        if not matched_terms:
            continue

        matches.append(
            build_match_preview(
                record=record,
                matched_terms=matched_terms,
            )
        )

    limited_matches = tuple(matches[:match_limit])

    return GreenhouseBoardValidationResult(
        board_token=candidate.board_token,
        source_name=connector.source_name,
        selection_status=candidate.selection_status,
        requested_url=requested_url,
        status="reachable",
        total_jobs=len(records),
        total_matching_jobs=len(matches),
        matching_jobs=limited_matches,
        matched_term_counts=summarize_matched_terms(matches),
        recommendation=classify_recommendation(
            status="reachable",
            total_jobs=len(records),
            matching_jobs=matches,
        ),
        rationale=candidate.rationale,
    )


def select_candidates(
    candidate_keys: Sequence[str],
    include_reserve: bool,
) -> list[GreenhouseBoardCandidate]:
    if candidate_keys:
        unknown = sorted(set(candidate_keys) - set(CANDIDATES))
        if unknown:
            available = ", ".join(sorted(CANDIDATES))
            raise SystemExit(
                "Unknown Greenhouse candidate(s): "
                f"{', '.join(unknown)}. Available: {available}"
            )

        return [CANDIDATES[key] for key in candidate_keys]

    candidates = [
        candidate
        for candidate in CANDIDATES.values()
        if candidate.selection_status == "batch_1_candidate"
    ]

    if include_reserve:
        candidates.extend(
            candidate
            for candidate in CANDIDATES.values()
            if candidate.selection_status == "batch_1_reserve"
        )

    return candidates


def format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "<none>"

    return ", ".join(f"{term}={count}" for term, count in counts.items())


def print_summary(results: Sequence[GreenhouseBoardValidationResult]) -> None:
    print("Greenhouse Board Candidate Validation")
    print("Mode: defensive preview")
    print("Database writes: none")
    print("Detail pages fetched: none")
    print()

    for result in results:
        print("---")
        print(f"board_token: {result.board_token}")
        print(f"source_name: {result.source_name}")
        print(f"selection_status: {result.selection_status}")
        print(f"status: {result.status}")
        print(f"total_jobs: {result.total_jobs}")
        print(f"total_matching_jobs: {result.total_matching_jobs}")
        print(f"exported_matching_jobs: {len(result.matching_jobs)}")
        print(f"matched_terms: {format_counts(result.matched_term_counts)}")
        print(f"recommendation: {result.recommendation}")
        print(f"requested_url: {result.requested_url}")

        if result.error:
            print(f"error: {result.error}")

        if result.matching_jobs:
            print("matches:")
            for match in result.matching_jobs:
                terms = ", ".join(match.matched_terms)
                print(f"  - {match.title or '<missing title>'} | {match.location or '<missing location>'} | {terms}")

    print()
    print("Interpretation boundary:")
    print("- This script validates Greenhouse board candidates only.")
    print("- It does not create search profiles, source-value snapshots or raw_jobs.")
    print("- A positive match is activation evidence, not yet long-term source value.")


def write_exports(
    results: Sequence[GreenhouseBoardValidationResult],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_path = output_dir / "greenhouse_board_candidate_validation.csv"
    matches_path = output_dir / "greenhouse_board_candidate_matches.csv"

    with summary_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()

        for result in results:
            writer.writerow(
                {
                    "board_token": result.board_token,
                    "source_name": result.source_name,
                    "selection_status": result.selection_status,
                    "requested_url": result.requested_url,
                    "status": result.status,
                    "total_jobs": result.total_jobs,
                    "total_matching_jobs": result.total_matching_jobs,
                    "exported_matching_jobs": len(result.matching_jobs),
                    "matched_terms": format_counts(result.matched_term_counts),
                    "recommendation": result.recommendation,
                    "rationale": result.rationale,
                    "error": result.error,
                }
            )

    with matches_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=MATCH_CSV_FIELDS)
        writer.writeheader()

        for result in results:
            for match in result.matching_jobs:
                writer.writerow(
                    {
                        "board_token": result.board_token,
                        "external_job_id": match.external_job_id,
                        "title": match.title,
                        "location": match.location,
                        "absolute_url": match.absolute_url,
                        "matched_terms": ", ".join(match.matched_terms),
                    }
                )

    print("Exported Greenhouse board validation files:")
    print(f"- {summary_path}")
    print(f"- {matches_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate selected Greenhouse board candidates without database writes."
    )

    parser.add_argument(
        "--candidate",
        action="append",
        default=[],
        choices=sorted(CANDIDATES),
        help="Greenhouse board candidate to validate. May be used multiple times.",
    )
    parser.add_argument(
        "--include-reserve",
        action="store_true",
        help="Include reserve candidates such as celonis in the default validation set.",
    )
    parser.add_argument(
        "--term",
        action="append",
        default=[],
        help="Override default local search terms. May be used multiple times.",
    )
    parser.add_argument(
        "--match-limit",
        type=int,
        default=10,
        help="Maximum matched jobs to print/export per board.",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        help="Optional directory for CSV review exports.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.match_limit < 0:
        parser.error("--match-limit must be zero or greater.")

    candidates = select_candidates(
        candidate_keys=args.candidate,
        include_reserve=args.include_reserve,
    )
    terms = make_search_terms(args.term or DEFAULT_SEARCH_TERMS)

    results = [
        validate_candidate(
            candidate=candidate,
            search_terms=terms,
            match_limit=args.match_limit,
        )
        for candidate in candidates
    ]

    print_summary(results)

    if args.export_dir:
        write_exports(results=results, output_dir=args.export_dir)


if __name__ == "__main__":
    main()
