from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm
from src.search_intelligence.market_sensor_controlled_activation import (
    BA_LOCAL_PROFILE_NAME,
    BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME,
    BA_SOURCE_NAME,
    EXPECTED_BA_REMOTE_TERMS,
    MarketSensorProfileState,
    MarketSensorTermState,
)
from src.search_intelligence.sensor001e_ba_remote_bounded_sample_execution import (
    build_sensor001e_bounded_sample_execution,
)


class FakeConnector:
    source_name = BA_SOURCE_NAME

    def fetch_jobs(self, profile: SearchProfile, search_term: SearchTerm):
        return (
            [
                RawJobRecord(
                    source_name=BA_SOURCE_NAME,
                    source_url="ba://1",
                    external_job_id=f"{search_term.search_term}-1",
                    raw_data={"job": {"titel": f"{search_term.search_term} Remote Data Engineer", "arbeitgeber": "New Remote GmbH", "arbeitsort": "Remote"}},
                ),
                RawJobRecord(
                    source_name=BA_SOURCE_NAME,
                    source_url="ba://2",
                    external_job_id=f"{search_term.search_term}-2",
                    raw_data={"job": {"titel": "Pflegefachkraft", "arbeitgeber": "Known AG", "arbeitsort": "Hannover"}},
                ),
            ],
            f"https://example.invalid?q={search_term.search_term}",
        )


def local_profile() -> MarketSensorProfileState:
    return MarketSensorProfileState(
        id=1,
        profile_name=BA_LOCAL_PROFILE_NAME,
        source_name=BA_SOURCE_NAME,
        search_term="Data Engineer",
        search_location="30629",
        search_radius_km=50,
        offer_type=1,
        page_size=10,
        is_active=True,
    )


def profile() -> MarketSensorProfileState:
    return MarketSensorProfileState(
        id=20,
        profile_name=BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME,
        source_name=BA_SOURCE_NAME,
        search_term="Data Engineer",
        search_location=None,
        search_radius_km=None,
        offer_type=1,
        page_size=10,
        is_active=False,
    )


def term(value: str) -> MarketSensorTermState:
    return MarketSensorTermState(
        profile_name=BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME,
        search_term=value,
        is_active=True,
    )


def test_sensor001e_requires_explicit_execution_approval() -> None:
    report = build_sensor001e_bounded_sample_execution(
        profiles=(local_profile(), profile()),
        terms=tuple(term(value) for value in EXPECTED_BA_REMOTE_TERMS),
        connector=FakeConnector(),
        existing_raw_job_lookup=lambda source_name, external_job_id: False,
        max_terms=2,
        execute_approved=False,
    ).as_dict()

    assert report["overall_status"] == "approval_required"
    assert report["safety_boundary"]["external_requests"] is False
    assert report["term_results"] == []


def test_sensor001e_executes_bounded_sample_without_db_write_boundary() -> None:
    report = build_sensor001e_bounded_sample_execution(
        profiles=(local_profile(), profile()),
        terms=tuple(term(value) for value in EXPECTED_BA_REMOTE_TERMS),
        connector=FakeConnector(),
        existing_raw_job_lookup=lambda source_name, external_job_id: external_job_id.endswith("-2"),
        known_company_keys={"known-ag"},
        max_terms=1,
        execute_approved=True,
    ).as_dict()

    assert report["overall_status"] == "sample_executed"
    assert report["sample_terms"] == ["Data Engineer"]
    assert report["metrics"]["total_loaded_by_term"] == {"Data Engineer": 2}
    assert report["metrics"]["inserted_count_by_term"] == {"Data Engineer": 1}
    assert report["metrics"]["duplicate_count_by_term"] == {"Data Engineer": 1}
    assert report["metrics"]["remote_signal_count"] == 1
    assert report["metrics"]["local_or_hannover_overlap_count"] == 1
    assert report["metrics"]["profile_relevant_title_count"] == 1
    assert report["metrics"]["irrelevant_title_count"] == 1
    assert report["safety_boundary"]["database_writes"] is False
    assert report["safety_boundary"]["bronze_silver_gold_mutation"] is False


def test_sensor001e_script_is_directly_executable_from_repo_root() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_sensor001e_ba_remote_bounded_sample_execution.py",
            "--help",
        ],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "SENSOR-001E" in result.stdout
