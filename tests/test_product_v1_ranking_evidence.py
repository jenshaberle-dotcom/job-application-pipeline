from __future__ import annotations

from src.search_intelligence.product_v1_assessment_evidence import (
    extract_product_v1_assessment_evidence,
)
from src.search_intelligence.product_v1_ranking_evidence import (
    RUBRIC_VERSION,
    build_product_v1_ranking_evidence,
)


URL = "https://jobs.example.com/jobs/ranking-1"


def _assessment(description: str, *, title: str = "Data Engineer"):
    return extract_product_v1_assessment_evidence(
        description=description,
        title=title,
        source_url=URL,
    )


def test_strong_ml_data_reliability_role_scores_from_explicit_signals() -> None:
    title = "Machine Learning Engineer"
    description = (
        "Permanent employment. We use a hybrid work model. "
        "Fluent German and English are required. The contract is 35-40 hours per week. "
        "We are looking for a senior-level professional. "
        "You build machine learning and MLOps solutions with Generative AI, LLMs and PyTorch. "
        "The role owns data pipelines, SQL, Spark, Databricks, a lakehouse and ETL. "
        "Reliability, test automation, observability, CI/CD, production systems and Terraform "
        "are explicit parts of the work."
    )
    assessment = _assessment(description, title=title)

    evidence = build_product_v1_ranking_evidence(
        title=title,
        description=description,
        origin_validation_status="validated",
        activity_status="active",
        assessment_evidence=assessment,
    )

    assert evidence.profile_direction_score == 100
    assert evidence.data_focus_score == 90
    assert evidence.reliability_focus_score == 100
    assert evidence.evidence_quality_score == 100
    assert evidence.uncertainties == ()
    assert evidence.rubric_version == RUBRIC_VERSION
    assert evidence.ranking_authority is False
    assert evidence.product_authority is False

    for reference in evidence.references:
        source = title if reference.source_surface == "title" else description
        assert source[reference.span_start : reference.span_end] == reference.evidence
        assert reference.source_surface in {"title", "description"}


def test_data_engineer_score_is_generic_and_transparent() -> None:
    title = "Data Engineer"
    description = "Build data pipelines with SQL for our platform."
    assessment = _assessment(description, title=title)

    evidence = build_product_v1_ranking_evidence(
        title=title,
        description=description,
        origin_validation_status="validated",
        activity_status="active",
        assessment_evidence=assessment,
    )

    assert evidence.profile_direction_score == 85
    assert evidence.data_focus_score == 50
    assert evidence.reliability_focus_score == 0
    assert evidence.evidence_quality_score == 70
    assert "assessment_evidence_incomplete:0/5" in evidence.uncertainties

    data_signals = {
        reference.signal
        for reference in evidence.references
        if reference.factor == "data_focus"
    }
    assert data_signals == {"data_role_title", "data_pipelines", "sql"}


def test_overlapping_reliability_evidence_is_not_double_counted() -> None:
    title = "Data Engineer"
    description = "Test automation is required for this role."
    assessment = _assessment(description, title=title)

    evidence = build_product_v1_ranking_evidence(
        title=title,
        description=description,
        origin_validation_status="validated",
        activity_status="active",
        assessment_evidence=assessment,
    )

    reliability_references = [
        reference
        for reference in evidence.references
        if reference.factor == "reliability_focus"
    ]
    assert evidence.reliability_focus_score == 20
    assert [reference.signal for reference in reliability_references] == ["testing_quality"]
    assert reliability_references[0].evidence.casefold() == "test automation"


def test_separate_iac_evidence_remains_additive_after_overlap_skip() -> None:
    title = "Data Engineer"
    description = "Test automation is required. Terraform is also required."
    assessment = _assessment(description, title=title)

    evidence = build_product_v1_ranking_evidence(
        title=title,
        description=description,
        origin_validation_status="validated",
        activity_status="active",
        assessment_evidence=assessment,
    )

    reliability_references = [
        reference
        for reference in evidence.references
        if reference.factor == "reliability_focus"
    ]
    assert evidence.reliability_focus_score == 40
    assert [reference.signal for reference in reliability_references] == [
        "testing_quality",
        "automation_iac",
    ]
    assert reliability_references[1].evidence.casefold() == "terraform"


def test_missing_fit_signals_are_not_invented() -> None:
    title = "Project Coordinator"
    description = "Coordinate stakeholders and maintain project documentation."
    assessment = _assessment(description, title=title)

    evidence = build_product_v1_ranking_evidence(
        title=title,
        description=description,
        origin_validation_status="validated",
        activity_status="active",
        assessment_evidence=assessment,
    )

    assert evidence.profile_direction_score == 0
    assert evidence.data_focus_score == 0
    assert evidence.reliability_focus_score == 0
    assert evidence.evidence_quality_score == 70
    assert evidence.references == ()


def test_evidence_quality_requires_origin_activity_and_assessment_coverage() -> None:
    title = "Senior Data Engineer"
    description = (
        "Permanent employment. Hybrid work model. Fluent German and English. "
        "35-40 hours per week. We require a senior-level professional."
    )
    assessment = _assessment(description, title=title)
    assert assessment.unresolved_fields == ()

    evidence = build_product_v1_ranking_evidence(
        title=title,
        description=description,
        origin_validation_status="pending",
        activity_status="unknown",
        assessment_evidence=assessment,
    )

    assert evidence.evidence_quality_score == 40
    assert evidence.uncertainties == (
        "origin_validation_not_confirmed",
        "current_activity_not_confirmed",
    )


def test_scores_are_bounded_and_payload_grants_no_rank_or_top5_authority() -> None:
    title = "ML Engineer"
    description = (
        "Machine learning MLOps Generative AI LLM PyTorch. "
        "Data pipelines SQL Spark Databricks lakehouse ETL. "
        "Reliability test automation observability CI/CD production systems Terraform."
    )
    assessment = _assessment(description, title=title)

    evidence = build_product_v1_ranking_evidence(
        title=title,
        description=description,
        origin_validation_status="validated",
        activity_status="active",
        assessment_evidence=assessment,
    )
    payload = evidence.canonical_payload()

    for key in (
        "profile_direction_score",
        "data_focus_score",
        "reliability_focus_score",
        "evidence_quality_score",
    ):
        assert 0 <= payload[key] <= 100
    assert "rank" not in payload
    assert "product_rank" not in payload
    assert "top5" not in payload
    assert payload["ranking_authority"] is False
    assert payload["product_authority"] is False
