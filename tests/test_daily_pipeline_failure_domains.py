from __future__ import annotations

import os
from pathlib import Path
import subprocess


SCRIPT = Path("scripts/run_daily_pipeline.sh").resolve()


def _prepare_fake_home(tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / "home"
    project = home / "projects" / "job-application-pipeline"
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
  exit \"${DB_READY_EXIT:-0}\"
fi
case \"$*\" in
  *\"-m src.ingest_jobs --role employer_origin\"*) exit \"${ORIGIN_EXIT:-0}\" ;;
  *\"-m src.ingest_jobs --role sensor\"*) exit \"${SENSOR_EXIT:-0}\" ;;
  *\"-m src.run_silver_jobs\"*) exit \"${SILVER_EXIT:-0}\" ;;
  *\"-m scripts.create_source_value_snapshot\"*) exit \"${SNAPSHOT_EXIT:-0}\" ;;
  *) echo \"unexpected fake python invocation: $*\" >&2; exit 91 ;;
esac
""",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    activate = venv_bin / "activate"
    activate.write_text(
        'export PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd):$PATH"\n',
        encoding="utf-8",
    )

    return home, call_log


def _run_daily(
    tmp_path: Path,
    *,
    origin_exit: int = 0,
    sensor_exit: int = 0,
    silver_exit: int = 0,
    snapshot_exit: int = 0,
) -> tuple[subprocess.CompletedProcess[str], list[str], str]:
    home, call_log = _prepare_fake_home(tmp_path)
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "CALL_LOG": str(call_log),
            "ORIGIN_EXIT": str(origin_exit),
            "SENSOR_EXIT": str(sensor_exit),
            "SILVER_EXIT": str(silver_exit),
            "SNAPSHOT_EXIT": str(snapshot_exit),
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
    calls = call_log.read_text(encoding="utf-8").splitlines()
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
