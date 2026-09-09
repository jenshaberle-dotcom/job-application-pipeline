from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.connectors.employer_origin_acquisition import AcquiredJobPage
from src.connectors.generic_employer_origin import GenericOriginSource, _record
from src.ingestion.generic_origin_bronze_admission import (
    admit_generic_origin_bronze_record,
    evaluate_generic_origin_bronze_record,
)
from src.silver.relevance import (
    get_accessibility_matches,
    get_role_matches,
    get_skill_matches,
    get_silver_decision_reason,
    is_relevant_for_silver,
)
from src.silver.transformer import (
    get_supported_source_patterns,
    transform_raw_job_to_silver,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only production-gate funnel audit for query-proven generic "
            "Employer-Origin jobs. No gate semantics are changed or bypassed."
        )
    )
    parser.add_argument("--search-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _load_company_names(candidate_ids: list[int]) -> dict[int, str]:
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SHOW transaction_read_only")
            row = cur.fetchone()
            if str(row["transaction_read_only"]) != "on":
                raise RuntimeError("stage funnel audit must be read-only")
            cur.execute(
                """
                SELECT id, company_name
                FROM employer_origin_source_candidates
                WHERE id = ANY(%s)
                """,
                (candidate_ids,),
            )
            return {int(row["id"]): str(row["company_name"]) for row in cur.fetchall()}


def _source_supported_by_default_silver(source_name: str) -> bool:
    for pattern in get_supported_source_patterns():
        if "%" in pattern:
            prefix = pattern.split("%", 1)[0]
            if source_name.startswith(prefix):
                return True
        elif source_name == pattern:
            return True
    return False


def _term_for_job(source: dict, final_url: str) -> str:
    for outcome in source.get("outcomes") or []:
        if not isinstance(outcome, dict):
            continue
        for job in outcome.get("jobs") or []:
            if isinstance(job, dict) and str(job.get("final_url") or "") == final_url:
                return str(outcome.get("query") or "")
    return ""


def _raw_jobs(search_payload: dict) -> list[tuple[dict, object]]:
    proven_sources = [
        source
        for source in search_payload.get("sources") or []
        if isinstance(source, dict) and source.get("search_semantics_proven") is True
    ]
    candidate_ids = [int(source["candidate_id"]) for source in proven_sources]
    company_names = _load_company_names(candidate_ids)
    rows: list[tuple[dict, object]] = []
    synthetic_id = 1

    for source in proven_sources:
        candidate_id = int(source["candidate_id"])
        company_key = str(source["company_key"])
        source_name = str(source["source_name"])
        origin_url = str(source["origin_url"])
        generic_source = GenericOriginSource(
            candidate_id=candidate_id,
            company_key=company_key,
            company_name=company_names[candidate_id],
            candidate_url=origin_url,
        )
        for item in source.get("jobs") or []:
            if not isinstance(item, dict):
                continue
            job = AcquiredJobPage(**item)
            term = _term_for_job(source, job.final_url)
            record = _record(source_name, generic_source, job, term)
            rows.append(
                (
                    {
                        "id": synthetic_id,
                        "source_name": record.source_name,
                        "external_job_id": record.external_job_id,
                        "source_url": record.source_url,
                        "raw_data": record.raw_data,
                    },
                    record,
                )
            )
            synthetic_id += 1
    return rows


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    search_payload = json.loads(args.search_json.read_text(encoding="utf-8"))
    rows = _raw_jobs(search_payload)

    bronze_failures: Counter[str] = Counter()
    silver_reasons: Counter[str] = Counter()
    transformer_failures: Counter[str] = Counter()
    item_rows: list[dict] = []

    bronze_pass_count = 0
    silver_default_selected_count = 0
    silver_relevant_if_selected_count = 0
    silver_transformed_if_selected_count = 0
    actual_current_path_silver_count = 0

    for raw_job, record in rows:
        bronze_decision = evaluate_generic_origin_bronze_record(record)
        for failure in bronze_decision.failures:
            bronze_failures[failure] += 1
        admitted = admit_generic_origin_bronze_record(record)
        if admitted is not None:
            bronze_pass_count += 1
            raw_job = {**raw_job, "raw_data": admitted.raw_data}

        default_selected = (
            admitted is not None
            and _source_supported_by_default_silver(record.source_name)
        )
        if default_selected:
            silver_default_selected_count += 1

        role_matches = get_role_matches(raw_job) if admitted is not None else []
        skill_matches = get_skill_matches(raw_job) if admitted is not None else []
        accessibility_matches = (
            get_accessibility_matches(raw_job) if admitted is not None else []
        )
        silver_reason = (
            get_silver_decision_reason(raw_job)
            if admitted is not None
            else "not_bronze_admitted"
        )
        silver_relevant = admitted is not None and is_relevant_for_silver(raw_job)
        if admitted is not None:
            silver_reasons[silver_reason] += 1
        if silver_relevant:
            silver_relevant_if_selected_count += 1

        transformed = None
        transform_error = None
        if silver_relevant:
            try:
                transformed = transform_raw_job_to_silver(raw_job)
                silver_transformed_if_selected_count += 1
            except Exception as exc:
                transform_error = f"{type(exc).__name__}:{exc}"
                transformer_failures[transform_error] += 1

        if default_selected and silver_relevant and transformed is not None:
            actual_current_path_silver_count += 1

        item_rows.append(
            {
                "source_name": record.source_name,
                "source_url": record.source_url,
                "title": raw_job.get("raw_data", {}).get("job", {}).get("title"),
                "bronze": {
                    "passed": bronze_decision.passed,
                    "failures": list(bronze_decision.failures),
                },
                "silver_default_selector": {
                    "passed": default_selected,
                    "reason": (
                        "source_supported_by_default_silver"
                        if default_selected
                        else (
                            "not_bronze_admitted"
                            if admitted is None
                            else "source_family_not_in_default_silver_patterns"
                        )
                    ),
                },
                "silver_relevance_if_selected": {
                    "passed": silver_relevant,
                    "reason": silver_reason,
                    "role_matches": role_matches,
                    "skill_matches": skill_matches,
                    "accessibility_matches": accessibility_matches,
                },
                "silver_transform_if_selected": {
                    "passed": transformed is not None,
                    "error": transform_error,
                    "value": transformed,
                },
            }
        )

    payload = {
        "status": "generic_origin_stage_funnel_audit",
        "summary": {
            "search_query_proven_job_count": len(rows),
            "bronze_admitted_count": bronze_pass_count,
            "bronze_rejected_count": len(rows) - bronze_pass_count,
            "silver_default_selector_count": silver_default_selected_count,
            "silver_default_selector_rejected_count": (
                bronze_pass_count - silver_default_selected_count
            ),
            "silver_relevant_if_selected_count": silver_relevant_if_selected_count,
            "silver_transformed_if_selected_count": silver_transformed_if_selected_count,
            "current_normal_path_reaches_silver_count": actual_current_path_silver_count,
            "gold_product_readiness_reached_count": 0,
            "control_center_reached_count": 0,
        },
        "reason_counts": {
            "bronze_failures": dict(bronze_failures),
            "silver_relevance": dict(silver_reasons),
            "silver_transform_failures": dict(transformer_failures),
        },
        "current_default_silver_source_patterns": get_supported_source_patterns(),
        "items": item_rows,
        "boundary": {
            "database_writes": False,
            "network_requests": False,
            "production_gate_functions_reused": True,
            "special_company_allowlist": False,
            "gate_semantics_changed": False,
            "downstream_gold_and_cc_not_faked": True,
            "downstream_reason": (
                "Gold/Product/CC are not evaluated until records actually pass the "
                "normal persisted Bronze->Silver path."
            ),
        },
    }
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    summary = payload["summary"]
    print(f"FUNNEL_SEARCH_QUERY_PROVEN={summary['search_query_proven_job_count']}")
    print(f"FUNNEL_BRONZE_ADMITTED={summary['bronze_admitted_count']}")
    print(f"FUNNEL_BRONZE_REJECTED={summary['bronze_rejected_count']}")
    print(f"FUNNEL_SILVER_DEFAULT_SELECTED={summary['silver_default_selector_count']}")
    print(
        "FUNNEL_SILVER_RELEVANT_IF_SELECTED="
        f"{summary['silver_relevant_if_selected_count']}"
    )
    print(
        "FUNNEL_SILVER_TRANSFORMED_IF_SELECTED="
        f"{summary['silver_transformed_if_selected_count']}"
    )
    print(
        "FUNNEL_CURRENT_NORMAL_PATH_REACHES_SILVER="
        f"{summary['current_normal_path_reaches_silver_count']}"
    )
    for reason, count in sorted(bronze_failures.items()):
        print(f"FUNNEL_BRONZE_DROP={reason}|count={count}")
    for reason, count in sorted(silver_reasons.items()):
        print(f"FUNNEL_SILVER_REASON={reason}|count={count}")
    print("FUNNEL_DATABASE_WRITES=0")
    print("FUNNEL=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
