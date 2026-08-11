from __future__ import annotations

import argparse
import json
from typing import Iterable

import psycopg
from psycopg.rows import dict_row

from scripts.run_employer_origin_detail_evidence_repair_agent import (
    SourceCandidate,
    discover_link_candidates,
)
from scripts.run_origin_source_discovery_agent import http_probe
from src.config import get_database_config
from src.job_lifecycle_health import fetch_exact_detail
from src.search_intelligence.bounded_origin_candidate_hypotheses import (
    generate_bounded_origin_candidate_hypotheses,
)
from src.search_intelligence.detail_candidate_budget import (
    DETAIL_CANDIDATE_SELECTION_VERSION,
    prioritize_detail_candidates,
)
from src.search_intelligence.origin_seed_pool import normalize_company_key
from src.search_intelligence.origin_source_discovery_agent import (
    discover_origin_source,
    result_to_json,
)
from src.search_intelligence.product_v1_contenders import (
    DEFAULT_CONTENDER_LIMIT,
    build_contender_manifest,
)
from src.search_intelligence.product_v1_origin_vacancy_bridge import (
    ExactDetailAttempt,
    OriginCandidateSnapshot,
    SilverContender,
    contender_from_manifest_row,
    evaluate_exact_detail_attempts,
    origin_candidate_from_row,
    resolution_payload,
    resolve_origin_candidate,
)
from src.search_intelligence.product_v1_refill import run_bounded_refill
from src.search_intelligence.product_v1_transient_origin import (
    classify_transient_origin_result,
    should_attempt_transient_origin,
    transient_origin_resolution_payload,
)


DEFAULT_CURRENT_TARGET = 5
MAX_EXPLICIT_TARGETS = 5
DEFAULT_MAX_ORIGIN_CANDIDATES = 12
MAX_ORIGIN_CANDIDATES = 30
DEFAULT_ORIGIN_TIMEOUT_SECONDS = 5.0
DEFAULT_MAX_SEED_PAGES = 3
DEFAULT_MAX_DETAIL_PAGES = 8


def bounded_positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def bounded_positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive number")
    return parsed


def load_read_only_state() -> tuple[str, list[dict], list[OriginCandidateSnapshot]]:
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SHOW transaction_read_only")
            read_only = str(cur.fetchone()["transaction_read_only"])
            if read_only != "on":
                raise RuntimeError("origin vacancy bridge requires a read-only transaction")

            cur.execute(
                "SELECT "
                "silver_job_id, title, company_name, city, country, "
                "publication_date, source_name, source_url, canonical_source_type, "
                "origin_validation_status, work_model, commute_minutes, "
                "lifecycle_status "
                "FROM gold_product_v1_job_readiness "
                "ORDER BY silver_job_id"
            )
            inventory_rows = [dict(row) for row in cur.fetchall()]

            cur.execute(
                "SELECT "
                "id, company_key, company_name, candidate_url, "
                "source_name_candidate, source_family_candidate, "
                "source_target_candidate, source_type_candidate, status, risk_level "
                "FROM employer_origin_source_candidates "
                "ORDER BY id"
            )
            candidate_rows = [
                origin_candidate_from_row(dict(row)) for row in cur.fetchall()
            ]
        conn.rollback()

    return read_only, inventory_rows, candidate_rows


def select_contenders(
    manifest: dict[str, object],
    *,
    requested_silver_job_ids: Iterable[int],
) -> list[dict]:
    rows = list(manifest["rows"])
    by_id = {int(row["silver_job_id"]): row for row in rows}
    requested = list(dict.fromkeys(int(value) for value in requested_silver_job_ids))
    if len(requested) > MAX_EXPLICIT_TARGETS:
        raise ValueError(
            f"At most {MAX_EXPLICIT_TARGETS} explicit Silver targets are allowed."
        )
    if requested:
        missing = [value for value in requested if value not in by_id]
        if missing:
            raise ValueError(
                "Explicit targets are not present in the current bounded Product V1 "
                f"contender pool: {missing}"
            )
        return [by_id[value] for value in requested]

    return rows


def _source_candidate(snapshot: OriginCandidateSnapshot) -> SourceCandidate:
    return SourceCandidate(
        id=snapshot.candidate_id,
        company_key=snapshot.company_key,
        company_name=snapshot.company_name,
        candidate_url=snapshot.candidate_url or "",
        source_name_candidate=snapshot.source_name_candidate,
        source_family_candidate=snapshot.source_family_candidate,
        source_target_candidate=snapshot.source_target_candidate,
        source_type_candidate=snapshot.source_type_candidate,
        status=snapshot.status,
        risk_level=snapshot.risk_level,
    )


def _transient_source_candidate(
    contender: SilverContender,
    *,
    selected_url: str,
    risk_level: str,
) -> SourceCandidate:
    company_key = normalize_company_key(contender.company_name)
    return SourceCandidate(
        id=0,
        company_key=company_key,
        company_name=contender.company_name,
        candidate_url=selected_url,
        source_name_candidate=f"{company_key}:transient_product_v1_origin",
        source_family_candidate=company_key,
        source_target_candidate=None,
        source_type_candidate="employer_origin_career_site",
        status="transient_read_only",
        risk_level=risk_level,
    )


def run_transient_origin_discovery(
    contender: SilverContender,
    *,
    max_origin_candidates: int,
    origin_timeout_seconds: float,
) -> tuple[SourceCandidate | None, dict[str, object]]:
    company_key = normalize_company_key(contender.company_name)
    deterministic_candidates = generate_bounded_origin_candidate_hypotheses(
        company_key=company_key,
        company_name=contender.company_name,
        source_family_candidate=company_key,
        max_candidates=max_origin_candidates,
    )
    discovery = discover_origin_source(
        company_key=company_key,
        company_name=contender.company_name,
        source_family_candidate=company_key,
        market_evidence_urls=(),
        search_result_candidates=deterministic_candidates,
        search_results=(),
        target_location=contender.city or "Hannover",
        probe=lambda url: http_probe(
            url,
            timeout_seconds=origin_timeout_seconds,
        ),
        max_generated_candidates=0,
    )
    classified = classify_transient_origin_result(discovery)
    evidence = result_to_json(discovery)
    evidence["classification"] = transient_origin_resolution_payload(classified)
    evidence["deterministic_candidate_strategy"] = "diverse_brand_tld_bounded"
    evidence["deterministic_candidate_urls"] = [
        candidate.url for candidate in deterministic_candidates
    ]
    evidence["provider_requests"] = 0
    evidence["external_search_discovery_enabled"] = False
    evidence["persisted_candidate_created"] = False
    evidence["candidate_or_origin_url_writes"] = False

    if (
        classified.status != "ready_for_bounded_detail_discovery"
        or not classified.selected_url
    ):
        return None, evidence

    return (
        _transient_source_candidate(
            contender,
            selected_url=classified.selected_url,
            risk_level=classified.risk_level,
        ),
        evidence,
    )


def run_bridge_for_contender(
    row: dict,
    *,
    candidates: list[OriginCandidateSnapshot],
    max_origin_candidates: int,
    origin_timeout_seconds: float,
    max_seed_pages: int,
    max_detail_pages: int,
) -> dict[str, object]:
    contender = contender_from_manifest_row(row)
    resolution = resolve_origin_candidate(contender, candidates)
    result: dict[str, object] = {
        "inspection_priority": contender.inspection_priority,
        "silver_job_id": contender.silver_job_id,
        "title": contender.title,
        "company_name": contender.company_name,
        "geography_bucket": contender.geography_bucket,
        "historical_source": {
            "source_name": contender.source_name,
            "source_url": contender.source_url,
            "canonical_source_type": contender.canonical_source_type,
            "treated_as_current_activity_truth": False,
        },
        "origin_candidate_resolution": resolution_payload(resolution),
        "transient_origin_discovery": None,
        "detail_discovery": None,
        "exact_vacancy": None,
    }

    candidate: SourceCandidate | None = None
    if resolution.status == "ready_for_bounded_detail_discovery":
        assert resolution.candidate is not None
        candidate = _source_candidate(resolution.candidate)
    elif should_attempt_transient_origin(resolution.status):
        candidate, evidence = run_transient_origin_discovery(
            contender,
            max_origin_candidates=max_origin_candidates,
            origin_timeout_seconds=origin_timeout_seconds,
        )
        result["transient_origin_discovery"] = evidence
        if candidate is None:
            return result
    else:
        return result

    location_terms = tuple(
        dict.fromkeys(
            value
            for value in (contender.city, "Hannover", "remote", "Deutschland")
            if value
        )
    )
    link_candidates, rejected_urls, requested_urls, discovery_evidence = (
        discover_link_candidates(
            candidate=candidate,
            gates={},
            profile_terms=(contender.title,),
            location_terms=location_terms,
            max_seed_pages=max_seed_pages,
            enable_search_discovery=False,
            max_search_queries=1,
            max_search_results=1,
        )
    )

    bounded_links, selection_evidence = prioritize_detail_candidates(
        target_title=contender.title,
        company_name=contender.company_name,
        candidates=link_candidates,
        limit=max_detail_pages,
    )
    attempts = [
        ExactDetailAttempt(
            url=link.url,
            link_text=link.text,
            probe=fetch_exact_detail(link.url),
        )
        for link in bounded_links
    ]
    exact_vacancy = evaluate_exact_detail_attempts(contender, attempts)
    result["detail_discovery"] = {
        "external_search_discovery_enabled": False,
        "provider_requests": 0,
        "preliminary_detail_candidate_count": len(link_candidates),
        "detail_pages_checked": len(attempts),
        "detail_candidate_selection_version": DETAIL_CANDIDATE_SELECTION_VERSION,
        "detail_candidate_selection": [
            item.to_evidence() for item in selection_evidence
        ],
        "requested_seed_urls": list(requested_urls),
        "rejected_urls": list(rejected_urls),
        "discovery_evidence": discovery_evidence,
    }
    result["exact_vacancy"] = exact_vacancy
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve bounded Product V1 Silver contenders to exact employer-origin "
            "vacancy URLs with provider-free read-only evidence."
        )
    )
    parser.add_argument(
        "--silver-job-id",
        action="append",
        type=bounded_positive_int,
        default=[],
        help=(
            "Exact Silver target from the current bounded Product V1 contender pool. "
            "Repeat up to five times. Without explicit targets, inspect the bounded "
            "pool lazily until the current-vacancy target is reached or exhausted."
        ),
    )
    parser.add_argument(
        "--limit",
        type=bounded_positive_int,
        default=DEFAULT_CURRENT_TARGET,
        help=(
            "Maximum current vacancies to confirm before stopping. Product V1 "
            "remains at-most-five/no-fill."
        ),
    )
    parser.add_argument(
        "--contender-pool-limit",
        type=bounded_positive_int,
        default=DEFAULT_CONTENDER_LIMIT,
        help=(
            "Hard maximum contender/network-inspection envelope. Product V1 is "
            f"bounded to {DEFAULT_CONTENDER_LIMIT}."
        ),
    )
    parser.add_argument(
        "--max-origin-candidates",
        type=bounded_positive_int,
        default=DEFAULT_MAX_ORIGIN_CANDIDATES,
        help=(
            "Maximum deterministic employer-origin URL candidates probed for a "
            "contender that has no persisted employer-origin candidate row."
        ),
    )
    parser.add_argument(
        "--origin-timeout-seconds",
        type=bounded_positive_float,
        default=DEFAULT_ORIGIN_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--max-seed-pages",
        type=bounded_positive_int,
        default=DEFAULT_MAX_SEED_PAGES,
    )
    parser.add_argument(
        "--max-detail-pages",
        type=bounded_positive_int,
        default=DEFAULT_MAX_DETAIL_PAGES,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.limit > DEFAULT_CURRENT_TARGET:
        raise SystemExit(f"--limit must be <= {DEFAULT_CURRENT_TARGET}")
    if args.contender_pool_limit < args.limit:
        raise SystemExit("--contender-pool-limit must be >= --limit")
    if args.contender_pool_limit > DEFAULT_CONTENDER_LIMIT:
        raise SystemExit(
            f"--contender-pool-limit must be <= {DEFAULT_CONTENDER_LIMIT}"
        )
    if args.max_origin_candidates > MAX_ORIGIN_CANDIDATES:
        raise SystemExit(
            f"--max-origin-candidates must be <= {MAX_ORIGIN_CANDIDATES}"
        )

    read_only, inventory_rows, candidates = load_read_only_state()
    manifest = build_contender_manifest(
        inventory_rows,
        transaction_read_only=read_only,
        limit=args.contender_pool_limit,
    )
    try:
        selected = select_contenders(
            manifest,
            requested_silver_job_ids=args.silver_job_id,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    explicit_targets = bool(args.silver_job_id)
    refill_target = min(args.limit, len(selected)) if explicit_targets else args.limit
    refill_maximum = len(selected) if explicit_targets else args.contender_pool_limit
    if not selected:
        results: list[dict[str, object]] = []
        refill_evidence = {
            "strategy": "lazy_until_current_target_or_pool_exhausted",
            "target_current_vacancies": refill_target,
            "max_network_contenders": refill_maximum,
            "network_contenders_available": 0,
            "network_contenders_inspected": 0,
            "current_vacancies_confirmed": 0,
            "remaining_uninspected": 0,
            "stop_reason": "bounded_pool_exhausted",
        }
    else:
        results, refill_evidence = run_bounded_refill(
            selected,
            inspect=lambda row: run_bridge_for_contender(
                row,
                candidates=candidates,
                max_origin_candidates=args.max_origin_candidates,
                origin_timeout_seconds=args.origin_timeout_seconds,
                max_seed_pages=args.max_seed_pages,
                max_detail_pages=args.max_detail_pages,
            ),
            target_current_vacancies=refill_target,
            max_network_contenders=refill_maximum,
        )

    payload = {
        "status": "product_v1_origin_vacancy_bridge",
        "transaction_read_only": read_only,
        "purpose": "bounded_exact_origin_vacancy_evidence_not_ranking",
        "contender_pool": {
            "limit": args.contender_pool_limit,
            "selected_for_network_inspection": len(results),
            "target_current_vacancies": args.limit,
            "current_vacancies_confirmed": refill_evidence[
                "current_vacancies_confirmed"
            ],
            "remaining_uninspected": refill_evidence["remaining_uninspected"],
            "network_contenders_available": refill_evidence[
                "network_contenders_available"
            ],
            "max_network_contenders": args.contender_pool_limit,
            "stop_reason": refill_evidence["stop_reason"],
            "refill_strategy": refill_evidence["strategy"],
            "source_manifest_counts": manifest["counts"],
        },
        "results": results,
        "boundary": {
            "database_writes": False,
            "health_observation_writes": False,
            "candidate_or_origin_url_writes": False,
            "transient_origin_candidate_persistence": False,
            "bronze_or_silver_writes": False,
            "hard_filter_or_assessment_writes": False,
            "ranking_or_top5_writes": False,
            "application_writes": False,
            "source_or_scheduler_writes": False,
            "external_search_discovery": False,
            "provider_or_llm": False,
            "browser_automation": False,
            "bounded_ordinary_http_only": True,
            "max_network_contenders": args.contender_pool_limit,
            "target_current_vacancies": args.limit,
            "refill_strategy": "lazy_until_current_target_or_pool_exhausted",
            "max_generated_origin_candidates_per_missing_candidate": (
                args.max_origin_candidates
            ),
            "max_seed_pages_per_contender": args.max_seed_pages,
            "max_detail_pages_per_contender": args.max_detail_pages,
            "transient_health_classification_only": True,
        },
    }
    print(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
