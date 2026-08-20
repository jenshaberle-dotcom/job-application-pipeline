from __future__ import annotations

from typing import Any


def validate_stage_counts(
    *,
    connector_record_count: int,
    post_filter_count: int,
) -> None:
    if connector_record_count < 0:
        raise ValueError("connector_record_count must be nonnegative")
    if post_filter_count < 0:
        raise ValueError("post_filter_count must be nonnegative")
    if post_filter_count > connector_record_count:
        raise ValueError("post_filter_count cannot exceed connector_record_count")


def record_ingestion_stage_counts(
    repository: Any,
    *,
    ingestion_run_id: int,
    connector_record_count: int,
    post_filter_count: int,
) -> None:
    """Persist deterministic stage counts without widening test doubles.

    Production repositories expose ``get_connection``. Lightweight unit-test
    repositories may instead provide ``record_ingestion_stage_counts`` to capture
    the contract, or omit both interfaces when the test does not exercise telemetry.
    """

    validate_stage_counts(
        connector_record_count=connector_record_count,
        post_filter_count=post_filter_count,
    )

    explicit = getattr(repository, "record_ingestion_stage_counts", None)
    if callable(explicit):
        explicit(
            ingestion_run_id=ingestion_run_id,
            connector_record_count=connector_record_count,
            post_filter_count=post_filter_count,
        )
        return

    get_connection = getattr(repository, "get_connection", None)
    if not callable(get_connection):
        return

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingestion_runs
                SET
                    connector_record_count = %s,
                    post_filter_count = %s
                WHERE id = %s;
                """,
                (
                    connector_record_count,
                    post_filter_count,
                    ingestion_run_id,
                ),
            )
