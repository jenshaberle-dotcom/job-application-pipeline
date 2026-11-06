"""JAP local safety gate: audit, source-only backup, isolated PoC staging, apply.

Run inside WSL/Linux. Never pushes secrets, runtime databases or downloaded job
records. Never modifies the live checkout before an explicitly approved apply.
Standard library only; staging runs the existing PoC's pytest suite.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from uuid import uuid4

CLASSIC = "jenshaberle-dotcom/job-application-pipeline"
RUNTIME = "jenshaberle-dotcom/job-pipeline-runtime"
POC = "poc/hannover-tech-registry-factory-e2e-20261106"
TESTS = (
    "tests/test_hannover_tech_registry_poc.py",
    "tests/test_hannover_profile_market.py",
    "tests/test_hannover_solution_architecture_staging.py",
)
SAFE_SUFFIX = {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".rst",
               ".txt", ".toml", ".yaml", ".yml", ".sql", ".sh", ".ps1",
               ".bat", ".html", ".css", ".scss", ".xml", ".ini", ".cfg"}
SAFE_DIRS = {"src", "scripts", "tests", "frontend", "docs", "contracts", "db",
             ".github", "examples", "config", "tools", "app", "apps", "packages",
             "cli", "bin", "workflows"}
BAN_DIRS = {".git", "node_modules", ".venv", "venv", "runs", "exports", "outputs",
            "logs", "data", "datasets", "artifacts", "backups", "dist", "build",
            "coverage", ".next", "__pycache__", ".pytest_cache", ".cache",
            "secrets", "keys", "tmp", "vendor", "playwright-report", "test-results"}
BAN_NAMES = {".env", "secrets.json", "credentials.json", "token.json", "id_rsa",
             "id_ed25519", "auth.json", "service-account.json", "cookies.json",
             "session.json", ".npmrc", ".pypirc", "config.local.json"}
SENSITIVE = [
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(rb"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{22,}\b"),
    re.compile(rb"\bsk-[A-Za-z0-9_-]{24,}\b"),
    re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{24,}\b"),
]
MAX_FILE = 1_500_000
MAX_TOTAL = 100_000_000
MAX_FILES = 15000


class GateError(RuntimeError):
    pass


def scrub(message: str) -> str:
    return re.sub(r"(https?://)[^/\s@]+@", r"\1[REDACTED]@", message)


def git(where: Path, *args: str, check: bool = True) -> str:
    command = ["git", "-C", str(where), *args]
    p = subprocess.run(command, capture_output=True, text=True, errors="replace")
    if check and p.returncode:
        raise GateError("Git command failed (" + " ".join(args[:3]) + "): " +
                        scrub(p.stderr.strip())[:500])
    return p.stdout.strip()


def root(path: str | Path, expected: str | None) -> Path:
    raw = Path(path).expanduser().resolve(strict=True)
    repo_root = Path(git(raw, "rev-parse", "--show-toplevel")).resolve()
    if raw != repo_root:
        raise GateError(f"Use repository root rather than nested directory: {raw}")
    if expected:
        url = git(raw, "remote", "get-url", "origin")
        path_match = re.search(
            r"(?:github\.com[:/])([^/:]+/[^/:]+?)(?:\.git)?/?$", url
        )
        if not path_match or path_match.group(1).lower() != expected.lower():
            raise GateError(f"origin must be GitHub repository {expected}")
    return raw


def audit_repo(repo: Path) -> dict:
    dirty = git(repo, "status", "--porcelain=v1", "--untracked-files=normal")
    branch = git(repo, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    upstream = git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name",
                   "@{upstream}", check=False)
    ahead, behind = None, None
    if upstream:
        result = git(repo, "rev-list", "--left-right", "--count",
                     f"{upstream}...HEAD", check=False)
        try:
            behind, ahead = map(int, result.split())
        except (ValueError, TypeError):
            pass
    return {
        "local_path": str(repo), "branch": branch or "DETACHED_HEAD",
        "head": git(repo, "rev-parse", "HEAD"),
        "upstream": upstream or None,
        "ahead_local_commits": ahead, "behind_local_commits": behind,
        "changed_path_count": len(dirty.splitlines()),
        "dirty": bool(dirty),
    }


def is_safe(relative: Path) -> bool:
    parts = relative.parts
    if not parts or any(part in BAN_DIRS for part in parts[:-1]):
        return False
    name = parts[-1]
    lower = name.lower()
    if (lower in BAN_NAMES or lower.endswith((".pem", ".key", ".p12", ".pfx",
                                            ".sqlite", ".sqlite3", ".db", ".bak",
                                            ".zip", ".pdf", ".log"))
            or lower.startswith((".env.", "id_rsa", "id_ed25519", "credentials.",
                                 "secrets.", "token.", "client_secret"))):
        return False
    if len(parts) == 1:
        return (name in {"Makefile", "Dockerfile", ".gitignore", ".dockerignore"}
                or lower.startswith(("readme", "requirements", "pyproject",
                                     "package", "docker-compose", "compose")))
    return parts[0] in SAFE_DIRS and relative.suffix.lower() in SAFE_SUFFIX


def source_files(repo: Path) -> tuple[list[tuple[Path, bytes]], dict]:
    # git ls-files is used because arbitrary ignored/untracked data must not be read.
    p = subprocess.run(["git", "-C", str(repo), "ls-files", "--cached", "--others",
                        "--exclude-standard", "-z"], capture_output=True)
    if p.returncode:
        raise GateError("Could not enumerate tracked + unignored untracked source files")
    candidates = sorted(set(os.fsdecode(x) for x in p.stdout.split(b"\x00") if x))
    if len(candidates) > MAX_FILES:
        raise GateError("Too many files for bounded snapshot")
    chosen: list[tuple[Path, bytes]] = []
    skipped = 0
    size = 0
    blocked: list[str] = []
    for name in candidates:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise GateError("Unsafe path in Git index")
        file = repo / relative
        if (not is_safe(relative) or not file.exists() or file.is_symlink()
                or not file.is_file() or not file.resolve().is_relative_to(repo)):
            skipped += 1
            continue
        if file.stat().st_size > MAX_FILE:
            skipped += 1
            continue
        content = file.read_bytes()
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            skipped += 1
            continue
        if any(pattern.search(content) for pattern in SENSITIVE):
            blocked.append(str(relative))
            continue
        size += len(content)
        if size > MAX_TOTAL:
            raise GateError("Source snapshot total exceeds 100 MB budget")
        chosen.append((relative, content))
    if blocked:
        raise GateError("Potential credential material in source files; NO PUSH. " +
                        ", ".join(blocked[:15]))
    if not chosen:
        raise GateError("No eligible source files found; NO PUSH")
    return chosen, {"eligible": len(chosen), "skipped": skipped, "bytes": size}


def plan_snapshot(repo: Path, expected: str, output: Path) -> dict:
    """Preview exact candidate paths and hashes; no Git writes or network calls."""
    files, size = source_files(repo)
    plan = {
        "repository": expected,
        "audit": audit_repo(repo),
        "candidate_source_scope": size,
        "selected_paths_sha256": {
            path.as_posix(): hashlib.sha256(content).hexdigest()
            for path, content in files
        },
        "warning": (
            "Review every selected path before approving a push to a public "
            "repository. Secret patterns are only a basic safety screen."
        ),
    }
    target = output / (expected.split("/")[1] + "-plan.json")
    target.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    return {"plan": str(target), "scope": size}


def backup(repo: Path, expected: str, output: Path) -> dict:
    audit = audit_repo(repo)
    files, size = source_files(repo)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    branch = "backup/jap-host-source-" + timestamp + "-" + uuid4().hex[:8]
    manifest = {
        "schema": "jap.local_source_snapshot.v1", "source_repository": expected,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "local_head": audit["head"], "local_branch": audit["branch"],
        "dirty_at_capture": audit["dirty"], "eligible_files": size["eligible"],
        "skipped_files": size["skipped"], "source_bytes": size["bytes"],
        "note": ("Orphan source snapshot: approved code/docs/tests only; "
                 "not a history backup, not a DB/data/secret backup."),
        "sha256_by_path": {p.as_posix(): hashlib.sha256(b).hexdigest() for p, b in files},
    }
    with tempfile.TemporaryDirectory(prefix="jap-safe-snapshot-") as temporary:
        temp = Path(temporary)
        git(temp, "init", "-q")
        for relative, content in files:
            dest = temp / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
        (temp / "JAP_LOCAL_SOURCE_SNAPSHOT.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        git(temp, "add", "--all", "--force")
        git(temp, "-c", "user.name=JAP Local Snapshot", "-c",
            "user.email=jap-snapshot@localhost", "commit", "-qm",
            "Source-only snapshot: " + expected + " from " + audit["head"][:10])
        sha = git(temp, "rev-parse", "HEAD")
        origin = git(repo, "remote", "get-url", "origin")
        git(temp, "remote", "add", "origin", origin)
        git(temp, "push", "--quiet", "origin", "HEAD:refs/heads/" + branch)
    fetched = git(repo, "ls-remote", "--heads", "origin", branch)
    if not fetched or fetched.split()[0] != sha:
        raise GateError("Remote backup verification mismatch; do not stage integration")
    receipt = {
        "repo": expected, "backup_branch": branch, "backup_sha": sha,
        "remote_verified": True, "audit": audit, "scope": size,
        "source_only": True,
    }
    (output / (expected.split("/")[1] + "-backup.json")).write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def stage_poc(classic: Path, output: Path) -> dict:
    baseline = audit_repo(classic)
    classic_receipt = output / "job-application-pipeline-backup.json"
    runtime_receipt = output / "job-pipeline-runtime-backup.json"
    if not classic_receipt.exists() or not runtime_receipt.exists():
        raise GateError("Both remote snapshot receipts are required before staging")
    for receipt_file in (classic_receipt, runtime_receipt):
        if not json.loads(receipt_file.read_text(encoding="utf-8")).get("remote_verified"):
            raise GateError("Backup not verified, cannot stage")
    git(classic, "fetch", "origin", POC + ":refs/remotes/origin/" + POC)
    slug = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:6]
    branch = "integration/hannover-profile-poc-" + slug
    worktree = output / ("integration-" + slug)
    git(classic, "worktree", "add", "-b", branch, str(worktree), baseline["head"])
    receipt = {"status": "not_validated", "source_path": str(classic),
               "base_branch": baseline["branch"], "base_sha": baseline["head"],
               "integration_branch": branch, "worktree_path": str(worktree),
               "poc_ref": POC, "integration_sha": None, "tests_passed": False}
    try:
        git(worktree, "merge", "--no-ff", "--no-commit", "refs/remotes/origin/" + POC)
    except GateError as exc:
        receipt["status"] = "merge_conflict_manual_review"
        receipt["error"] = str(exc)
    else:
        p = subprocess.run([sys.executable, "-m", "pytest", "-q", *TESTS],
                           cwd=worktree, capture_output=True, text=True)
        (output / "integration-tests.log").write_text(
            p.stdout + "\n" + p.stderr, encoding="utf-8")
        if p.returncode:
            receipt["status"] = "tests_failed_no_apply"
            receipt["test_exit_code"] = p.returncode
        else:
            if git(worktree, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False):
                git(worktree, "-c", "user.name=JAP PoC Integration", "-c",
                    "user.email=jap-integration@localhost", "commit", "-qm",
                    "Merge isolated Hannover profile PoC after local tests")
            receipt["integration_sha"] = git(worktree, "rev-parse", "HEAD")
            receipt["tests_passed"] = True
            receipt["status"] = "staged_tested_not_applied"
    (output / "integration-receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def apply_poc(classic: Path, output: Path) -> dict:
    receipt_file = output / "integration-receipt.json"
    if not receipt_file.exists():
        raise GateError("No integration receipt; run prepare first")
    receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    if receipt.get("status") != "staged_tested_not_applied" or not receipt.get("tests_passed"):
        raise GateError("Only a fully tested integration may be applied")
    if str(classic) != receipt.get("source_path"):
        raise GateError("Integration belongs to another classic checkout")
    audit = audit_repo(classic)
    if audit["dirty"] or audit["branch"] != receipt["base_branch"]:
        raise GateError("Active working tree must be clean on the original branch")
    if audit["head"] != receipt["base_sha"]:
        raise GateError("Local HEAD changed since staging; run prepare again")
    if git(classic, "rev-parse", receipt["integration_branch"]) != receipt["integration_sha"]:
        raise GateError("Staged integration branch changed; refuse to apply")
    git(classic, "merge", "--ff-only", receipt["integration_branch"])
    receipt["status"] = "applied_locally_not_pushed"
    receipt["applied_sha"] = git(classic, "rev-parse", "HEAD")
    receipt_file.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--classic", required=True, help="Path to live JAP Classic checkout")
    parser.add_argument("--runtime", required=True, help="Path to live JAP Runtime checkout")
    parser.add_argument("--output", default="~/jap-poc-guard", help="Receipts outside git repositories")
    parser.add_argument("action", choices=("audit", "plan", "backup", "prepare", "apply"))
    parser.add_argument("--confirm", default="", help="Explicit mutation approval token")
    args = parser.parse_args()
    try:
        classic = root(args.classic, CLASSIC)
        runtime = root(args.runtime, RUNTIME)
        output = Path(args.output).expanduser().resolve()
        if any(output == r or r in output.parents for r in (classic, runtime)):
            raise GateError("Output directory must be outside both live repositories")
        if args.action == "audit":
            print(json.dumps({"classic": audit_repo(classic),
                              "runtime": audit_repo(runtime)}, indent=2))
            return
        if args.action == "plan":
            output.mkdir(parents=True, exist_ok=True)
            print(json.dumps({"classic": plan_snapshot(classic, CLASSIC, output),
                              "runtime": plan_snapshot(runtime, RUNTIME, output)},
                             indent=2))
            return
        expected = {"backup": "BACKUP", "prepare": "BACKUP_AND_STAGE", "apply": "APPLY"}
        if args.confirm != expected[args.action]:
            raise GateError("Explicit --confirm " + expected[args.action] + " is required")
        output.mkdir(parents=True, exist_ok=True)
        if args.action in ("backup", "prepare"):
            print("BACKUP classic (safe source-only snapshot)...", flush=True)
            c = backup(classic, CLASSIC, output)
            print("Remote verified:", c["repo"], c["backup_branch"], flush=True)
            print("BACKUP runtime (safe source-only snapshot)...", flush=True)
            r = backup(runtime, RUNTIME, output)
            print("Remote verified:", r["repo"], r["backup_branch"], flush=True)
            if args.action == "prepare":
                receipt = stage_poc(classic, output)
                print(json.dumps(receipt, indent=2))
        elif args.action == "apply":
            print(json.dumps(apply_poc(classic, output), indent=2))
    except (GateError, FileNotFoundError, OSError, ValueError) as exc:
        print("STOP: " + scrub(str(exc)), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

