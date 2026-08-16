from __future__ import annotations

from pathlib import Path


REPOSITORY = Path("src/ingestion/repository.py")


def repository_source() -> str:
    return REPOSITORY.read_text(encoding="utf-8")


def test_observation_write_persists_current_projection_hash_and_contract() -> None:
    source = repository_source()

    assert "evidence = recurring_observation_evidence(record)" in source
    assert "evidence_hash = recurring_observation_evidence_hash(record)" in source
    assert "normalized_evidence," in source
    assert "normalized_evidence_hash," in source
    assert "evidence_contract_version," in source
    assert "%s::jsonb" in source
    assert "json.dumps(evidence, ensure_ascii=False)" in source
    assert "normalized_evidence = EXCLUDED.normalized_evidence" in source
    assert "normalized_evidence_hash = EXCLUDED.normalized_evidence_hash" in source
    assert "evidence_contract_version = EXCLUDED.evidence_contract_version" in source
    assert "RECURRING_OBSERVATION_EVIDENCE_CONTRACT_VERSION" in source


def test_bronze_duplicate_write_semantics_remain_do_nothing() -> None:
    source = repository_source()
    save_raw_job = source.split("def save_raw_job(", maxsplit=1)[1].split(
        "def find_existing_raw_job_id(", maxsplit=1
    )[0]

    assert "ON CONFLICT (source_name, external_job_id)" in save_raw_job
    assert "DO NOTHING" in save_raw_job
    assert "DO UPDATE" not in save_raw_job
    assert "content_hash" not in save_raw_job


def test_observation_evidence_write_does_not_grant_product_authority() -> None:
    source = repository_source()
    save_observation = source.split("def save_job_observation(", maxsplit=1)[1].split(
        "def finish_ingestion_run(", maxsplit=1
    )[0]

    for forbidden in (
        "silver_jobs",
        "job_lifecycle_health",
        "ranking",
        "application",
        "source_activation",
        "scheduler",
    ):
        assert forbidden not in save_observation.casefold()
