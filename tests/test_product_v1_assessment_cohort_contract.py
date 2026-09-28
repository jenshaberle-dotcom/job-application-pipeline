from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_product_v1_assessment_cohort.py"
WORKFLOW = ROOT / ".github" / "workflows" / "product-v1-assessment-cohort.yml"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_product_assessment_cohort_is_reusable_not_job_specific() -> None:
    runner = _text(RUNNER)

    assert "job_application_pipeline.product_v1_assessment_cohort.v1" in runner
    assert "--evaluated-target" in runner
    assert "--top5-target" in runner
    assert "--candidate-cap" in runner
    assert "profile_fit_complete" in runner
    assert "profile_fit_decision" in runner
    assert "affinity_authority_status" in runner
    assert "is_employer_origin_review_source" in runner

    for forbidden in (
        "TARGET_IDS",
        "Encavis GmbH",
        "Hornetsecurity GmbH",
        "Computacenter AG",
        "Sopra Steria",
        "Hannover Re",
        "silver_job_id = 646",
        "silver_job_id = 655",
    ):
        assert forbidden not in runner


def test_product_assessment_cohort_keeps_fit_and_ranking_authorities_separate() -> None:
    runner = _text(RUNNER)

    assert '"direct_top5_writes": False' in runner
    assert '"direct_rank_writes": False' in runner
    assert '"hard_filter_operator_auto_pass": False' in runner
    assert '"candidate_fit_and_affinity_remain_separate": True' in runner
    assert '"numeric_candidate_fit_authority_created": False' in runner
    assert '"combined_score_authority_created": False' in runner
    assert "run_product_v1_assessment_cohort" not in runner.replace(
        '"scripts.run_product_v1_assessment_cohort"', ""
    )


def test_product_assessment_cohort_target_is_ten_evaluated_and_exact_five_top_jobs() -> None:
    runner = _text(RUNNER)
    workflow = _text(WORKFLOW)

    assert 'parser.add_argument("--evaluated-target", type=int, default=10)' in runner
    assert 'parser.add_argument("--top5-target", type=int, default=5)' in runner
    assert 'int(final["profile_fit_complete_count"]) >= args.evaluated_target' in runner
    assert 'int(final["profile_fit_passed_count"]) >= args.top5_target' in runner
    assert 'int(final["rankable_job_count"]) >= args.top5_target' in runner
    assert 'int(final["top_job_count"]) == args.top5_target' in runner

    assert "ASSESSMENT_COHORT_EVALUATED_TARGET_MUST_BE_TEN" in workflow
    assert "ASSESSMENT_COHORT_TOP5_TARGET_MUST_BE_FIVE" in workflow
    assert "ASSESSMENT_COHORT_COMPLETE_FIT_LT_10" in workflow
    assert "ASSESSMENT_COHORT_TOP5_NOT_EXACTLY_5" in workflow


def test_product_assessment_cohort_has_readonly_plan_before_apply() -> None:
    workflow = _text(WORKFLOW)

    plan = workflow.index("Read-only plan 10-job Fit cohort")
    apply = workflow.index("Apply existing Product authorities")
    prove = workflow.index("Prove final Product truth")
    assert plan < apply < prove
    assert 'PGOPTIONS="-c default_transaction_read_only=on"' in workflow
    assert "unset PGOPTIONS || true" in workflow
    assert "<!-- jap-product-assessment-cohort:apply:v1 -->" in workflow
    assert "github.event.issue.number == 1113" in workflow
    assert "github.event.comment.author_association == 'OWNER'" in workflow


def test_product_assessment_cohort_uses_rcc_runtime_and_not_public_pip_bootstrap() -> None:
    workflow = _text(WORKFLOW)

    assert "job-pipeline-runtime-linux" in workflow
    assert "Resolve verified RCC runtime context" in workflow
    assert '"capability:postgresql"' in workflow
    assert "ASSESSMENT_COHORT_RCC_RUNTIME=PASS" in workflow
    assert "python3 -m venv" not in workflow
    assert "pip install -r requirements.txt" not in workflow
