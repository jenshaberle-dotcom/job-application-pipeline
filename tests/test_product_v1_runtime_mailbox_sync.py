from __future__ import annotations

from scripts.product_v1_runtime_mailbox_sync import (
    DEFAULT_INTERVAL_SECONDS,
    MailboxSyncScheduler,
)


def test_mailbox_sync_default_cadence_is_30_minutes() -> None:
    assert DEFAULT_INTERVAL_SECONDS == 30 * 60


def test_scheduler_runs_startup_then_30m_reason_without_parallel_timer_logic() -> None:
    reasons: list[str] = []

    class StopAfterScheduled:
        def wait(self, _seconds: int) -> bool:
            if reasons:
                return True
            return False

        def set(self) -> None:
            pass

    scheduler = MailboxSyncScheduler(sync=lambda *, reason: reasons.append(reason) or {"status": "pass"})
    scheduler._stop = StopAfterScheduled()  # type: ignore[assignment]
    scheduler._run()

    assert reasons == ["startup", "scheduled_30m"]


def test_control_center_owns_one_mailbox_sync_endpoint() -> None:
    source = (
        __import__("pathlib").Path(__file__).parents[1]
        / "scripts"
        / "run_product_v1_demo_control_center.py"
    ).read_text(encoding="utf-8")
    assert 'MAILBOX_SYNC_PATH = "/api/v1/product-v1/mailbox-sync"' in source
    assert 'sync_mailbox(reason="operator_refresh")' in source
    assert "MailboxSyncScheduler()" in source


def test_existing_refresh_button_triggers_mailbox_sync_before_truth_reload() -> None:
    source = (
        __import__("pathlib").Path(__file__).parents[1]
        / "frontend"
        / "control-center"
        / "src"
        / "ProductTruthContext.tsx"
    ).read_text(encoding="utf-8")
    sync = source.index('window.fetch("/api/v1/product-v1/mailbox-sync"')
    truth = source.index("readProductTruth<unknown>({ fresh: true })")
    assert sync < truth
    assert "Mailbox sync returned" in source
