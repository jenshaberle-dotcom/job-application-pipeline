"""Read-only Product V1 capability-evidence audit for current employer-origin jobs.

The runner inspects persisted Product V1 assessment and hard-filter truth for the
current demo cohort. It never mutates database state, calls a provider, performs a
network request, or creates capability-fit / ranking / application authority.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.search_intelligence.product_v1_contenders import classify_role_title


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".runtime" / "demo" / "product_v1_capability_evidence_audit.json"
DEFAULT_COHORT_SOURCES = ("personio:eraneos", "personio:1komma5grad")
EMPLOYER_ORIGIN_SOURCE_TYPES = frozenset(
    {
        "employer_origin_career_site",
        "employer_origin_ats_backed_career_site",
    }
)

AUDIT_SQL = """
    SELECT
        readiness.silver_job_id,
        readiness.company_name,
        readiness.title,
        readiness.source_name,
        readiness.source_url,
        readiness.canonical_source_type,
        readiness.lifecycle_status,
        readiness.product_readiness_status,
        assessment.employment_type,
        assessment.employment_evidence_status,
        assessment.required_languages,
        assessment.language_evidence_status,
        assessment.weekly_hours_min,
        assessment.weekly_hours_max,
        assessment.weekly_hours_evidence_status,
        assessment.work_model,
        assessment.title_seniority,
        assessment.requirements_seniority,
        assessment.seniority_evidence_status,
        assessment.capability_fit_status,
        assessment.explanations,
        assessment.uncertainties,
        hard_filter.employment_status,
        hard_filter.language_status,
        hard_filter.weekly_hours_status,
        hard_filter.seniority_status,
        hard_filter.salary_signal,
        hard_filter.deterministic_hard_filter_status,
        hard_filter.hard_filter_status,
        hard_filter.hard_filter_reasons
    FROM gold_product_v1_job_readiness readiness
    JOIN job_product_assessments assessment
      ON assessment.silver_job_id = readiness.silver_job_id
    JOIN gold_product_v1_hard_filter_evaluation hard_filter
      ON hard_filter.silver_job_id = readiness.silver_job_id
    WHERE (
        (%s::bigint[] IS NOT NULL AND readiness.silver_job_id = ANY(%s))
        OR
        (%s::bigint[] IS NULL AND readiness.source_name = ANY(%s))
    )
    ORDER BY readiness.silver_job_id
"""


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _role_relevant(title: object) -> bool:
    return classify_role_title(str(title or "")) is not None


def select_audit_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    requested_ids: Sequence[int] = (),
) -> list[dict[str, object]]:
    requested = set(int(value) for value in requested_ids)
    selected: list[dict[str, object]] = []
    for row in rows:
        silver_job_id = int(row.get("silver_job_id") or 0)
        if requested and silver_job_id not in requested:
            continue
        if str(row.get("canonical_source_type") or "") not in EMPLOYER_ORIGIN_SOURCE_TYPES:
            continue
        if str(row.get("lifecycle_status") or "") != "active_confirmed":
            continue
        if not _role_relevant(row.get("title")):
            continue
        selected.append(dict(row))
    return selected


def _unknown_components(row: Mapping[str, object]) -> list[str]:
    checks = (
        ("employment", row.get("employment_status")),
        ("languages", row.get("language_status")),
        ("weekly_hours", row.get("weekly_hours_status")),
        ("seniority_and_capability_fit", row.get("seniority_status")),
    )
    return [name for name, status in checks if status == "manual_review_required"]


def _source_observed_factors(row: Mapping[str, object]) -> list[str]:
    explanations = row.get("explanations")
    if not isinstance(explanations, list):
        return []
    return sorted(
        {
            str(item.get("factor"))
            for item in explanations
            if isinstance(item, Mapping)
            and item.get("status") == "source_observed"
            and item.get("factor")
        }
    )


def build_report(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    jobs: list[dict[str, object]] = []
    unknown_counter: Counter[str] = Counter()
    readiness_counter: Counter[str] = Counter()

    for row in rows:
        unknown_components = _unknown_components(row)
        unknown_counter.update(unknown_components)
        readiness_counter[str(row.get("product_readiness_status") or "unknown")] += 1
        jobs.append(
            {
                **{str(key): _json_safe(value) for key, value in row.items()},
                "unknown_components": unknown_components,
                "source_observed_factors": _source_observed_factors(row),
            }
        )

    return {
        "schema": "job_application_pipeline.product_v1_capability_evidence_audit.v1",
        "mode": "read_only",
        "summary": {
            "job_count": len(jobs),
            "readiness_counts": dict(sorted(readiness_counter.items())),
            "unknown_component_counts": dict(sorted(unknown_counter.items())),
            "capability_fit_unknown_count": sum(
                1 for row in jobs if row.get("capability_fit_status") == "unknown"
            ),
            "deterministic_hard_filter_unknown_count": sum(
                1
                for row in jobs
                if row.get("deterministic_hard_filter_status") == "unknown"
            ),
        },
        "jobs": jobs,
        "boundaries": {
            "database_reads": True,
            "database_writes": False,
            "network_requests": 0,
            "provider_or_llm_requests": 0,
            "candidate_fact_writes": False,
            "capability_fit_decision_created": False,
            "hard_filter_review_created": False,
            "ranking_scores_created": False,
            "top5_mutation": False,
            "application_or_submission_actions": False,
        },
    }


def _read_rows(
    *,
    source_names: Sequence[str],
    silver_job_ids: Sequence[int],
) -> list[dict[str, object]]:
    job_ids_param = list(silver_job_ids) if silver_job_ids else None
    conn = psycopg.connect(**get_database_config(), row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute("BEGIN READ ONLY")
            cur.execute(
                AUDIT_SQL,
                (
                    job_ids_param,
                    job_ids_param,
                    job_ids_param,
                    list(source_names),
                ),
            )
            rows = [dict(row) for row in cur.fetchall()]
        conn.rollback()
        return rows
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-name", action="append", default=[])
    parser.add_argument("--silver-job-id", action="append", type=int, default=[])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source_names = tuple(
        dict.fromkeys(
            str(value).strip()
            for value in args.source_name
            if str(value).strip()
        )
    ) or DEFAULT_COHORT_SOURCES
    silver_job_ids = tuple(dict.fromkeys(int(value) for value in args.silver_job_id))
    if any(value <= 0 for value in silver_job_ids):
        raise SystemExit("--silver-job-id values must be positive")

    rows = select_audit_rows(
        _read_rows(source_names=source_names, silver_job_ids=silver_job_ids),
        requested_ids=silver_job_ids,
    )
    report = build_report(rows)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = report["summary"]
    print("============================================")
    print("PRODUCT V1 CAPABILITY EVIDENCE AUDIT")
    print("============================================")
    print(f"JOBS={summary['job_count']}")
    print(
        "READINESS_COUNTS="
        + json.dumps(summary["readiness_counts"], sort_keys=True)
    )
    print(
        "UNKNOWN_COMPONENT_COUNTS="
        + json.dumps(summary["unknown_component_counts"], sort_keys=True)
    )
    for row in report["jobs"]:
        print(
            "JOB="
            f"{row['silver_job_id']}|{row['source_name']}|"
            f"{row['product_readiness_status']}|{row['title']}"
        )
        print(
            "EVIDENCE="
            f"observed={row['source_observed_factors']}|"
            f"unknown={row['unknown_components']}|"
            f"capability_fit={row['capability_fit_status']}|"
            f"deterministic={row['deterministic_hard_filter_status']}|"
            f"effective={row['hard_filter_status']}"
        )
    print("DATABASE_WRITES=0")
    print("NETWORK_REQUESTS=0")
    print("PROVIDER_REQUESTS=0")
    print(f"artifact={args.output.resolve()}")
    print("PRODUCT_V1_CAPABILITY_EVIDENCE_AUDIT=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
