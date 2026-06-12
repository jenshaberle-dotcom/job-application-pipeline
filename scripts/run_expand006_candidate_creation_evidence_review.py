#!/usr/bin/env python3
"""EXPAND-006 read-only candidate creation evidence review.

This script is intentionally additive and defensive. It creates a review report
that can support the next controlled candidate creation decision without
creating candidates, updating gates, activating connectors, mutating pipeline
state, or contacting external services.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "expand006.candidate_creation_evidence_review.v1"
DEFAULT_EXPORT_PREFIX = "expand006_candidate_creation_evidence_review"

SAFETY_BOUNDARY: dict[str, bool] = {
    "read_only": True,
    "external_requests": False,
    "database_writes": False,
    "pipeline_mutation": False,
    "candidate_or_gate_mutation": False,
    "connector_activation": False,
    "scheduler_change": False,
}

RELEVANT_RELATION_HINTS = (
    "candidate",
    "market",
    "evidence",
    "origin",
    "gate",
    "review",
    "dry",
    "expand",
)

KNOWN_RELATIONS = (
    "employer_origin_source_candidates",
    "market_evidence",
    "employer_origin_candidate_gate_reviews",
    "employer_origin_candidate_gate_events",
    "gold_candidate_lifecycle_status",
    "search_intelligence_orchestrator_runs",
    "search_intelligence_orchestrator_steps",
    "gold_search_intelligence_orchestrator_attention_steps",
)

STATUS_COLUMN_CANDIDATES = (
    "status",
    "candidate_status",
    "review_status",
    "gate_status",
    "decision",
    "lifecycle_status",
    "current_stage",
    "source_type",
    "evidence_origin",
    "decision_boundary",
)

IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def timestamp_for_filename(now: datetime | None = None) -> str:
    value = now or datetime.now(timezone.utc)
    return value.strftime("%Y%m%d-%H%M%S")


def repo_root_from(start: Path | None = None) -> Path:
    start = start or Path.cwd()
    try:
        output = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start,
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
        if output:
            return Path(output)
    except Exception:
        pass
    return start.resolve()


def run_command(cmd: list[str], cwd: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            cmd,
            cwd=cwd,
            check=False,
            text=True,
            capture_output=True,
            timeout=30,
        )
        return {
            "command": cmd,
            "exit_code": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except Exception as exc:
        return {"command": cmd, "exit_code": None, "stdout": "", "stderr": str(exc)}


def collect_git_context(root: Path) -> dict[str, Any]:
    branch = run_command(["git", "branch", "--show-current"], root)
    head = run_command(["git", "log", "-1", "--oneline", "--decorate"], root)
    status = run_command(["git", "status", "--short"], root)
    return {
        "branch": branch.get("stdout", ""),
        "head": head.get("stdout", ""),
        "dirty": bool(status.get("stdout", "")),
        "status_short": status.get("stdout", ""),
        "command_errors": [
            item for item in (branch, head, status) if item.get("exit_code") not in (0, None)
        ],
    }


def collect_migration_hints(root: Path) -> dict[str, Any]:
    migration_dir = root / "db" / "migrations"
    if not migration_dir.exists():
        return {"status": "missing", "migration_dir": str(migration_dir), "matches": []}

    matches: list[dict[str, Any]] = []
    for path in sorted(migration_dir.glob("*.sql")):
        text = path.read_text(encoding="utf-8", errors="replace")
        lower = text.lower()
        hit_terms = [term for term in RELEVANT_RELATION_HINTS if term in lower]
        if hit_terms:
            matches.append(
                {
                    "path": str(path.relative_to(root)),
                    "hit_terms": hit_terms,
                    "line_count": len(text.splitlines()),
                }
            )
    return {
        "status": "pass",
        "migration_dir": str(migration_dir.relative_to(root)),
        "match_count": len(matches),
        "matches_tail": matches[-25:],
    }


def quote_ident(identifier: str) -> str:
    if not IDENTIFIER_RE.match(identifier):
        raise ValueError(f"Unsafe SQL identifier: {identifier!r}")
    return '"' + identifier.replace('"', '""') + '"'


def safe_json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [safe_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): safe_json_value(val) for key, val in value.items()}
    return str(value)


@dataclass(frozen=True)
class RelationRef:
    schema: str
    name: str
    kind: str

    @property
    def qualified_sql(self) -> str:
        return f"{quote_ident(self.schema)}.{quote_ident(self.name)}"

    @property
    def qualified_name(self) -> str:
        return f"{self.schema}.{self.name}"


def connect_db(database_url: str | None) -> Any:
    try:
        import psycopg  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local environment
        raise RuntimeError(f"psycopg unavailable: {exc}") from exc

    if database_url:
        return psycopg.connect(database_url)

    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return psycopg.connect(env_url)

    # Let libpq use PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD/.pgpass/defaults.
    return psycopg.connect("")


def fetch_relation_columns(cur: Any, relation: RelationRef) -> list[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
        """,
        (relation.schema, relation.name),
    )
    return [row[0] for row in cur.fetchall()]


def fetch_status_breakdowns(cur: Any, relation: RelationRef, columns: list[str]) -> list[dict[str, Any]]:
    breakdowns: list[dict[str, Any]] = []
    for column in STATUS_COLUMN_CANDIDATES:
        if column not in columns:
            continue
        sql = (
            f"SELECT {quote_ident(column)}::text AS value, count(*) AS row_count "
            f"FROM {relation.qualified_sql} "
            f"GROUP BY {quote_ident(column)}::text "
            "ORDER BY row_count DESC, value NULLS LAST LIMIT 20"
        )
        cur.execute(sql)
        breakdowns.append(
            {
                "column": column,
                "values": [
                    {"value": safe_json_value(row[0]), "row_count": row[1]}
                    for row in cur.fetchall()
                ],
            }
        )
    return breakdowns


def fetch_sample_rows(cur: Any, relation: RelationRef, columns: list[str], limit: int) -> list[dict[str, Any]]:
    if not columns or limit <= 0:
        return []
    selected_columns = columns[: min(len(columns), 20)]
    sql = (
        "SELECT "
        + ", ".join(quote_ident(column) for column in selected_columns)
        + f" FROM {relation.qualified_sql} LIMIT %s"
    )
    cur.execute(sql, (limit,))
    rows = cur.fetchall()
    return [
        {column: safe_json_value(value) for column, value in zip(selected_columns, row)}
        for row in rows
    ]


def discover_relations(cur: Any) -> list[RelationRef]:
    cur.execute(
        """
        SELECT table_schema, table_name, table_type
        FROM information_schema.tables
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name
        """
    )
    relations: list[RelationRef] = []
    for schema, name, kind in cur.fetchall():
        lower = name.lower()
        if name in KNOWN_RELATIONS or any(term in lower for term in RELEVANT_RELATION_HINTS):
            relations.append(RelationRef(schema=schema, name=name, kind=kind))
    return relations


def collect_database_review(database_url: str | None, sample_limit: int) -> dict[str, Any]:
    try:
        conn = connect_db(database_url)
    except Exception as exc:
        return {
            "status": "unavailable",
            "reason": str(exc),
            "read_only_transaction": False,
            "relations": [],
        }

    relations_out: list[dict[str, Any]] = []
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("BEGIN READ ONLY")
                cur.execute("SET LOCAL statement_timeout = '30s'")
                relations = discover_relations(cur)
                for relation in relations:
                    try:
                        columns = fetch_relation_columns(cur, relation)
                        cur.execute(f"SELECT count(*) FROM {relation.qualified_sql}")
                        row_count = cur.fetchone()[0]
                        relations_out.append(
                            {
                                "relation": relation.qualified_name,
                                "kind": relation.kind,
                                "row_count": row_count,
                                "columns": columns,
                                "status_breakdowns": fetch_status_breakdowns(cur, relation, columns),
                                "sample_rows": fetch_sample_rows(cur, relation, columns, sample_limit),
                            }
                        )
                    except Exception as exc:
                        relations_out.append(
                            {
                                "relation": relation.qualified_name,
                                "kind": relation.kind,
                                "status": "inspect_failed",
                                "reason": str(exc),
                            }
                        )
                cur.execute("ROLLBACK")
        return {
            "status": "pass",
            "read_only_transaction": True,
            "relation_count": len(relations_out),
            "relations": relations_out,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "reason": str(exc),
            "read_only_transaction": True,
            "relations": relations_out,
        }
    finally:
        conn.close()


def derive_apply_boundary(report: dict[str, Any]) -> dict[str, Any]:
    db_status = report.get("database", {}).get("status")
    relation_count = report.get("database", {}).get("relation_count", 0) or 0
    return {
        "decision_boundary": "review_only_not_apply",
        "apply_gate_status": "blocked_until_explicit_manual_approval_and_runtime_apply_gate",
        "candidate_creation_allowed_by_this_report": False,
        "minimum_next_runtime_requirements": [
            "dry-run candidate rows are visible in a read-only report",
            "each candidate has source/evidence provenance",
            "duplicate and normalization risk is reviewed",
            "generic proof matrix has no candidate-specific shortcut",
            "apply step remains a separate command with explicit approval",
        ],
        "review_signal_strength": "inspectable" if db_status == "pass" and relation_count else "context_only",
    }


def build_report(root: Path, include_db: bool, database_url: str | None, sample_limit: int) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now_iso(),
        "repo_root": str(root),
        "safety_boundary": SAFETY_BOUNDARY,
        "git": collect_git_context(root),
        "migrations": collect_migration_hints(root),
        "database": {
            "status": "skipped",
            "reason": "Database review skipped. Pass --include-db for read-only DB inspection.",
            "read_only_transaction": False,
            "relations": [],
        },
    }
    if include_db:
        report["database"] = collect_database_review(database_url, sample_limit=sample_limit)
    report["apply_boundary"] = derive_apply_boundary(report)
    report["next_safe_action"] = {
        "action": "review_candidate_creation_evidence_before_apply_gate",
        "requires_user_decision": True,
        "reason": "EXPAND-006 is evidence review only; candidate creation apply remains blocked.",
    }
    return report


def markdown_table(rows: Iterable[Iterable[Any]]) -> str:
    lines = []
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(lines)


def render_markdown(report: dict[str, Any]) -> str:
    database = report.get("database", {})
    apply_boundary = report.get("apply_boundary", {})
    lines = [
        "# EXPAND-006 Candidate Creation Evidence Review",
        "",
        f"Generated: `{report.get('generated_at_utc')}`",
        f"Repo head: `{report.get('git', {}).get('head', '')}`",
        "",
        "## Safety boundary",
        "",
        markdown_table(
            [
                ("Signal", "Value"),
                ("---", "---"),
                *[(key, value) for key, value in report.get("safety_boundary", {}).items()],
            ]
        ),
        "",
        "## Apply boundary",
        "",
        f"- Decision boundary: `{apply_boundary.get('decision_boundary')}`",
        f"- Apply gate status: `{apply_boundary.get('apply_gate_status')}`",
        f"- Candidate creation allowed by this report: `{apply_boundary.get('candidate_creation_allowed_by_this_report')}`",
        f"- Review signal strength: `{apply_boundary.get('review_signal_strength')}`",
        "",
        "## Database review",
        "",
        f"- Status: `{database.get('status')}`",
        f"- Read-only transaction: `{database.get('read_only_transaction')}`",
    ]
    if database.get("reason"):
        lines.append(f"- Reason: {database.get('reason')}")
    lines.append("")

    relations = database.get("relations") or []
    if relations:
        lines.extend(["### Relevant relations", ""])
        lines.append(markdown_table([("Relation", "Rows", "Breakdowns"), ("---", "---:", "---")]))
        # Replace last two rows with table header manually so alignment survives simple renderer.
        lines.pop()
        lines.append("| Relation | Rows | Breakdowns |")
        lines.append("| --- | ---: | --- |")
        for relation in relations[:40]:
            breakdown_cols = ", ".join(
                item.get("column", "") for item in relation.get("status_breakdowns", [])
            )
            lines.append(
                f"| `{relation.get('relation')}` | {relation.get('row_count', 'n/a')} | {breakdown_cols or 'n/a'} |"
            )
        lines.append("")

    migrations = report.get("migrations", {})
    lines.extend(
        [
            "## Migration hints",
            "",
            f"- Status: `{migrations.get('status')}`",
            f"- Relevant migration matches: `{migrations.get('match_count', 0)}`",
            "",
            "## Next safe action",
            "",
            f"`{report.get('next_safe_action', {}).get('action')}`",
            "",
            "This report is intentionally not an apply mechanism. It prepares review evidence only.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: dict[str, Any], export_dir: Path, prefix: str = DEFAULT_EXPORT_PREFIX) -> dict[str, str]:
    export_dir.mkdir(parents=True, exist_ok=True)
    stamp = timestamp_for_filename()
    json_path = export_dir / f"{prefix}_{stamp}.json"
    markdown_path = export_dir / f"{prefix}_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-db", action="store_true", help="Attempt read-only DB inspection.")
    parser.add_argument("--database-url", default=None, help="Optional database URL; defaults to env/libpq.")
    parser.add_argument("--sample-limit", type=int, default=5, help="Maximum sample rows per relation.")
    parser.add_argument("--export-dir", default="exports", help="Directory for JSON/Markdown reports.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = repo_root_from()
    report = build_report(
        root=root,
        include_db=args.include_db,
        database_url=args.database_url,
        sample_limit=max(0, args.sample_limit),
    )
    paths = write_report(report, root / args.export_dir)
    print("# EXPAND-006 Candidate Creation Evidence Review")
    print(f"status={report.get('database', {}).get('status')}")
    print(f"boundary={report.get('apply_boundary', {}).get('decision_boundary')}")
    print(f"json={paths['json']}")
    print(f"markdown={paths['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
