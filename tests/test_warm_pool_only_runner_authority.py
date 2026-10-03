from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
DEMAND = ROOT / ".rcc" / "workload-demands.json"
TRIGGERS = ROOT / ".github" / "triggers"


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
        ".rcc/" + "runner-profiles/",
        "jap-general-" + "linux-warm",
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


def test_jap_has_only_current_rcc_assigned_workload_targets() -> None:
    workflows = sorted(path.name for path in WORKFLOWS.iterdir())
    assert workflows == [
        "jap-windows-desktop-host-release.yml",
        "pr-validation.yml",
        "product-v1-assessment-cohort.yml",
        "rcc-general-pool-proof.yml",
    ]

    workflow = (WORKFLOWS / "product-v1-assessment-cohort.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "- self-hosted" in workflow
    assert "${{ inputs.rcc_facade_label }}" in workflow
    assert "${{ inputs.rcc_assignment_label }}" in workflow
    assert "rcc-assignment-proof-[0-9a-f]{32}" in workflow
    assert "RCC_ASSIGNED_RUNNER" in workflow
    assert "runs_on_json" not in workflow
    assert "reservation_id:" not in workflow
    assert "physical_runner:" not in workflow
    assert "facade_runner:" not in workflow
    assert "ubuntu-" not in workflow
    assert "windows-" not in workflow
    assert "rcc-general-linux-0" not in workflow


    pr_workflow = (WORKFLOWS / "pr-validation.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in pr_workflow
    assert "source_sha:" in pr_workflow
    for retired_input in ("pr_number:", "expected_ref:", "expected_head_sha:", "correlation_id:"):
        assert retired_input not in pr_workflow
    assert "rcc_facade_label:" in pr_workflow
    assert "rcc_assignment_label:" in pr_workflow
    assert "- self-hosted" in pr_workflow
    assert "${{ inputs.rcc_facade_label }}" in pr_workflow
    assert "${{ inputs.rcc_assignment_label }}" in pr_workflow
    assert "rcc-assignment-proof-[0-9a-f]{32}" in pr_workflow
    assert "pytest -q" in pr_workflow
    assert "check_documentation_references.py" in pr_workflow
    assert "check_documentation_architecture.py" in pr_workflow
    assert "validate_ci_contract.py" in pr_workflow
    assert '"$PR_PYTHON" -m ruff check' in pr_workflow
    assert "ubuntu-" not in pr_workflow
    assert "windows-" not in pr_workflow
    assert "rcc-general-linux-0" not in pr_workflow
    assert "runs_on_json" not in pr_workflow
    assert "physical_runner:" not in pr_workflow
    assert "facade_runner:" not in pr_workflow


def test_product_release_publisher_is_exact_rcc_general_windows_workload() -> None:
    release = (WORKFLOWS / "jap-windows-desktop-host-release.yml").read_text(
        encoding="utf-8"
    )

    assert "name: JAP product-local Windows release" in release
    assert "workflow_dispatch:" in release
    assert "source_sha:" in release
    assert "rcc_facade_label:" in release
    assert "rcc_assignment_label:" in release
    assert "- self-hosted" in release
    assert "${{ inputs.rcc_facade_label }}" in release
    assert "${{ inputs.rcc_assignment_label }}" in release
    assert "rcc-assignment-proof-[0-9a-f]{32}" in release
    assert "PowerShell 7 fleet baseline missing" in release
    assert "Node 22 capability missing" in release
    assert ".NET 8 capability missing" in release
    assert "RCC runtime context missing" in release
    assert "jap-winapp-product-v" in release
    assert "JAP-Control-Center-Desktop-win-x64.zip" in release
    assert "JAP-Control-Center-Runtime.zip" in release

    for forbidden in (
        "ubuntu-latest",
        "windows-latest",
        "actions/setup-python",
        "actions/setup-node",
        "actions/setup-dotnet",
        "pip install",
        "job-pipeline-runtime-",
        "physical_runner",
        "facade_runner",
        "runs_on_json",
    ):
        assert forbidden not in release


def test_project_owned_runner_allocation_and_profiles_are_physically_absent() -> None:
    assert not (ROOT / ".rcc" / "runner-contract.json").exists()
    assert not (ROOT / ".rcc" / "runner-profiles").exists()

    demand = json.loads(DEMAND.read_text(encoding="utf-8"))
    assert demand["schema_version"] == "jap.rcc_workload_demands.v2"
    assert demand["repository_id"] == 1230805345
    assert demand["repository"] == "jenshaberle-dotcom/job-application-pipeline"

    authority = demand["authority"]
    assert authority["allocation"] == "RCC_AUTO_ONLY"
    assert authority["reservation"] == "RCC_ATOMIC"
    assert authority["physical_selection"] == "RCC_ONLY"
    assert authority["facade_selection"] == "RCC_ONLY"
    assert authority["profile_materialization"] == "RCC_ONLY"
    assert authority["capability_provisioning"] == "RCC_ONLY"
    assert authority["github_hosted_fallback"] is False
    assert authority["broad_project_routing"] is False
    assert authority["ephemeral_assignment_required"] is True
    assert authority["consumer_runner_lifecycle"] is False
    assert authority["consumer_runner_profile_ownership"] is False

    runtime = demand["project_runtime"]["python"]
    assert runtime["version"] == "3.12.14"
    assert runtime["package_set"] == {
        "path": ".rcc/python-package-sets/jap-product-v1.txt",
        "sha256": "da7a156bcab92414a1615e92fa06f85f684f67bc5da4cd226ca6985ac1610bfe",
    }

    assert demand["demand_profiles"] == {
        "linux-base": {
            "platform": "linux-wsl",
            "runtime": ["python-project"],
            "capabilities": [],
        },
        "windows-release": {
            "platform": "windows",
            "runtime": ["python-project"],
            "capabilities": ["dotnet-sdk-8", "node-22"],
        },
    }
    assert demand["workflow_demands"] == {
        "pr-validation.yml": "linux-base",
        "product-v1-assessment-cohort.yml": "linux-base",
        "jap-windows-desktop-host-release.yml": "windows-release",
        "rcc-general-pool-proof.yml": "windows-release",
    }
    package = ROOT / runtime["package_set"]["path"]
    assert package.is_file()
    assert hashlib.sha256(package.read_bytes()).hexdigest() == runtime["package_set"]["sha256"]

    assert demand["ownership"]["runner_profiles"] == "RCC"
    assert demand["ownership"]["allocation"] == "RCC"
    assert demand["ownership"]["qualification"] == "RCC"
    assert demand["workflow_admission"] == {
        "pr-validation.yml": {
            "event": "pull_request",
            "source_binding": "pull_request_head_sha",
            "base_branch": "main",
            "auto_dispatch": True,
            "effect_semantics": "validation-only",
        },
    }


def test_legacy_workflow_trigger_authority_is_physically_absent() -> None:
    trigger_files = sorted(path.name for path in TRIGGERS.iterdir() if path.is_file())
    assert trigger_files == [".gitkeep"]


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

    assert "RCC_ASSIGNMENT_LABEL" in text
    assert "rcc-assignment-proof-[0-9a-f]{32}" in text
    assert '${RCC_ASSIGNMENT_LABEL#rcc-assignment-proof-}' in text
    assert "RCC_ASSIGNED_RUNNER" in text
    assert "rcc-general-linux-0" not in text


def test_registered_workloads_match_physical_workflows() -> None:
    contract = json.loads((ROOT / "PROJECT-DRJ.json").read_text(encoding="utf-8"))
    registered = contract["github_actions"]["managed_workflows"]
    assert {entry["path"] for entry in registered} == {
        str(path.relative_to(ROOT)) for path in WORKFLOWS.iterdir() if path.is_file()
    }
    assert all(entry["manual_dispatch"] for entry in registered)
    assert len(registered) == len({entry["path"] for entry in registered})


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


def test_pool_proof_fails_the_step_when_hardcut_tests_fail() -> None:
    proof = (WORKFLOWS / "rcc-general-pool-proof.yml").read_text()
    assert "pytest -q tests/test_warm_pool_only_runner_authority.py\n          if ($LASTEXITCODE -ne 0) { throw 'RCC source hardcut proof failed' }" in proof
