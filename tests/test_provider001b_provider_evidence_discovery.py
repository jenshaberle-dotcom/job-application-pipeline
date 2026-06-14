
from __future__ import annotations

from pathlib import Path

from scripts.run_provider001b_provider_evidence_discovery import (
    build_evidence_hits,
    build_report,
    classify_provider_signal,
    extract_urls,
    render_markdown,
    safety_boundary,
    summarize_hits,
    write_reports,
    database_url_from_env,
    DB_ENV_NAMES,
)


def test_provider001b_safety_boundary_is_read_only() -> None:
    boundary = safety_boundary()
    assert boundary["read_only"] is True
    assert boundary["external_requests"] is False
    assert boundary["database_writes"] is False
    assert boundary["pipeline_mutation"] is False
    assert boundary["candidate_or_gate_mutation"] is False
    assert boundary["connector_activation"] is False


def test_provider001b_classifies_common_ats_hosts() -> None:
    signals = classify_provider_signal("https://jobs.personio.de/acme and https://boards.greenhouse.io/acme")
    providers = {signal.provider for signal in signals}
    assert "personio" in providers
    assert "greenhouse" in providers
    assert max(signal.confidence for signal in signals) >= 0.95


def test_provider001b_extracts_urls_without_duplicates() -> None:
    urls = extract_urls("A https://example.com/jobs, B https://example.com/jobs C https://jobs.lever.co/acme")
    assert urls == ["https://example.com/jobs", "https://jobs.lever.co/acme"]


def test_provider001b_builds_hits_and_summary() -> None:
    records = [
        {
            "relation": "employer_origin_source_candidates",
            "row_index": 1,
            "identity": "acme",
            "text": "source_url=https://jobs.personio.de/acme employer_name=Acme",
        },
        {
            "relation": "silver_jobs",
            "row_index": 2,
            "identity": "other",
            "text": "company career page without known provider",
        },
    ]
    hits = build_evidence_hits(records)
    summary = summarize_hits(records, hits)
    assert len(hits) == 1
    assert hits[0]["evidence_strength"] == "strong_provider_url"
    assert summary["records_scanned"] == 2
    assert summary["provider_hit_count"] == 1
    assert summary["providers"]["personio"] == 1
    assert [provider["provider"] for provider in hits[0]["providers"]].count("personio") >= 1


def test_provider001b_report_and_markdown_keep_review_boundary(tmp_path: Path) -> None:
    report = build_report(
        records=[
            {
                "relation": "raw_jobs",
                "row_index": 1,
                "identity": "acme",
                "text": "apply_url=https://apply.workable.com/acme",
            }
        ],
        database_status={
            "status": "pass",
            "reason": "fixture",
            "read_only_transaction": True,
        },
    )
    markdown = render_markdown(report)
    assert report["boundary"] == "review_output_only_not_pipeline_input"
    assert report["next_recommended_work"]["work_item"] == "PROVIDER-001C Provider Coverage Decision Bundle"
    assert "does not approve candidates" in markdown
    written = write_reports(report, tmp_path, "20260613-190000")
    assert Path(written["json"]).exists()
    assert Path(written["markdown"]).exists()


def test_provider001b_db_url_discovers_project_env_alias(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    for name in DB_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("JOB_PIPELINE_DB_DSN", "postgresql://u:p@localhost:5432/app")
    assert database_url_from_env() == "postgresql://u:p@localhost:5432/app"


def test_provider001b_db_url_loads_local_env_file_alias(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    for name in DB_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    (tmp_path / ".env").write_text("JOB_PIPELINE_DB_DSN=postgresql://u:p@localhost:5432/app\n", encoding="utf-8")
    assert database_url_from_env() == "postgresql://u:p@localhost:5432/app"


def test_provider001b_db_url_discovers_docker_compose_postgres(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    for name in DB_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    (tmp_path / "docker-compose.yml").write_text(
        """
services:
  db:
    image: postgres:17
    environment:
      - POSTGRES_USER=pipeline
      - POSTGRES_PASSWORD=pipeline
      - POSTGRES_DB=job_pipeline
    ports:
      - "15432:5432"
""",
        encoding="utf-8",
    )
    assert database_url_from_env() == "postgresql://pipeline:pipeline@localhost:15432/job_pipeline"

