from pathlib import Path


def test_approval_gated_connector_build_agent_uses_shared_database_config() -> None:
    text = Path("scripts/run_approval_gated_connector_build_agent.py").read_text(encoding="utf-8")

    assert "from src.config import get_database_config" in text
    assert "psycopg.connect(**get_database_config())" in text
    assert "DatabaseConfig.dsn()" not in text
    assert "os.environ[" not in text


def test_approval_gated_connector_build_agent_reads_build_queue_evidence() -> None:
    text = Path("scripts/run_approval_gated_connector_build_agent.py").read_text(encoding="utf-8")

    assert "def load_build_queue_evidence" in text
    assert "gold_connector_build_candidate_queue" in text
    assert "recommended_command_or_review" in text
    assert "build_queue_evidence=build_queue_evidence" in text


def test_fallback_investigation_spec_uses_build_queue_evidence() -> None:
    text = Path("scripts/run_approval_gated_connector_build_agent.py").read_text(encoding="utf-8")

    assert "sample_job_urls" in text
    assert '"origin_source"' in text
    assert '"detail_urls": sample_job_urls' in text
    assert "queue.get(\"queue_reason\")" in text


def test_approval_gated_connector_build_agent_overwrite_allows_regeneration() -> None:
    text = Path("scripts/run_approval_gated_connector_build_agent.py").read_text(encoding="utf-8")

    assert "existing_artifacts_blocked = artifact_files_exist(preliminary) and not args.overwrite" in text
    assert "artifact_files_exist=existing_artifacts_blocked" in text
