from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.run_stepstone_compact_order_failure_repro_once import (
    LOCKED_BASELINE_OBSERVED_AT,
    ONE_TIME_OVERRIDE_TOKEN,
    authorize_one_time_early_override,
    consume_one_time_override,
)
from scripts.run_stepstone_order_failure_repro_probe import APPROVAL_TOKEN


RUNNER = Path("scripts/run_stepstone_compact_order_failure_repro_once.py")


def test_authorizes_only_locked_review_before_normal_cooldown(tmp_path: Path) -> None:
    authorization = authorize_one_time_early_override(
        execute=True,
        approval_token=APPROVAL_TOKEN,
        override_token=ONE_TIME_OVERRIDE_TOKEN,
        baseline_observed_at=LOCKED_BASELINE_OBSERVED_AT,
        cooldown_hours=24,
        marker_path=tmp_path / "override.used.json",
        now=datetime(2026, 8, 3, 9, 0, tzinfo=UTC),
    )

    assert authorization["execution_allowed_now"] is True
    assert authorization["execution_mode"] == (
        "operator_approved_one_time_early_override"
    )
    assert authorization["one_time_override_consumed"] is False


def test_blocks_wrong_override_token(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="exact --one-time-cooldown-override-token"):
        authorize_one_time_early_override(
            execute=True,
            approval_token=APPROVAL_TOKEN,
            override_token="wrong",
            baseline_observed_at=LOCKED_BASELINE_OBSERVED_AT,
            cooldown_hours=24,
            marker_path=tmp_path / "override.used.json",
            now=datetime(2026, 8, 3, 9, 0, tzinfo=UTC),
        )


def test_blocks_different_baseline_observation(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="locked review-4 baseline"):
        authorize_one_time_early_override(
            execute=True,
            approval_token=APPROVAL_TOKEN,
            override_token=ONE_TIME_OVERRIDE_TOKEN,
            baseline_observed_at=datetime(2026, 8, 3, 7, 2, tzinfo=UTC),
            cooldown_hours=24,
            marker_path=tmp_path / "override.used.json",
            now=datetime(2026, 8, 3, 9, 0, tzinfo=UTC),
        )


def test_override_is_atomically_consumed_once(tmp_path: Path) -> None:
    marker = tmp_path / "override.used.json"
    authorization = authorize_one_time_early_override(
        execute=True,
        approval_token=APPROVAL_TOKEN,
        override_token=ONE_TIME_OVERRIDE_TOKEN,
        baseline_observed_at=LOCKED_BASELINE_OBSERVED_AT,
        cooldown_hours=24,
        marker_path=marker,
        now=datetime(2026, 8, 3, 9, 0, tzinfo=UTC),
    )

    consumed = consume_one_time_override(
        authorization=authorization,
        marker_path=marker,
    )

    assert marker.is_file()
    assert consumed["one_time_override_consumed"] is True
    with pytest.raises(SystemExit, match="already consumed"):
        consume_one_time_override(
            authorization=authorization,
            marker_path=marker,
        )


def test_override_expires_when_normal_cooldown_elapses(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="regular cooldown has elapsed"):
        authorize_one_time_early_override(
            execute=True,
            approval_token=APPROVAL_TOKEN,
            override_token=ONE_TIME_OVERRIDE_TOKEN,
            baseline_observed_at=LOCKED_BASELINE_OBSERVED_AT,
            cooldown_hours=24,
            marker_path=tmp_path / "override.used.json",
            now=datetime(2026, 8, 4, 7, 2, tzinfo=UTC),
        )


def test_wrapper_does_not_modify_normal_runner_contract() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert "import scripts.run_stepstone_compact_order_failure_repro as compact" in source
    assert "compact.enforce_execution_gate = one_time_gate" in source
    assert "compact.enforce_execution_gate = original_gate" in source
    assert "os.O_CREAT | os.O_EXCL | os.O_WRONLY" in source
    assert "LOCKED_BASELINE_OBSERVED_AT" in source
