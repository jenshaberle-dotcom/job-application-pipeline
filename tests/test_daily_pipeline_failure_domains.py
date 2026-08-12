from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess


SCRIPT = Path("scripts/run_daily_pipeline.sh").resolve()
WINDOWS_WRAPPER = Path("scripts/windows/run_scheduled_pipeline.ps1").resolve()
REPOSITORY_ID = 1230805345
REPOSITORY = "jenshaberle-dotcom/job-application-pipeline"
RUNNER_NAME = "job-pipeline-runtime-linux"


def _prepare_fake_home(tmp_path: Path) -> tuple[Path, Path, Path]:
    home = tmp_path / "home"
    project = home / "managed" / "relocated-pipeline"
    venv_bin = project / ".venv" / "bin"
    venv_bin.mkdir(parents=True)

    call_log = tmp_path / "python_calls.log"
    fake_python = venv_bin / "python"
    fake_python.write_text(
        """#!/usr/bin/env bash
set -u
printf '%s\\n' \"$*\" >> \"$CALL_LOG\"
if [ \"${1:-}\" = \"-\" ]; then
  cat >/dev/null
  exit \"${FAKE_DB_READY_EXIT:-0}\"
fi
case \"$*\" in
  *\"-m src.ingest_jobs --role employer_origin\"*) exit \"${FAKE_ORIGIN_EXIT:-0}\" ;;
  *\"-m src.ingest_jobs --role sensor\"*) exit \"${FAKE_SENSOR_EXIT:-0}\" ;;
  *\"-m src.run_silver_jobs\"*) exit \"${FAKE_SILVER_EXIT:-0}\" ;;
  *\"-m scripts.create_source_value_snapshot\"*) exit \"${FAKE_SNAPSHOT_EXIT:-0}\" ;;
  *) echo \"unexpected fake python invocation: $*\" >&2; exit 91 ;;
esac
""",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    env_file = project / ".env"
    env_file.write_text("POSTGRES_HOST=example.invalid\n", encoding="utf-8")

    context_dir = (
        home
        / ".config"
        / "DeepOceanInfrastructure"
        / "RCC"
        / "runtime-contexts"
    )
    context_dir.mkdir(parents=True)
    context_file = context_dir / f"{REPOSITORY_ID}-{RUNNER_NAME}.json"
    required_checks = [
        "repository_identity",
        "checkout",
        "checkout_repository",
        "env_file",
        "env_keys",
        "interpreter",
        "interpreter_probe",
        "capability:postgresql",
    ]
    context_file.write_text(
        json.dumps(
            {
                "RepositoryId": REPOSITORY_ID,
                "Repository": REPOSITORY,
                "RunnerName": RUNNER_NAME,
                "Platform": "linux-wsl",
                "Status": "PASS",
                "PrimaryFailure": "",
                "ValidatedAt": "2026-08-12T08:00:00+00:00",
                "CheckoutRoot": str(project),
                "EnvFile": str(env_file),
                "Interpreter": str(fake_python),
                "ProjectionPath": str(context_file),
                "RequiredEnvKeys": [
                    "POSTGRES_HOST",
                    "POSTGRES_PORT",
                    "POSTGRES_DB",
                    "POSTGRES_USER",
                    "POSTGRES_PASSWORD",
                ],
                "Capabilities": ["postgresql"],
                "Checks": [
                    {"Id": check_id, "Status": "PASS", "Detail": "test"}
                    for check_id in required_checks
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return home, call_log, context_file


def _run_daily(
    tmp_path: Path,
    *,
    origin_exit: int = 0,
    sensor_exit: int = 0,
    silver_exit: int = 0,
    snapshot_exit: int = 0,
    context_status: str = "PASS",
    remove_context: bool = False,
) -> tuple[subprocess.CompletedProcess[str], list[str], str]:
    home, call_log, context_file = _prepare_fake_home(tmp_path)
    if remove_context:
        context_file.unlink()
    elif context_status != "PASS":
        context = json.loads(context_file.read_text(encoding="utf-8"))
        context["Status"] = context_status
        context["PrimaryFailure"] = "RUNTIME_CONTEXT_STALE"
        context_file.write_text(json.dumps(context, indent=2), encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "CALL_LOG": str(call_log),
            # Use names that the production shell does not reuse for its own
            # component result variables. Otherwise Bash legitimately overwrites
            # the inherited test controls before the fake child process starts.
            "FAKE_ORIGIN_EXIT": str(origin_exit),
            "FAKE_SENSOR_EXIT": str(sensor_exit),
            "FAKE_SILVER_EXIT": str(silver_exit),
            "FAKE_SNAPSHOT_EXIT": str(snapshot_exit),
        }
    )
    completed = subprocess.run(
        ["bash", str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    calls = (
        call_log.read_text(encoding="utf-8").splitlines()
        if call_log.exists()
        else []
    )
    logs = sorted((home / "job-pipeline-logs").glob("daily_pipeline_*.log"))
    assert len(logs) == 1
    log_text = logs[0].read_text(encoding="utf-8")
    return completed, calls, log_text


def test_sensor_failure_does_not_block_silver_or_daily_core_success(tmp_path: Path) -> None:
    completed, calls, log_text = _run_daily(tmp_path, sensor_exit=1)

    assert completed.returncode == 0
    assert any("--role employer_origin" in call for call in calls)
    assert any("--role sensor" in call for call in calls)
    assert any("-m src.run_silver_jobs" in call for call in calls)
    assert any("-m scripts.create_source_value_snapshot" in call for call in calls)
    assert "OK_WITH_SENSOR_DEGRADATION" in log_text
    assert "authoritative origin freshness will continue" in log_text


def test_origin_failure_still_runs_silver_but_fails_authoritative_core(tmp_path: Path) -> None:
    completed, calls, log_text = _run_daily(tmp_path, origin_exit=1)

    assert completed.returncode == 1
    assert any("--role sensor" in call for call in calls)
    assert any("-m src.run_silver_jobs" in call for call in calls)
    assert "successful origin observations can reach Silver" in log_text
    assert "FAILED_AUTHORITATIVE_CORE" in log_text


def test_silver_failure_is_hard_failure_and_skips_snapshot(tmp_path: Path) -> None:
    completed, calls, log_text = _run_daily(tmp_path, silver_exit=1)

    assert completed.returncode == 1
    assert any("-m src.run_silver_jobs" in call for call in calls)
    assert not any("-m scripts.create_source_value_snapshot" in call for call in calls)
    assert "SKIP source value snapshot because Silver normalization failed" in log_text
    assert "FAILED_AUTHORITATIVE_CORE" in log_text


def test_missing_rcc_runtime_context_fails_closed_before_pipeline_work(tmp_path: Path) -> None:
    completed, calls, log_text = _run_daily(tmp_path, remove_context=True)

    assert completed.returncode == 1
    assert calls == []
    assert "RUNTIME_CONTEXT_NOT_REGISTERED" in log_text


def test_stale_rcc_runtime_context_fails_closed_before_pipeline_work(tmp_path: Path) -> None:
    completed, calls, log_text = _run_daily(tmp_path, context_status="STALE")

    assert completed.returncode == 1
    assert calls == []
    assert "RCC runtime context rejected" in log_text


def test_runtime_consumers_no_longer_guess_pipeline_checkout() -> None:
    daily = SCRIPT.read_text(encoding="utf-8")
    wrapper = WINDOWS_WRAPPER.read_text(encoding="utf-8")

    assert '$HOME/projects/job-application-pipeline' not in daily
    assert "source .venv/bin/activate" not in daily
    assert "RCC_CONTEXT_FILE" in daily
    assert "RUNTIME_PYTHON" in daily

    assert '~/projects/job-application-pipeline' not in wrapper
    assert '[string]$ProjectPath' not in wrapper
    assert "runtime-contexts/$RepositoryId-$RunnerName.json" in wrapper
    assert "--cd $ProjectPath" in wrapper
