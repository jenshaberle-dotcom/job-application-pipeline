#!/usr/bin/env python3
"""Read-only WSL worktree/remote delivery gate. This is NOT an OS sandbox.

A caller MUST run before the first mutation and after every pushed checkpoint.
It cannot prevent an agent from ignoring the script or writing outside Git.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys


class GateBlocked(RuntimeError):
    pass


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise GateBlocked(reason)


def git(path: Path, *arguments: str) -> str:
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
    result = subprocess.run(
        ["git", "-C", str(path), *arguments], text=True, capture_output=True,
        timeout=30, check=False, env=env
    )
    require(result.returncode == 0, "GIT_READ_FAILED:" + arguments[0])
    return result.stdout.strip()


def remote_commit(path: Path, ref: str) -> str:
    value = git(path, "ls-remote", "origin", "refs/heads/" + ref)
    columns = value.split()
    require(len(columns) == 2 and re.fullmatch(r"[0-9a-f]{40}", columns[0]) is not None,
            "REMOTE_REF_NOT_UNAMBIGUOUS")
    require(columns[1] == "refs/heads/" + ref, "REMOTE_REF_MISMATCH")
    return columns[0]


def accepted_origin(url: str, full_name: str) -> bool:
    return re.fullmatch(
        r"(?:git@github\.com:|ssh://git@github\.com/|https://github\.com/)"
        + re.escape(full_name) + r"(?:\.git)?/?", url.strip()
    ) is not None


def restart_admits(snapshot: dict, phase: str) -> bool:
    if phase == "inspect":
        return True
    admission = snapshot.get("work_admission") or {}
    return snapshot.get("state") == "PASS" and admission.get("normal_new_project_mutation_blocked") is False


def within_worktree(root: Path, allowed_root: Path) -> bool:
    """Exact resolved ancestor, never a textual path-prefix match."""
    return root != allowed_root and allowed_root in root.parents


def cwd_is_in_repo(root: Path) -> bool:
    here = Path.cwd().resolve()
    return here == root or root in here.parents


def verify(phase: str) -> dict[str, str]:
    release = Path("/proc/sys/kernel/osrelease")
    require(sys.platform.startswith("linux") and release.is_file()
            and "microsoft" in release.read_text().lower(), "WSL_ONLY")

    root = Path(__file__).resolve().parents[1]
    contract = json.loads((root / "PROJECT-LOCAL-WORKSPACE.json").read_text())
    full_name = contract["repository"]
    name = full_name.split("/")[-1]
    require(contract["canonical_branch"] == "main"
            and contract["repository_id"] > 0, "WORKSPACE_CONTRACT_MISMATCH")
    require(full_name == "jenshaberle-dotcom/" + name, "REPOSITORY_IDENTITY_NOT_EXPECTED")

    restart = json.loads((root / "POST-MIGRATION-RESTART.json").read_text())
    require(restart["repository"]["repository_id"] == contract["repository_id"]
            and restart["repository"]["full_name"] == full_name,
            "RESTART_REPOSITORY_MISMATCH")
    require(restart_admits(restart, phase), "RESTART_GATE_BLOCKED")

    home = str(Path.home())
    canonical = Path(contract["canonical_checkout"]["path"].replace("$HOME", home)).resolve()
    allowed_root = Path(contract["project_workspaces"]["root"].replace("$HOME", home)).resolve()
    require(canonical == Path.home() / "projects" / name, "CANONICAL_PATH_CHANGED")
    require(allowed_root == Path.home() / "worktrees" / name, "WORKTREE_ROOT_CHANGED")
    require(root == Path(git(root, "rev-parse", "--show-toplevel")).resolve(),
            "EXECUTION_OUTSIDE_GIT_ROOT")

    if phase != "inspect":
        require(cwd_is_in_repo(root), "CURRENT_DIRECTORY_OUTSIDE_WORKTREE")

    for folder in (canonical, root):
        require(accepted_origin(git(folder, "config", "--get", "remote.origin.url"), full_name),
                "ORIGIN_IDENTITY_MISMATCH")
    require(git(canonical, "branch", "--show-current") == "main", "CANONICAL_NOT_MAIN")
    require(not git(canonical, "status", "--porcelain"), "CANONICAL_NOT_CLEAN")
    require(git(canonical, "rev-parse", "HEAD") == remote_commit(canonical, "main"),
            "CANONICAL_MAIN_STALE")

    if phase != "inspect":
        require(root != canonical and within_worktree(root, allowed_root),
                "MUTATION_OUTSIDE_DECLARED_WSL_WORKTREE")
        expected = "worktree " + str(root)
        registered = git(canonical, "worktree", "list", "--porcelain").splitlines()
        require(expected in registered, "UNREGISTERED_WORKTREE")
        branch = git(root, "branch", "--show-current")
        require(branch != "" and branch != "main", "MUTATION_REQUIRES_NAMED_FEATURE_BRANCH")
        if phase == "after-push":
            require(not git(root, "status", "--porcelain"), "UNCOMMITTED_OR_UNTRACKED_OUTPUT")
            require(git(root, "rev-parse", "HEAD") == remote_commit(root, branch),
                    "COMMIT_NOT_VERIFIED_ON_REMOTE")
        return {"state": "PASS", "phase": phase, "repository": full_name,
                "branch": branch, "source_sha": git(root, "rev-parse", "HEAD")}
    return {"state": "PASS", "phase": phase, "repository": full_name,
            "branch": git(root, "branch", "--show-current"),
            "source_sha": git(root, "rev-parse", "HEAD")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("inspect", "before-edit", "after-push"),
                        default="before-edit")
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.phase), sort_keys=True))
        return 0
    except (GateBlocked, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        reason = str(exc).splitlines()[0][:120]
        print(json.dumps({"state": "BLOCKED", "reason": reason}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
