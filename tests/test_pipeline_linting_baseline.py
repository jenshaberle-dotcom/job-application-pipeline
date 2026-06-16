from pathlib import Path
import tomllib


def test_ruff_baseline_is_declared_in_pyproject() -> None:
    pyproject = Path("pyproject.toml")
    assert pyproject.exists()

    payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    ruff = payload["tool"]["ruff"]
    lint = ruff["lint"]

    assert ruff["target-version"] == "py312"
    assert ruff["line-length"] == 100
    assert set(lint["select"]) == {"E4", "E7", "E9", "F"}

    excluded = set(ruff["extend-exclude"])
    assert "exports" in excluded
    assert ".venv" in excluded
    assert "docs/archive/governance/retired-chat-continuation/legacy_code" in excluded
    assert "docs/archive/governance/retired-chat-continuation/legacy_tests" in excluded


def test_ruff_is_a_dev_dependency_not_mcp_hard_gate_yet() -> None:
    requirements = Path("requirements-dev.txt")
    assert requirements.exists()
    lines = [
        line.strip()
        for line in requirements.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    assert any(line.startswith("ruff==") for line in lines)

    docs = Path("docs/reference/development/linting.md")
    assert docs.exists()
    text = docs.read_text(encoding="utf-8")

    assert "not yet a hard MCP target gate" in text
    assert "pytest -q" in text
