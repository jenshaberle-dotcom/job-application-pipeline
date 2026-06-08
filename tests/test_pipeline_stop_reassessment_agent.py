from __future__ import annotations

from scripts.run_pipeline_stop_reassessment_agent import (
    StopCandidate,
    StopGate,
    assess_stop_validity,
    collect_stop_signals,
    report_payload,
    render_markdown_report,
    write_reports,
)


def candidate(
    company_key: str = "ratiodata",
    candidate_url: str | None = "https://karriere.ratiodata.de/stellenangebote",
    status: str = "abort_documented",
    risk_level: str = "blocked",
) -> StopCandidate:
    return StopCandidate(
        candidate_id=5,
        company_key=company_key,
        company_name=company_key.upper(),
        candidate_url=candidate_url,
        source_name_candidate=f"{company_key}:discovery",
        source_family_candidate=company_key,
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status=status,
        risk_level=risk_level,
    )


def gate(
    name: str = "technical_reachability_gate",
    status: str = "manual_review_required",
    decision: str = "manual_review_required",
    stop_reason: str | None = None,
) -> StopGate:
    return StopGate(
        gate_name=name,
        gate_status=status,
        decision=decision,
        stop_reason=stop_reason,
        evidence={},
    )


def test_access_risk_stop_with_concrete_url_is_flagged_as_likely_over_sensitive() -> None:
    assessment = assess_stop_validity(
        candidate(),
        {
            "technical_reachability_gate": gate(
                stop_reason="source response contains bot-defense or access-risk markers"
            )
        },
        target_location="hannover",
        reviewed_by="jens",
    )

    assert assessment is not None
    assert assessment.stop_validity == "needs_reassessment_likely_over_sensitive"
    assert assessment.false_negative_risk == "high"
    assert assessment.stage2_repair_plan is not None
    assert "run_employer_origin_detail_evidence_repair_agent" in assessment.stage2_repair_plan.dry_run_command
    assert "--dry-run" in assessment.stage2_repair_plan.dry_run_command
    assert assessment.stage2_repair_plan.apply_command.endswith("--reviewed-by jens")


def test_missing_url_stop_gets_source_url_recovery_stage2_plan() -> None:
    assessment = assess_stop_validity(
        candidate("vhv_gruppe", candidate_url=None, status="discovery", risk_level="medium"),
        {},
        target_location="hannover",
        reviewed_by="jens",
    )

    assert assessment is not None
    assert assessment.stop_validity == "unconfirmed_stop_recovery_needed"
    assert assessment.stage2_repair_plan is not None
    assert assessment.stage2_repair_plan.action == "run_bounded_source_url_recovery"
    assert "run_employer_origin_source_url_recovery_agent" in assessment.stage2_repair_plan.dry_run_command
    assert "--apply" in assessment.stage2_repair_plan.apply_command


def test_detail_gap_stop_gets_detail_repair_plan() -> None:
    assessment = assess_stop_validity(
        candidate("hannover_ruck", candidate_url="https://jobs.hannover-re.com/", status="discovery", risk_level="medium"),
        {
            "detail_evidence_gate": gate(
                name="detail_evidence_gate",
                stop_reason="bounded detail discovery found no concrete detail pages with profile and target-location/remote evidence",
            )
        },
        target_location="hannover",
        reviewed_by="jens",
    )

    assert assessment is not None
    assert assessment.stop_validity == "unconfirmed_detail_evidence_gap"
    assert assessment.stage2_repair_plan is not None
    assert assessment.stage2_repair_plan.action == "run_bounded_detail_evidence_repair"


def test_candidate_without_stop_signal_is_not_included() -> None:
    assessment = assess_stop_validity(
        candidate("hdi", status="active_controlled", risk_level="low"),
        {
            "detail_evidence_gate": gate(
                name="detail_evidence_gate",
                status="passed",
                decision="passed",
                stop_reason=None,
            )
        },
        target_location="hannover",
        reviewed_by="jens",
    )

    assert assessment is None


def test_report_payload_summarizes_false_negative_risk_and_stage2_contract(tmp_path) -> None:
    assessment = assess_stop_validity(
        candidate(),
        {
            "technical_reachability_gate": gate(
                stop_reason="source response contains bot-defense or access-risk markers"
            )
        },
        target_location="hannover",
        reviewed_by="jens",
    )
    assert assessment is not None

    payload = report_payload(
        [assessment],
        benchmark_label="stopper_smoke",
        target_location="hannover",
        reviewed_by="jens",
    )
    markdown = render_markdown_report(payload)
    json_path, md_path = write_reports(payload, tmp_path, "stopper smoke")

    assert payload["campaign"] == "REPAIR-001 Stop Review and Repair Candidate Audit"
    assert payload["boundary"]["no_gate_review_write"] is True
    assert payload["report_contract"]["stop_taxonomy_integration"].startswith("dominant stop category")
    assert payload["summary"]["stage2_repair_plan_count"] == 1
    assert payload["summary"]["high_false_negative_risk_count"] == 1
    assert payload["summary"]["dominant_lifecycle_class_counts"]["review_stop"] == 1
    assert payload["summary"]["dominant_stop_category_counts"]["manual_review_required"] == 1
    assert payload["summary"]["repair_audit_order"][0]["company_key"] == "ratiodata"
    assert "Stage 2 dry-run command" in markdown
    assert "Repair audit order" in markdown
    assert json_path.name == "stopper_smoke_stop_reassessment.json"
    assert md_path.read_text(encoding="utf-8").startswith("# REPAIR-001 Stop Review and Repair Candidate Audit")


def test_collect_stop_signals_includes_candidate_and_gate_stoppers() -> None:
    signals = collect_stop_signals(
        candidate(),
        {
            "risk_gate": gate(
                name="risk_gate",
                status="manual_review_required",
                decision="manual_review_required",
                stop_reason="source response contains bot-defense or access-risk markers",
            )
        },
    )

    assert {signal["kind"] for signal in signals} == {
        "candidate_status",
        "candidate_risk_level",
        "gate_stop",
    }
    gate_signal = next(signal for signal in signals if signal["kind"] == "gate_stop")
    assert gate_signal["stop_lifecycle_class"] == "review_stop"
    assert gate_signal["repair_strategy_id"] == "operator_review_triage"
    assert gate_signal["recommended_next_safe_action"] == "manual_review_or_targeted_reprocess_plan"
    assert gate_signal["safety_zone"] == "SZ2_EVIDENCE_AND_GATES"


def test_report_orders_false_negative_risk_stops_before_generic_manual_review() -> None:
    missing_url = assess_stop_validity(
        candidate("vhv_gruppe", candidate_url=None, status="discovery", risk_level="medium"),
        {},
        target_location="hannover",
        reviewed_by="jens",
    )
    generic_review = assess_stop_validity(
        candidate("manual_case", status="manual_review_required", risk_level="medium"),
        {},
        target_location="hannover",
        reviewed_by="jens",
    )

    assert missing_url is not None
    assert generic_review is not None

    payload = report_payload(
        [generic_review, missing_url],
        benchmark_label="repair_order",
        target_location="hannover",
        reviewed_by="jens",
    )

    ordered = payload["summary"]["repair_audit_order"]
    assert ordered[0]["company_key"] == "vhv_gruppe"
    assert ordered[0]["dominant_lifecycle_class"] == "false_negative_risk_stop"
    assert ordered[0]["dominant_stop_category"] == "recoverable_url_problem"
    assert payload["items"][0]["candidate"]["company_key"] == "vhv_gruppe"
