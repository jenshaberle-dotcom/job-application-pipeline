from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.resolve_rcc_runtime_context import resolve


ROOT = Path(__file__).resolve().parents[1]
IDENTITY = {
    "repository_id": 1230805345,
    "repository": "jenshaberle-dotcom/job-application-pipeline",
    "runner": "assigned-facade",
    "source_sha": "a" * 40,
}


def projection() -> dict:
    # Demand-v2 executor projection has neither CheckoutRoot nor legacy Checks.
    return {
        "RepositoryId": IDENTITY["repository_id"],
        "Repository": IDENTITY["repository"],
        "RunnerName": IDENTITY["runner"],
        "Platform": "linux-wsl",
        "SourceSha": IDENTITY["source_sha"],
        "Status": "PASS",
        "PrimaryFailure": "",
        "Interpreter": "/content-addressed/runtime/bin/python",
        "ProfileId": "assigned-profile",
        "ProfileHash": "b" * 64,
    }


def test_content_addressed_interpreter_is_independent_of_source_checkout() -> None:
    assert resolve(projection(), **IDENTITY) == "/content-addressed/runtime/bin/python"


def windows_projection() -> dict:
    context = projection()
    context.update(Platform="windows", Interpreter=r"C:\RCC\runtime\python.exe")
    return context


def test_windows_context_accepts_absolute_content_addressed_interpreter() -> None:
    assert resolve(windows_projection(), **IDENTITY, platform="windows") == r"C:\RCC\runtime\python.exe"


@pytest.mark.parametrize("key,value", [
    ("Platform", "linux-wsl"), ("SourceSha", "c" * 40),
    ("PrimaryFailure", "failed"), ("ProfileHash", "invalid"),
    ("Interpreter", r"C:relative\python.exe"),
    ("Interpreter", r"\relative\python.exe"),
    ("Interpreter", "C:\\python.exe\nINJECTED=value"),
    ("Interpreter", "C:\\python.exe\0"),
])
def test_windows_context_rejects_wrong_source_platform_and_unsafe_paths(
    key: str, value: object,
) -> None:
    context = windows_projection()
    context[key] = value
    with pytest.raises(ValueError):
        resolve(context, **IDENTITY, platform="windows")


def test_windows_cli_returns_only_verified_interpreter(tmp_path: Path) -> None:
    context = windows_projection()
    path = tmp_path / "windows-context.json"
    path.write_text(json.dumps(context))
    result = subprocess.run([
        sys.executable, str(ROOT / "scripts/resolve_rcc_runtime_context.py"),
        str(path), str(IDENTITY["repository_id"]), IDENTITY["repository"],
        IDENTITY["runner"], IDENTITY["source_sha"], "windows",
    ], capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.strip() == context["Interpreter"]
    assert result.stderr == ""


@pytest.mark.parametrize("name", [
    "jap-windows-desktop-host-release.yml", "rcc-general-pool-proof.yml",
])
def test_windows_workloads_bind_runtime_and_scope_checkout_cleanup(name: str) -> None:
    workflow = (ROOT / ".github/workflows" / name).read_text()
    assert "scripts/resolve_rcc_runtime_context.py" in workflow
    assert "$env:SOURCE_SHA windows" in workflow
    assert "Exact-source RCC Windows runtime verification failed" in workflow
    assert "path: rcc-workload-${{ github.run_id }}-${{ github.run_attempt }}" in workflow
    cleanup = workflow.split("      - name: Delete ephemeral Windows candidate\n", 1)[1]
    assert "if: always()" in cleanup
    assert "working-directory: ${{ runner.temp }}" in cleanup
    assert '"rcc-workload-$($env:GITHUB_RUN_ID)-$($env:GITHUB_RUN_ATTEMPT)"' in cleanup
    assert "Remove-Item -LiteralPath $sourceRoot" in cleanup


@pytest.mark.parametrize("key,value", [
    ("RepositoryId", 42), ("Repository", "owner/other"),
    ("RunnerName", "stale-facade"), ("Platform", "windows"),
    ("SourceSha", "c" * 40), ("Status", "FAIL"), ("PrimaryFailure", "failed"),
    ("ProfileId", ""), ("ProfileHash", "invalid"),
    ("Interpreter", "relative/python"), ("Interpreter", "/python\nINJECTED=value"),
    ("Interpreter", None),
])
def test_stale_failed_or_malformed_context_is_rejected(key: str, value: object) -> None:
    context = projection()
    context[key] = value
    with pytest.raises(ValueError):
        resolve(context, **IDENTITY)


def test_cli_rejection_emits_no_interpreter(tmp_path: Path) -> None:
    context = projection()
    context["SourceSha"] = "c" * 40
    path = tmp_path / "context.json"
    path.write_text(json.dumps(context))
    result = subprocess.run([
        sys.executable, str(ROOT / "scripts/resolve_rcc_runtime_context.py"),
        str(path), str(IDENTITY["repository_id"]), IDENTITY["repository"],
        IDENTITY["runner"], IDENTITY["source_sha"],
    ], capture_output=True, text=True)
    assert result.returncode == 1
    assert result.stdout == ""
    assert "SourceSha" in result.stderr


def test_pr_checkout_cleanup_runs_after_failure_and_is_scoped(tmp_path: Path) -> None:
    workflow = (ROOT / ".github/workflows/pr-validation.yml").read_text()
    cleanup = workflow.split("      - name: Delete ephemeral candidate\n", 1)[1]
    assert "if: always()" in cleanup
    script = cleanup.split("        run: |\n", 1)[1]
    script = "\n".join(line[10:] for line in script.splitlines())
    source = tmp_path / "rcc-workload-123-1"
    source.mkdir()
    (source / "candidate").write_text("partial failed checkout")
    retained = tmp_path / "other-workload"
    retained.mkdir()
    env = {**os.environ, "GITHUB_WORKSPACE": str(tmp_path),
           "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1"}
    subprocess.run(["bash", "-c", script], env=env, check=True, capture_output=True)
    assert not source.exists()
    assert retained.is_dir()
