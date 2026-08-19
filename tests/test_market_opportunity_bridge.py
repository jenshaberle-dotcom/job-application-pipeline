from pathlib import Path
import subprocess
import sys

from src.search_intelligence.market_opportunity_bridge import (
    MarketOpportunity,
    bridge_outcome_from_exact_status,
    opportunity_geography,
    product_authority_boundary,
    risk_gate_blocks,
)

ROOT = Path(__file__).resolve().parents[1]


def _opportunity(*, location: str | None, remote_signal: str) -> MarketOpportunity:
    return MarketOpportunity(
        opportunity_id=1,
        company_name="Example GmbH",
        title="Machine Learning Engineer",
        observation_channel="linkedin",
        evidence_url=None,
        observed_at=None,
        location=location,
        remote_signal=remote_signal,
    )


def test_remote_germany_observation_maps_to_germany_remote_policy() -> None:
    assert opportunity_geography(
        _opportunity(location="Deutschland (Remote)", remote_signal="remote_possible")
    ) == (None, "Deutschland", "germany_remote")


def test_hannover_observation_keeps_hannover_identity() -> None:
    assert opportunity_geography(
        _opportunity(location="Hannover", remote_signal="onsite_only")
    ) == ("Hannover", "Deutschland", "hannover_explicit")


def test_risk_authority_is_never_overridden() -> None:
    assert risk_gate_blocks(candidate_risk_level="blocked", risk_gate=None)
    assert risk_gate_blocks(
        candidate_risk_level="low",
        risk_gate={"gate_status": "manual_review_required"},
    )
    assert not risk_gate_blocks(
        candidate_risk_level="low",
        risk_gate={"gate_status": "passed"},
    )


def test_exact_vacancy_outcomes_remain_separate_from_product_authority() -> None:
    assert bridge_outcome_from_exact_status("current_vacancy_confirmed")[0] == "verified_active"
    assert bridge_outcome_from_exact_status("inactive_vacancy_confirmed")[0] == "verified_closed"
    assert bridge_outcome_from_exact_status("no_concrete_detail_candidates")[0] == "detail_candidate_required"
    boundary = product_authority_boundary()
    assert boundary["market_evidence_remains_observational"] is True
    assert boundary["silver_write"] is False
    assert boundary["ranking_authority"] is False
    assert boundary["application_authority"] is False


def test_migration_projects_manual_market_evidence_without_granting_authority() -> None:
    migration = (ROOT / "db/migrations/098_create_market_opportunity_verification.sql").read_text(encoding="utf-8")
    assert "gold_market_opportunity_status" in migration
    assert "manual_market_observation" in migration
    assert "FALSE AS ranking_authority" in migration
    assert "FALSE AS application_authority" in migration


def test_runner_reuses_existing_cascade_and_disables_tavily() -> None:
    runner = (ROOT / "scripts/run_market_opportunity_vacancy_bridge.py").read_text(encoding="utf-8")
    assert "run_bridge_for_contender" in runner
    assert "detail_booster.run" in runner
    assert "disable_tavily=True" in runner
    assert "max_tavily_requests=0" in runner
    assert "provider_output_authority" in runner
    assert "approve_market_opportunity_verification" in runner
    assert "INSERT INTO market_opportunity_verification_observations" in runner
    assert "INSERT INTO silver_jobs" not in runner


def test_bridge_cli_entrypoint_runs_as_direct_script() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/run_market_opportunity_vacancy_bridge_cli.py"),
            "--help",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "--opportunity-id" in completed.stdout
    assert "--execute-provider-booster" in completed.stdout
