from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_product_v1_assessment_cohort.py"
WORKFLOW = ROOT / ".github" / "workflows" / "product-v1-assessment-cohort.yml"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_product_assessment_cohort_is_generic_current_truth() -> None:
    runner = _text(RUNNER)

    assert "job_application_pipeline.product_v1_assessment_cohort.v1" in runner
    assert "--evaluated-target" in runner
    assert "--top5-target" in runner
    assert "--candidate-cap" in runner
    assert '"selection_mode": "bounded_current_product_truth"' in runner
    assert "authorized_recurring_employer_origin_sources" in runner
    assert "is_employer_origin_review_source" in runner
    assert "_selected_candidates" in runner

    for forbidden in (
        "TARGET_IDS",
        "Encavis GmbH",
        "Hornetsecurity GmbH",
        "Computacenter AG",
        "Sopra Steria",
        "Hannover Re",
    ):
        assert forbidden not in runner


def test_product_assessment_keeps_fit_affinity_gates_and_ranking_separate() -> None:
    runner = _text(RUNNER)

    assert '"direct_top5_writes": False' in runner
    assert '"direct_rank_writes": False' in runner
    assert '"hard_filter_operator_auto_pass": False' in runner
    assert '"top5_must_be_subset_of_selected_cohort": True' in runner
    assert '"candidate_fit_and_affinity_remain_separate": True' in runner
    assert '"candidate_fit_is_job_skills_vs_cv_skills": True' in runner
    assert '"numeric_candidate_fit_authority_created": True' in runner
    assert '"all_selected_require_numeric_candidate_fit": True' in runner
    assert '"all_selected_require_authoritative_affinity": True' in runner
    assert '"combined_score_authority_created": False' in runner


def test_assessment_cohort_size_is_bounded_but_not_demo_fixed() -> None:
    runner = _text(RUNNER)
    workflow = _text(WORKFLOW)

    assert 'parser.add_argument("--evaluated-target", type=int, default=10)' in runner
    assert 'parser.add_argument("--candidate-cap", type=int, default=10)' in runner
    assert "args.candidate_cap == args.evaluated_target" in runner
    assert 'int(final["candidate_fit_authoritative_count"]) >= args.evaluated_target' in runner
    assert 'int(final["affinity_authoritative_count"]) >= args.evaluated_target' in runner
    assert 'int(final["top_job_count"]) == args.top5_target' in runner

    assert 'test "$EVALUATED_TARGET" = "10"' not in workflow
    assert 'test "$CANDIDATE_CAP" = "10"' not in workflow
    assert 'test "$CANDIDATE_CAP" -eq "$EVALUATED_TARGET"' in workflow
    assert "ASSESSMENT_COHORT_CANDIDATE_FIT_BELOW_TARGET" in workflow
    assert "ASSESSMENT_COHORT_AFFINITY_BELOW_TARGET" in workflow
    assert "ASSESSMENT_COHORT_TOP5_COUNT_MISMATCH" in workflow


def test_assessment_cohort_has_readonly_plan_before_apply_and_uses_rcc() -> None:
    workflow = _text(WORKFLOW)

    plan = workflow.index("Read-only plan Product assessment cohort")
    apply = workflow.index("Apply existing Product authorities")
    prove = workflow.index("Prove final Product truth")
    assert plan < apply < prove
    assert 'PGOPTIONS="-c default_transaction_read_only=on"' in workflow
    assert "unset PGOPTIONS || true" in workflow
    assert "workflow_dispatch:" in workflow
    assert "Prove exact RCC assignment handoff" in workflow
    assert "- self-hosted" in workflow
    assert "${{ inputs.rcc_facade_label }}" in workflow
    assert "${{ inputs.rcc_assignment_label }}" in workflow
    assert "rcc-assignment-proof-[0-9a-f]{32}" in workflow
    assert "Resolve verified RCC runtime context" in workflow
    assert '"capability:postgresql"' in workflow
    assert "python3 -m venv" not in workflow
    assert "pip install -r requirements.txt" not in workflow
