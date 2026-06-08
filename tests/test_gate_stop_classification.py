from __future__ import annotations

from src.search_intelligence.gate_stop_classification import classify_gate_stop


def test_classifies_deutsche_bahn_style_stop_as_recoverable_url_problem() -> None:
    result = classify_gate_stop(
        gate_name="technical_reachability_gate",
        gate_status="manual_review_required",
        decision="manual_review_required",
        stop_reason="bounded source URL recovery found no reachable company-related career/job URL",
        evidence={"decision": "no_reachable_recovery_url_found", "previous_candidate_url": "https://db.jobs/de-de/jobs"},
    )

    assert result.category == "recoverable_url_problem"
    assert result.terminal is False
    assert result.default_reprocess == "allow_with_recovery"


def test_classifies_ratiodata_style_captcha_markers_as_review_not_terminal() -> None:
    result = classify_gate_stop(
        gate_name="risk_gate",
        gate_status="failed",
        decision="abort_documented",
        stop_reason="source response contains bot-defense or access-risk markers",
        evidence={"status_code": 200, "risk_markers": ["captcha", "recaptcha"]},
    )

    assert result.category == "risk_marker_review"
    assert result.terminal is False
    assert result.default_reprocess == "allow_with_review"


def test_classifies_confirmed_access_denied_as_terminal_access_risk() -> None:
    result = classify_gate_stop(
        gate_name="risk_gate",
        gate_status="failed",
        decision="abort_documented",
        stop_reason="source response contains bot-defense or access-risk markers",
        evidence={"status_code": 403, "risk_markers": ["access denied", "bot detection"]},
    )

    assert result.category == "terminal_access_risk"
    assert result.terminal is True
    assert result.default_reprocess == "block_without_explicit_override"


def test_classifies_adesso_style_detail_stop_as_detail_discovery_gap() -> None:
    result = classify_gate_stop(
        gate_name="detail_evidence_gate",
        gate_status="manual_review_required",
        decision="manual_review_required",
        stop_reason="multi-origin repair found no concrete detail pages with profile and target/remote signals",
        evidence={"details": [], "rejected_urls": ["https://jobs.example.com/ :: not_concrete_job_detail_url"]},
    )

    assert result.category == "detail_discovery_gap"
    assert result.terminal is False
    assert result.default_reprocess == "allow_with_detail_discovery"


def test_classifies_unqualified_abort_as_terminal_unclassified() -> None:
    result = classify_gate_stop(
        gate_name="scope_gate",
        gate_status="failed",
        decision="abort_documented",
        stop_reason="agent MVP only supports one listing page per run",
        evidence={"max_listing_pages": 2},
    )

    assert result.category == "terminal_unclassified"
    assert result.terminal is True


def test_classification_evidence_includes_stop002_registry_fields() -> None:
    result = classify_gate_stop(
        gate_name="relevance_gate",
        gate_status="manual_review_required",
        decision="manual_review_required",
        stop_reason="bounded preview did not expose target-location or remote evidence",
        evidence={},
    )

    evidence = result.as_evidence()

    assert evidence["stop_lifecycle_class"] == "false_negative_risk_stop"
    assert evidence["false_negative_risk"] == "high"
    assert evidence["repair_strategy_id"] == "bounded_relevance_evidence_discovery"
    assert evidence["recommended_next_safe_action"] == "run_relevance_evidence_discovery_plan"
    assert evidence["safety_zone"] == "SZ2_EVIDENCE_AND_GATES"
