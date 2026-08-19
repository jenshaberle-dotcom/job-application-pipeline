from __future__ import annotations

import subprocess
import sys


def test_control_center_supports_direct_operator_launcher() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/run_product_v1_control_center.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, result.stderr
    assert "usage: run_product_v1_control_center.py" in result.stdout
    assert "--frontend-dist" in result.stdout
    assert "ModuleNotFoundError" not in result.stderr


def test_control_center_still_supports_module_launcher() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "scripts.run_product_v1_control_center", "--help"],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, result.stderr
    assert "--frontend-dist" in result.stdout
    assert "ModuleNotFoundError" not in result.stderr
