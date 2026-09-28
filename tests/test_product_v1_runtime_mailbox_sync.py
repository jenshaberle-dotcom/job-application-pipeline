from __future__ import annotations

import pytest

import scripts.product_v1_runtime_mailbox_sync as mailbox_sync
from scripts.product_v1_runtime_mailbox_sync import (
    DEFAULT_INTERVAL_SECONDS,
    MailboxRuntimeSyncError,
    MailboxSyncScheduler,
)


def test_mailbox_sync_default_cadence_is_30_minutes() -> None:
    assert DEFAULT_INTERVAL_SECONDS == 30 * 60


def test_scheduler_runs_startup_then_30m_reason_without_parallel_timer_logic() -> None:
    reasons: list[str] = []

    class StopAfterScheduled:
        calls = 0

        def wait(self, _seconds: int) -> bool:
            self.calls += 1
            return self.calls > 1

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


def test_operator_refresh_waits_for_inflight_startup_sync_before_truth_reload() -> None:
    source = (
        __import__("pathlib").Path(__file__).parents[1]
        / "scripts"
        / "product_v1_runtime_mailbox_sync.py"
    ).read_text(encoding="utf-8")
    assert 'blocking = reason == "operator_refresh"' in source
    assert "_LOCK.acquire(blocking=blocking)" in source


def test_control_center_refreshes_truth_after_startup_and_every_30_minutes() -> None:
    source = (
        __import__("pathlib").Path(__file__).parents[1]
        / "frontend"
        / "control-center"
        / "src"
        / "ProductTruthContext.tsx"
    ).read_text(encoding="utf-8")
    assert "void refreshProductTruth().catch(() => undefined);" in source
    assert "30 * 60 * 1000" in source
    assert "window.clearInterval(interval)" in source


def test_mailbox_failure_does_not_fail_closed_product_truth() -> None:
    source = (
        __import__("pathlib").Path(__file__).parents[1]
        / "frontend"
        / "control-center"
        / "src"
        / "ProductTruthContext.tsx"
    ).read_text(encoding="utf-8")
    assert 'if (!sync.ok) mailboxSyncWarning = `Mailbox sync returned ${sync.status}`;' in source
    assert "const truth = await readProductTruth<unknown>({ fresh: true });" in source
    assert "if (mailboxSyncWarning) console.warn(mailboxSyncWarning);" in source
    assert 'if (!sync.ok) throw new Error(`Mailbox sync returned ${sync.status}`);' not in source


def test_private_runtime_adoption_is_exact_clean_main_fast_forward(monkeypatch, tmp_path) -> None:
    root = tmp_path / "job-pipeline-runtime"
    (root / ".git").mkdir(parents=True)
    calls: list[tuple[str, ...]] = []
    status_calls = 0

    def fake_git(_root, *args: str, timeout: int = 60) -> str:
        nonlocal status_calls
        assert _root == root
        calls.append(args)
        if args == ("branch", "--show-current"):
            return "main"
        if args == ("status", "--porcelain", "--untracked-files=all"):
            status_calls += 1
            return ""
        if args == ("remote", "get-url", "origin"):
            return "git@github.com:jenshaberle-dotcom/job-pipeline-runtime.git"
        if args == ("rev-parse", "HEAD"):
            return "a" * 40 if len([x for x in calls if x == args]) == 1 else "b" * 40
        if args == ("fetch", "origin", "refs/heads/main:refs/remotes/origin/main"):
            assert timeout == 90
            return ""
        if args == ("rev-parse", "refs/remotes/origin/main"):
            return "b" * 40
        if args == ("merge-base", "--is-ancestor", "HEAD", "refs/remotes/origin/main"):
            return ""
        if args == ("merge", "--ff-only", "refs/remotes/origin/main"):
            return ""
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(mailbox_sync, "_runtime_root", lambda: root)
    monkeypatch.setattr(mailbox_sync, "_run_runtime_git", fake_git)

    result = mailbox_sync._adopt_private_runtime_main()

    assert result["private_runtime_before_sha"] == "a" * 40
    assert result["private_runtime_after_sha"] == "b" * 40
    assert result["private_runtime_updated"] is True
    assert result["private_runtime_branch"] == "main"
    assert result["private_runtime_adoption"] == "fast_forward_only"
    assert status_calls == 2
    assert ("merge", "--ff-only", "refs/remotes/origin/main") in calls


def test_private_runtime_adoption_refuses_dirty_checkout_before_fetch(
    monkeypatch, tmp_path
) -> None:
    root = tmp_path / "job-pipeline-runtime"
    (root / ".git").mkdir(parents=True)
    calls: list[tuple[str, ...]] = []

    def fake_git(_root, *args: str, timeout: int = 60) -> str:
        calls.append(args)
        if args == ("branch", "--show-current"):
            return "main"
        if args == ("status", "--porcelain", "--untracked-files=all"):
            return " M scripts/f5_gmail_readonly_bridge.py"
        raise AssertionError(f"unexpected git call after dirty proof: {args}")

    monkeypatch.setattr(mailbox_sync, "_runtime_root", lambda: root)
    monkeypatch.setattr(mailbox_sync, "_run_runtime_git", fake_git)

    with pytest.raises(MailboxRuntimeSyncError, match="private_runtime_checkout_dirty"):
        mailbox_sync._adopt_private_runtime_main()

    assert not any(call and call[0] == "fetch" for call in calls)


def test_private_runtime_adoption_refuses_wrong_origin(monkeypatch, tmp_path) -> None:
    root = tmp_path / "job-pipeline-runtime"
    (root / ".git").mkdir(parents=True)

    def fake_git(_root, *args: str, timeout: int = 60) -> str:
        if args == ("branch", "--show-current"):
            return "main"
        if args == ("status", "--porcelain", "--untracked-files=all"):
            return ""
        if args == ("remote", "get-url", "origin"):
            return "https://github.com/example/wrong-runtime.git"
        raise AssertionError(f"unexpected git call after origin proof: {args}")

    monkeypatch.setattr(mailbox_sync, "_runtime_root", lambda: root)
    monkeypatch.setattr(mailbox_sync, "_run_runtime_git", fake_git)

    with pytest.raises(MailboxRuntimeSyncError, match="private_runtime_origin_mismatch"):
        mailbox_sync._adopt_private_runtime_main()


def test_mailbox_sync_adopts_runtime_before_scanning() -> None:
    source = (
        __import__("pathlib").Path(__file__).parents[1]
        / "scripts"
        / "product_v1_runtime_mailbox_sync.py"
    ).read_text(encoding="utf-8")
    adopt = source.index("runtime = _adopt_private_runtime_main()")
    scan = source.index("scan = _scan_normalized(normalized)")
    apply = source.index("applied = _apply_idempotent(rows)")
    assert adopt < scan < apply


def test_private_runtime_adoption_has_no_destructive_git_authority() -> None:
    source = (
        __import__("pathlib").Path(__file__).parents[1]
        / "scripts"
        / "product_v1_runtime_mailbox_sync.py"
    ).read_text(encoding="utf-8")
    assert '"fetch",' in source
    assert '"merge", "--ff-only"' in source
    for forbidden in (
        "reset --hard",
        "checkout -f",
        '"checkout",',
        '"pull",',
        '"rebase",',
        "clean -fd",
    ):
        assert forbidden not in source
