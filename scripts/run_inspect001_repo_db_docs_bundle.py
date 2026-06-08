#!/usr/bin/env python3
"""INSPECT-001A read-only Repo/DB/Docs inspection bundle.

This script creates a compact inspection report for the current repository state.
It is intentionally read-only:
- no external network requests
- no database writes
- no candidate, gate, connector, Bronze/Silver/Gold, scheduler, or UI mutation

Outputs:
- exports/inspect001_repo_db_docs_bundle_<timestamp>.json
- exports/inspect001_repo_db_docs_bundle_<timestamp>.md
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_DOC_PATHS = [
    "README.md",
    "docs/README.md",
    "docs/current",
    "docs/guides",
    "docs/reference",
    "docs/decisions",
    "docs/planning",
    "docs/archive",
]

EXPECTED_TOOLING_PATHS = [
    "scripts/run_project_state_snapshot.py",
    "scripts/run_inspect001_repo_db_docs_bundle.py",
]

EXPECTED_DB_RELATIONS = [
    "raw_jobs",
    "ingestion_runs",
    "search_profiles",
    "search_terms",
    "silver_jobs",
    "employer_origin_source_candidates",
    "employer_origin_candidate_gate_reviews",
    "employer_origin_candidate_gate_events",
    "gold_candidate_lifecycle_status",
    "search_intelligence_orchestrator_runs",
    "search_intelligence_orchestrator_steps",
]

HORIZONTAL_BUNDLE_ALLOWED_SCOPE = [
    "governance documentation",
    "validation tooling",
    "inspection tooling",
    "handover tooling",
    "read-only state and next-safe-action reporting",
]
HORIZONTAL_BUNDLE_EXCLUDED_SCOPE = [
    "product pipeline decisions",
    "database mutation",
    "external source execution",
    "scheduler semantics",
    "candidate, gate, connector, Bronze, Silver, or Gold behavior",
]


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_command(command: list[str], cwd: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        return {
            "command": command,
            "exit_code": 127,
            "stdout": "",
            "stderr": str(exc),
            "ok": False,
        }

    return {
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "ok": completed.returncode == 0,
    }


def status_from_missing(missing: list[str]) -> str:
    return "pass" if not missing else "warn"


def inspect_git(root: Path) -> dict[str, Any]:
    branch = run_command(["git", "branch", "--show-current"], root)
    head = run_command(["git", "log", "-1", "--oneline", "--decorate"], root)
    status = run_command(["git", "status", "--short"], root)
    recent = run_command(["git", "log", "--oneline", "-5"], root)

    changed_files = [
        line.strip()
        for line in status["stdout"].splitlines()
        if line.strip()
    ]

    git_available = bool(branch["ok"] and head["ok"] and status["ok"])
    return {
        "status": "pass" if git_available and not changed_files else "warn",
        "branch": branch["stdout"],
        "head": head["stdout"],
        "dirty": bool(changed_files),
        "changed_files": changed_files,
        "recent_log": recent["stdout"].splitlines() if recent["ok"] else [],
        "command_errors": [
            {
                "command": result["command"],
                "exit_code": result["exit_code"],
                "stderr": result["stderr"],
            }
            for result in [branch, head, status, recent]
            if not result["ok"]
        ],
    }


def inspect_paths(root: Path, expected_paths: list[str]) -> dict[str, Any]:
    present: list[str] = []
    missing: list[str] = []

    for relative in expected_paths:
        path = root / relative
        if path.exists():
            present.append(relative)
        else:
            missing.append(relative)

    return {
        "status": status_from_missing(missing),
        "present": present,
        "missing": missing,
    }


def inspect_migrations(root: Path) -> dict[str, Any]:
    migration_roots = [
        root / "migrations",
        root / "sql" / "migrations",
        root / "db" / "migrations",
    ]
    existing_roots = [path for path in migration_roots if path.exists()]

    files: list[str] = []
    for migration_root in existing_roots:
        files.extend(
            str(path.relative_to(root))
            for path in sorted(migration_root.rglob("*"))
            if path.is_file()
        )

    if not existing_roots:
        return {
            "status": "unavailable",
            "reason": "No known migration directory found.",
            "migration_roots": [],
            "file_count": 0,
            "tail": [],
        }

    return {
        "status": "pass" if files else "warn",
        "reason": "Migration files found." if files else "Migration directories exist but no files were found.",
        "migration_roots": [str(path.relative_to(root)) for path in existing_roots],
        "file_count": len(files),
        "tail": files[-30:],
    }


def database_url_from_env() -> str | None:
    for name in ["JOB_PIPELINE_DATABASE_URL", "DATABASE_URL", "POSTGRES_DSN"]:
        value = os.environ.get(name)
        if value:
            return value
    return None


def inspect_database(expected_relations: list[str]) -> dict[str, Any]:
    dsn = database_url_from_env()
    if not dsn:
        return {
            "status": "unavailable",
            "reason": "No database DSN found in JOB_PIPELINE_DATABASE_URL, DATABASE_URL, or POSTGRES_DSN.",
            "read_only_transaction": False,
            "relations_checked": expected_relations,
            "present_relations": [],
            "missing_relations": [],
        }

    try:
        import psycopg
    except ImportError as exc:
        return {
            "status": "unavailable",
            "reason": f"psycopg import failed: {exc}",
            "read_only_transaction": False,
            "relations_checked": expected_relations,
            "present_relations": [],
            "missing_relations": [],
        }

    try:
        with psycopg.connect(dsn, autocommit=False) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                    """
                )
                relation_names = {row[0] for row in cursor.fetchall()}

                present = [
                    relation
                    for relation in expected_relations
                    if relation in relation_names
                ]
                missing = [
                    relation
                    for relation in expected_relations
                    if relation not in relation_names
                ]

                connection.rollback()

        return {
            "status": "pass" if not missing else "warn",
            "reason": "Database inspection completed in a read-only transaction.",
            "read_only_transaction": True,
            "relations_checked": expected_relations,
            "present_relations": present,
            "missing_relations": missing,
        }
    except Exception as exc:  # pragma: no cover - defensive boundary reporting
        return {
            "status": "unavailable",
            "reason": f"Database inspection failed: {exc}",
            "read_only_transaction": False,
            "relations_checked": expected_relations,
            "present_relations": [],
            "missing_relations": [],
        }



def build_horizontal_bundle_eligibility(sections: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []

    git = sections["git"]
    if git["status"] != "pass":
        blockers.append("git_state_not_pass")
    if git["dirty"]:
        blockers.append("worktree_dirty")
    if sections["documentation"]["status"] != "pass":
        blockers.append("documentation_structure_not_pass")
    if sections["tooling"]["status"] != "pass":
        blockers.append("tooling_anchors_not_pass")
    if sections["migrations"]["status"] not in {"pass", "warn"}:
        blockers.append("migration_visibility_unavailable")

    return {
        "mode_id": "FREEZE-001A",
        "eligible": not blockers,
        "blocked_reasons": blockers,
        "database_inspection_required": False,
        "database_unavailable_is_blocking": False,
        "impact_matrix": {
            "pipeline_decision": False,
            "database_mutation": False,
            "external_requests": False,
            "scheduler_coupling": False,
            "candidate_gate_connector_coupling": False,
            "bronze_silver_gold_coupling": False,
            "hidden_runtime_dependency_allowed": False,
        },
        "allowed_scope": HORIZONTAL_BUNDLE_ALLOWED_SCOPE,
        "excluded_scope": HORIZONTAL_BUNDLE_EXCLUDED_SCOPE,
        "fan_in_validation_required": [
            "targeted tests for every touched tooling surface",
            "python scripts/run_validate001_unified_validation.py --profile commit",
            "git diff --check",
            "git status --short",
        ],
    }

def build_report(root: Path, include_db: bool) -> dict[str, Any]:
    sections = {
        "git": inspect_git(root),
        "documentation": inspect_paths(root, EXPECTED_DOC_PATHS),
        "tooling": inspect_paths(root, EXPECTED_TOOLING_PATHS),
        "migrations": inspect_migrations(root),
        "database": (
            inspect_database(EXPECTED_DB_RELATIONS)
            if include_db
            else {
                "status": "skipped",
                "reason": "Database inspection disabled. Pass --include-db to attempt read-only DB checks.",
                "read_only_transaction": False,
                "relations_checked": EXPECTED_DB_RELATIONS,
                "present_relations": [],
                "missing_relations": [],
            }
        ),
    }

    horizontal_bundle_eligibility = build_horizontal_bundle_eligibility(sections)

    section_statuses = [section["status"] for section in sections.values()]
    if any(status == "fail" for status in section_statuses):
        overall_status = "fail"
    elif any(status in {"warn", "unavailable"} for status in section_statuses):
        overall_status = "warn"
    else:
        overall_status = "pass"

    return {
        "schema_version": "inspect001.repo_db_docs_bundle.v1",
        "generated_at_utc": iso_now(),
        "repo_root": str(root),
        "overall_status": overall_status,
        "safety_boundary": {
            "read_only": True,
            "external_requests": False,
            "database_writes": False,
            "pipeline_mutation": False,
            "candidate_or_gate_mutation": False,
            "connector_activation": False,
        },
        "horizontal_bundle_eligibility": horizontal_bundle_eligibility,
        "sections": sections,
        "next_safe_action": {
            "action": "review_inspection_report_then_select_next_patch",
            "requires_user_decision": overall_status != "pass",
            "reason": (
                "Warnings or unavailable checks should be reviewed before using the report as a handover anchor."
                if overall_status != "pass"
                else "Inspection passed; next patch can be selected from the current work-item sequence."
            ),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    sections = report["sections"]
    eligibility = report.get("horizontal_bundle_eligibility") or {}
    lines = [
        "# INSPECT-001A Repo/DB/Docs Inspection Bundle",
        "",
        f"Generated: `{report['generated_at_utc']}`",
        f"Schema: `{report['schema_version']}`",
        f"Overall status: `{report['overall_status']}`",
        "",
        "## Safety boundary",
        "",
    ]

    for key, value in report["safety_boundary"].items():
        lines.append(f"- {key}: `{value}`")

    lines.extend([
        "",
        "## Horizontal bundle eligibility",
        "",
        f"- Mode ID: `{eligibility.get('mode_id')}`",
        f"- Eligible: `{eligibility.get('eligible')}`",
        f"- Blocked reasons: `{', '.join(eligibility.get('blocked_reasons') or []) or 'none'}`",
        f"- Database inspection required: `{eligibility.get('database_inspection_required')}`",
        f"- Database unavailable is blocking: `{eligibility.get('database_unavailable_is_blocking')}`",
        "",
        "### Excluded scope",
        "",
    ])
    lines.extend([f"- {item}" for item in eligibility.get("excluded_scope") or []] or ["- none"])

    git = sections["git"]
    lines.extend([
        "",
        "## Git",
        "",
        f"- Status: `{git['status']}`",
        f"- Branch: `{git['branch']}`",
        f"- Head: `{git['head']}`",
        f"- Dirty: `{git['dirty']}`",
        "",
        "### Changed files",
        "",
    ])
    lines.extend([f"- `{item}`" for item in git["changed_files"]] or ["- none"])

    docs = sections["documentation"]
    lines.extend([
        "",
        "## Documentation structure",
        "",
        f"- Status: `{docs['status']}`",
        "",
        "### Missing expected paths",
        "",
    ])
    lines.extend([f"- `{item}`" for item in docs["missing"]] or ["- none"])

    tooling = sections["tooling"]
    lines.extend([
        "",
        "## Tooling anchors",
        "",
        f"- Status: `{tooling['status']}`",
        "",
        "### Missing expected paths",
        "",
    ])
    lines.extend([f"- `{item}`" for item in tooling["missing"]] or ["- none"])

    migrations = sections["migrations"]
    lines.extend([
        "",
        "## Migrations",
        "",
        f"- Status: `{migrations['status']}`",
        f"- Reason: {migrations['reason']}",
        f"- File count: `{migrations['file_count']}`",
        "",
        "### Latest migration files",
        "",
    ])
    lines.extend([f"- `{item}`" for item in migrations["tail"]] or ["- none"])

    database = sections["database"]
    lines.extend([
        "",
        "## Database",
        "",
        f"- Status: `{database['status']}`",
        f"- Reason: {database['reason']}",
        f"- Read-only transaction: `{database['read_only_transaction']}`",
        "",
        "### Missing expected relations",
        "",
    ])
    lines.extend([f"- `{item}`" for item in database["missing_relations"]] or ["- none"])

    next_safe_action = report["next_safe_action"]
    lines.extend([
        "",
        "## Next safe action",
        "",
        f"- Action: `{next_safe_action['action']}`",
        f"- Requires user decision: `{next_safe_action['requires_user_decision']}`",
        f"- Reason: {next_safe_action['reason']}",
        "",
    ])

    return "\n".join(lines)


def write_reports(report: dict[str, Any], output_dir: Path, stamp: str) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / f"inspect001_repo_db_docs_bundle_{stamp}.json"
    markdown_path = output_dir / f"inspect001_repo_db_docs_bundle_{stamp}.md"

    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(report), encoding="utf-8")

    return {
        "json": str(json_path),
        "markdown": str(markdown_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a read-only INSPECT-001A Repo/DB/Docs inspection bundle."
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root. Defaults to current working directory.",
    )
    parser.add_argument(
        "--output-dir",
        default="exports",
        help="Output directory for JSON/Markdown reports. Defaults to exports/.",
    )
    parser.add_argument(
        "--include-db",
        action="store_true",
        help="Attempt read-only DB checks using JOB_PIPELINE_DATABASE_URL, DATABASE_URL, or POSTGRES_DSN.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    output_dir = Path(args.output_dir)

    stamp = utc_timestamp()
    report = build_report(root=root, include_db=args.include_db)
    written = write_reports(report, output_dir=output_dir, stamp=stamp)

    print("# INSPECT-001A Repo/DB/Docs Inspection Bundle")
    print(f"overall_status={report['overall_status']}")
    print(f"json={written['json']}")
    print(f"markdown={written['markdown']}")
    return 0 if report["overall_status"] in {"pass", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
