from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def test_v5_canonical_module_entrypoint_exposes_help() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.run_deterministic_connector_builder_layer_audit_v5",
            "--help",
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Replay V3 builder" in completed.stdout
    assert "--output" in completed.stdout
