from src.search_intelligence.product_v1_origin_guard import (
    evaluate_product_origin_guard,
)


def _evaluate(**overrides):
    values = {
        "source_url": "https://jobs.example.com/job/123",
        "source_name": None,
        "canonical_source_type": "employer_origin_career_site",
        "lifecycle_status": "active_confirmed",
        "origin_validation_status": "validated",
        "product_readiness_status": "rankable",
    }
    values.update(overrides)
    return evaluate_product_origin_guard(**values)


def test_current_validated_employer_origin_https_is_actionable() -> None:
    result = _evaluate()
    assert result.eligible is True
    assert result.reason == "current_employer_origin_confirmed"
    assert result.employer_origin_url == "https://jobs.example.com/job/123"


def test_ats_backed_origin_is_actionable() -> None:
    result = _evaluate(
        source_url="https://example.jobs.personio.de/job/123",
        canonical_source_type="employer_origin_ats_backed_career_site",
    )
    assert result.eligible is True


def test_known_origin_source_can_compensate_for_diagnostic_type_gap() -> None:
    result = _evaluate(
        source_url="https://company.jobs.personio.de/job/123?language=de",
        source_name="personio:company",
        canonical_source_type="unknown",
    )
    assert result.eligible is True


def test_verified_origin_resolution_can_promote_aggregator_discovery_provenance() -> None:
    result = _evaluate(
        source_url="https://www.stepstone.de/stellenangebote/123",
        source_name="stepstone",
        canonical_source_type="aggregator",
        product_readiness_status="assessment_required",
        resolved_employer_origin_url="https://careers.example.com/jobs/123",
        resolved_origin_verified=True,
    )
    assert result.eligible is True
    assert result.reason == "verified_employer_origin_resolution"
    assert result.employer_origin_url == "https://careers.example.com/jobs/123"


def test_aggregator_hosts_and_source_families_are_discovery_only() -> None:
    for url in (
        "https://www.arbeitsagentur.de/jobsuche/jobdetail/1",
        "https://gute-jobs.de/viewjob-1",
        "https://www.stepstone.de/stellenangebote--x--1-inline.html",
    ):
        assert _evaluate(source_url=url).eligible is False

    for source_name in ("stepstone", "bundesagentur_fuer_arbeit", "gute_jobs"):
        result = _evaluate(
            source_url="https://jobs.example-employer.de/job/123",
            source_name=source_name,
        )
        assert result.eligible is False
        assert result.reason == "aggregator_source_is_discovery_only"


def test_non_https_missing_or_unvalidated_origin_fails_closed() -> None:
    assert _evaluate(source_url=None).eligible is False
    assert _evaluate(source_url="http://jobs.example.com/job/1").reason == (
        "employer_origin_https_url_required"
    )
    assert _evaluate(source_url="ba://12265-1").reason == (
        "employer_origin_https_url_required"
    )
    assert _evaluate(origin_validation_status="unknown").reason == (
        "employer_origin_not_validated"
    )


def test_inactive_or_non_origin_product_row_is_not_actionable() -> None:
    assert _evaluate(
        lifecycle_status="inactive_confirmed",
        product_readiness_status="blocked_inactive",
    ).eligible is False
    assert _evaluate(canonical_source_type="aggregator").eligible is False
