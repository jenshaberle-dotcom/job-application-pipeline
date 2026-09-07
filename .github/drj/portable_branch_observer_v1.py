#!/usr/bin/env python3
"""DRJ portable read-only branch observer v1.

Technical observation only. This script performs no mutation and grants no effect authority.
It classifies remote refs by fresh Git relationship and protection context so DRJ can
separate mechanically provable zero-unique residue from divergent/unique history.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
REPOSITORY = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ["GH_TOKEN"]
OUT = Path(os.environ.get("DRJ_OBSERVER_OUTPUT", "/tmp/drj-branch-observer.json"))
MAX_BRANCHES = int(os.environ.get("DRJ_OBSERVER_MAX_BRANCHES", "2000"))


class ObserverError(RuntimeError):
    pass


def api(path: str, *, allow_404: bool = False) -> Any:
    request = Request(
        f"{API_ROOT}/repos/{REPOSITORY}{path}",
        method="GET",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "drj-portable-branch-observer-v1",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310
            raw = response.read()
            return json.loads(raw) if raw else None
    except HTTPError as exc:
        if allow_404 and exc.code == 404:
            return None
        detail = exc.read().decode("utf-8", errors="replace")
        raise ObserverError(f"GitHub API GET {path} failed: {exc.code} {detail}") from exc


def paged(path: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    page = 1
    sep = "&" if "?" in path else "?"
    while True:
        items = list(api(f"{path}{sep}per_page=100&page={page}") or [])
        out.extend(items)
        if len(out) > MAX_BRANCHES and path.startswith("/branches"):
            raise ObserverError(f"branch bound exceeded: {len(out)} > {MAX_BRANCHES}")
        if len(items) < 100:
            return out
        page += 1
        if page > 25:
            raise ObserverError(f"pagination bound exceeded for {path}")


def root_json(path: str) -> dict[str, Any] | None:
    payload = api(f"/contents/{quote(path, safe='/')}", allow_404=True)
    if payload is None:
        return None
    if payload.get("type") != "file" or payload.get("encoding") != "base64":
        return None
    try:
        value = json.loads(base64.b64decode(payload["content"]).decode("utf-8"))
    except Exception as exc:  # fail-closed observation metadata only
        raise ObserverError(f"cannot parse {path}: {exc}") from exc
    return value if isinstance(value, dict) else None


def main() -> None:
    repository = api("")
    repo_id = int(repository["id"])
    default_branch = str(repository["default_branch"])
    branches = paged("/branches")
    pulls = paged("/pulls?state=open")

    live_refs: set[str] = set()
    for pull in pulls:
        head = (pull.get("head") or {}).get("ref")
        base = (pull.get("base") or {}).get("ref")
        if isinstance(head, str) and head:
            live_refs.add(head)
        if isinstance(base, str) and base:
            live_refs.add(base)

    mailbox = root_json("DRJ-RECONCILE-REQUEST.json") or {}
    desired = mailbox.get("desired_state") or {}
    persistent = {default_branch}
    for item in desired.get("persistent_refs") or []:
        if isinstance(item, str) and item:
            persistent.add(item)

    rows: list[dict[str, Any]] = []
    counts = {
        "default": 0,
        "zero_unique": 0,
        "divergent_unique": 0,
        "open_pr_protected": 0,
        "github_protected": 0,
        "persistent": 0,
    }

    for branch in sorted(branches, key=lambda item: str(item.get("name", ""))):
        name = str(branch["name"])
        sha = str((branch.get("commit") or {})["sha"])
        protected = bool(branch.get("protected", False))
        is_default = name == default_branch
        is_live = name in live_refs
        is_persistent = name in persistent
        row: dict[str, Any] = {
            "branch": name,
            "sha": sha,
            "is_default": is_default,
            "open_pr_protected": is_live,
            "github_protected": protected,
            "persistent": is_persistent,
        }

        if is_default:
            row["technical_class"] = "DEFAULT"
            counts["default"] += 1
        else:
            compare = api(
                f"/compare/{quote(default_branch, safe='')}...{quote(name, safe='')}"
            )
            ahead = int(compare["ahead_by"])
            behind = int(compare["behind_by"])
            row["ahead_by"] = ahead
            row["behind_by"] = behind
            if ahead == 0:
                row["technical_class"] = "ZERO_UNIQUE"
                counts["zero_unique"] += 1
            else:
                row["technical_class"] = "DIVERGENT_UNIQUE"
                counts["divergent_unique"] += 1

        if is_live and not is_default:
            counts["open_pr_protected"] += 1
        if protected and not is_default:
            counts["github_protected"] += 1
        if is_persistent and not is_default:
            counts["persistent"] += 1
        rows.append(row)

    payload = {
        "schema": "drj.portable_branch_observer.v1",
        "repository": REPOSITORY,
        "repository_id": repo_id,
        "default_branch": default_branch,
        "observed_at": datetime.now(UTC).isoformat(),
        "mode": "READ_ONLY_TECHNICAL_OBSERVATION",
        "effect_authority": False,
        "branch_count": len(branches),
        "non_default_count": max(0, len(branches) - 1),
        "open_pull_count": len(pulls),
        "mailbox_observed_semantic_at": mailbox.get("observed_semantic_at"),
        "counts": counts,
        "branches": rows,
        "invariants": [
            "NO_MUTATION_API",
            "NO_DELETE_AUTHORITY",
            "NAME_AGE_COUNT_NEVER_CLASSIFY_SEMANTIC_VALUE",
            "ZERO_UNIQUE_IS_TECHNICAL_STATE_ONLY",
            "DIVERGENT_UNIQUE_REQUIRES_SEMANTIC_HARVEST_CANONICALIZE_OR_REJECT",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"repository": REPOSITORY, "counts": counts, "output": str(OUT)}))


if __name__ == "__main__":
    main()
