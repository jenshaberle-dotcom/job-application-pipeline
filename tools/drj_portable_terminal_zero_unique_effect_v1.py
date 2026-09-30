#!/usr/bin/env python3
"""DRJ portable terminal ZERO_UNIQUE effect executor v1.

This is a narrow cross-repository transport executor for branches that already have
an explicit terminal SAFE_TO_RETIRE disposition in DRJ portfolio truth. It never
infers semantic value from branch name, age, merge state or count. Every target is
exact-SHA bound, all targets pass a complete read-only preflight before any effect,
and every target is re-observed immediately before one exact DELETE. Divergent,
protected, live-PR, default, moved-main or SHA-drifted refs fail closed.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
SCHEMA = "drj.portfolio_terminal_zero_unique_authority.v1"
MAX_EFFECTS = 20
MAX_TTL_SECONDS = 15 * 60
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
AUTHORITY_FIELDS = {
    "schema_version",
    "repository",
    "repository_id",
    "authority_head_sha",
    "effect_authorized",
    "authority_reference",
    "issued_at",
    "expires_at",
    "max_effects",
    "targets",
}
TARGET_FIELDS = {
    "branch",
    "expected_sha",
    "terminal_disposition",
    "terminal_record_ref",
}


class EffectError(RuntimeError):
    pass


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise EffectError(f"{field} must be a non-empty ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EffectError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise EffectError(f"{field} must be timezone-aware")
    return parsed.astimezone(UTC)


def _exact_branch(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise EffectError("branch must be non-empty")
    branch = value.removeprefix("refs/heads/")
    if not branch or "*" in branch or "?" in branch or branch.startswith("scope:"):
        raise EffectError("branch must be one exact ref")
    return branch


def load_authority(path: Path, repository: str, now: datetime | None = None) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != AUTHORITY_FIELDS:
        raise EffectError("authority fields do not match canonical schema")
    if value["schema_version"] != SCHEMA:
        raise EffectError("unsupported authority schema")
    if value["repository"] != repository:
        raise EffectError("authority repository mismatch")
    if not isinstance(value["repository_id"], int) or isinstance(value["repository_id"], bool):
        raise EffectError("repository_id must be an integer")
    if not isinstance(value["authority_head_sha"], str) or _SHA40.fullmatch(value["authority_head_sha"]) is None:
        raise EffectError("authority_head_sha must be exact lowercase SHA")
    if value["effect_authorized"] is not True:
        raise EffectError("effect_authorized must be true")
    reference = value["authority_reference"]
    if not isinstance(reference, str) or not reference.startswith(
        "github-issue-comment:jenshaberle-dotcom/Data-Retention-Janitor#76:"
    ):
        raise EffectError("authority_reference must bind DRJ owner Issue #76 comment")
    issued = _timestamp(value["issued_at"], "issued_at")
    expires = _timestamp(value["expires_at"], "expires_at")
    if expires <= issued or (expires - issued).total_seconds() > MAX_TTL_SECONDS:
        raise EffectError("authority TTL must be >0 and <=15 minutes")
    observed = (now or datetime.now(UTC)).astimezone(UTC)
    if observed < issued or observed > expires:
        raise EffectError("authority is not currently valid")
    max_effects = value["max_effects"]
    if not isinstance(max_effects, int) or isinstance(max_effects, bool) or not 1 <= max_effects <= MAX_EFFECTS:
        raise EffectError("max_effects must be between 1 and 20")
    targets = value["targets"]
    if not isinstance(targets, list) or len(targets) != max_effects:
        raise EffectError("targets must contain exactly max_effects items")
    seen: set[str] = set()
    normalized: list[dict[str, str]] = []
    for item in targets:
        if not isinstance(item, dict) or set(item) != TARGET_FIELDS:
            raise EffectError("target fields do not match canonical schema")
        branch = _exact_branch(item["branch"])
        sha = item["expected_sha"]
        if not isinstance(sha, str) or _SHA40.fullmatch(sha) is None:
            raise EffectError(f"expected_sha invalid for {branch}")
        if item["terminal_disposition"] != "SAFE_TO_RETIRE":
            raise EffectError(f"terminal disposition is not SAFE_TO_RETIRE for {branch}")
        record = item["terminal_record_ref"]
        if not isinstance(record, str) or not record.startswith(
            "github:jenshaberle-dotcom/Data-Retention-Janitor/docs/status/current/portfolio-disposition/"
        ):
            raise EffectError(f"terminal_record_ref is not canonical DRJ disposition for {branch}")
        if branch in seen:
            raise EffectError(f"duplicate target {branch}")
        seen.add(branch)
        normalized.append({**item, "branch": branch})
    return {**value, "targets": normalized}


class GitHubApi:
    def __init__(self, repository: str, token: str):
        self.repository = repository
        self.token = token

    def call(self, method: str, path: str, *, allow_404: bool = False) -> Any:
        req = Request(
            f"{API_ROOT}/repos/{self.repository}{path}",
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "drj-portable-terminal-zero-unique-effect-v1",
            },
        )
        try:
            with urlopen(req, timeout=30) as response:  # noqa: S310
                raw = response.read()
                return json.loads(raw) if raw else None
        except HTTPError as exc:
            if allow_404 and exc.code == 404:
                return None
            detail = exc.read().decode("utf-8", errors="replace")
            raise EffectError(f"GitHub API {method} {path} failed: {exc.code} {detail}") from exc


def observe(api: GitHubApi, authority: dict[str, Any], target: dict[str, str]) -> dict[str, Any]:
    repo = api.call("GET", "")
    repo_id = int(repo["id"])
    if repo_id != authority["repository_id"]:
        raise EffectError("repository identity mismatch")
    default = str(repo["default_branch"])
    branch = target["branch"]
    if branch == default:
        raise EffectError("default branch can never be a target")

    default_ref = api.call("GET", f"/git/ref/heads/{quote(default, safe='/')}")
    default_sha = str((default_ref.get("object") or {}).get("sha") or "")
    if default_sha != authority["authority_head_sha"]:
        raise EffectError(
            f"canonical main moved: expected={authority['authority_head_sha']} observed={default_sha}"
        )

    ref = api.call("GET", f"/git/ref/heads/{quote(branch, safe='/')}", allow_404=True)
    if ref is None:
        raise EffectError(f"target ref already absent: {branch}")
    sha = str((ref.get("object") or {}).get("sha") or "")
    if sha != target["expected_sha"]:
        raise EffectError(f"target SHA drift for {branch}: expected={target['expected_sha']} observed={sha}")

    branch_info = api.call("GET", f"/branches/{quote(branch, safe='')}")
    protected = bool(branch_info.get("protected", False))
    if protected:
        raise EffectError(f"GitHub protection blocks {branch}")

    owner = authority["repository"].split("/", 1)[0]
    head_q = urlencode({"state": "open", "head": f"{owner}:{branch}", "per_page": "1"})
    base_q = urlencode({"state": "open", "base": branch, "per_page": "1"})
    if api.call("GET", f"/pulls?{head_q}") or api.call("GET", f"/pulls?{base_q}"):
        raise EffectError(f"open PR protects {branch}")

    compare = api.call("GET", f"/compare/{quote(default, safe='')}...{quote(branch, safe='')}")
    ahead = int(compare["ahead_by"])
    behind = int(compare["behind_by"])
    if ahead != 0:
        raise EffectError(f"ZERO_UNIQUE required for {branch}, ahead_by={ahead}")
    return {
        "branch": branch,
        "sha": sha,
        "default_branch": default,
        "authority_head_sha": default_sha,
        "ahead_by": ahead,
        "behind_by": behind,
        "protected": False,
        "open_pr": False,
        "terminal_disposition": target["terminal_disposition"],
        "terminal_record_ref": target["terminal_record_ref"],
    }


def delete_exact(api: GitHubApi, observation: dict[str, Any]) -> dict[str, Any]:
    branch = observation["branch"]
    api.call("DELETE", f"/git/refs/heads/{quote(branch, safe='/')}")
    absent = api.call("GET", f"/git/ref/heads/{quote(branch, safe='/')}", allow_404=True) is None
    if not absent:
        raise EffectError(f"post-effect absence verification failed for {branch}")
    return {
        "branch": branch,
        "target_sha": observation["sha"],
        "state": "RECONCILED_PASS",
        "verified_absent": True,
        "terminal_record_ref": observation["terminal_record_ref"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="DRJ terminal ZERO_UNIQUE effect v1")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--authority", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise EffectError("GH_TOKEN is required")
    authority = load_authority(Path(args.authority), args.repository)
    api = GitHubApi(args.repository, token)

    # Complete cohort preflight first: zero effects unless every target is currently clear.
    prepared: dict[str, dict[str, Any]] = {}
    for target in authority["targets"]:
        prepared[target["branch"]] = observe(api, authority, target)

    campaign: dict[str, Any] = {
        "schema_version": "drj.portfolio_terminal_zero_unique_effect_outcome.v1",
        "repository": args.repository,
        "repository_id": authority["repository_id"],
        "authority_reference": authority["authority_reference"],
        "authority_head_sha": authority["authority_head_sha"],
        "requested": len(authority["targets"]),
        "effects_attempted": 0,
        "effects_reconciled_pass": 0,
        "state": "PREFLIGHT_PASS",
        "results": [],
    }
    failure: str | None = None
    for target in authority["targets"]:
        branch = target["branch"]
        try:
            fresh = observe(api, authority, target)
            if fresh != prepared[branch]:
                raise EffectError(f"target precondition drift after cohort preflight: {branch}")
            campaign["effects_attempted"] += 1
            result = delete_exact(api, fresh)
            campaign["results"].append(result)
            campaign["effects_reconciled_pass"] += 1
        except Exception as exc:
            failure = f"{exc.__class__.__name__}: {exc}"
            campaign["state"] = "PARTIAL_FAIL_CLOSED"
            campaign["failure"] = failure
            break
    if failure is None:
        campaign["state"] = "RECONCILED_PASS"
    Path(args.output).write_text(json.dumps(campaign, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(campaign, indent=2, sort_keys=True))
    return 0 if failure is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
