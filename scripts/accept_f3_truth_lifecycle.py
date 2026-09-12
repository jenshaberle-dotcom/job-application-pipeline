"""Read-only F3 Product acceptance for canonical vacancy identity and lifecycle truth."""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from urllib.parse import urlsplit

import psycopg
from psycopg.rows import dict_row

from scripts.product_v1_control_center_base import load_product_v1_payload
from scripts.product_v1_job_presentation_runtime import enrich_product_payload_for_operator
from src.config import get_database_config


SENSOR_SOURCE_FAMILIES = frozenset(
    {
        "bundesagentur_fuer_arbeit",
        "stepstone",
        "gute_jobs",
        "gute-jobs",
        "indeed",
        "linkedin",
    }
)
LOCALE_SEGMENTS = frozenset({"de", "en", "fr", "es", "it", "nl", "pl"})
EXPECTED_FI_STRONG_IDS = frozenset({"e362/b", "420/b"})


def _locale_neutral_path(value: object) -> str:
    parsed = urlsplit(str(value or "").strip())
    parts = [part for part in parsed.path.split("/") if part]
    if parts and parts[0].casefold() in LOCALE_SEGMENTS:
        parts = parts[1:]
    return "/" + "/".join(parts)


def _load_persisted_evidence() -> tuple[list[dict[str, object]], dict[str, int], int, int]:
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    """
                    SELECT
                        identity.silver_job_id,
                        identity.source_name,
                        identity.source_url,
                        identity.lifecycle_status,
                        identity.strong_identifier,
                        identity.identifier_evidence_kind,
                        identity.identity_kind,
                        identity.canonical_vacancy_key,
                        identity.identity_group_size,
                        identity.is_representative,
                        silver.title,
                        silver.company_name
                    FROM gold_vacancy_identity identity
                    JOIN silver_jobs silver ON silver.id = identity.silver_job_id
                    WHERE lower(coalesce(silver.company_name, '')) LIKE '%finanz informatik%'
                       OR lower(identity.source_name) LIKE '%finanz_informatik%'
                    ORDER BY identity.canonical_vacancy_key, identity.silver_job_id
                    """
                )
                fi_rows = [dict(row) for row in cur.fetchall()]

                cur.execute(
                    """
                    SELECT count(*)::integer AS count
                    FROM gold_current_job_opportunities current_job
                    JOIN gold_job_lifecycle_health lifecycle
                      ON lifecycle.silver_job_id = current_job.id
                    WHERE lifecycle.lifecycle_status <> 'active_confirmed'
                    """
                )
                noncurrent_in_current = int(cur.fetchone()["count"])

                cur.execute(
                    """
                    SELECT
                        count(*) FILTER (
                            WHERE lifecycle_status = 'stale_needs_refresh'
                        )::integer AS stale_count,
                        count(*) FILTER (
                            WHERE lifecycle_status = 'inactive_confirmed'
                        )::integer AS inactive_count,
                        count(*) FILTER (
                            WHERE lifecycle_status = 'unverifiable'
                        )::integer AS unverifiable_count,
                        count(DISTINCT source_name)::integer AS source_families
                    FROM gold_job_lifecycle_health
                    """
                )
                lifecycle_counts = {
                    key: int(value or 0) for key, value in dict(cur.fetchone()).items()
                }

                cur.execute(
                    """
                    SELECT count(*)::integer AS multi_location_jobs
                    FROM (
                        SELECT silver_job_id
                        FROM silver_job_locations
                        GROUP BY silver_job_id
                        HAVING count(*) > 1
                    ) locations
                    """
                )
                multi_location_jobs = int(cur.fetchone()["multi_location_jobs"])
        conn.rollback()
    return fi_rows, lifecycle_counts, multi_location_jobs, noncurrent_in_current


def _assert_identity_truth(fi_rows: list[dict[str, object]]) -> tuple[int, int, int]:
    if not fi_rows:
        raise SystemExit("F3_FI_IDENTITY_ROWS_MISSING")

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in fi_rows:
        grouped[str(row["canonical_vacancy_key"])].append(row)

    duplicate_groups = [rows for rows in grouped.values() if len(rows) > 1]
    strong_groups = [
        rows
        for rows in duplicate_groups
        if rows[0]["identity_kind"] == "strong_origin_identifier"
    ]
    bounded_groups = [
        rows
        for rows in duplicate_groups
        if rows[0]["identity_kind"] == "bounded_same_run_detail_equivalence"
    ]
    if len(strong_groups) < 2:
        raise SystemExit(f"F3_FI_STRONG_GROUPS_TOO_LOW:{len(strong_groups)}")
    if len(bounded_groups) < 3:
        raise SystemExit(f"F3_FI_BOUNDED_GROUPS_TOO_LOW:{len(bounded_groups)}")

    for rows in duplicate_groups:
        representatives = sum(bool(row["is_representative"]) for row in rows)
        if representatives != 1:
            raise SystemExit(
                "F3_IDENTITY_REPRESENTATIVE_COUNT:"
                f"{rows[0]['canonical_vacancy_key']}:{representatives}"
            )
        if any(int(row["identity_group_size"]) != len(rows) for row in rows):
            raise SystemExit("F3_IDENTITY_GROUP_SIZE_DRIFT")

    strong_ids = {
        str(row.get("strong_identifier") or "").casefold()
        for rows in strong_groups
        for row in rows
    }
    if not EXPECTED_FI_STRONG_IDS.issubset(strong_ids):
        raise SystemExit(f"F3_EXPECTED_STRONG_IDS_MISSING:{sorted(strong_ids)}")

    for rows in duplicate_groups:
        print(
            "F3_CANONICAL_GROUP="
            + json.dumps(rows, default=str, ensure_ascii=False, sort_keys=True)
        )
    return len(duplicate_groups), len(strong_groups), len(bounded_groups)


def _assert_lifecycle_truth(
    lifecycle_counts: dict[str, int],
    *,
    multi_location_jobs: int,
    noncurrent_in_current: int,
) -> None:
    if noncurrent_in_current != 0:
        raise SystemExit(f"F3_CURRENT_VIEW_LIFECYCLE_LEAK:{noncurrent_in_current}")
    if lifecycle_counts["stale_count"] <= 0:
        raise SystemExit("F3_STALE_AUDIT_COHORT_MISSING")
    if lifecycle_counts["inactive_count"] <= 0:
        raise SystemExit("F3_INACTIVE_AUDIT_COHORT_MISSING")
    if lifecycle_counts["source_families"] < 2:
        raise SystemExit("F3_MULTI_FAMILY_LIFECYCLE_COHORT_MISSING")
    if multi_location_jobs <= 0:
        raise SystemExit("F3_MULTI_LOCATION_AUDIT_COHORT_MISSING")


def _assert_product_truth() -> tuple[int, int]:
    payload = enrich_product_payload_for_operator(load_product_v1_payload())
    jobs = [row for row in payload.get("job_readiness", []) if isinstance(row, dict)]

    sensor_rows = [
        row
        for row in jobs
        if str(row.get("source_name") or "").split(":", 1)[0].casefold()
        in SENSOR_SOURCE_FAMILIES
    ]
    if sensor_rows:
        raise SystemExit(f"F3_SENSOR_REVIEW_LEAK:{len(sensor_rows)}")

    noncurrent_rows = [
        row
        for row in jobs
        if str(row.get("lifecycle_status") or "").replace("_", " ").casefold()
        != "active confirmed"
    ]
    if noncurrent_rows:
        raise SystemExit(f"F3_NONCURRENT_REVIEW_LEAK:{len(noncurrent_rows)}")

    presentation_duplicates = [
        row
        for row in payload.get("duplicate_origin_jobs", [])
        if isinstance(row, dict)
    ]
    if presentation_duplicates:
        raise SystemExit(
            f"F3_PRESENTATION_LAYER_STILL_REPAIRS_DUPLICATES:{len(presentation_duplicates)}"
        )

    visible_fi = [
        row
        for row in jobs
        if "finanz informatik" in str(row.get("company_name") or "").casefold()
    ]
    neutral_counts = Counter(
        (str(row.get("source_name") or ""), _locale_neutral_path(row.get("source_url")))
        for row in visible_fi
        if row.get("source_url")
    )
    residual_aliases = [key for key, count in neutral_counts.items() if count > 1]
    if residual_aliases:
        raise SystemExit(f"F3_FI_VISIBLE_ALIAS_RESIDUAL:{residual_aliases}")
    return len(jobs), len(visible_fi)


def main() -> int:
    fi_rows, lifecycle_counts, multi_location_jobs, noncurrent_in_current = (
        _load_persisted_evidence()
    )
    duplicate_groups, strong_groups, bounded_groups = _assert_identity_truth(fi_rows)
    _assert_lifecycle_truth(
        lifecycle_counts,
        multi_location_jobs=multi_location_jobs,
        noncurrent_in_current=noncurrent_in_current,
    )
    product_jobs, visible_fi = _assert_product_truth()

    print(f"F3_FI_IDENTITY_MEMBERS={len(fi_rows)}")
    print(f"F3_FI_DUPLICATE_GROUPS={duplicate_groups}")
    print(f"F3_FI_STRONG_GROUPS={strong_groups}")
    print(f"F3_FI_BOUNDED_GROUPS={bounded_groups}")
    print(f"F3_LIFECYCLE_STALE_AUDIT={lifecycle_counts['stale_count']}")
    print(f"F3_LIFECYCLE_INACTIVE_AUDIT={lifecycle_counts['inactive_count']}")
    print(f"F3_LIFECYCLE_UNVERIFIABLE_AUDIT={lifecycle_counts['unverifiable_count']}")
    print(f"F3_LIFECYCLE_SOURCE_FAMILIES={lifecycle_counts['source_families']}")
    print(f"F3_MULTI_LOCATION_JOBS={multi_location_jobs}")
    print(f"F3_PRODUCT_REVIEW_JOBS={product_jobs}")
    print(f"F3_PRODUCT_VISIBLE_FI={visible_fi}")
    print("F3_PRESENTATION_DUPLICATE_REPAIR=0")
    print("F3_TRUTH_LIFECYCLE_ACCEPTANCE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
