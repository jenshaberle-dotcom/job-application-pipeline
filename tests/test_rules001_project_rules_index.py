from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "run_rules001_validate_index.py"
RULES_PATH = REPO_ROOT / "docs" / "reference" / "governance" / "workflow" / "rules001_project_rules_index.md"


def load_module():
    spec = importlib.util.spec_from_file_location("rules001", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rules_index_contains_required_active_rule_anchors() -> None:
    module = load_module()

    result = module.validate_rules_index(RULES_PATH)

    assert result["schema_version"] == "rules001.index_validation.v1"
    assert result["status"] == "pass"
    assert result["missing_anchor_groups"] == {}
    assert result["safety_boundary"]["read_only"] is True
    assert result["safety_boundary"]["database_writes"] is False


def test_missing_rules_file_fails_closed(tmp_path: Path) -> None:
    module = load_module()

    result = module.validate_rules_index(tmp_path / "missing.md")

    assert result["status"] == "fail"
    assert "rules_file" in result["missing_anchor_groups"]


def test_missing_required_anchor_group_is_reported(tmp_path: Path) -> None:
    module = load_module()
    rules_file = tmp_path / "rules.md"
    rules_file.write_text("# Incomplete\n\nDo not commit directly on main.\n", encoding="utf-8")

    result = module.validate_rules_index(rules_file)

    assert result["status"] == "fail"
    assert "architecture_and_safety" in result["missing_anchor_groups"]
    assert "white_whale" in result["missing_anchor_groups"]


def test_write_report_creates_json_and_markdown(tmp_path: Path) -> None:
    module = load_module()
    result = module.validate_rules_index(RULES_PATH)

    written = module.write_report(result, tmp_path)

    json_path = Path(written["json"])
    markdown_path = Path(written["markdown"])

    assert json_path.exists()
    assert markdown_path.exists()
    assert "rules001.index_validation.v1" in json_path.read_text(encoding="utf-8")
    assert "RULES-001A Index Validation" in markdown_path.read_text(encoding="utf-8")


def test_render_markdown_result_lists_missing_anchors(tmp_path: Path) -> None:
    module = load_module()
    missing_rules = tmp_path / "missing.md"

    result = module.validate_rules_index(missing_rules)
    markdown = module.render_markdown_result(result)

    assert "# RULES-001A Index Validation" in markdown
    assert "Status: `fail`" in markdown
    assert "`rules_file`" in markdown


def test_default_output_dir_is_run_scoped_under_exports() -> None:
    module = load_module()

    output_dir = module.default_output_dir("20260613-123456")

    assert output_dir == Path("exports") / "rules001_index_validation_20260613-123456"
