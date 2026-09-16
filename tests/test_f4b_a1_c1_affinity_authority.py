from pathlib import Path


MIGRATION = Path("db/migrations/111_restore_pd051_threshold_and_create_affinity_authority.sql")
AFFINITY_RUNNER = Path("scripts/run_f4b_affinity_authority.py")
APPLY_WORKFLOW = Path(".github/retired-workflows/rcc-blue-cutover-20260916/f4b-a1-c1-apply.yml")
HISTORICAL_TOP5 = Path("scripts/run_product_v1_top5_policy_review.py")
SERVICE = Path("src/search_intelligence/product_v1_service.py")


def test_a1_reaffirms_70_and_fails_closed_on_unexpected_policy_drift() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "current_threshold NOT IN (60.00, 70.00)" in sql
    assert "minimum_quality_score = 70.00" in sql
    assert "product-v1-2026-09-16-affinity-v1" in sql
    assert "F4B_C1_PD052_WEIGHT_DRIFT" in sql


def test_c1_affinity_view_requires_exact_current_binding() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    affinity = sql[sql.index("CREATE OR REPLACE VIEW gold_product_v1_affinity") :]
    assert "review.status = 'active'" in affinity
    assert "review.policy_version = policy.policy_version" in affinity
    assert "review.assessment_updated_at = assessment.updated_at" in affinity
    assert "review.assessment_detail_sha256 = coalesce" in affinity
    assert "'pd-052'::text AS affinity_authority" in affinity


def test_readiness_uses_exact_affinity_but_keeps_hard_filter_gate() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    readiness = sql[sql.index("CREATE OR REPLACE VIEW gold_product_v1_job_readiness") :]
    assert "affinity.affinity_score::numeric AS overall_quality_score" in readiness
    assert "WHEN hard_filter_status = 'failed' THEN 'blocked_hard_filter'" in readiness
    assert "WHEN hard_filter_status = 'unknown'" in readiness
    assert "WHEN overall_quality_score IS NULL THEN 'assessment_required'" in readiness
    assert readiness.index("WHEN hard_filter_status = 'failed'") < readiness.index(
        "WHEN overall_quality_score IS NULL"
    )
    assert "affinity_authority_status" in readiness


def test_c1_preserves_existing_readiness_numeric_types() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "'profile_direction_score')::numeric(6,2)" in sql
    assert "'reliability_focus_score')::numeric(6,2)" in sql
    assert "'data_focus_score')::numeric(6,2)" in sql
    assert "'evidence_quality_score')::numeric(6,2)" in sql
    assert "affinity.affinity_score::numeric AS overall_quality_score" in sql


def test_c1_json_binding_parameters_have_explicit_text_types() -> None:
    source = AFFINITY_RUNNER.read_text(encoding="utf-8")
    assert "'assessment_detail_sha256',CAST(%s AS text)" in source
    assert "'policy_version',CAST(%s AS text)" in source


def test_a1_c1_apply_is_retry_safe_after_exact_migration_success() -> None:
    source = APPLY_WORKFLOW.read_text(encoding="utf-8")
    assert "tracked_target = tracked.get(target)" in source
    assert 'tracked_target.execution_status != "success"' in source
    assert "F4B_A1_C1_MIGRATION_STATE=already_applied" in source
    assert "F4B_A1_C1_UNEXPECTED_PENDING_AFTER_TARGET" in source
    assert '--apply-exact "$TARGET_MIGRATION"' in source


def test_c1_runner_writes_no_fit_combined_or_top5_authority() -> None:
    source = AFFINITY_RUNNER.read_text(encoding="utf-8")
    assert "candidate_fit_writes\": False" in source
    assert "hard_filter_writes\": False" in source
    assert "combined_score_writes\": False" in source
    assert "top5_direct_writes\": False" in source
    assert "provider_or_llm_requests\": 0" in source
    assert "exact_persisted_revision" in source
    assert "affinity_authority\": \"pd-052\"" in source


def test_historical_demo_60_mutation_is_retired() -> None:
    source = HISTORICAL_TOP5.read_text(encoding="utf-8")
    assert "PD-051_REAFFIRMED_70" in source
    assert "HISTORICAL_AUDIT_ONLY" in source
    assert "UPDATE product_v1_ranking_policy" not in source


def test_payload_separates_affinity_fit_and_combined_truth() -> None:
    source = SERVICE.read_text(encoding="utf-8")
    assert 'enriched["affinity_score"]' in source
    assert 'enriched["combined_score"] = None' in source
    assert '"affinity_is_not_candidate_fit": True' in source
    assert '"affinity_is_not_combined_score": True' in source
    assert '"combined_score_authority": False' in source
