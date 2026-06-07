from __future__ import annotations

from pathlib import Path

from scripts.check_governance_drift import collect_governance_drift


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_governance_drift_flags_unregistered_agent_script(tmp_path: Path) -> None:
    _write(tmp_path / "scripts/run_new_magic_agent.py", "print('x')\n")
    _write(tmp_path / "tests/test_new_magic_agent.py", "def test_x(): assert True\n")
    _write(tmp_path / "docs/governance/agent_governance_registry.md", "# Registry\n")

    report = collect_governance_drift(tmp_path, strict=True)

    assert "scripts/run_new_magic_agent.py" in report.unregistered_agent_like_scripts
    assert report.strict_failed is True
    assert any(
        finding.code == "agent_like_script_missing_governance_reference"
        for finding in report.findings
    )


def test_governance_drift_accepts_registered_agent_script(tmp_path: Path) -> None:
    _write(tmp_path / "scripts/run_registered_agent.py", "print('x')\n")
    _write(
        tmp_path / "docs/governance/agent_governance_registry.md",
        "Registered script: run_registered_agent\n",
    )

    report = collect_governance_drift(tmp_path, strict=True)

    assert report.unregistered_agent_like_scripts == []
    assert report.strict_failed is False


def test_governance_drift_default_mode_is_advisory(tmp_path: Path) -> None:
    _write(tmp_path / "scripts/run_new_magic_agent.py", "print('x')\n")
    _write(tmp_path / "docs/governance/agent_governance_registry.md", "# Registry\n")

    report = collect_governance_drift(tmp_path, strict=False)

    assert report.unregistered_agent_like_scripts == ["scripts/run_new_magic_agent.py"]
    assert report.strict_failed is False
