from __future__ import annotations

from pathlib import Path

from src.search_intelligence.cand001_validated_origin_url_persistence import (
    BOUNDARY,
    CandidatePersistenceSnapshot,
    OriginUrlValidationEvidence,
    build_persistence_plan_item,
    evidence_from_origin_discovery_payload,
    markdown_report,
    report_payload,
    summarize_plan,
)


def candidate(candidate_url: str | None = None, status: str = "discovery") -> CandidatePersistenceSnapshot:
    return CandidatePersistenceSnapshot(
        candidate_id=36,
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        status=status,
        candidate_url=candidate_url,
        risk_level="medium",
    )


def good_evidence(url: str = "https://jobs.hannover-re.com/") -> OriginUrlValidationEvidence:
    return OriginUrlValidationEvidence(
        selected_url=url,
        success_tier="A",
        decision="origin_url_candidate_selected",
        confidence_score=1.0,
        reason="reachable career/job-like URL",
        risk_level="low",
    )


def test_empty_candidate_url_recommends_sz1_persistence() -> None:
    item = build_persistence_plan_item(candidate(), good_evidence())
    assert item.decision == "persist_validated_candidate_url"
    assert item.review_status == "write_recommended"
    assert item.apply_allowed is True
    assert item.manual_review_required is True
    assert item.safety_zone == "SZ1_CANDIDATE_METADATA"


def test_active_controlled_is_protected_by_default() -> None:
    item = build_persistence_plan_item(candidate(status="active_controlled"), good_evidence())
    assert item.decision == "skip_protected_active_controlled"
    assert item.apply_allowed is False
    assert item.review_status == "skipped"


def test_existing_same_url_is_no_action() -> None:
    item = build_persistence_plan_item(candidate("https://jobs.hannover-re.com"), good_evidence())
    assert item.decision == "no_action_already_persisted"
    assert item.manual_review_required is False


def test_existing_different_url_requires_manual_review() -> None:
    item = build_persistence_plan_item(candidate("https://example.com/careers"), good_evidence())
    assert item.decision == "manual_review_required_url_conflict"
    assert item.apply_allowed is False
    assert item.manual_review_required is True


def test_weak_url_finder_evidence_is_not_written() -> None:
    weak = OriginUrlValidationEvidence(
        selected_url="https://jobs.hannover-re.com/",
        success_tier="D",
        decision="not_found",
        confidence_score=0.2,
        reason="weak",
        risk_level="medium",
    )
    item = build_persistence_plan_item(candidate(), weak)
    assert item.decision == "manual_review_required"
    assert item.apply_allowed is False


def test_duplicate_selected_url_requires_manual_review() -> None:
    item = build_persistence_plan_item(candidate(), good_evidence(), duplicate_selected_url_exists=True)
    assert item.decision == "manual_review_required_duplicate_url"
    assert item.apply_allowed is False


def test_summary_and_markdown_report_include_boundaries() -> None:
    item = build_persistence_plan_item(candidate(), good_evidence())
    summary = summarize_plan([item])
    assert summary.write_recommended_count == 1
    assert summary.boundary["no_export_as_input_source_of_truth"] is True
    payload = report_payload(benchmark_label="cand001_test", items=[item])
    md = markdown_report(payload)
    assert "CAND-001 Validated Origin URL Persistence Gate" in md
    assert "persist_validated_candidate_url" in md
    assert "URL-Finder report exports are review context" in md


def test_migration_and_docs_exist() -> None:
    migration = Path("db/migrations/073_create_candidate_origin_url_persistence_reviews.sql").read_text(encoding="utf-8")
    assert "candidate_origin_url_persistence_reviews" in migration
    assert "no scheduler changes" in migration
    doc = Path("docs/planning/cand001_validated_origin_url_persistence_gate.md").read_text(encoding="utf-8")
    assert "CAND-001" in doc
    assert "not source-of-truth inputs" in doc


def test_boundary_is_sz1_only() -> None:
    assert BOUNDARY["sz1_candidate_metadata_transition"] is True
    assert BOUNDARY["no_gate_write"] is True
    assert BOUNDARY["no_source_activation"] is True


def test_live_origin_payload_without_explicit_tier_derives_a_tier() -> None:
    evidence = evidence_from_origin_discovery_payload(
        {
            "selected_url": "https://jobs.hannover-re.com/",
            "decision": "origin_url_candidate_selected",
            "confidence_score": 1.0,
            "reason": "reachable career/job-like URL",
            "risk_level": "low",
        }
    )

    assert evidence.success_tier == "A"
    item = build_persistence_plan_item(candidate(), evidence)
    assert item.decision == "persist_validated_candidate_url"
    assert item.review_status == "write_recommended"
    assert item.apply_allowed is True
def test_apply_sql_handles_null_and_empty_candidate_url() -> None:
    script = Path("scripts/run_cand001_validated_origin_url_persistence_gate.py").read_text(encoding="utf-8")
    assert "candidate_url IS NULL OR btrim(candidate_url) = ''" in script
