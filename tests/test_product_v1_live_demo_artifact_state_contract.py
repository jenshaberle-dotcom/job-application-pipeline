from __future__ import annotations

from pathlib import Path

import pytest

from scripts import run_product_v1_live_demo as live_demo


def _exercise(monkeypatch, tmp_path, *, code: int, state: str) -> Path:
    monkeypatch.setattr(live_demo, "DEMO_ARTIFACT_ROOT", tmp_path.resolve())
    target = tmp_path / "diagnostic.json"

    def fake_run_module(_module: str, *, arguments: list[str]) -> int:
        staged = Path(arguments[arguments.index("--output") + 1])
        staged.write_text(f'{{"state":"{state}"}}\n', encoding="utf-8")
        return code

    monkeypatch.setattr(live_demo, "_run_module", fake_run_module)
    live_demo._run_module_with_atomic_output(
        "scripts.fake_probe",
        arguments=[],
        output=target,
    )
    return target


def test_zero_exit_with_blocked_state_fails_closed(monkeypatch, tmp_path) -> None:
    with pytest.raises(RuntimeError, match="exit/status disagreement"):
        _exercise(monkeypatch, tmp_path, code=0, state="blocked")
    assert not (tmp_path / "diagnostic.json").exists()


def test_nonzero_exit_with_pass_state_fails_closed(monkeypatch, tmp_path) -> None:
    with pytest.raises(RuntimeError, match="exit/status disagreement"):
        _exercise(monkeypatch, tmp_path, code=2, state="pass")
    assert not (tmp_path / "diagnostic.json").exists()


def test_unknown_readiness_state_fails_closed(monkeypatch, tmp_path) -> None:
    with pytest.raises(RuntimeError, match="invalid readiness state"):
        _exercise(monkeypatch, tmp_path, code=2, state="unknown")
    assert not (tmp_path / "diagnostic.json").exists()
