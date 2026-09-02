from __future__ import annotations

from scripts.run_demo_recall_first_product_frontier import (
    application_status_for_job,
    select_recall_first_rows,
    selected_top_job,
)


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "silver_job_id": 1,
        "source_name": "personio:1komma5grad",
        "lifecycle_status": "active_confirmed",
        "title": "Platform Engineer",
    }
    row.update(overrides)
    return row


def test_recall_first_selection_keeps_adjacent_titles() -> None:
    rows = [
        _row(silver_job_id=1, title="Platform Engineer"),
        _row(silver_job_id=2, title="Office Manager"),
        _row(
            silver_job_id=3,
            source_name="market:example",
            title="Machine Learning Engineer",
        ),
        _row(
            silver_job_id=4,
            lifecycle_status="inactive_confirmed",
            title="Data Engineer",
        ),
    ]

    selected = select_recall_first_rows(
        rows,
        authorized_sources={"personio:1komma5grad"},
    )

    assert [row["silver_job_id"] for row in selected] == [1, 2]


def test_top_job_uses_rank_before_score() -> None:
    payload = {
        "top_jobs": [
            {
                "silver_job_id": 2,
                "product_rank": 2,
                "overall_quality_score": 95,
            },
            {
                "silver_job_id": 1,
                "product_rank": 1,
                "overall_quality_score": 70.4,
            },
        ]
    }

    assert selected_top_job(payload)["silver_job_id"] == 1


def test_application_status_is_exact_job_bound() -> None:
    payload = {
        "application_readiness": [
            {
                "silver_job_id": 1,
                "application_readiness_status": "blocked_job_not_eligible",
            },
            {
                "silver_job_id": 434,
                "application_readiness_status": "ready_for_generation",
            },
        ]
    }

    assert application_status_for_job(payload, 434) == "ready_for_generation"
    assert application_status_for_job(payload, 999) is None
