from __future__ import annotations

import argparse

import subprocess
import sys
from pathlib import Path

from src.search_intelligence.market_sensor_activation_plan import (
    BA_REMOTE_NATIONWIDE_PROFILE_NAME,
    BA_SOURCE_NAME,
    MarketSensorProfile,
    MarketSensorSearchTerm,
    build_ba_remote_nationwide_activation_plan,
    render_activation_sql_draft,
)


def test_build_ba_remote_nationwide_activation_plan_keeps_profile_inactive() -> None:
    profile = MarketSensorProfile(
        id=1,
        profile_name="ba_data_engineer_30629_50km",
        source_name=BA_SOURCE_NAME,
        search_term="Data Engineer",
        search_location="30629",
        search_radius_km=50,
        offer_type=1,
        page_size=10,
        is_active=True,
    )
    terms = (
        MarketSensorSearchTerm(id=1, search_profile_id=1, search_term="Data Engineer", is_active=True),
        MarketSensorSearchTerm(id=2, search_profile_id=1, search_term="Analytics Engineer", is_active=True),
        MarketSensorSearchTerm(id=3, search_profile_id=1, search_term="data engineer", is_active=True),
    )

    plan = build_ba_remote_nationwide_activation_plan((profile,), terms)
    payload = plan.as_dict()

    assert payload["overall_status"] == "review_required"
    assert payload["activation_changes"]["activate_now"] is False
    assert payload["activation_changes"]["pipeline_mutation_now"] is False
    assert payload["proposed_profile"]["profile_name"] == BA_REMOTE_NATIONWIDE_PROFILE_NAME
    assert payload["proposed_profile"]["search_location"] is None
    assert payload["proposed_profile"]["search_radius_km"] is None
    assert payload["proposed_profile"]["is_active"] is False
    assert payload["proposed_search_terms"] == ["Data Engineer", "Analytics Engineer"]
    assert "Every market sensor" in payload["generic_requirement"]


def test_build_ba_remote_nationwide_activation_plan_requires_baseline() -> None:
    plan = build_ba_remote_nationwide_activation_plan((), ())

    payload = plan.as_dict()

    assert payload["overall_status"] == "baseline_missing"
    assert payload["proposed_profile"] is None
    assert payload["activation_changes"]["activate_now"] is False


def test_activation_sql_draft_is_review_only_and_rolls_back() -> None:
    profile = MarketSensorProfile(
        id=1,
        profile_name="ba_data_engineer_30629_50km",
        source_name=BA_SOURCE_NAME,
        search_term="Data Engineer",
        search_location="30629",
        search_radius_km=50,
        offer_type=1,
        page_size=10,
        is_active=True,
    )

    plan = build_ba_remote_nationwide_activation_plan((profile,), ())
    sql = render_activation_sql_draft(plan)

    assert "REVIEW DRAFT ONLY" in sql
    assert "ROLLBACK;" in sql
    assert "COMMIT;" not in sql
    assert "FALSE" in sql
    assert BA_REMOTE_NATIONWIDE_PROFILE_NAME in sql


def test_sensor001b_script_is_directly_executable_from_repo_root() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_sensor001b_ba_remote_nationwide_activation_plan.py",
            "--help",
        ],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Generate SENSOR-001B" in result.stdout

def test_load_ba_state_docker_fallback_returns_profiles_terms_and_access_method(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "run_sensor001b_ba_remote_nationwide_activation_plan.py"

    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "sensor001b_activation_plan_script_under_test",
        script_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    profile = MarketSensorProfile(
        id=1,
        profile_name="ba_data_engineer_30629_50km",
        source_name=BA_SOURCE_NAME,
        search_term="Data Engineer",
        search_location="30629",
        search_radius_km=50,
        offer_type=1,
        page_size=10,
        is_active=True,
    )
    term = MarketSensorSearchTerm(
        id=1,
        search_profile_id=1,
        search_term="Data Engineer",
        is_active=True,
    )

    monkeypatch.setattr(module, "resolve_dsn", lambda explicit_dsn: None)
    monkeypatch.setattr(module, "load_ba_state_with_docker_psql", lambda args: ((profile,), (term,)))

    args = argparse.Namespace(
        dsn=None,
        source_name=BA_SOURCE_NAME,
        no_docker_fallback=False,
    )

    profiles, terms, access_method = module.load_ba_state(args)

    assert profiles == (profile,)
    assert terms == (term,)
    assert access_method == "docker_exec_psql"
