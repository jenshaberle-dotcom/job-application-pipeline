"""Inspect Personio Bronze and Silver pipeline state.

Read-only helper for validating whether Personio raw_jobs are available
and whether they have already been transformed into silver_jobs.

Usage:

    python -m scripts.inspect_personio_pipeline_state
"""

from __future__ import annotations

import psycopg

from src.config import get_database_config


def print_table(headers: list[str], rows: list[list[object]]) -> None:
    if not rows:
        print("No rows.")
        return

    widths = [
        max(len(str(value)) for value in [header] + [row[index] for row in rows])
        for index, header in enumerate(headers)
    ]

    print(" | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))

    for row in rows:
        print(" | ".join(str(value).ljust(widths[index]) for index, value in enumerate(row)))


def main() -> None:
    config = get_database_config()

    with psycopg.connect(**config) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    sp.id,
                    sp.profile_name,
                    sp.source_name,
                    sp.search_location,
                    sp.search_radius_km,
                    sp.page_size,
                    sp.is_active,
                    STRING_AGG(st.search_term, ', ' ORDER BY st.id) AS active_search_terms
                FROM search_profiles sp
                LEFT JOIN search_terms st
                    ON st.search_profile_id = sp.id
                   AND st.is_active = TRUE
                WHERE sp.source_name LIKE 'personio:%'
                GROUP BY
                    sp.id,
                    sp.profile_name,
                    sp.source_name,
                    sp.search_location,
                    sp.search_radius_km,
                    sp.page_size,
                    sp.is_active
                ORDER BY sp.id;
                """
            )
            profiles = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    ir.id,
                    sp.profile_name,
                    ir.source_name,
                    ir.status,
                    ir.total_loaded,
                    ir.inserted_count,
                    ir.duplicate_count,
                    ir.started_at,
                    ir.finished_at
                FROM ingestion_runs ir
                LEFT JOIN search_profiles sp
                    ON sp.id = ir.search_profile_id
                WHERE ir.source_name LIKE 'personio:%'
                ORDER BY ir.id DESC
                LIMIT 10;
                """
            )
            runs = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    r.id AS raw_job_id,
                    r.source_name,
                    r.external_job_id,
                    r.source_url,
                    r.raw_data->'job'->>'title' AS bronze_title,
                    r.raw_data->'job'->>'company_name' AS bronze_company,
                    r.raw_data->'job'->>'location' AS bronze_location,
                    r.raw_data->'source_target'->>'target_key' AS target_key,
                    r.raw_data->'extraction'->>'connector_mode' AS connector_mode,
                    r.raw_data->'extraction'->>'detail_page_fetched' AS detail_page_fetched,
                    r.raw_data->'extraction'->>'pagination_used' AS pagination_used,
                    s.id AS silver_job_id,
                    s.title AS silver_title,
                    s.company_name AS silver_company,
                    s.city AS silver_city,
                    s.postal_code AS silver_postal_code,
                    s.country AS silver_country,
                    s.normalized_title,
                    s.normalized_company_name,
                    s.normalized_location,
                    s.canonical_key_candidate,
                    s.canonical_source_type,
                    s.canonical_status
                FROM raw_jobs r
                LEFT JOIN silver_jobs s
                    ON s.raw_job_id = r.id
                WHERE r.source_name LIKE 'personio:%'
                ORDER BY r.id DESC
                LIMIT 20;
                """
            )
            records = cursor.fetchall()

    print()
    print("=== Personio Search Profiles ===")
    print()
    print_table(
        headers=[
            "id",
            "profile",
            "source",
            "location",
            "radius",
            "page_size",
            "active",
            "terms",
        ],
        rows=[list(row) for row in profiles],
    )

    print()
    print("=== Recent Personio Ingestion Runs ===")
    print()
    print_table(
        headers=[
            "id",
            "profile",
            "source",
            "status",
            "loaded",
            "inserted",
            "duplicates",
            "started_at",
            "finished_at",
        ],
        rows=[list(row) for row in runs],
    )

    print()
    print("=== Personio Bronze / Silver Records ===")
    print()
    print_table(
        headers=[
            "raw_id",
            "source",
            "external_id",
            "bronze_title",
            "bronze_company",
            "bronze_location",
            "target",
            "silver_id",
            "silver_title",
            "silver_company",
            "silver_city",
            "silver_postal_code",
            "silver_country",
            "normalized_title",
            "normalized_company",
            "normalized_location",
            "canonical_key",
            "canonical_type",
            "canonical_status",
        ],
        rows=[
            [
                row[0],
                row[1],
                row[2],
                row[4],
                row[5],
                row[6],
                row[7],
                row[11],
                row[12],
                row[13],
                row[14],
                row[15],
                row[16],
                row[17],
                row[18],
                row[19],
                row[20],
                row[21],
                row[22],
            ]
            for row in records
        ],
    )

    bronze_count = len(records)
    silver_count = sum(1 for row in records if row[11] is not None)

    print()
    print("=== Readiness Signal ===")
    print()
    print(f"personio_bronze_records_seen: {bronze_count}")
    print(f"personio_silver_records_seen: {silver_count}")

    if bronze_count and not silver_count:
        print("next_step: add Personio support to the Silver transformer")
    elif bronze_count and silver_count:
        print("next_step: run source value exploration and document Personio findings")
    else:
        print("next_step: run Personio ingestion or apply the Personio search profile migration")


if __name__ == "__main__":
    main()
