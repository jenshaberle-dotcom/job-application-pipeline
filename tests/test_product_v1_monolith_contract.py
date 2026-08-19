from pathlib import Path

from src.search_intelligence.product_v1_service import build_product_v1_payload


FOUNDATION_MIGRATION = Path(
    "db/migrations/077_create_product_v1_monolith_foundation.sql"
)
POLICY_MIGRATION = Path(
    "db/migrations/078_activate_product_v1_operator_policy.sql"
)
TRACKING_MIGRATION = Path("db/migrations/054_create_schema_migrations.sql")
MIGRATION_PREP = Path("scripts/prepare_product_v1_runtime_migration.py")
RUNNER = Path("scripts/run_product_v1_monolith.py")
API = Path("scripts/run_product_v1_control_center.py")
FRONTEND = Path("frontend/control-center")


def test_foundation_migration_connects_all_four_product_pillars_without_guessing() -> None:
    sql = FOUNDATION_MIGRATION.read_text(encoding="utf-8")

    assert "current_exclusion_wave_index" in sql
    assert "skip_empty_exclusion_wave" in sql
    assert "product_v1_ranking_policy" in sql
    assert "operator_decision_required" in sql
    assert "job_product_assessments" in sql
    assert "application_source_documents" in sql
    assert "application_draft_requests" in sql
    assert "gold_product_v1_job_readiness" in sql
    assert "gold_product_v1_top_jobs" in sql
    assert "gold_product_v1_application_readiness" in sql
    assert "top_job_limit,\n    minimum_quality_score" in sql
    assert "NULL,\n    NULL" in sql


def test_policy_migration_activates_exact_operator_selected_top5_contract() -> None:
    sql = POLICY_MIGRATION.read_text(encoding="utf-8")

    assert "status = 'approved'" in sql
    assert "top_job_limit = 5" in sql
    assert "top_job_semantics = 'at_most_no_fill'" in sql
    assert "minimum_quality_score = 70.00" in sql
    assert "'profile_direction', 0.40" in sql
    assert "'reliability_focus', 0.25" in sql
    assert "'data_focus', 0.20" in sql
    assert "'evidence_quality', 0.15" in sql
    assert "comparable_score_delta = 3.00" in sql
    assert "score_components_reasons_uncertainties_missing_information" in sql


def test_policy_migration_keeps_current_compensation_local_only() -> None:
    sql = POLICY_MIGRATION.read_text(encoding="utf-8")

    assert "product_v1_hard_filter_policy" in sql
    assert "permanent_employment_required" in sql
    assert "'[\"de\", \"en\"]'::jsonb" in sql
    assert "35.00" in sql
    assert "40.00" in sql
    assert "soft_negotiable_target" in sql
    assert "75000" in sql
    assert "requirements_and_capability_fit_over_title" in sql
    assert "reject_junior_title_with_senior_requirements" in sql
    assert "current_compensation_storage" in sql
    assert "local_runtime_only" in sql
    assert "current_salary_gross_eur" not in sql
    assert "current_compensation_gross_eur" not in sql


def test_runtime_migration_preparation_is_read_only_and_targeted_by_default() -> None:
    source = MIGRATION_PREP.read_text(encoding="utf-8")

    assert "077_create_product_v1_monolith_foundation.sql" in source
    assert "078_activate_product_v1_operator_policy.sql" in source
    assert "apply_product_v1_runtime_migrations_077_078" in source
    assert "if not args.apply" in source
    assert "mode: read_only" in source
    assert "unresolved_predecessors" in source
    assert "no provider call" in source


def test_runtime_migration_uses_a_tracking_mode_allowed_by_schema_contract() -> None:
    source = MIGRATION_PREP.read_text(encoding="utf-8")
    tracking_sql = TRACKING_MIGRATION.read_text(encoding="utf-8")

    assert 'execution_mode="script_apply"' in source
    assert "'script_apply'" in tracking_sql
    assert "product_v1_atomic_apply" not in source


def test_monolith_runner_is_read_only_and_provider_free_by_default() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert 'parser.add_argument("--fetch-stepstone", action="store_true"' in source
    assert 'parser.add_argument("--write-review-state", action="store_true")' in source
    assert 'parser.add_argument("--apply-cooldowns", action="store_true")' in source
    assert '"provider_calls": False' in source
    assert '"application_submission": False' in source
    assert "--write-review-state requires --fetch-stepstone" in source


def test_product_v1_api_has_only_reviewed_final_approval_mutation() -> None:
    source = API.read_text(encoding="utf-8")

    assert 'parsed.path == "/api/v1/product-v1"' in source
    assert 'parsed.path == "/api/v1/source-connectors"' in source
    assert "FINAL_APPROVAL_ACTION_PATH" in source
    assert "parse_final_approval_action_payload" in source
    assert "apply_final_approval_action" in source
    assert "def do_POST" in source
    assert "METHOD_NOT_ALLOWED" in source
    assert '"approval_token"' not in source
    assert "subprocess" not in source
    assert "provider" in source
    assert "rank_product_jobs" in source
    assert "product_v1_hard_filter_policy" in source


def test_payload_exposes_operator_blockers_instead_of_fake_top5() -> None:
    payload = build_product_v1_payload(
        wave_states=[],
        job_readiness=[],
        top_jobs=[],
        ranking_policy={"status": "operator_decision_required"},
        application_readiness=[],
        application_sources=[],
        migration_ready=True,
    )

    blocker_codes = {item["code"] for item in payload["operator_blockers"]}
    assert blocker_codes == {
        "ranking_policy_required",
        "base_cv_required",
        "base_application_letter_required",
    }
    assert payload["top_jobs"] == []
    assert payload["boundaries"]["no_provider_call"] is True
    assert payload["boundaries"]["no_automatic_application"] is True


def test_approved_policies_leave_only_application_source_blockers() -> None:
    payload = build_product_v1_payload(
        wave_states=[],
        job_readiness=[],
        top_jobs=[],
        ranking_policy={"status": "approved"},
        hard_filter_policy={"status": "approved"},
        application_readiness=[],
        application_sources=[],
        migration_ready=True,
    )

    blocker_codes = {item["code"] for item in payload["operator_blockers"]}
    assert blocker_codes == {
        "base_cv_required",
        "base_application_letter_required",
    }
    assert payload["hard_filter_policy"]["status"] == "approved"
    assert (
        payload["boundaries"][
            "current_compensation_is_local_runtime_context_only"
        ]
        is True
    )


def test_react_control_center_consumes_the_product_api() -> None:
    package = (FRONTEND / "package.json").read_text(encoding="utf-8")
    app = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")
    styles = (FRONTEND / "src" / "styles.css").read_text(encoding="utf-8")

    assert '"react"' in package
    assert '"build": "tsc --noEmit && vite build"' in package
    assert 'fetch("/api/v1/product-v1"' in app
    assert "StepStone waves" in app
    assert "Authoritative Top 5" in app
    assert "Application preparation" in app
    assert "Product-level gates" in app
    assert "Draft generation is separate from application submission" in app
    assert "--ocean-950" in styles
    assert ".jobs-workspace" in styles
    assert ".source-workspace" in styles
    assert ".operations-grid" in styles
