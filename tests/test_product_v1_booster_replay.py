from __future__ import annotations

from datetime import date
from hashlib import sha256

from src.search_intelligence.product_v1_application_context import (
    ApplicationSourceDocumentSnapshot,
    ApplicationTargetSnapshot,
    CandidateFactSnapshot,
    build_product_v1_application_context,
)
from src.search_intelligence.product_v1_assessment_evidence import (
    extract_product_v1_assessment_evidence,
)
from src.search_intelligence.product_v1_booster_replay import (
    application_booster_input,
    assessment_booster_input,
    ranking_booster_input,
)
from src.search_intelligence.product_v1_ranking_evidence import (
    build_product_v1_ranking_evidence,
)


URL = "https://jobs.example.com/booster-replay/42"
TODAY = date(2026, 8, 18)


def _assessment(description: str):
    return extract_product_v1_assessment_evidence(
        title="Data Engineer",
        description=description,
        source_url=URL,
    )


def _ranking(description: str):
    assessment = _assessment(description)
    return build_product_v1_ranking_evidence(
        title="Data Engineer",
        description=description,
        origin_validation_status="validated",
        activity_status="active",
        assessment_evidence=assessment,
    )


def _document(document_type: str, content: str):
    return ApplicationSourceDocumentSnapshot(
        document_type=document_type,
        source_label=document_type,
        source_reference=f"local://{document_type}",
        content_sha256=sha256(content.encode("utf-8")).hexdigest(),
        content=content,
        status="approved",
    )


def _fact(statement: str):
    return CandidateFactSnapshot(
        fact_key="python",
        category="skill",
        evidence_class="professional_employment",
        approval_status="approved",
        statement=statement,
        capability_tags=("Python",),
        limitations=(),
    )


def _application_context(statement: str):
    target = ApplicationTargetSnapshot(
        silver_job_id=42,
        product_rank=2,
        title="Data Engineer",
        company_name="Example GmbH",
        source_url=URL,
        canonical_source_type="employer_origin",
        product_readiness_status="rankable",
        origin_validation_status="validated",
        activity_status="active",
        hard_filter_status="passed",
        detail_text="Data Engineer role. We need Python for reliable data pipelines.",
    )
    return build_product_v1_application_context(
        target=target,
        candidate_profile_status="approved",
        candidate_profile_sha256="a" * 64,
        candidate_facts=(_fact(statement),),
        source_documents=(
            _document("base_cv", "CV structure"),
            _document("base_application_letter", "Letter structure"),
        ),
        as_of_date=TODAY,
    )


def test_assessment_identity_is_stable_and_changes_with_deterministic_evidence() -> None:
    first = assessment_booster_input(_assessment("Join our data platform team."))
    same = assessment_booster_input(_assessment("Join our data platform team."))
    changed = assessment_booster_input(
        _assessment("Join our data platform team. Hybrid work model.")
    )

    assert first == same
    assert first.normalized_input_hash != changed.normalized_input_hash
    assert first.provider_requests == 0
    assert first.product_authority is False


def test_ranking_identity_requires_source_and_changes_with_ranking_evidence() -> None:
    baseline = ranking_booster_input(
        _ranking("Build data pipelines with SQL."),
        source_identity=URL,
    )
    changed = ranking_booster_input(
        _ranking("Build data pipelines with SQL and observability."),
        source_identity=URL,
    )

    assert baseline.normalized_input_hash != changed.normalized_input_hash
    assert baseline.source_identity == URL
    assert baseline.product_authority is False


def test_application_identity_changes_when_authoritative_candidate_fact_manifest_changes() -> None:
    baseline = application_booster_input(
        _application_context("I use Python professionally.")
    )
    changed = application_booster_input(
        _application_context("I use Python professionally in production systems.")
    )

    assert baseline.source_identity == f"silver_job:42|{URL}"
    assert baseline.normalized_input_hash != changed.normalized_input_hash
    assert baseline.database_requests == 0
    assert baseline.product_authority is False


def test_product_v1_input_binds_exact_scope_to_terminal_replay_guard() -> None:
    booster_input = assessment_booster_input(
        _assessment("Join our data platform team.")
    )
    first = booster_input.replay_decision(
        unresolved_scope=("work_model", "weekly_hours"),
    )
    replay = booster_input.replay_decision(
        unresolved_scope=("weekly_hours", "work_model"),
        prior_terminal_input_fingerprints=(first.input_fingerprint,),
    )
    changed_scope = booster_input.replay_decision(
        unresolved_scope=("work_model",),
        prior_terminal_input_fingerprints=(first.input_fingerprint,),
    )

    assert first.provider_eligible is True
    assert replay.provider_eligible is False
    assert replay.replay_suppressed is True
    assert replay.provider_requests == 0
    assert changed_scope.provider_eligible is True
