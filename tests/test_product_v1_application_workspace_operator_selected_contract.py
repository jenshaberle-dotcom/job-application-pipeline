from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "scripts" / "product_v1_application_workspace_runtime.py"
CONTEXT = ROOT / "src" / "search_intelligence" / "product_v1_application_context.py"
WORKSPACE = ROOT / "src" / "search_intelligence" / "product_v1_application_workspace.py"


def test_runtime_falls_back_from_top5_to_exact_current_job_without_fabricating_rank() -> None:
    source = RUNTIME.read_text(encoding="utf-8")

    assert "FROM gold_product_v1_top_jobs" in source
    assert "FROM gold_product_v1_job_readiness" in source
    assert "target_authority_source = TOP5_AUTHORITY_SOURCE" in source
    assert "target_authority_source = OPERATOR_SELECTED_AUTHORITY_SOURCE" in source
    assert "authority_source=target_authority_source" in source
    assert "current Product job was not found" in source
    assert "operator_selected_job_is_not_top5_authority" in source
    assert "hard_filter_unknown_does_not_become_passed" in source
    assert '"database_writes": False' in source
    assert '"application_writes": 0' in source
    assert '"submission_writes": 0' in source
    assert '"send_actions": 0' in source


def test_operator_selected_authority_keeps_known_hard_filter_failure_closed() -> None:
    context = CONTEXT.read_text(encoding="utf-8")
    workspace = WORKSPACE.read_text(encoding="utf-8")

    assert 'OPERATOR_SELECTED_AUTHORITY_SOURCE = "operator_selected_current_job"' in context
    assert 'reasons.append("known_hard_filter_conflict")' in context
    assert 'reasons.append("operator_selected_target_must_not_claim_top5_rank")' in context
    assert 'reasons.append("application_target_authority_required")' in context
    assert "hard_filter_status != \"passed\"" in context
    assert "authority_source: str = TOP5_AUTHORITY_SOURCE" in workspace
    assert "product_rank = None" in workspace
