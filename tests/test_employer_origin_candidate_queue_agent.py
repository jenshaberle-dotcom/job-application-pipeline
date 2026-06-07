from __future__ import annotations

from scripts.run_employer_origin_agent_chain import GateReview, REQUIRED_CONNECTOR_ARTIFACT_GATES, connector_artifact_paths
from scripts.run_employer_origin_candidate_queue_agent import (
    CONNECTOR_CANDIDATE_GATE,
    SOURCE_LIFECYCLE_GATE,
    CandidateSummary,
    build_queue,
    classify_queue_item,
    render_markdown_report,
    render_queue,
    report_payload,
    summarize_queue,
    write_reports,
)


def candidate(
    company_key: str = "hdi",
    status: str = "candidate",
    candidate_id: int = 1,
) -> CandidateSummary:
    return CandidateSummary(
        candidate_id=candidate_id,
        company_key=company_key,
        company_name=company_key.upper(),
        source_name_candidate=f"{company_key}:hannover",
        source_family_candidate=company_key,
        status=status,
        risk_level="low",
        latest_gate_order=None,
        latest_gate_name=None,
        blocked_gate_count=0,
        manual_review_gate_count=0,
        passed_gate_count=0,
        total_gate_count=0,
    )


def gate(
    name: str,
    status: str,
    decision: str,
    stop_reason: str | None = None,
    evidence: dict | None = None,
) -> GateReview:
    return GateReview(
        gate_name=name,
        gate_status=status,
        decision=decision,
        stop_reason=stop_reason,
        evidence=evidence or {},
    )


def passed_artifact_gates() -> dict[str, GateReview]:
    gates = {name: gate(name, "passed", "continue") for name in REQUIRED_CONNECTOR_ARTIFACT_GATES}
    gates[CONNECTOR_CANDIDATE_GATE] = gate(
        CONNECTOR_CANDIDATE_GATE,
        "passed",
        "build_connector_candidate",
        evidence={
            "connector_candidate_spec": {
                "detail_evidence": {
                    "detail_urls": ["https://careers.hdi.group/jobs/product-owner-data-platform"]
                }
            }
        },
    )
    return gates


def test_active_controlled_candidate_prioritizes_missing_lifecycle_tracking() -> None:
    item = classify_queue_item(
        candidate("finanz_informatik", status="active_controlled"),
        {},
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=False,
    )

    assert item.next_action == "run_source_lifecycle_tracking"
    assert "run_employer_origin_source_lifecycle_tracking_agent" in (item.command or "")


def test_lifecycle_passed_active_candidate_is_monitor_only() -> None:
    item = classify_queue_item(
        candidate("finanz_informatik", status="active_controlled"),
        {
            SOURCE_LIFECYCLE_GATE: gate(SOURCE_LIFECYCLE_GATE, "passed", "continue"),
            CONNECTOR_CANDIDATE_GATE: gate(
                CONNECTOR_CANDIDATE_GATE,
                "passed",
                "build_connector_candidate",
            ),
            "detail_evidence_gate": gate("detail_evidence_gate", "passed", "continue"),
        },
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=False,
    )

    assert item.next_action == "monitor_source_lifecycle"
    assert item.command is None


def test_blocked_detail_evidence_without_repair_is_manual_review_stop() -> None:
    item = classify_queue_item(
        candidate("hdi"),
        {
            "detail_evidence_gate": gate(
                "detail_evidence_gate",
                "manual_review_required",
                "manual_review_required",
                "no concrete detail URLs",
            )
        },
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=False,
    )

    assert item.next_action == "stop_manual_review_required"
    assert item.command is None


def test_blocked_detail_evidence_with_repair_gets_chain_command() -> None:
    item = classify_queue_item(
        candidate("hdi"),
        {
            "detail_evidence_gate": gate(
                "detail_evidence_gate",
                "manual_review_required",
                "manual_review_required",
                "no concrete detail URLs",
            )
        },
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=True,
    )

    assert item.next_action == "run_detail_evidence_repair"
    assert "--attempt-repair" in (item.command or "")


def test_queue_sorting_prioritizes_lifecycle_then_implementation_then_repair() -> None:
    items = build_queue(
        [
            candidate("hdi", candidate_id=1),
            candidate("finanz_informatik", status="active_controlled", candidate_id=2),
            candidate("rossmann", candidate_id=3),
        ],
        {
            1: {
                "detail_evidence_gate": gate(
                    "detail_evidence_gate",
                    "manual_review_required",
                    "manual_review_required",
                )
            },
            2: {},
            3: passed_artifact_gates(),
        },
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=True,
    )

    assert [item.next_action for item in items] == [
        "run_source_lifecycle_tracking",
        "run_connector_artifact_generator",
        "run_detail_evidence_repair",
    ]


def test_render_queue_contains_actionable_command_when_available() -> None:
    item = classify_queue_item(
        candidate("hdi"),
        {
            "detail_evidence_gate": gate(
                "detail_evidence_gate",
                "manual_review_required",
                "manual_review_required",
            )
        },
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=True,
    )

    text = "\n".join(render_queue([item]))

    assert "Employer-Origin Candidate Queue" in text
    assert "next_action: run_detail_evidence_repair" in text
    assert "command: python -m scripts.run_employer_origin_agent_chain" in text

def test_completed_active_controlled_source_is_monitor_only_and_has_no_command() -> None:
    item = classify_queue_item(
        candidate("finanz_informatik", status="active_controlled"),
        {
            SOURCE_LIFECYCLE_GATE: gate(SOURCE_LIFECYCLE_GATE, "passed", "continue"),
            CONNECTOR_CANDIDATE_GATE: gate(
                CONNECTOR_CANDIDATE_GATE,
                "passed",
                "build_connector_candidate",
            ),
            "detail_evidence_gate": gate("detail_evidence_gate", "passed", "continue"),
        },
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=True,
    )

    assert item.next_action == "monitor_source_lifecycle"
    assert item.command is None

def test_exhausted_detail_evidence_repair_is_not_repeated_even_when_repair_allowed() -> None:
    item = classify_queue_item(
        candidate("hdi"),
        {
            "detail_evidence_gate": gate(
                "detail_evidence_gate",
                "manual_review_required",
                "manual_review_required",
                "bounded repair found no concrete detail pages with profile and target/remote signals",
            )
        },
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=True,
    )

    assert item.next_action == "run_pipeline_stop_reassessment"
    assert item.command is not None
    assert "run_pipeline_stop_reassessment_agent" in item.command
    assert "reassessment" in item.reason


def test_detail_evidence_repair_exhaustion_requires_specific_stop_reason() -> None:
    item = classify_queue_item(
        candidate("hdi"),
        {
            "detail_evidence_gate": gate(
                "detail_evidence_gate",
                "manual_review_required",
                "manual_review_required",
                "temporary network issue",
            )
        },
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=True,
    )

    assert item.next_action == "run_detail_evidence_repair"
    assert item.command is not None


def test_queue_routes_incomplete_s4a_gates_to_build_readiness_before_artifacts() -> None:
    item = classify_queue_item(
        candidate("hdi"),
        {
            "detail_evidence_gate": gate("detail_evidence_gate", "passed", "continue"),
            CONNECTOR_CANDIDATE_GATE: gate(
                CONNECTOR_CANDIDATE_GATE,
                "passed",
                "build_connector_candidate",
            ),
        },
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=True,
    )

    assert item.next_action == "run_connector_build_readiness_agent"
    assert item.command is not None



def test_queue_uses_gate_evidence_to_route_s4a_ready_candidate_to_artifact_generation() -> None:
    item = classify_queue_item(
        candidate("rossmann"),
        passed_artifact_gates(),
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=True,
    )

    assert item.next_action == "run_connector_artifact_generator"
    assert item.command is not None


def test_queue_routes_validated_candidate_to_explicit_approval_stop(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    for path in connector_artifact_paths("rossmann"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# generated", encoding="utf-8")

    gates = passed_artifact_gates()
    gates["connector_validation_gate"] = gate(
        "connector_validation_gate",
        "passed",
        "ready_for_final_approval",
    )

    item = classify_queue_item(
        candidate("rossmann"),
        gates,
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=True,
    )

    assert item.next_action == "stop_explicit_approval_required"
    assert item.command is None


def test_queue_routes_recheckable_inactive_candidate_before_repair_loop() -> None:
    item = classify_queue_item(
        candidate("hdi", status="manual_review_required"),
        {
            "professional_relevance_gate": gate(
                "professional_relevance_gate",
                "manual_review_required",
                "manual_review_required",
                "fehlende fachliche Relevanz im aktuellen Stellenbestand",
            )
        },
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=False,
    )

    assert item.next_action == "run_employer_origin_recheck"
    assert item.command is not None
    assert "run_employer_origin_agent_chain" in item.command

def test_queue_summary_counts_actions_statuses_and_safety_zones() -> None:
    items = build_queue(
        [
            candidate("hdi", candidate_id=1),
            candidate("finanz_informatik", status="active_controlled", candidate_id=2),
        ],
        {
            1: {
                "detail_evidence_gate": gate(
                    "detail_evidence_gate",
                    "manual_review_required",
                    "manual_review_required",
                    "no concrete detail URLs",
                )
            },
            2: {},
        },
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=True,
    )

    summary = summarize_queue(items)

    assert summary["candidate_count"] == 2
    assert summary["actionable_command_count"] == 2
    assert summary["action_counts"] == {
        "run_detail_evidence_repair": 1,
        "run_source_lifecycle_tracking": 1,
    }
    assert summary["safety_zone_counts"] == {"SZ2_EVIDENCE_AND_GATES": 2}
    assert summary["first_actionable_command"].startswith("python -m scripts.run_employer_origin")


def test_queue_report_payload_preserves_read_only_contract_and_candidate_url() -> None:
    queue_item = classify_queue_item(
        candidate("hdi"),
        {"detail_evidence_gate": gate("detail_evidence_gate", "passed", "continue")},
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=False,
    )

    payload = report_payload(
        [queue_item],
        benchmark_label="chain_smoke",
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=False,
    )

    assert payload["campaign"] == "EO Candidate Chain Readiness Plan"
    assert payload["boundary"]["no_connector_registration"] is True
    assert payload["report_contract"]["command"].startswith("planned command")
    assert payload["items"][0]["safety_zone"] == "SZ2_EVIDENCE_AND_GATES"
    assert payload["items"][0]["is_actionable"] is True


def test_render_queue_and_markdown_include_source_url_and_report_contract(tmp_path) -> None:
    summary = candidate("hdi")
    summary = CandidateSummary(
        **{**summary.__dict__, "candidate_url": "https://careers.hdi.group/jobs"}
    )
    queue_item = classify_queue_item(
        summary,
        {"detail_evidence_gate": gate("detail_evidence_gate", "manual_review_required", "manual_review_required")},
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=True,
    )
    payload = report_payload(
        [queue_item],
        benchmark_label="chain smoke",
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=True,
    )

    rendered_queue = "\n".join(render_queue([queue_item]))
    markdown = render_markdown_report(payload)
    json_path, md_path = write_reports(payload, tmp_path, "chain smoke")

    assert "candidate_url: https://careers.hdi.group/jobs" in rendered_queue
    assert "Safety zone" in markdown
    assert "Planned command" in markdown
    assert json_path.name == "chain_smoke_candidate_chain_readiness.json"
    assert md_path.read_text(encoding="utf-8").startswith("# EO Candidate Chain Readiness Plan")


def test_abort_documented_or_blocked_candidates_do_not_receive_repair_command() -> None:
    item = classify_queue_item(
        CandidateSummary(
            **{
                **candidate("ratiodata").__dict__,
                "status": "abort_documented",
                "risk_level": "blocked",
            }
        ),
        {},
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=True,
    )

    assert item.next_action == "run_pipeline_stop_reassessment"
    assert item.command is not None
    assert "run_pipeline_stop_reassessment_agent" in item.command
    assert "blocked operational boundary" in item.reason


def test_summary_counts_manual_review_statuses_and_stop_boundaries() -> None:
    queue_item = classify_queue_item(
        candidate("clarios", status="manual_review_required"),
        {"detail_evidence_gate": gate("detail_evidence_gate", "manual_review_required", "manual_review_required")},
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=True,
    )
    payload = report_payload(
        [queue_item],
        benchmark_label="chain_smoke",
        target_location="hannover",
        reviewed_by="jens",
        allow_repair=True,
    )

    assert payload["summary"]["manual_review_or_stop_count"] == 1
    assert payload["items"][0]["requires_operator_review"] is True
    assert payload["items"][0]["review_boundary_reason"] in {
        "candidate_status=manual_review_required",
        "latest_gate_status=manual_review_required",
        "manual_review_gate_count>0",
    }
