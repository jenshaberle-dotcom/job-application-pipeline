from pathlib import Path

from src.search_intelligence.successfactors_locations import (
    extract_successfactors_locations,
    parse_location_field,
)


MIGRATION = Path("db/migrations/086_create_silver_job_locations.sql").read_text(
    encoding="utf-8"
)
RUNNER = Path("scripts/run_eon_location_projection.py").read_text(
    encoding="utf-8"
)


def location_pairs(text: str) -> tuple[tuple[str, str], ...]:
    return tuple(
        (location.city, location.country)
        for location in extract_successfactors_locations(text)
    )


def test_extracts_exact_eon_multi_location_metadata() -> None:
    text = (
        "What you need to know: Job Req ID: 245124 Contract type: Permanent "
        "Working time: Part or Full time Company: E.ON Digital Technology GmbH "
        "Location: Essen, Hannover, München Function area: IT/Digital; Consulting"
    )

    assert location_pairs(text) == (
        ("Essen", "DE"),
        ("Hannover", "DE"),
        ("München", "DE"),
    )


def test_extracts_country_paired_successfactors_footer_and_deduplicates() -> None:
    text = (
        "Location: Essen, Hannover, München Function area: IT/Digital "
        "Location: Essen, DE Hannover, DE München, DE"
    )

    assert location_pairs(text) == (
        ("Essen", "DE"),
        ("Hannover", "DE"),
        ("München", "DE"),
    )


def test_parser_does_not_guess_locations_from_unlabelled_prose() -> None:
    text = (
        "We collaborate across Essen, Hannover and München. "
        "Enjoy hybrid work from a flexible location."
    )

    assert extract_successfactors_locations(text) == ()


def test_parser_rejects_non_city_work_model_values() -> None:
    assert parse_location_field("Remote") == ()
    assert parse_location_field("Hybrid") == ()
    assert parse_location_field("Home Office") == ()


def test_migration_preserves_legacy_city_and_enforces_location_identity() -> None:
    assert "CREATE TABLE IF NOT EXISTS silver_job_locations" in MIGRATION
    assert "REFERENCES silver_jobs(id) ON DELETE CASCADE" in MIGRATION
    assert "uq_silver_job_locations_identity" in MIGRATION
    assert "uq_silver_job_locations_one_primary" in MIGRATION
    assert "UPDATE silver_jobs" not in MIGRATION
    assert "INSERT INTO silver_job_locations" not in MIGRATION


def test_runner_is_exact_idempotent_and_side_effect_bounded() -> None:
    assert "EXPECTED_RAW_JOB_ID = 26342" in RUNNER
    assert "EXPECTED_SILVER_JOB_ID = 466" in RUNNER
    assert 'EXPECTED_LEGACY_CITY = "Essen"' in RUNNER
    assert 'APPROVAL_TOKEN = PROJECTION_KEY' in RUNNER
    assert "is_authorized_pilot_raw_data" in RUNNER
    assert "ON CONFLICT DO NOTHING" in RUNNER
    assert "pg_advisory_xact_lock" in RUNNER
    assert '"network_requests": 0' in RUNNER
    assert '"provider_requests": 0' in RUNNER
    assert '"scheduler_changed": False' in RUNNER
    assert '"connector_activated": False' in RUNNER
    assert '"legacy_silver_city_changed": False' in RUNNER
    assert '"ranking_scores_created": False' in RUNNER
    assert '"hard_filter_decision_created": False' in RUNNER
    assert "requests.get" not in RUNNER
