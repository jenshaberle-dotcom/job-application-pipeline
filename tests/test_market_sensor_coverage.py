from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

from src.search_intelligence.market_sensor_coverage import (
    REMOTE_NATIONWIDE_INTENT,
    MarketSensorProfile,
    assess_all_market_sensors,
    assess_market_sensor_coverage,
    supports_remote_nationwide_target,
)


def test_ba_hannover_only_sensor_has_remote_nationwide_gap() -> None:
    profiles = (
        MarketSensorProfile(
            profile_key="ba_data_engineer_30629_50km",
            source_name="bundesagentur_fuer_arbeit",
            search_location="Hannover",
            search_radius_km=50,
            search_terms=("Data Engineer", "Analytics Engineer"),
        ),
    )

    assessment = assess_market_sensor_coverage("bundesagentur_fuer_arbeit", profiles)

    assert assessment.status == "gap_detected"
    assert assessment.local_target.status == "covered"
    assert assessment.remote_nationwide_target.intent == REMOTE_NATIONWIDE_INTENT
    assert assessment.remote_nationwide_target.status == "missing"
    assert "missing_germany_wide_remote_options_profile" in assessment.coverage_gaps
    assert assessment.next_action == "design_bounded_remote_nationwide_validation_profile_before_activation"


def test_remote_location_profile_covers_germany_wide_remote_options() -> None:
    profile = MarketSensorProfile(
        profile_key="personio_eraneos_data_engineer_remote",
        source_name="personio:eraneos",
        search_location="remote",
        search_terms=("Data Engineer",),
    )

    assert supports_remote_nationwide_target(profile) is True


def test_inactive_remote_profile_does_not_cover_remote_options() -> None:
    profile = MarketSensorProfile(
        profile_key="sensor_data_engineer_remote",
        source_name="example_sensor",
        search_location="remote",
        search_terms=("Data Engineer",),
        is_active=False,
    )

    assessment = assess_market_sensor_coverage("example_sensor", (profile,))

    assert assessment.status == "gap_detected"
    assert "no_active_market_sensor_profile" in assessment.coverage_gaps
    assert "missing_germany_wide_remote_options_profile" in assessment.coverage_gaps


def test_generic_market_sensor_passes_when_local_and_remote_profiles_exist() -> None:
    profiles = (
        MarketSensorProfile(
            profile_key="example_data_engineer_hannover",
            source_name="example_sensor",
            search_location="Hannover",
            search_terms=("Data Engineer",),
        ),
        MarketSensorProfile(
            profile_key="example_data_engineer_deutschland_remote",
            source_name="example_sensor",
            search_location="Deutschland remote",
            search_terms=("Data Engineer", "Homeoffice"),
        ),
    )

    assessment = assess_market_sensor_coverage("example_sensor", profiles)

    assert assessment.status == "pass"
    assert assessment.coverage_gaps == ()
    assert assessment.next_action == "monitor_sensor_value_and_overlap"


def test_assess_all_market_sensors_keeps_requirement_generic() -> None:
    profiles = (
        MarketSensorProfile(
            profile_key="ba_data_engineer_30629_50km",
            source_name="bundesagentur_fuer_arbeit",
            search_location="Hannover",
        ),
        MarketSensorProfile(
            profile_key="stepstone_data_engineer_remote_deutschland",
            source_name="stepstone",
            search_location="Deutschland remote",
        ),
    )

    assessments = assess_all_market_sensors(profiles)

    assert [assessment.source_name for assessment in assessments] == [
        "bundesagentur_fuer_arbeit",
        "stepstone",
    ]
    assert all(assessment.remote_nationwide_target.intent == REMOTE_NATIONWIDE_INTENT for assessment in assessments)

def test_validation_script_is_directly_executable_from_repo_root() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_sensor001a_market_sensor_coverage_validation.py",
            "--help",
        ],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Validate generic market-sensor" in result.stdout

def test_validation_script_reports_database_unavailable_without_traceback(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "run_sensor001a_market_sensor_coverage_validation.py"

    spec = importlib.util.spec_from_file_location(
        "sensor001a_validation_script_under_test",
        script_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def raise_operational_error(_dsn: str):
        raise module.psycopg.OperationalError("simulated database unavailable")

    monkeypatch.setattr(module.psycopg, "connect", raise_operational_error)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_sensor001a_market_sensor_coverage_validation.py",
            "--source-name",
            "bundesagentur_fuer_arbeit",
            "--output-dir",
            str(tmp_path),
        ],
    )

    exit_code = module.main()
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "overall_status=db_unavailable" in captured.out
    assert "database_error=OperationalError: simulated database unavailable" in captured.out
    assert "Traceback" not in captured.err
    assert list(tmp_path.glob("sensor001a_market_sensor_coverage_validation_*.json"))
    assert list(tmp_path.glob("sensor001a_market_sensor_coverage_validation_*.md"))
