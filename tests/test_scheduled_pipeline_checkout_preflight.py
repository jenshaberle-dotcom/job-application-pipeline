from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import prepare_scheduled_pipeline_checkout as preflight


def _identity_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    current = root / "docs" / "current"
    current.mkdir(parents=True)
    (root / ".git").mkdir()
    (current / "operations.md").write_text("current operations\n", encoding="utf-8")
    (current / "REPOSITORY-IDENTITY.json").write_text(
        json.dumps(
            {
                "schema": "reentry.repository_identity.v1",
                "execution_target": {
                    "repository_id": 1230805345,
                    "canonical_name": "jenshaberle-dotcom/job-application-pipeline",
                    "repository_role": "product_authority_and_pipeline_repository",
                    "canonical_default_branch": "main",
                },
                "reentry_binding": {
                    "bound_repository_id": 1230805345,
                    "contract_paths": ["docs/current/operations.md"],
                },
                "relationship_policy": {
                    "execution_target_is_not_inferred_from_relationships": True,
                    "authority_source_does_not_become_execution_target": True,
                    "related_repositories": [
                        {
                            "repository_id": 1316856786,
                            "canonical_name": "jenshaberle-dotcom/job-pipeline-runtime",
                            "may_supply_reentry_authority": False,
                            "may_be_mutation_target": False,
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    return root


def _live_repository(repository_id: int = 1230805345) -> dict[str, object]:
    return {
        "id": repository_id,
        "full_name": "jenshaberle-dotcom/job-application-pipeline",
        "default_branch": "main",
    }


def test_normalize_remote_accepts_supported_github_forms() -> None:
    expected = "jenshaberle-dotcom/job-application-pipeline"
    assert preflight.normalize_remote(f"https://github.com/{expected}.git") == expected
    assert preflight.normalize_remote(f"git@github.com:{expected}.git") == expected
    assert preflight.normalize_remote(f"ssh://git@github.com/{expected}.git") == expected


def test_clean_behind_checkout_fast_forwards_only(monkeypatch, tmp_path: Path) -> None:
    root = _identity_root(tmp_path)
    before = "a" * 40
    after = "b" * 40
    calls: list[tuple[str, ...]] = []
    status_calls = 0

    def fake_run_git(_root: Path, *args: str) -> str:
        nonlocal status_calls
        calls.append(args)
        if args == ("remote", "get-url", "origin"):
            return "https://github.com/jenshaberle-dotcom/job-application-pipeline.git"
        if args == ("branch", "--show-current"):
            return "main"
        if args == ("status", "--porcelain=v1"):
            status_calls += 1
            return ""
        if args == ("rev-parse", "HEAD"):
            return before if ("merge", "--ff-only", "origin/main") not in calls else after
        if args == ("fetch", "--quiet", "origin", "main"):
            return ""
        if args == ("rev-parse", "origin/main"):
            return after
        if args == ("merge", "--ff-only", "origin/main"):
            return "Updating"
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(preflight, "run_git", fake_run_git)
    monkeypatch.setattr(
        preflight.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    result = preflight.prepare_checkout(
        root,
        live_repository_loader=_live_repository,
    )

    assert result["status"] == "SCHEDULED_CHECKOUT_READY"
    assert result["before_sha"] == before
    assert result["after_sha"] == after
    assert result["updated"] is True
    assert ("merge", "--ff-only", "origin/main") in calls
    assert status_calls == 2


def test_dirty_checkout_fails_before_fetch(monkeypatch, tmp_path: Path) -> None:
    root = _identity_root(tmp_path)
    calls: list[tuple[str, ...]] = []

    def fake_run_git(_root: Path, *args: str) -> str:
        calls.append(args)
        if args == ("remote", "get-url", "origin"):
            return "git@github.com:jenshaberle-dotcom/job-application-pipeline.git"
        if args == ("branch", "--show-current"):
            return "main"
        if args == ("status", "--porcelain=v1"):
            return " M local-change.txt"
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(preflight, "run_git", fake_run_git)

    with pytest.raises(preflight.ScheduledCheckoutError, match="local modifications"):
        preflight.prepare_checkout(root, live_repository_loader=_live_repository)

    assert not any(args and args[0] == "fetch" for args in calls)


def test_wrong_live_repository_id_fails_closed(monkeypatch, tmp_path: Path) -> None:
    root = _identity_root(tmp_path)

    def fake_run_git(_root: Path, *args: str) -> str:
        if args == ("remote", "get-url", "origin"):
            return "https://github.com/jenshaberle-dotcom/job-application-pipeline"
        if args == ("branch", "--show-current"):
            return "main"
        if args == ("status", "--porcelain=v1"):
            return ""
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(preflight, "run_git", fake_run_git)

    with pytest.raises(preflight.ScheduledCheckoutError, match="immutable repository id mismatch"):
        preflight.prepare_checkout(
            root,
            live_repository_loader=lambda: _live_repository(999),
        )
