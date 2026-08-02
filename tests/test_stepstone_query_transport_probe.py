from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.run_stepstone_query_transport_probe import (
    APPROVAL_TOKEN,
    DEFAULT_NOT_BEFORE_UTC,
    enforce_execution_gate,
)


RUNNER = Path("scripts/run_stepstone_query_transport_probe.py")


def test_runner_has_hard_cooldown_and_read_only_boundaries() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert 'DEFAULT_NOT_BEFORE_UTC = "2026-08-03T04:26:00+00:00"' in source
    assert "DEFAULT_MAX_REQUESTS = 8" in source
    assert '"not_before_gate_enforced": True' in source
    assert '"approval_token_required": True' in source
    assert '"page_one_only": True' in source
    assert '"no_pagination": True' in source
    assert '"no_detail_pages": True' in source
    assert '"no_database_write": True' in source
    assert '"no_candidate_creation": True' in source
    assert '"no_provider_call": True' in source
    assert '"production_adoption_allowed": False' in source


def test_execution_gate_rejects_wrong_token() -> None:
    with pytest.raises(SystemExit, match="exact --approval-token"):
        enforce_execution_gate(
            approval_token="wrong",
            not_before_utc=DEFAULT_NOT_BEFORE_UTC,
            now=datetime(2026, 8, 3, 5, 0, tzinfo=UTC),
        )


def test_execution_gate_rejects_early_run() -> None:
    with pytest.raises(SystemExit, match="blocked by cooldown"):
        enforce_execution_gate(
            approval_token=APPROVAL_TOKEN,
            not_before_utc=DEFAULT_NOT_BEFORE_UTC,
            now=datetime(2026, 8, 3, 4, 25, 59, tzinfo=UTC),
        )


def test_execution_gate_allows_run_at_boundary() -> None:
    not_before = enforce_execution_gate(
        approval_token=APPROVAL_TOKEN,
        not_before_utc=DEFAULT_NOT_BEFORE_UTC,
        now=datetime(2026, 8, 3, 4, 26, tzinfo=UTC),
    )

    assert not_before == datetime(2026, 8, 3, 4, 26, tzinfo=UTC)
