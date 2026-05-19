"""Show a compact ingestion run summary.

This script is read-only. It summarizes recent ingestion_runs and compares them
against currently active search profiles.

Usage:

    python -m scripts.show_ingestion_run_summary
    python -m scripts.show_ingestion_run_summary --hours 6
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any

import psycopg

from src.config import get_database_config


@dataclass(frozen=True)
class ActiveProfile:
    profile_name: str
    source_name: str


@dataclass(frozen=True)
class ProfileRunSummary:
    profile_name: str
    source_name: str
    source_family: str
    run_count: int
    success_count: int
    failed_count: int
    total_loaded: int
    inserted_count: int
    duplicate_count: int
    first_started_at: Any
    last_finished_at: Any


def source_family(source_name: str) -> str:
    return source_name.split(":", 1)[0]


def load_active_profiles(connection: psycopg.Connection) -> list[ActiveProfile]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                profile_name,
                source_name
            FROM search_profiles
            WHERE is_active = TRUE
            ORDER BY source_name, profile_name;
            """
        )

        return [
            ActiveProfile(
                profile_name=row[0],
                source_name=row[1],
            )
            for row in cursor.fetchall()
        ]


def load_recent_run_summaries(
    connection: psycopg.Connection,
    hours: int,
) -> list[ProfileRunSummary]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                sp.profile_name,
                ir.source_name,
                CASE
                    WHEN POSITION(':' IN ir.source_name) > 0
                    THEN SPLIT_PART(ir.source_name, ':', 1)
                    ELSE ir.source_name
                END AS source_family,
                COUNT(*) AS run_count,
                COUNT(*) FILTER (WHERE ir.status = 'success') AS success_count,
                COUNT(*) FILTER (WHERE ir.status <> 'success') AS failed_count,
                COALESCE(SUM(ir.total_loaded), 0) AS total_loaded,
                COALESCE(SUM(ir.inserted_count), 0) AS inserted_count,
                COALESCE(SUM(ir.duplicate_count), 0) AS duplicate_count,
                MIN(ir.started_at) AS first_started_at,
                MAX(ir.finished_at) AS last_finished_at
            FROM ingestion_runs ir
            LEFT JOIN search_profiles sp
                ON sp.id = ir.search_profile_id
            WHERE ir.started_at >= NOW() - (%s * INTERVAL '1 hour')
            GROUP BY
                sp.profile_name,
                ir.source_name,
                source_family
            ORDER BY
                source_family,
                sp.profile_name;
            """,
            (hours,),
        )

        return [
            ProfileRunSummary(
                profile_name=row[0] or "<unknown>",
                source_name=row[1],
                source_family=row[2],
                run_count=row[3],
                success_count=row[4],
                failed_count=row[5],
                total_loaded=row[6],
                inserted_count=row[7],
                duplicate_count=row[8],
                first_started_at=row[9],
                last_finished_at=row[10],
            )
            for row in cursor.fetchall()
        ]


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [
        max(len(str(value)) for value in [header] + [row[index] for row in rows])
        for index, header in enumerate(headers)
    ]

    print(" | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))

    for row in rows:
        print(" | ".join(str(value).ljust(widths[index]) for index, value in enumerate(row)))


def print_summary(hours: int) -> None:
    config = get_database_config()

    with psycopg.connect(**config) as connection:
        active_profiles = load_active_profiles(connection)
        summaries = load_recent_run_summaries(
            connection=connection,
            hours=hours,
        )

    active_profile_names = {profile.profile_name for profile in active_profiles}
    observed_profile_names = {summary.profile_name for summary in summaries}
    observed_active_profile_names = active_profile_names & observed_profile_names
    missing_profile_names = sorted(active_profile_names - observed_profile_names)

    print()
    print(f"=== Ingestion Run Summary: last {hours} hour(s) ===")
    print()
    print(f"active_profiles:          {len(active_profiles)}")
    print(f"active_profiles_observed: {len(observed_active_profile_names)}")
    print(f"missing_active_profiles:  {len(missing_profile_names)}")

    if missing_profile_names:
        print()
        print("Missing active profiles:")
        for profile_name in missing_profile_names:
            print(f"- {profile_name}")

    print()
    print("=== Recent Runs by Profile ===")

    if not summaries:
        print()
        print("No ingestion runs found in the selected time window.")
        return

    rows = [
        [
            summary.profile_name,
            summary.source_name,
            summary.source_family,
            str(summary.run_count),
            str(summary.success_count),
            str(summary.failed_count),
            str(summary.total_loaded),
            str(summary.inserted_count),
            str(summary.duplicate_count),
            str(summary.last_finished_at),
        ]
        for summary in summaries
    ]

    print()
    print_table(
        headers=[
            "profile",
            "source",
            "family",
            "runs",
            "ok",
            "failed",
            "loaded",
            "inserted",
            "duplicates",
            "last_finished",
        ],
        rows=rows,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--hours",
        type=int,
        default=2,
        help="Time window in hours for recent ingestion runs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print_summary(hours=args.hours)


if __name__ == "__main__":
    main()
