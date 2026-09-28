from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
PROFILE = ROOT / ".rcc" / "runner-profiles" / "linux-wsl.json"


def _forbidden_tokens() -> tuple[str, ...]:
    # Construct retired identities from fragments so the guard itself does not
    # preserve searchable copies that can be mistaken for active authority.
    return (
        "job-" + "pipeline-runtime-linux",
        "RCC_JAP_" + "BLUE_ASSIGNMENT_FROZEN",
        "RCC_JAP_" + "LEGACY_DIRECT_ASSIGNMENT_ALLOWED",
        "warm-" + "runner-heartbeat.yml",
        "warm-" + "runner-route.yml",
        "trusted-local-" + "product-campaign.yml",
        "rcc-real-" + "warm-canary.yml",
        ".rcc/" + "runner-contract.json",
        "run_" + "scheduled_pipeline.ps1",
        "rcc-general-linux-01" + "--jap",
        "RCC_" + "PHYSICAL_RUNNER",
        "RCC_" + "FACADE_RUNNER",
    )


def _text_files() -> list[Path]:
    roots = [
        ROOT / ".github",
        ROOT / ".rcc",
        ROOT / "docs" / "current",
        ROOT / "docs" / "planning" / "active",
        ROOT / "scripts",
        ROOT / "tests",
    ]
    result: list[Path] = []
    for base in roots:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in {
                ".md", ".txt", ".json", ".yml", ".yaml", ".py", ".sh", ".ps1"
            }:
                result.append(path)
    return result


def test_jap_has_only_rcc_assigned_workload_target() -> None:
    workflows = sorted(path.name for path in WORKFLOWS.glob("*.yml"))
    assert workflows == ["product-v1-assessment-cohort.yml"]

    workflow = (WORKFLOWS / workflows[0]).read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "runs-on: ${{ fromJSON(inputs.runs_on_json) }}" in workflow
    assert "rcc-assignment-[0-9a-f]{32}" in workflow
    assert "RCC_ASSIGNED_RUNNER" in workflow
    assert "physical_runner:" not in workflow
    assert "facade_runner:" not in workflow
    assert "ubuntu-" not in workflow
    assert "windows-" not in workflow
    assert "rcc-general-linux-0" not in workflow


def test_project_owned_runner_allocation_contract_is_physically_absent() -> None:
    assert not (ROOT / ".rcc" / "runner-contract.json").exists()

    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    assert profile["profile_id"] == "jap-general-linux-warm"
    assert profile["runner_labels"] == []
    assert profile["profile_hash"] == (
        "1419b2268a4daad29640a5871727da63dcb78f96c50e390f16e783228889f14e"
    )


def test_no_retired_runner_authority_survives_code_tests_or_current_docs() -> None:
    offenders: list[str] = []
    tokens = _forbidden_tokens()

    for path in _text_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in tokens:
            if token in text:
                offenders.append(f"{path.relative_to(ROOT)}::{token}")

    assert offenders == []


def test_daily_runtime_requires_rcc_reservation_and_ephemeral_assignment() -> None:
    text = (ROOT / "scripts" / "run_daily_pipeline.sh").read_text(encoding="utf-8")

    assert "RCC_RESERVATION_ID" in text
    assert "RCC_ASSIGNMENT_LABEL" in text
    assert "rcc-assignment-[0-9a-f]{32}" in text
    assert "RCC_RUNTIME_RUNNER_NAME" in text
    assert "rcc-general-linux-0" not in text
