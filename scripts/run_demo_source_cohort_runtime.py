"""Guarded runtime for the DEMO-001 live source cohort.

Default mode is read-only planning. The execution path is deliberately narrow:

existing active + recurring-enabled profile -> existing connector -> Bronze ->
normal recurring lifecycle reconciliation -> Silver for the exact new ingestion run.

It does not create or activate profiles, invent source authority, write Product V1
assessments/ranking, call an LLM/provider, or submit an application.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from typing import Sequence

from psycopg.rows import dict_row

from src.ingest_jobs import (
    configure_ingestion_execution_application_name,
    load_recurring_profile_names,
    profile_source_role,
    run_profile,
)
from src.ingestion.repository import JobIngestionRepository
from src.connectors.registry import SourceRole
from src.run_silver_jobs import main as run_silver_jobs


EXECUTION_TOKEN = "DEMO-001-INGEST-LIVE-COHORT"


@dataclass(frozen=True)
class CohortTarget:
    profile_name: str
    source_name: str


COHORT: tuple[CohortTarget, ...] = (
    CohortTarget(
        profile_name="personio_eraneos_data_engineer_remote",
        source_name="personio:eraneos",
    ),
    CohortTarget(
        profile_name="personio_1komma5grad_data_engineer_germany",
        source_name="personio:1komma5grad",
    ),
)


def _active_terms(repository: JobIngestionRepository, profile_name: str) -> list[str]:
    return [
        str(term.search_term)
        for _profile, term in repository.load_active_search_terms(profile_name)
    ]


def build_plan(repository: JobIngestionRepository) -> dict[str, object]:
    active_profiles = repository.load_active_search_profiles()
    active_by_name = {profile.profile_name: profile for profile in active_profiles}
    recurring_names = load_recurring_profile_names(repository, active_profiles)

    rows: list[dict[str, object]] = []
    blockers: list[str] = []

    for target in COHORT:
        profile = active_by_name.get(target.profile_name)
        if profile is None:
            rows.append(
                {
                    "profile_name": target.profile_name,
                    "source_name": target.source_name,
                    "active": False,
                    "recurring_ingestion_enabled": False,
                    "source_role": None,
                    "active_terms": [],
                    "ready": False,
                }
            )
            blockers.append(f"missing_active_profile:{target.profile_name}")
            continue

        source_matches = profile.source_name == target.source_name
        recurring = profile.profile_name in recurring_names
        try:
            role = profile_source_role(profile)
        except ValueError:
            role = None
        terms = _active_terms(repository, profile.profile_name)
        ready = (
            source_matches
            and recurring
            and role == SourceRole.EMPLOYER_ORIGIN
            and bool(terms)
        )

        if not source_matches:
            blockers.append(
                f"source_binding_mismatch:{target.profile_name}:{profile.source_name}"
            )
        if not recurring:
            blockers.append(f"recurring_disabled:{target.profile_name}")
        if role != SourceRole.EMPLOYER_ORIGIN:
            blockers.append(f"not_employer_origin:{target.profile_name}")
        if not terms:
            blockers.append(f"no_active_terms:{target.profile_name}")

        rows.append(
            {
                "profile_name": target.profile_name,
                "source_name": profile.source_name,
                "active": True,
                "recurring_ingestion_enabled": recurring,
                "source_role": role.value if role is not None else None,
                "active_terms": terms,
                "page_size": profile.page_size,
                "search_location": profile.search_location,
                "search_radius_km": profile.search_radius_km,
                "ready": ready,
            }
        )

    return {
        "schema": "job_application_pipeline.demo_source_cohort_runtime.v1",
        "mode": "plan",
        "cohort_ready": not blockers,
        "targets": rows,
        "blockers": blockers,
        "boundaries": {
            "database_reads": True,
            "database_writes": False,
            "network_requests": 0,
            "profile_activation": False,
            "source_activation": False,
            "product_assessment_writes": False,
            "ranking_or_top5_writes": False,
            "provider_or_llm_requests": 0,
            "application_or_submission_writes": False,
        },
    }


def _latest_ingestion_run_id(
    repository: JobIngestionRepository,
    *,
    profile_id: int,
    source_name: str,
    after_id: int,
) -> int:
    with repository.get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id
                FROM ingestion_runs
                WHERE search_profile_id = %s
                  AND source_name = %s
                  AND id > %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (profile_id, source_name, after_id),
            )
            row = cur.fetchone()
    if row is None:
        raise RuntimeError(
            f"no new ingestion run found for profile_id={profile_id} source={source_name}"
        )
    return int(row["id"])


def _max_ingestion_run_id(repository: JobIngestionRepository) -> int:
    with repository.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT coalesce(max(id), 0) FROM ingestion_runs")
            row = cur.fetchone()
    return int(row[0] if row else 0)


def execute(repository: JobIngestionRepository, plan: dict[str, object]) -> dict[str, object]:
    if plan.get("cohort_ready") is not True:
        raise RuntimeError("demo cohort is not ready; execution refused")

    active_profiles = repository.load_active_search_profiles()
    profiles_by_name = {profile.profile_name: profile for profile in active_profiles}
    execution_id = configure_ingestion_execution_application_name()
    outcomes: list[dict[str, object]] = []

    for target in COHORT:
        profile = profiles_by_name[target.profile_name]
        before_id = _max_ingestion_run_id(repository)

        # The plan already proved this exact profile is active, recurring-enabled,
        # employer-origin and source-bound. Enabling the existing recurring-health
        # path therefore preserves, rather than bypasses, lifecycle authority.
        run_profile(
            repository=repository,
            profile=profile,
            recurring_health_enabled=True,
        )
        ingestion_run_id = _latest_ingestion_run_id(
            repository,
            profile_id=profile.id,
            source_name=profile.source_name,
            after_id=before_id,
        )

        run_silver_jobs(
            [
                "--source",
                profile.source_name,
                "--ingestion-run-id",
                str(ingestion_run_id),
                "--limit",
                str(max(int(profile.page_size or 0), 100)),
            ]
        )
        outcomes.append(
            {
                "profile_name": profile.profile_name,
                "source_name": profile.source_name,
                "ingestion_run_id": ingestion_run_id,
                "bronze_and_observation_path_executed": True,
                "recurring_lifecycle_path_executed": True,
                "silver_exact_run_path_executed": True,
            }
        )

    return {
        "schema": "job_application_pipeline.demo_source_cohort_runtime.v1",
        "mode": "execute",
        "execution_id": execution_id,
        "targets": outcomes,
        "boundaries": {
            "existing_active_profiles_only": True,
            "existing_connectors_only": True,
            "bronze_writes": True,
            "job_observation_writes": True,
            "recurring_lifecycle_writes": True,
            "silver_writes": True,
            "profile_activation": False,
            "source_activation": False,
            "product_assessment_writes": False,
            "ranking_or_top5_writes": False,
            "provider_or_llm_requests": 0,
            "application_or_submission_writes": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute-token",
        help=(
            "Exact opt-in token for the bounded live cohort. Omit for read-only plan."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repository = JobIngestionRepository()
    plan = build_plan(repository)

    if not args.execute_token:
        print(json.dumps(plan, indent=2, default=str, sort_keys=True))
        print("DEMO_SOURCE_COHORT_PLAN=" + ("PASS" if plan["cohort_ready"] else "BLOCKED"))
        return 0 if plan["cohort_ready"] else 2

    if args.execute_token != EXECUTION_TOKEN:
        raise SystemExit("invalid --execute-token; live cohort execution refused")
    if plan["cohort_ready"] is not True:
        print(json.dumps(plan, indent=2, default=str, sort_keys=True))
        raise SystemExit("DEMO_SOURCE_COHORT_EXECUTION_BLOCKED")

    result = execute(repository, plan)
    print(json.dumps(result, indent=2, default=str, sort_keys=True))
    print("DEMO_SOURCE_COHORT_EXECUTION=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
