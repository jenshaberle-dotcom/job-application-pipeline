from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.product_v1_f5_application_actions import (
    ACTION_NAME,
    ApplicationActionError,
    SubmissionRecordRequest,
    application_key_for_job,
    build_job_identity_snapshot,
    canonical_sha256,
    parse_submission_record_request,
    submission_idempotency_key,
)


MODULE = Path("scripts/product_v1_f5_application_actions.py")


def test_parse_requires_explicit_record_action_and_timezone() -> None:
    request = parse_submission_record_request(
        {
            "action": ACTION_NAME,
            "silver_job_id": 42,
            "submitted_at": "2026-09-16T17:00:00+02:00",
            "submission_channel": "employer_portal",
            "authority_reference": "operator:portal-confirmation",
        }
    )

    assert request.silver_job_id == 42
    assert request.submitted_at == datetime(2026, 9, 16, 15, 0, tzinfo=timezone.utc)
    assert request.confirmed_by == "local_operator"

    with pytest.raises(ApplicationActionError, match="unsupported_application_action"):
        parse_submission_record_request(
            {
                "action": "submit_application",
                "silver_job_id": 42,
                "submitted_at": "2026-09-16T17:00:00+02:00",
                "submission_channel": "employer_portal",
                "authority_reference": "x",
            }
        )

    with pytest.raises(ApplicationActionError, match="submitted_at_timezone_required"):
        parse_submission_record_request(
            {
                "action": ACTION_NAME,
                "silver_job_id": 42,
                "submitted_at": "2026-09-16T17:00:00",
                "submission_channel": "employer_portal",
                "authority_reference": "x",
            }
        )


def test_job_identity_snapshot_and_hash_are_stable() -> None:
    source = {
        "id": 42,
        "canonical_job_key": "example:42",
        "source_system": "employer_origin",
        "source_job_id": "42",
        "source_url": "https://example.test/jobs/42",
        "title": "ML Engineer",
        "company_name": "Example GmbH",
        "company_key": "example",
        "location_raw": "Hannover",
        "description_text": "not part of the bounded identity snapshot",
    }
    first = build_job_identity_snapshot(source)
    second = build_job_identity_snapshot(dict(reversed(list(source.items()))))

    assert first == second
    assert "description_text" not in first
    assert len(canonical_sha256(first)) == 64
    assert canonical_sha256(first) == canonical_sha256(second)


def test_submission_idempotency_is_exact_and_deterministic() -> None:
    request = SubmissionRecordRequest(
        silver_job_id=42,
        submitted_at=datetime(2026, 9, 16, 15, 0, tzinfo=timezone.utc),
        submission_channel="employer_portal",
        authority_reference="operator:portal-confirmation",
    )
    key = application_key_for_job(42)

    assert key == "silver-job:42"
    assert submission_idempotency_key(application_key=key, request=request) == (
        submission_idempotency_key(application_key=key, request=request)
    )


def test_action_source_has_no_external_submission_or_email_path() -> None:
    source = MODULE.read_text(encoding="utf-8").lower()

    assert "requests.post" not in source
    assert "smtp" not in source
    assert "selenium" not in source
    assert "playwright" not in source
    assert "gmail api" not in source
    assert "'operator_confirmation'" in source
    assert "external_submission_action" in source
    assert "record_operator_confirmed_submission" in source


def test_date_only_manual_capture_is_first_class_and_time_is_not_required() -> None:
    request = parse_submission_record_request(
        {
            "action": ACTION_NAME,
            "silver_job_id": 42,
            "submitted_on": "2026-09-20",
            "submission_channel": "employer_portal",
            "authority_reference": "operator:portal",
        }
    )

    assert request.submitted_precision == "date"
    assert request.submitted_at.date().isoformat() == "2026-09-20"
    assert request.submitted_at.tzinfo == timezone.utc


def test_manual_external_job_requires_employer_and_title_but_no_silver_job() -> None:
    request = parse_submission_record_request(
        {
            "action": ACTION_NAME,
            "submitted_on": "2026-09-20",
            "submission_channel": "external_platform",
            "authority_reference": "operator:internal-portal",
            "employer_name": "CARIAD",
            "job_title": "A.I. Reporting Specialist",
            "source_url": "https://example.test/jobs/ai-reporting",
        }
    )

    assert request.silver_job_id is None
    assert request.is_external_job is True
    assert request.employer_name == "CARIAD"
    assert request.job_title == "A.I. Reporting Specialist"
