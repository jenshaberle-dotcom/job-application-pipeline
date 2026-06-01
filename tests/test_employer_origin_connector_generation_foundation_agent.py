from __future__ import annotations

from scripts.run_employer_origin_connector_generation_foundation_agent import render_markdown
from src.search_intelligence.employer_origin_connector_generation import (
    GateReassessmentSignal,
    GateReview,
    REQUIRED_GENERATION_GATES,
    SourceCandidate,
    build_connector_generation_plan,
)


def test_generation_foundation_markdown_is_review_artifact_not_activation() -> None:
    candidate = SourceCandidate(
        candidate_id=7,
        company_key="hdi",
        company_name="HDI Group",
        candidate_url="https://careers.hdi.group/jobs",
        source_name_candidate="hdi:hannover",
        source_family_candidate="hdi",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="connector_candidate",
        risk_level="low",
    )
    gates = {
        name: GateReview(name, "passed", "continue", None, {})
        for name in REQUIRED_GENERATION_GATES
    }
    gates["connector_candidate_gate"] = GateReview(
        "connector_candidate_gate",
        "passed",
        "build_connector_candidate",
        None,
        {
            "connector_candidate_spec": {
                "detail_evidence": {
                    "detail_urls": ["https://careers.hdi.group/jobs/product-owner-data-platform"]
                }
            }
        },
    )
    plan = build_connector_generation_plan(candidate=candidate, gates=gates)

    markdown = render_markdown(plan)

    assert "does not create an auto-PR" in markdown
    assert "does not activate a source" in markdown
    assert "does not write Bronze records" in markdown
    assert "run_employer_origin_connector_artifact_generator" in markdown


def test_render_markdown_surfaces_learning_reassessment_signal() -> None:
    plan = build_connector_generation_plan(
        candidate=SourceCandidate(
            candidate_id=2,
            company_key="hdi",
            company_name="HDI Group",
            candidate_url="https://careers.hdi.group/jobs",
            source_name_candidate="hdi:hannover",
            source_family_candidate="hdi",
            source_target_candidate="hannover",
            source_type_candidate="employer_origin_career_site",
            status="manual_review_required",
            risk_level="low",
        ),
        gates={},
        reassessment_signal=GateReassessmentSignal(
            status="open",
            false_negative_risk_level="critical",
            priority=120,
            trigger_reason="market evidence changed",
            suggested_search_terms=("analytics",),
            updated_at="2026-06-01",
            latest_gate_reviewed_at="2026-05-29",
        ),
        reviewed_by="jens",
    )

    markdown = render_markdown(plan)

    assert "## Learning Reassessment Signal" in markdown
    assert "gate reassessment required: `true`" in markdown
    assert "false-negative risk level: `critical`" in markdown
    assert "suggested search terms: `analytics`" in markdown
    assert "latest gate reviewed at: `2026-05-29`" in markdown
