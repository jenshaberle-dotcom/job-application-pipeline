from __future__ import annotations

import json
import re
import subprocess
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
        "origin_provider_" + "snapshot_runner",
        "origin_" + "runtime_lease",
        "origin_provider_" + "tools_checklist",
    )


def _text_files() -> list[Path]:
    # Git inventory includes root contracts, src, Windows assets and all docs,
    # including archives. Generated files and local environments are not authority.
    names = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=ROOT
    ).decode("utf-8").split("\0")
    return [ROOT / name for name in names if name and (ROOT / name).is_file()]


def test_jap_has_only_rcc_assigned_workload_target() -> None:
    workflows = sorted(path.name for path in WORKFLOWS.iterdir())
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
    assert "runner_labels" not in profile
    assert "runner_role" not in profile
    assert "routing_group" not in profile
    assert profile["profile_hash"] == (
        "1419b2268a4daad29640a5871727da63dcb78f96c50e390f16e783228889f14e"
    )


def test_no_retired_runner_authority_survives_code_tests_or_current_docs() -> None:
    offenders: list[str] = []
    tokens = _forbidden_tokens()

    for path in _text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError:
            continue
        for token in tokens:
            if token in text:
                offenders.append(f"{path.relative_to(ROOT)}::{token}")

    assert offenders == []


def test_daily_runtime_requires_rcc_reservation_and_ephemeral_assignment() -> None:
    text = (ROOT / "scripts" / "run_daily_pipeline.sh").read_text(encoding="utf-8")

    assert "RCC_RESERVATION_ID" in text
    assert "RCC_ASSIGNMENT_LABEL" in text
    assert "rcc-assignment-[0-9a-f]{32}" in text
    assert "RCC_ASSIGNED_RUNNER" in text
    assert "rcc-general-linux-0" not in text


def test_registered_workloads_match_physical_workflows() -> None:
    contract = json.loads((ROOT / "PROJECT-DRJ.json").read_text(encoding="utf-8"))
    registered = contract["github_actions"]["managed_workflows"]
    assert {entry["path"] for entry in registered} == {
        str(path.relative_to(ROOT)) for path in WORKFLOWS.iterdir() if path.is_file()
    }
    assert all(entry["manual_dispatch"] for entry in registered)


def test_workflow_references_do_not_reanimate_deleted_execution_paths() -> None:
    offenders = []
    for path in _text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError:
            continue
        for reference in re.findall(r"\.github/workflows/[\w.-]+\.ya?ml", text):
            if not (ROOT / reference).is_file():
                offenders.append(f"{path.relative_to(ROOT)}::{reference}")
    assert offenders == []
