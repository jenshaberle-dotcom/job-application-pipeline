from __future__ import annotations

from dataclasses import replace

import pytest

from src.job_lifecycle_health import (
    APPROVAL_TOKEN,
    COVERAGE_EXACT_DETAIL,
    OUTCOME_CLOSED,
    OUTCOME_SEEN_ACTIVE,
    OUTCOME_UNVERIFIABLE,
    HealthClassification,
    HttpProbeResult,
    JobHealthTarget,
    build_health_probe_manifest,
    classify_exact_detail,
    ensure_expected_target,
    normalize_url_identity,
    title_is_confirmed,
)


TARGET_URL = "https://jobs.example.com/job/Senior-Data-Engineer/12345/"


def target() -> JobHealthTarget:
    return JobHealthTarget(
        silver_job_id=42,
        raw_job_id=420,
        ingestion_run_id=2596,
        source_name="example:discovery",
        external_job_id="12345:abcdef",
        source_url=TARGET_URL,
        title="Senior Data Engineer",
        canonical_source_type="employer_origin_career_site",
        raw_source_type="employer_origin_career_site",
    )


class FakeRepository:
    def __init__(self, current_target: JobHealthTarget | None = None) -> None:
        self.current_target = current_target or target()
        self.load_calls = 0
        self.append_calls = 0
        self.appended: tuple[JobHealthTarget, HealthClassification, str] | None = None

    def load_target(self, silver_job_id: int) -> JobHealthTarget:
        self.load_calls += 1
        assert silver_job_id == self.current_target.silver_job_id
        return self.current_target

    def append_health_observation(
        self,
        *,
        expected_target: JobHealthTarget,
        classification: HealthClassification,
        observed_by: str,
    ) -> int:
        self.append_calls += 1
        self.appended = (expected_target, classification, observed_by)
        return 77


def active_fetcher(url: str, *, timeout_seconds: float) -> HttpProbeResult:
    assert url == TARGET_URL
    assert timeout_seconds > 0
    return HttpProbeResult(
        status_code=200,
        final_url=TARGET_URL,
        response_text=(
            "<html><title>Senior Data Engineer</title>"
            "<body>Senior Data Engineer - apply now</body></html>"
        ),
        redirect_count=0,
    )


def test_normalize_url_identity_ignores_fragment_trailing_slash_and_query_order() -> None:
    left = "HTTPS://Jobs.Example.com/job/123/?b=2&a=1#fragment"
    right = "https://jobs.example.com/job/123?a=1&b=2"
    assert normalize_url_identity(left) == normalize_url_identity(right)


def test_title_confirmation_uses_normalized_page_text() -> None:
    assert title_is_confirmed(
        "(Senior) Data Engineer",
        "<title>Jobs</title><h1>Senior Data Engineer</h1>",
    )


def test_exact_2xx_url_and_title_is_seen_active() -> None:
    result = classify_exact_detail(target(), active_fetcher(TARGET_URL, timeout_seconds=5))
    assert result.outcome == OUTCOME_SEEN_ACTIVE
    assert result.coverage == COVERAGE_EXACT_DETAIL
    assert result.evidence_reason == "exact_detail_url_and_title_confirmed"
    assert result.evidence["url_identity_match"] is True
    assert result.evidence["title_match"] is True
    assert "response_text" not in result.evidence


def test_http_410_is_closed_exact_detail() -> None:
    result = classify_exact_detail(
        target(),
        HttpProbeResult(
            status_code=410,
            final_url=TARGET_URL,
            response_text="Gone",
            redirect_count=0,
        ),
    )
    assert result.outcome == OUTCOME_CLOSED
    assert result.coverage == COVERAGE_EXACT_DETAIL
    assert result.evidence_reason == "http_410_gone_on_exact_detail"


def test_http_404_remains_unverifiable_without_source_specific_contract() -> None:
    result = classify_exact_detail(
        target(),
        HttpProbeResult(
            status_code=404,
            final_url=TARGET_URL,
            response_text="Not found",
            redirect_count=0,
        ),
    )
    assert result.outcome == OUTCOME_UNVERIFIABLE
    assert (
        result.evidence_reason
        == "http_404_requires_source_specific_closure_validation"
    )


@pytest.mark.parametrize("status_code", [401, 403, 429, 500, 503])
def test_non_authoritative_http_status_is_unverifiable(status_code: int) -> None:
    result = classify_exact_detail(
        target(),
        HttpProbeResult(
            status_code=status_code,
            final_url=TARGET_URL,
            response_text="blocked or failed",
            redirect_count=0,
        ),
    )
    assert result.outcome == OUTCOME_UNVERIFIABLE
    assert result.evidence_reason == "http_status_not_authoritative_for_lifecycle"


def test_transport_failure_is_unverifiable() -> None:
    result = classify_exact_detail(
        target(),
        HttpProbeResult(
            status_code=None,
            final_url=TARGET_URL,
            response_text="",
            redirect_count=0,
            error_type="Timeout",
            error_message="timed out",
        ),
    )
    assert result.outcome == OUTCOME_UNVERIFIABLE
    assert result.evidence_reason == "network_or_transport_failure"


def test_redirect_to_different_url_is_unverifiable_even_with_matching_title() -> None:
    result = classify_exact_detail(
        target(),
        HttpProbeResult(
            status_code=200,
            final_url="https://jobs.example.com/search/",
            response_text="Senior Data Engineer",
            redirect_count=1,
        ),
    )
    assert result.outcome == OUTCOME_UNVERIFIABLE
    assert result.evidence_reason == "final_url_changed_concrete_identity"


def test_title_mismatch_is_unverifiable_on_same_2xx_url() -> None:
    result = classify_exact_detail(
        target(),
        HttpProbeResult(
            status_code=200,
            final_url=TARGET_URL,
            response_text="Careers at Example - no concrete vacancy title here",
            redirect_count=0,
        ),
    )
    assert result.outcome == OUTCOME_UNVERIFIABLE
    assert result.evidence_reason == "vacancy_title_not_confirmed_on_detail_page"


def test_expected_identity_mismatch_fails_before_network() -> None:
    repository = FakeRepository(
        replace(target(), source_name="other:discovery")
    )
    fetch_calls = 0

    def forbidden_fetcher(url: str, *, timeout_seconds: float) -> HttpProbeResult:
        nonlocal fetch_calls
        fetch_calls += 1
        raise AssertionError("network must not run after identity mismatch")

    with pytest.raises(ValueError, match="Source identity mismatch"):
        build_health_probe_manifest(
            silver_job_id=42,
            expected_source_name="example:discovery",
            expected_source_url=TARGET_URL,
            apply=False,
            approval_token=None,
            observed_by=None,
            repository=repository,
            fetcher=forbidden_fetcher,
        )

    assert repository.load_calls == 1
    assert repository.append_calls == 0
    assert fetch_calls == 0


def test_wrong_apply_token_blocks_before_db_and_network() -> None:
    repository = FakeRepository()
    fetch_calls = 0

    def forbidden_fetcher(url: str, *, timeout_seconds: float) -> HttpProbeResult:
        nonlocal fetch_calls
        fetch_calls += 1
        raise AssertionError("network must not run with wrong approval token")

    with pytest.raises(ValueError, match="Invalid lifecycle health approval token"):
        build_health_probe_manifest(
            silver_job_id=42,
            expected_source_name="example:discovery",
            expected_source_url=TARGET_URL,
            apply=True,
            approval_token="wrong",
            observed_by="jens",
            repository=repository,
            fetcher=forbidden_fetcher,
        )

    assert repository.load_calls == 0
    assert repository.append_calls == 0
    assert fetch_calls == 0


def test_apply_requires_observer_before_db_and_network() -> None:
    repository = FakeRepository()

    with pytest.raises(ValueError, match="--observed-by is required"):
        build_health_probe_manifest(
            silver_job_id=42,
            expected_source_name="example:discovery",
            expected_source_url=TARGET_URL,
            apply=True,
            approval_token=APPROVAL_TOKEN,
            observed_by=None,
            repository=repository,
            fetcher=active_fetcher,
        )

    assert repository.load_calls == 0
    assert repository.append_calls == 0


def test_dry_run_probes_but_never_writes() -> None:
    repository = FakeRepository()
    manifest = build_health_probe_manifest(
        silver_job_id=42,
        expected_source_name="example:discovery",
        expected_source_url=TARGET_URL,
        apply=False,
        approval_token=None,
        observed_by=None,
        repository=repository,
        fetcher=active_fetcher,
    )

    assert repository.load_calls == 1
    assert repository.append_calls == 0
    assert manifest["mode"] == "dry_run"
    assert manifest["classification"]["outcome"] == OUTCOME_SEEN_ACTIVE
    assert manifest["write"]["applied"] is False
    assert manifest["boundary"]["health_observation_write"] is False


def test_apply_writes_exact_classification_once_after_probe() -> None:
    repository = FakeRepository()
    manifest = build_health_probe_manifest(
        silver_job_id=42,
        expected_source_name="example:discovery",
        expected_source_url=TARGET_URL,
        apply=True,
        approval_token=APPROVAL_TOKEN,
        observed_by="jens",
        repository=repository,
        fetcher=active_fetcher,
    )

    assert repository.load_calls == 1
    assert repository.append_calls == 1
    assert repository.appended is not None
    written_target, classification, observed_by = repository.appended
    assert written_target == target()
    assert classification.outcome == OUTCOME_SEEN_ACTIVE
    assert observed_by == "jens"
    assert manifest["mode"] == "apply"
    assert manifest["write"]["job_health_observation_id"] == 77
    assert manifest["boundary"]["health_observation_write"] is True


def test_non_employer_origin_target_is_rejected() -> None:
    with pytest.raises(ValueError, match="not an employer_origin_career_site"):
        ensure_expected_target(
            replace(
                target(),
                canonical_source_type="aggregator",
                raw_source_type="aggregator_result_card",
            ),
            expected_source_name="example:discovery",
            expected_source_url=TARGET_URL,
        )
