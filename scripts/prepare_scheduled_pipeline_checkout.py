#!/usr/bin/env python3
"""Prepare the persistent scheduled Pipeline checkout without overwriting local work."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

from scripts.check_reentry_identity import classify_live, load_json, validate_static


EXPECTED_REPOSITORY = "jenshaberle-dotcom/job-application-pipeline"
EXPECTED_REPOSITORY_ID = 1230805345
EXPECTED_BRANCH = "main"
IDENTITY_PATH = Path("docs/current/REPOSITORY-IDENTITY.json")


class ScheduledCheckoutError(RuntimeError):
    pass


def run_git(root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise ScheduledCheckoutError(
            f"git {' '.join(args)} failed: {stderr or exc.returncode}"
        ) from exc
    return completed.stdout.strip()


def normalize_remote(value: str) -> str:
    remote = value.strip().removesuffix(".git")
    prefixes = (
        "https://github.com/",
        "ssh://git@github.com/",
        "git@github.com:",
    )
    for prefix in prefixes:
        if remote.startswith(prefix):
            return remote.removeprefix(prefix)
    return remote


def fetch_live_repository() -> dict[str, Any]:
    request = Request(
        f"https://api.github.com/repos/{EXPECTED_REPOSITORY}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "job-pipeline-scheduled-checkout-preflight/1.0",
        },
    )
    with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed GitHub API origin.
        payload = json.load(response)
    return {
        "id": int(payload["id"]),
        "full_name": str(payload["full_name"]),
        "default_branch": str(payload["default_branch"]),
    }


def prepare_checkout(
    root: Path,
    *,
    live_repository_loader: Callable[[], dict[str, Any]] = fetch_live_repository,
) -> dict[str, Any]:
    root = root.resolve()
    if not (root / ".git").exists():
        raise ScheduledCheckoutError(f"not a git checkout: {root}")

    identity = load_json(root / IDENTITY_PATH)
    validate_static(root, identity)

    remote = normalize_remote(run_git(root, "remote", "get-url", "origin"))
    if remote != EXPECTED_REPOSITORY:
        raise ScheduledCheckoutError(
            f"unexpected origin remote: expected={EXPECTED_REPOSITORY!r} observed={remote!r}"
        )

    branch = run_git(root, "branch", "--show-current")
    if branch != EXPECTED_BRANCH:
        raise ScheduledCheckoutError(
            f"scheduled checkout must be on {EXPECTED_BRANCH!r}, got {branch!r}"
        )

    dirty = run_git(root, "status", "--porcelain=v1")
    if dirty:
        raise ScheduledCheckoutError(
            "scheduled checkout has local modifications; refusing automatic update"
        )

    live = live_repository_loader()
    if live.get("id") != EXPECTED_REPOSITORY_ID:
        raise ScheduledCheckoutError(
            "live immutable repository id mismatch: "
            f"expected={EXPECTED_REPOSITORY_ID} observed={live.get('id')!r}"
        )
    if live.get("default_branch") != EXPECTED_BRANCH:
        raise ScheduledCheckoutError(
            "live default branch drift: "
            f"expected={EXPECTED_BRANCH!r} observed={live.get('default_branch')!r}"
        )
    identity_status = classify_live(
        identity,
        live.get("id"),
        str(live.get("full_name") or ""),
    )
    if identity_status != "IDENTITY_VERIFIED":
        raise ScheduledCheckoutError(
            f"scheduled checkout repository identity not verified: {identity_status}"
        )

    before = run_git(root, "rev-parse", "HEAD")
    run_git(root, "fetch", "--quiet", "origin", EXPECTED_BRANCH)
    remote_head = run_git(root, "rev-parse", f"origin/{EXPECTED_BRANCH}")

    ancestor = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "merge-base",
            "--is-ancestor",
            before,
            remote_head,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if ancestor.returncode != 0:
        raise ScheduledCheckoutError(
            "local scheduled checkout is ahead of or diverged from origin/main; "
            "automatic update refused"
        )

    updated = before != remote_head
    if updated:
        run_git(root, "merge", "--ff-only", f"origin/{EXPECTED_BRANCH}")

    after = run_git(root, "rev-parse", "HEAD")
    if after != remote_head:
        raise ScheduledCheckoutError(
            f"scheduled checkout did not converge to origin/main: local={after} remote={remote_head}"
        )
    if run_git(root, "status", "--porcelain=v1"):
        raise ScheduledCheckoutError("scheduled checkout became dirty after fast-forward")

    return {
        "status": "SCHEDULED_CHECKOUT_READY",
        "repository": EXPECTED_REPOSITORY,
        "repository_id": EXPECTED_REPOSITORY_ID,
        "branch": EXPECTED_BRANCH,
        "before_sha": before,
        "after_sha": after,
        "updated": updated,
        "identity_status": identity_status,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    result = prepare_checkout(Path(args.root))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ScheduledCheckoutError, OSError, ValueError) as exc:
        print(f"SCHEDULED_CHECKOUT_BLOCKED: {exc}")
        raise SystemExit(1)
