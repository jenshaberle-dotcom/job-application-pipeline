from __future__ import annotations

from src.search_intelligence.gate001_initial_gate_review import (
    CandidateSnapshot,
    ProbeResult,
    build_initial_gate_plan,
    host_is_disallowed,
    report_payload,
    security_precheck_url,
)


def candidate(url: str | None = "https://jobs.example.com/") -> CandidateSnapshot:
    return CandidateSnapshot(1, "example", "Example GmbH", "discovery", url)


def reachable_probe() -> ProbeResult:
    return ProbeResult(
        url="https://jobs.example.com/",
        final_url="https://jobs.example.com/",
        reachable=True,
        career_like=True,
        status_code=200,
        title="Example Jobs",
        response_bytes=1000,
        reason="reachable career/job-like URL",
    )


def test_persisted_candidate_url_passes_initial_gates_with_reachable_probe() -> None:
    plan = build_initial_gate_plan(candidate(), probe=reachable_probe(), reviewed_by="jens")

    statuses = {evaluation.gate_name: evaluation.gate_status for evaluation in plan.evaluations}
    assert statuses["source_discovery"] == "passed"
    assert statuses["technical_reachability_gate"] == "passed"
    assert statuses["risk_gate"] == "passed"
    assert plan.recommended_next_safe_action == "run_detail_evidence_discovery_plan"


def test_missing_candidate_url_requires_review_before_initial_gate_review() -> None:
    plan = build_initial_gate_plan(candidate(None), probe=None, reviewed_by="jens")

    assert len(plan.evaluations) == 1
    assert plan.evaluations[0].gate_name == "source_discovery"
    assert plan.evaluations[0].gate_status == "manual_review_required"
    assert plan.recommended_next_safe_action == "manual_review_initial_gate_outcome"


def test_no_probe_defers_technical_and_risk_gates() -> None:
    plan = build_initial_gate_plan(candidate(), probe=None, reviewed_by="jens")

    statuses = {evaluation.gate_name: evaluation.gate_status for evaluation in plan.evaluations}
    assert statuses["source_discovery"] == "passed"
    assert statuses["technical_reachability_gate"] == "deferred"
    assert statuses["risk_gate"] == "deferred"
    assert plan.recommended_next_safe_action == "manual_review_initial_gate_outcome"


def test_security_precheck_blocks_private_hosts() -> None:
    assert host_is_disallowed("127.0.0.1")[0] is True
    assert security_precheck_url("http://169.254.169.254/latest/meta-data")[0] is False
    assert security_precheck_url("https://jobs.example.com/")[0] is True


def test_report_payload_and_markdown_summary() -> None:
    plan = build_initial_gate_plan(candidate(), probe=reachable_probe(), reviewed_by="jens")
    payload = report_payload(benchmark_label="gate001_smoke", plans=[plan])

    assert payload["summary"]["candidate_count"] == 1
    assert payload["summary"]["passed_count"] == 3
    assert payload["summary"]["recommendation_counts"] == {"run_detail_evidence_discovery_plan": 1}
