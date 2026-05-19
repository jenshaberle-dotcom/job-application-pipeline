"""Explore Silver-layer duplicate candidates, company overlap and source value.

This script is intentionally read-only.

Run from the project root with:

    python -m scripts.explore_silver_source_value
"""

from collections.abc import Sequence
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config


SOURCE_VALUE_BASELINE_SQL = """
WITH key_groups AS (
    SELECT
        canonical_key_candidate,
        COUNT(*) AS row_count,
        COUNT(DISTINCT source_name) AS source_count
    FROM silver_jobs
    WHERE canonical_key_candidate IS NOT NULL
    GROUP BY canonical_key_candidate
),
source_base AS (
    SELECT
        source_name,
        COUNT(*) AS silver_jobs,
        COUNT(DISTINCT normalized_company_name)
            FILTER (WHERE normalized_company_name IS NOT NULL) AS distinct_companies,
        COUNT(DISTINCT canonical_key_candidate)
            FILTER (WHERE canonical_key_candidate IS NOT NULL) AS distinct_candidate_keys,
        COUNT(*) FILTER (WHERE title IS NOT NULL) AS with_title,
        COUNT(*) FILTER (WHERE company_name IS NOT NULL) AS with_company,
        COUNT(*) FILTER (WHERE normalized_location IS NOT NULL) AS with_normalized_location,
        COUNT(*) FILTER (WHERE publication_date IS NOT NULL) AS with_publication_date
    FROM silver_jobs
    GROUP BY source_name
),
source_overlap AS (
    SELECT
        s.source_name,
        COUNT(*) FILTER (WHERE kg.row_count > 1) AS rows_in_duplicate_candidate_groups,
        COUNT(*) FILTER (WHERE kg.source_count > 1) AS rows_in_cross_source_candidate_groups,
        COUNT(DISTINCT s.canonical_key_candidate)
            FILTER (WHERE kg.source_count > 1) AS cross_source_candidate_keys
    FROM silver_jobs s
    LEFT JOIN key_groups kg
        ON kg.canonical_key_candidate = s.canonical_key_candidate
    GROUP BY s.source_name
)
SELECT
    b.source_name,
    b.silver_jobs,
    b.distinct_companies,
    b.distinct_candidate_keys,
    ROUND(100.0 * b.distinct_companies / NULLIF(b.silver_jobs, 0), 1)
        AS unique_company_rate_pct,
    ROUND(100.0 * b.distinct_candidate_keys / NULLIF(b.silver_jobs, 0), 1)
        AS unique_candidate_key_rate_pct,
    ROUND(100.0 * b.with_title / NULLIF(b.silver_jobs, 0), 1)
        AS title_completeness_pct,
    ROUND(100.0 * b.with_company / NULLIF(b.silver_jobs, 0), 1)
        AS company_completeness_pct,
    ROUND(100.0 * b.with_normalized_location / NULLIF(b.silver_jobs, 0), 1)
        AS location_completeness_pct,
    ROUND(100.0 * b.with_publication_date / NULLIF(b.silver_jobs, 0), 1)
        AS publication_date_completeness_pct,
    COALESCE(o.rows_in_duplicate_candidate_groups, 0)
        AS rows_in_duplicate_candidate_groups,
    COALESCE(o.rows_in_cross_source_candidate_groups, 0)
        AS rows_in_cross_source_candidate_groups,
    COALESCE(o.cross_source_candidate_keys, 0)
        AS cross_source_candidate_keys
FROM source_base b
LEFT JOIN source_overlap o
    ON o.source_name = b.source_name
ORDER BY b.silver_jobs DESC, b.source_name;
"""


DUPLICATE_CANDIDATE_GROUPS_SQL = """
SELECT
    canonical_key_candidate,
    COUNT(*) AS row_count,
    COUNT(DISTINCT source_name) AS source_count,
    ARRAY_AGG(DISTINCT source_name ORDER BY source_name) AS sources
FROM silver_jobs
WHERE canonical_key_candidate IS NOT NULL
GROUP BY canonical_key_candidate
HAVING COUNT(*) > 1
ORDER BY source_count DESC, row_count DESC, canonical_key_candidate
LIMIT 50;
"""


COMPANY_SOURCE_OVERLAP_SQL = """
SELECT
    normalized_company_name,
    COUNT(*) AS row_count,
    COUNT(DISTINCT source_name) AS source_count,
    ARRAY_AGG(DISTINCT source_name ORDER BY source_name) AS sources,
    COUNT(DISTINCT normalized_title)
        FILTER (WHERE normalized_title IS NOT NULL) AS distinct_titles
FROM silver_jobs
WHERE normalized_company_name IS NOT NULL
GROUP BY normalized_company_name
HAVING COUNT(DISTINCT source_name) > 1
ORDER BY source_count DESC, row_count DESC, normalized_company_name
LIMIT 50;
"""


TOP_COMPANIES_SQL = """
SELECT
    normalized_company_name,
    COUNT(*) AS row_count,
    COUNT(DISTINCT source_name) AS source_count,
    ARRAY_AGG(DISTINCT source_name ORDER BY source_name) AS sources,
    COUNT(DISTINCT normalized_title)
        FILTER (WHERE normalized_title IS NOT NULL) AS distinct_titles
FROM silver_jobs
WHERE normalized_company_name IS NOT NULL
GROUP BY normalized_company_name
ORDER BY row_count DESC, source_count DESC, normalized_company_name
LIMIT 20;
"""


def format_value(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, list):
        return ", ".join(str(item) for item in value)

    return str(value)


def print_rows(title: str, rows: Sequence[dict[str, Any]]) -> None:
    print()
    print(f"=== {title} ===")

    if not rows:
        print("No rows.")
        return

    columns = list(rows[0].keys())
    widths = {
        column: max(
            len(column),
            *(len(format_value(row[column])) for row in rows),
        )
        for column in columns
    }

    header = " | ".join(column.ljust(widths[column]) for column in columns)
    separator = "-+-".join("-" * widths[column] for column in columns)

    print(header)
    print(separator)

    for row in rows:
        print(
            " | ".join(
                format_value(row[column]).ljust(widths[column])
                for column in columns
            )
        )


def fetch_rows(cursor: psycopg.Cursor, sql: str) -> list[dict[str, Any]]:
    cursor.execute(sql)
    return list(cursor.fetchall())


def main() -> None:
    config = get_database_config()

    with psycopg.connect(**config, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            source_value_rows = fetch_rows(cur, SOURCE_VALUE_BASELINE_SQL)
            duplicate_rows = fetch_rows(cur, DUPLICATE_CANDIDATE_GROUPS_SQL)
            company_overlap_rows = fetch_rows(cur, COMPANY_SOURCE_OVERLAP_SQL)
            top_company_rows = fetch_rows(cur, TOP_COMPANIES_SQL)

    print_rows("Silver Source Value Baseline", source_value_rows)
    print_rows("Duplicate Candidate Groups", duplicate_rows)
    print_rows("Company Source Overlap", company_overlap_rows)
    print_rows("Top Companies", top_company_rows)


if __name__ == "__main__":
    main()
