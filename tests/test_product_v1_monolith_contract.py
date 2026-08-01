from pathlib import Path

from src.search_intelligence.product_v1_service import build_product_v1_payload


MIGRATION = Path("db/migrations/077_create_product_v1_monolith_foundation.sql")
RUNNER = Path("scripts/run_product_v1_monolith.py")
API = Path("scripts/run_product_v1_control_center.py")
FRONTEND = Path("frontend/control-center")


def test_migration_connects_all_four_product_pillars_without_choosing_open_policy() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

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


def test_monolith_runner_is_read_only_and_provider_free_by_default() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert 'parser.add_argument("--fetch-stepstone", action="store_true"' in source
    assert 'parser.add_argument("--write-review-state", action="store_true")' in source
    assert 'parser.add_argument("--apply-cooldowns", action="store_true")' in source
    assert '"provider_calls": False' in source
    assert '"application_submission": False' in source
    assert "--write-review-state requires --fetch-stepstone" in source


def test_product_v1_api_has_no_mutating_route() -> None:
    source = API.read_text(encoding="utf-8")

    assert 'parsed.path == "/api/v1/product-v1"' in source
    assert "def do_POST" in source
    assert "METHOD_NOT_ALLOWED" in source
    assert "read-only" in source
    assert "subprocess" not in source
    assert "provider" in source


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


def test_react_control_center_consumes_the_read_only_product_api() -> None:
    package = (FRONTEND / "package.json").read_text(encoding="utf-8")
    app = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")
    styles = (FRONTEND / "src" / "styles.css").read_text(encoding="utf-8")

    assert '"react"' in package
    assert '"build": "tsc -b && vite build"' in package
    assert 'fetch("/api/v1/product-v1"' in app
    assert "StepStone Waves" in app
    assert "Top 5" in app
    assert "CV & application-letter assistant" in app
    assert "Operator gate" in app
    assert "--ocean-950" in styles
    assert "prefers-reduced-motion" in styles
