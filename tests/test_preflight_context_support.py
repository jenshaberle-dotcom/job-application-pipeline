from __future__ import annotations

from pathlib import Path
import json
import zipfile

from src.search_intelligence.preflight_context_support import (
    create_context_bundle,
    execute_read_only_query_specs,
    is_read_only_sql,
)


def test_context_bundle_accepts_relative_and_absolute_repo_paths(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "scripts").mkdir()
    relative_file = repo / "scripts" / "run_example.py"
    absolute_file = repo / "README.md"
    relative_file.write_text("print('ok')\n", encoding="utf-8")
    absolute_file.write_text("# Repo\n", encoding="utf-8")

    result = create_context_bundle(
        repo_root=repo,
        output_dir=Path("exports/context"),
        include_paths=[Path("scripts/run_example.py"), absolute_file],
    )

    assert sorted(result.included) == ["README.md", "scripts/run_example.py"]
    assert result.missing == ()
    assert result.skipped_outside_repo == ()
    with zipfile.ZipFile(result.zip_path) as archive:
        assert "scripts/run_example.py" in archive.namelist()
        assert "README.md" in archive.namelist()
        assert "exports/context/preflight_context_bundle_manifest.json" in archive.namelist()


def test_context_bundle_records_missing_and_skips_outside_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    outside = tmp_path / "outside.txt"
    repo.mkdir()
    outside.write_text("do not include\n", encoding="utf-8")

    result = create_context_bundle(
        repo_root=repo,
        output_dir=Path("exports/context"),
        include_paths=[Path("missing.txt"), outside],
    )

    assert result.included == ()
    assert result.missing == ("missing.txt",)
    assert result.skipped_outside_repo == (str(outside),)
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["boundary"] == "context_bundle_only_not_pipeline_input"


def test_is_read_only_sql_blocks_mutating_statements() -> None:
    assert is_read_only_sql("select * from employer_origin_source_candidates")
    assert is_read_only_sql("WITH x AS (select 1) select * from x")
    assert not is_read_only_sql("delete from raw_jobs")
    assert not is_read_only_sql("select 1; drop table raw_jobs")


class FakeCursor:
    def __init__(self, connection: "FakeConnection") -> None:
        self.connection = connection
        self.rows: list[dict[str, object]] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None

    def execute(self, sql: str) -> None:
        self.connection.executed.append(sql)
        if "missing_table" in sql:
            raise RuntimeError("relation does not exist")
        self.rows = [{"company_key": "hdi"}]

    def fetchall(self) -> list[dict[str, object]]:
        return self.rows


class FakeConnection:
    def __init__(self) -> None:
        self.executed: list[str] = []
        self.rollback_count = 0

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def rollback(self) -> None:
        self.rollback_count += 1


def test_read_only_query_specs_roll_back_after_failed_query_and_continue() -> None:
    connection = FakeConnection()

    result = execute_read_only_query_specs(
        connection,
        {
            "missing": "select * from missing_table",
            "next_ok": "select company_key from employer_origin_source_candidates",
            "blocked": "update raw_jobs set title = title",
        },
    )

    assert result["missing"]["status"] == "error"
    assert result["next_ok"]["status"] == "ok"
    assert result["next_ok"]["rows"] == [{"company_key": "hdi"}]
    assert result["blocked"]["status"] == "blocked_not_read_only"
    assert connection.rollback_count == 1
