from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_inspect001_repo_db_docs_bundle.py"


def load_module():
    spec = importlib.util.spec_from_file_location("inspect001", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create_minimal_repo(root: Path) -> None:
    for directory in [
        "docs/current",
        "docs/guides",
        "docs/reference",
        "docs/decisions",
        "docs/planning",
        "docs/archive",
        "scripts",
        "migrations",
    ]:
        (root / directory).mkdir(parents=True, exist_ok=True)

    (root / "README.md").write_text("# Root\n", encoding="utf-8")
    (root / "docs" / "README.md").write_text("# Docs\n", encoding="utf-8")
    (root / "scripts" / "run_project_state_snapshot.py").write_text(
        "print('snapshot')\n",
        encoding="utf-8",
    )
    (root / "scripts" / "run_inspect001_repo_db_docs_bundle.py").write_text(
        "print('inspect')\n",
        encoding="utf-8",
    )
    (root / "migrations" / "001_example.sql").write_text(
        "-- example\n",
        encoding="utf-8",
    )


def test_inspect_paths_reports_missing_paths(tmp_path: Path) -> None:
    module = load_module()

    (tmp_path / "docs").mkdir()
    result = module.inspect_paths(
        tmp_path,
        ["README.md", "docs", "missing.txt"],
    )

    assert result["status"] == "warn"
    assert result["present"] == ["docs"]
    assert result["missing"] == ["README.md", "missing.txt"]


def test_build_report_is_read_only_and_skips_db_by_default(tmp_path: Path) -> None:
    module = load_module()
    create_minimal_repo(tmp_path)

    report = module.build_report(root=tmp_path, include_db=False)

    assert report["schema_version"] == "inspect001.repo_db_docs_bundle.v1"
    assert report["safety_boundary"]["read_only"] is True
    assert report["safety_boundary"]["external_requests"] is False
    assert report["safety_boundary"]["database_writes"] is False
    assert report["sections"]["database"]["status"] == "skipped"


def test_render_markdown_contains_core_sections(tmp_path: Path) -> None:
    module = load_module()
    create_minimal_repo(tmp_path)
    report = module.build_report(root=tmp_path, include_db=False)

    markdown = module.render_markdown(report)

    assert "# INSPECT-001A Repo/DB/Docs Inspection Bundle" in markdown
    assert "## Safety boundary" in markdown
    assert "## Documentation structure" in markdown
    assert "## Database" in markdown
    assert "## Next safe action" in markdown


def test_write_reports_creates_json_and_markdown(tmp_path: Path) -> None:
    module = load_module()
    create_minimal_repo(tmp_path)
    report = module.build_report(root=tmp_path, include_db=False)

    output_dir = tmp_path / "exports"
    written = module.write_reports(report, output_dir=output_dir, stamp="20260608-132300")

    json_path = Path(written["json"])
    markdown_path = Path(written["markdown"])

    assert json_path.exists()
    assert markdown_path.exists()
