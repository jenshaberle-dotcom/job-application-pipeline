from __future__ import annotations

from src.search_intelligence.product_v1_assessment_evidence import (
    extract_product_v1_assessment_evidence,
)


SOURCE_URL = "https://jobs.example.com/jobs/123"


def _extract(*, description: str, title: str = "Data Engineer"):
    return extract_product_v1_assessment_evidence(
        description=description,
        title=title,
        source_url=SOURCE_URL,
    )


def test_extracts_source_grounded_hard_filter_evidence() -> None:
    evidence = _extract(
        title="Senior Data Engineer",
        description=(
            "This is a permanent position with a hybrid work model. "
            "Fluent German and English are required. "
            "The contract is 35-40 hours per week. "
            "We are looking for a senior-level professional to join the team."
        ),
    )

    assert evidence.employment_type == "permanent"
    assert evidence.required_languages == ("de", "en")
    assert evidence.weekly_hours_min == 35
    assert evidence.weekly_hours_max == 40
    assert evidence.work_model == "hybrid"
    assert evidence.title_seniority == "senior"
    assert evidence.requirements_seniority == "senior"
    assert evidence.conflicted_fields == ()
    assert evidence.unresolved_fields == ()

    patch = evidence.assessment_patch()
    assert patch["employment_evidence_status"] == "observed"
    assert patch["language_evidence_status"] == "observed"
    assert patch["weekly_hours_evidence_status"] == "observed"
    assert patch["seniority_evidence_status"] == "observed"

    assert evidence.references
    for reference in evidence.references:
        assert reference.source_url == SOURCE_URL
        assert reference.observed_value
        assert reference.canonical_value
        assert reference.evidence
        assert reference.span_end > reference.span_start


def test_experience_wording_never_becomes_requirements_seniority() -> None:
    evidence = _extract(
        description=(
            "You bring 8 years of professional experience and extensive professional "
            "experience in data engineering. Permanent employment."
        )
    )

    assert evidence.employment_type == "permanent"
    assert evidence.requirements_seniority == "unknown"
    assert "requirements_seniority" in evidence.unresolved_fields
    assert evidence.assessment_patch()["seniority_evidence_status"] == "unknown"


def test_conflicting_work_models_fail_closed() -> None:
    evidence = _extract(
        description=(
            "We use a hybrid work model. This is also described as a fully remote role."
        )
    )

    assert evidence.work_model == "unknown"
    assert "work_model" in evidence.conflicted_fields
    assert "work_model" in evidence.unresolved_fields


def test_conflicting_employment_types_fail_closed() -> None:
    evidence = _extract(
        description=(
            "The posting mentions a permanent position and a fixed-term contract."
        )
    )

    assert evidence.employment_type == "unknown"
    assert "employment_type" in evidence.conflicted_fields
    assert evidence.assessment_patch()["employment_evidence_status"] == "unknown"


def test_home_office_without_explicit_work_model_remains_unknown() -> None:
    evidence = _extract(description="Home Office is possible after onboarding.")

    assert evidence.work_model == "unknown"
    assert "work_model" in evidence.unresolved_fields


def test_observed_and_canonical_values_are_separate() -> None:
    evidence = _extract(description="Wir bieten eine unbefristete Anstellung.")
    employment_reference = next(
        reference
        for reference in evidence.references
        if reference.field == "employment_type"
    )

    assert employment_reference.canonical_value == "permanent"
    assert "unbefristet" in employment_reference.observed_value.casefold()
    assert employment_reference.observed_value != employment_reference.canonical_value


def test_unknown_evidence_does_not_create_hard_filter_facts() -> None:
    evidence = _extract(description="Join our data platform team and build pipelines.")

    assert evidence.employment_type == "unknown"
    assert evidence.required_languages == ()
    assert evidence.weekly_hours_min is None
    assert evidence.weekly_hours_max is None
    assert evidence.work_model == "unknown"
    assert evidence.title_seniority == "unknown"
    assert evidence.requirements_seniority == "unknown"
    assert set(evidence.unresolved_fields) == {
        "employment_type",
        "required_languages",
        "weekly_hours",
        "work_model",
        "title_seniority",
        "requirements_seniority",
    }
    assert evidence.canonical_payload()["authority"] == {
        "source_evidence_only": True,
        "candidate_fact_authority": False,
        "capability_fit_authority": False,
        "hard_filter_authority": False,
        "ranking_authority": False,
        "product_authority": False,
    }
