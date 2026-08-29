from __future__ import annotations

import subprocess
import sys
from pathlib import Path


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
    assert "--output" in completed.stdout
    assert "--target-location" in completed.stdout
