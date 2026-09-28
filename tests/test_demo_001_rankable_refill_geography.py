from __future__ import annotations

from scripts.run_demo_001_rankable_refill_apply import _selected_candidates
from scripts.run_demo_001_rankable_refill_scout import _authoritative_geography
from src.job_lifecycle_health import OUTCOME_SEEN_ACTIVE


def _candidate(*, silver_job_id: int, geography_eligible: bool) -> dict[str, object]:
    return {
        "silver_job_id": silver_job_id,
        "live_outcome": OUTCOME_SEEN_ACTIVE,
        "role_relevant": True,
        "geography_eligible": geography_eligible,
        "candidate_fact_matches": [
            {
                "fact_key": "training.data-engineering.python-sql",
                "matched_capability_tags": ["sql"],
            }
        ],
    }


def test_refill_selection_excludes_explicit_outside_germany_candidate() -> None:
    rows = [
        _candidate(silver_job_id=654, geography_eligible=False),
        _candidate(silver_job_id=646, geography_eligible=True),
    ]

    selected = _selected_candidates(rows, candidate_cap=10)

    assert [row["silver_job_id"] for row in selected] == [646]


def test_refill_scout_persists_geography_gate_and_source_fields() -> None:
    source = open(
        "scripts/run_demo_001_rankable_refill_scout.py",
        encoding="utf-8",
    ).read()

    assert "readiness.city" in source
    assert "readiness.country" in source
    assert "readiness.work_model" in source
    assert "readiness.commute_minutes" in source
    assert "REFILL_GEOGRAPHY_BUCKETS" in source
    assert '"geography_eligible": geography_eligible' in source
    assert 'and row["geography_eligible"]' in source
    assert '"positive_profile_geography_required_for_refill": True' in source
    assert '"geography_review_required_excluded": True' in source
    assert '"explicit_outside_germany_excluded": True' in source


def test_origin_location_country_excludes_explicit_mexico_even_when_legacy_is_unknown() -> None:
    signal = _authoritative_geography(
        {
            "city": None,
            "country": None,
            "work_model": None,
            "commute_minutes": None,
            "origin_locations": [
                {
                    "city": "San Pedro Garza Garcia",
                    "country_code": "MX",
                    "is_primary": True,
                    "evidence_source": "generic_origin_schema_job_location",
                }
            ],
        }
    )

    assert signal.bucket == "outside_germany"
    assert signal.eligible_for_bounded_pool is False
    assert signal.reason == "structured_origin_locations_outside_germany"


def test_germany_location_without_remote_hannover_or_commute_stays_review_required() -> None:
    signal = _authoritative_geography(
        {
            "origin_locations": [
                {"city": "London", "country_code": "GB"},
                {"city": "Berlin", "country_code": "DE"},
            ]
        }
    )

    assert signal.bucket == "commute_or_geography_review_required"
    assert signal.eligible_for_bounded_pool is True
    assert signal.reason == "structured_germany_location_without_hannover_remote_or_commute"


def test_structured_hannover_location_is_positive_profile_geography() -> None:
    signal = _authoritative_geography(
        {
            "origin_locations": [
                {"city": "Hannover", "country_code": "DE"},
            ]
        }
    )

    assert signal.bucket == "hannover_explicit"
    assert signal.eligible_for_bounded_pool is True


def test_structured_bundesweit_location_is_germany_remote_profile_geography() -> None:
    signal = _authoritative_geography(
        {
            "origin_locations": [
                {"city": "Bundesweit", "country_code": "DE"},
            ]
        }
    )

    assert signal.bucket == "germany_remote"
    assert signal.eligible_for_bounded_pool is True


def test_scout_queries_persisted_origin_location_authority() -> None:
    source = open(
        "scripts/run_demo_001_rankable_refill_scout.py",
        encoding="utf-8",
    ).read()

    assert "FROM silver_job_locations locations" in source
    assert "origin_location_sidecar_precedes_legacy_geography" in source
    assert "_authoritative_geography(row)" in source
