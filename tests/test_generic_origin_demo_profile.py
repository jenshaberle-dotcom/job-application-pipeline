from pathlib import Path


SCRIPT = Path("scripts/run_generic_origin_demo_profile.py")


def test_demo_profile_uses_generic_origin_and_stays_non_recurring() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert 'source_name = f"generic_origin:{key}"' in source
    assert 'PROFILE_PREFIX = "demo_generic_origin__"' in source
    assert "is_active = TRUE" in source
    assert "recurring_ingestion_enabled = FALSE" in source
    assert "python -m src.ingest_jobs --profile" in source
    assert "python -m src.run_silver_jobs --source" in source


def test_demo_profile_does_not_promote_global_source_authority() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "UPDATE employer_origin_source_candidates" not in source
    assert "generic_employer_origin_active_sources" not in source
    assert "connector_autonomy_authorization_events" not in source
    assert "scheduler" in source
