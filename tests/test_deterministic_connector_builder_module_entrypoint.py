from __future__ import annotations

import subprocess
import sys


def test_connector_builder_audit_module_entrypoint_help() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.run_deterministic_connector_builder_layer_audit",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "deterministic" in result.stdout.casefold()
    assert "connector" in result.stdout.casefold()
