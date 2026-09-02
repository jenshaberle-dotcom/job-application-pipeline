from __future__ import annotations

from pathlib import Path

from scripts.run_product_v1_capability_evidence_audit import (
    AUDIT_SQL,
    DEFAULT_OUTPUT,
    build_report,
    select_audit_rows,
)


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "silver_job_id": 511,
        "company_name": "Eraneos Analytics Germany GmbH",
        "title": "Data Engineer (all genders)",
        "source_name": "personio:eraneos",
        "source_url": "https://eraneos.jobs.personio.de/job/2767212?language=de",
        "canonical_source_type": "employer_origin_ats_backed_career_site",
        "lifecycle_status": "active_confirmed",
        "product_readiness_status": "hard_filter_evidence_required",
        "employment_type": "unknown",
        "employment_evidence_status": "unknown",
        "required_languages": ["de"],
        "language_evidence_status": "observed",
        "weekly_hours_min": None,
        "weekly_hours_max": None,
        "weekly_hours_evidence_status": "unknown",
        "work_model": "unknown",
        "title_seniority": "unknown",
        "requirements_seniority": "unknown",
        "seniority_evidence_status": "unknown",
        "capability_fit_status": "unknown",
        "explanations": [
            {
                "factor": "required_languages",
                "status": "source_observed",
                "canonical_value": "de",
            }
        ],
        "uncertainties": [
            {"factor": "weekly_hours", "status": "unknown"},
            {"factor": "capability_fit", "status": "unknown"},
        ],
        "employment_status": "manual_review_required",
        "language_status": "passed",
        "weekly_hours_status": "manual_review_required",
        "seniority_status": "manual_review_required",
        "salary_signal": "unknown",
        "deterministic_hard_filter_status": "unknown",
        "hard_filter_status": "unknown",
        "hard_filter_reasons": {},
    }
    row.update(overrides)
    return row


def test_default_output_stays_inside_gitignored_demo_runtime() -> None:
    assert isinstance(DEFAULT_OUTPUT, Path)
    assert DEFAULT_OUTPUT.parts[-3:] == (
        ".runtime",
        "demo",
        "product_v1_capability_evidence_audit.json",
    )


def test_audit_sql_is_read_only_select_surface() -> None:
    tokens = AUDIT_SQL.upper().split()
    assert "SELECT" in tokens
    for keyword in ("INSERT", "UPDATE", "DELETE", "MERGE", "TRUNCATE"):
        assert keyword not in tokens


def test_selection_keeps_only_current_role_relevant_employer_origin_jobs() -> None:
    rows = [
        _row(silver_job_id=511),
        _row(
            silver_job_id=512,
            canonical_source_type="market_sensor",
        ),
        _row(
            silver_job_id=513,
            lifecycle_status="inactive_confirmed",
        ),
        _row(
            silver_job_id=514,
            title="Office Manager",
        ),
    ]

    selected = select_audit_rows(rows)

    assert [row["silver_job_id"] for row in selected] == [511]


def test_explicit_id_selection_is_still_fail_closed_on_authority() -> None:
    selected = select_audit_rows(
        [
            _row(silver_job_id=511),
            _row(silver_job_id=512, canonical_source_type="market_sensor"),
        ],
        requested_ids=[512],
    )

    assert selected == []


def test_report_preserves_evidence_and_summarizes_unknown_components() -> None:
    report = build_report([_row()])

    assert report["summary"] == {
        "job_count": 1,
        "readiness_counts": {"hard_filter_evidence_required": 1},
        "unknown_component_counts": {
            "employment": 1,
            "seniority_and_capability_fit": 1,
            "weekly_hours": 1,
        },
        "capability_fit_unknown_count": 1,
        "deterministic_hard_filter_unknown_count": 1,
    }
    assert report["jobs"][0]["source_observed_factors"] == ["required_languages"]
    assert report["jobs"][0]["unknown_components"] == [
        "employment",
        "weekly_hours",
        "seniority_and_capability_fit",
    ]
    assert report["boundaries"]["database_writes"] is False
    assert report["boundaries"]["provider_or_llm_requests"] == 0
    assert report["boundaries"]["capability_fit_decision_created"] is False
