from __future__ import annotations

import pytest

from scripts.quarantine_invalid_bronze import (
    ObservedRow,
    RequestedExpectation,
    build_quarantine_plan,
    full_reason,
    normalize_expectations,
)


SOURCE = "computacenter:discovery"
REASON = "run_2546_non_job_false_positive_after_connector_hardening_425"
URL_1 = "https://jobs.computacenter.com/content/Cookie-Policy/?locale=en_GB"
URL_2 = (
    "https://jobs.computacenter.com/search/?searchby=location&q=&locationsearch="
    "&geolocation=&optionsFacetsDD_country=&optionsFacetsDD_city="
)


def observed(
    raw_job_id: int,
    source_url: str,
    *,
    source_name: str = SOURCE,
    silver_job_id: int | None = None,
    processing_decision: str | None = None,
    processing_reason: str | None = None,
) -> ObservedRow:
    return ObservedRow(
        raw_job_id=raw_job_id,
        source_name=source_name,
        external_job_id=f"external-{raw_job_id}",
        source_url=source_url,
        silver_job_id=silver_job_id,
        processing_decision=processing_decision,
        processing_reason=processing_reason,
    )


def expectations() -> list[RequestedExpectation]:
    return [
        RequestedExpectation(raw_job_id=30947, expected_source_url=URL_1),
        RequestedExpectation(raw_job_id=30948, expected_source_url=URL_2),
    ]


def test_exact_invalid_bronze_rows_plan_skipped_decision_inserts() -> None:
    plan = build_quarantine_plan(
        expectations=expectations(),
        observed_rows=[observed(30947, URL_1), observed(30948, URL_2)],
        expected_source=SOURCE,
        reason=REASON,
    )

    assert [row.raw_job_id for row in plan] == [30947, 30948]
    assert [row.action for row in plan] == [
        "insert_skipped_decision",
        "insert_skipped_decision",
    ]


def test_normalize_expectations_requires_exact_id_url_set() -> None:
    with pytest.raises(ValueError, match="Expected URLs must match"):
        normalize_expectations(
            [30947, 30948],
            [RequestedExpectation(raw_job_id=30947, expected_source_url=URL_1)],
        )


def test_plan_fails_closed_when_requested_row_is_missing() -> None:
    with pytest.raises(ValueError, match=r"missing=\[30948\]"):
        build_quarantine_plan(
            expectations=expectations(),
            observed_rows=[observed(30947, URL_1)],
            expected_source=SOURCE,
            reason=REASON,
        )


def test_plan_fails_closed_on_source_mismatch() -> None:
    with pytest.raises(ValueError, match="source mismatch"):
        build_quarantine_plan(
            expectations=[RequestedExpectation(30947, URL_1)],
            observed_rows=[observed(30947, URL_1, source_name="other:source")],
            expected_source=SOURCE,
            reason=REASON,
        )


def test_plan_fails_closed_on_url_mismatch() -> None:
    with pytest.raises(ValueError, match="URL mismatch"):
        build_quarantine_plan(
            expectations=[RequestedExpectation(30947, URL_1)],
            observed_rows=[observed(30947, URL_2)],
            expected_source=SOURCE,
            reason=REASON,
        )


def test_plan_refuses_existing_silver_job() -> None:
    with pytest.raises(ValueError, match="already has silver_job_id=77"):
        build_quarantine_plan(
            expectations=[RequestedExpectation(30947, URL_1)],
            observed_rows=[observed(30947, URL_1, silver_job_id=77)],
            expected_source=SOURCE,
            reason=REASON,
        )


def test_plan_refuses_conflicting_processing_decision() -> None:
    with pytest.raises(ValueError, match="conflicting processing decision"):
        build_quarantine_plan(
            expectations=[RequestedExpectation(30947, URL_1)],
            observed_rows=[
                observed(
                    30947,
                    URL_1,
                    processing_decision="included",
                    processing_reason="relevant_for_silver",
                )
            ],
            expected_source=SOURCE,
            reason=REASON,
        )


def test_identical_existing_quarantine_is_idempotent_noop() -> None:
    plan = build_quarantine_plan(
        expectations=[RequestedExpectation(30947, URL_1)],
        observed_rows=[
            observed(
                30947,
                URL_1,
                processing_decision="skipped",
                processing_reason=full_reason(REASON),
            )
        ],
        expected_source=SOURCE,
        reason=REASON,
    )

    assert plan[0].action == "already_quarantined"
