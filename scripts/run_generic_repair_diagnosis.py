from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
except ModuleNotFoundError:  # pragma: no cover - exercised only in minimal tool sandboxes
    psycopg = None  # type: ignore[assignment]
    sql = None  # type: ignore[assignment]
    dict_row = None  # type: ignore[assignment]

from src.config import get_database_config

DEFAULT_OUTPUT_DIR = Path("exports/generic_repair_diagnosis")
RELEVANT_TABLE_PATTERNS = (
    "candidate",
    "gate",
    "evidence",
    "repair",
    "observation",
    "connector",
    "source",
)
SEARCHABLE_COLUMN_NAMES = {
    "company_key",
    "company_name",
    "candidate_url",
    "source_url",
    "url",
    "host",
    "title",
    "description",
    "notes",
    "payload",
    "evidence",
    "result_payload",
    "raw_payload",
    "decision",
    "stop_reason",
    "gate_name",
}
CANDIDATE_LINK_COLUMN_PRIORITY = (
    "candidate_id",
    "employer_origin_source_candidate_id",
    "source_candidate_id",
    "employer_origin_candidate_id",
)
READ_ONLY_BOUNDARY: dict[str, bool] = {
    "read_only_schema_and_failure_pattern_diagnosis": True,
    "no_candidate_status_write": True,
    "no_candidate_url_write": True,
    "no_gate_review_write": True,
    "no_evidence_write": True,
    "no_connector_artifact_write": True,
    "no_external_requests": True,
}


@dataclass(frozen=True)
class TableColumn:
    name: str
    data_type: str


@dataclass(frozen=True)
class RelevantTable:
    name: str
    columns: tuple[TableColumn, ...]

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(column.name for column in self.columns)


def normalized_connect_kwargs(config: Any) -> dict[str, Any]:
    if isinstance(config, str):
        return {"conninfo": config}
    if hasattr(config, "dsn"):
        return {"conninfo": str(config.dsn)}
    if not isinstance(config, Mapping):
        raise TypeError(f"Unsupported database config type: {type(config)!r}")

    kwargs = dict(config)
    if "database" in kwargs and "dbname" not in kwargs:
        kwargs["dbname"] = kwargs.pop("database")

    allowed = {
        "dbname",
        "user",
        "password",
        "host",
        "port",
        "connect_timeout",
        "sslmode",
        "target_session_attrs",
        "application_name",
    }
    return {key: value for key, value in kwargs.items() if key in allowed and value is not None}


def require_psycopg() -> None:
    if psycopg is None or sql is None or dict_row is None:
        raise RuntimeError(
            "psycopg is required for live DIAG-001 database diagnosis; run inside the project virtual environment."
        )


def connect_database() -> psycopg.Connection[Any]:
    require_psycopg()
    kwargs = normalized_connect_kwargs(get_database_config())
    conninfo = kwargs.pop("conninfo", None)
    if conninfo is not None:
        return psycopg.connect(conninfo, **kwargs)
    return psycopg.connect(**kwargs)


def relevant_table_params(patterns: Sequence[str] = RELEVANT_TABLE_PATTERNS) -> tuple[str, ...]:
    return tuple(f"%{pattern}%" for pattern in patterns)


def relevant_tables_where_clause(patterns: Sequence[str] = RELEVANT_TABLE_PATTERNS) -> str:
    if not patterns:
        return "false"
    return " or ".join("table_name ilike %s" for _ in patterns)


def choose_candidate_identity_column(column_names: Sequence[str]) -> str:
    if "id" in column_names:
        return "id"
    if "candidate_id" in column_names:
        return "candidate_id"
    raise ValueError("No stable candidate identity column found; expected `id` or `candidate_id`.")


def choose_candidate_link_column(column_names: Sequence[str]) -> str | None:
    for candidate in CANDIDATE_LINK_COLUMN_PRIORITY:
        if candidate in column_names:
            return candidate
    return None


def searchable_columns(column_names: Sequence[str]) -> tuple[str, ...]:
    return tuple(column for column in column_names if column in SEARCHABLE_COLUMN_NAMES)


def json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [json_safe(item) for item in value]
    return str(value)


def rows_to_json_safe(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [{str(key): json_safe(value) for key, value in row.items()} for row in rows]


def fetch_relevant_table_names(conn: psycopg.Connection[Any]) -> list[str]:
    query = f"""
        select table_name
        from information_schema.tables
        where table_schema = 'public'
          and ({relevant_tables_where_clause()})
        order by table_name
    """
    with conn.cursor() as cur:
        cur.execute(query, relevant_table_params())
        return [str(row[0]) for row in cur.fetchall()]


def fetch_table_columns(conn: psycopg.Connection[Any], table_name: str) -> tuple[TableColumn, ...]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select column_name, data_type
            from information_schema.columns
            where table_schema = 'public'
              and table_name = %s
            order by ordinal_position
            """,
            (table_name,),
        )
        return tuple(TableColumn(str(row["column_name"]), str(row["data_type"])) for row in cur.fetchall())


def fetch_relevant_tables(conn: psycopg.Connection[Any]) -> list[RelevantTable]:
    return [RelevantTable(name, fetch_table_columns(conn, name)) for name in fetch_relevant_table_names(conn)]


def fetch_company_candidate_rows(conn: psycopg.Connection[Any], *, company_key: str) -> tuple[list[dict[str, Any]], str]:
    columns = fetch_table_columns(conn, "employer_origin_source_candidates")
    column_names = tuple(column.name for column in columns)
    identity_column = choose_candidate_identity_column(column_names)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            sql.SQL("""
                select *
                from {table}
                where company_key = %s
                order by {identity}
            """).format(
                table=sql.Identifier("employer_origin_source_candidates"),
                identity=sql.Identifier(identity_column),
            ),
            (company_key,),
        )
        return rows_to_json_safe(cur.fetchall()), identity_column


def fetch_rows_mentioning_company(
    conn: psycopg.Connection[Any],
    *,
    table: RelevantTable,
    company_key: str,
    limit: int,
) -> list[dict[str, Any]]:
    selected_columns = searchable_columns(table.column_names)
    if not selected_columns:
        return []

    where = sql.SQL(" or ").join(
        sql.SQL("cast({column} as text) ilike %s").format(column=sql.Identifier(column))
        for column in selected_columns
    )
    params = tuple(f"%{company_key}%" for _ in selected_columns)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            sql.SQL("select * from {table} where {where} limit %s").format(
                table=sql.Identifier(table.name),
                where=where,
            ),
            (*params, limit),
        )
        return rows_to_json_safe(cur.fetchall())


def fetch_rows_linked_by_candidate_id(
    conn: psycopg.Connection[Any],
    *,
    table: RelevantTable,
    candidate_ids: Sequence[int],
    limit: int,
) -> tuple[str | None, list[dict[str, Any]]]:
    link_column = choose_candidate_link_column(table.column_names)
    if link_column is None or not candidate_ids:
        return link_column, []

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            sql.SQL("select * from {table} where {link_column} = any(%s) limit %s").format(
                table=sql.Identifier(table.name),
                link_column=sql.Identifier(link_column),
            ),
            (list(candidate_ids), limit),
        )
        return link_column, rows_to_json_safe(cur.fetchall())


def build_diagnosis_payload(
    conn: psycopg.Connection[Any],
    *,
    company_key: str,
    row_limit: int,
) -> dict[str, Any]:
    relevant_tables = fetch_relevant_tables(conn)
    candidate_rows, identity_column = fetch_company_candidate_rows(conn, company_key=company_key)
    candidate_ids = [int(row[identity_column]) for row in candidate_rows if row.get(identity_column) is not None]

    mentioned_rows: dict[str, list[dict[str, Any]]] = {}
    linked_rows: dict[str, dict[str, Any]] = {}

    for table in relevant_tables:
        mentioned = fetch_rows_mentioning_company(conn, table=table, company_key=company_key, limit=row_limit)
        if mentioned:
            mentioned_rows[table.name] = mentioned

        link_column, linked = fetch_rows_linked_by_candidate_id(
            conn,
            table=table,
            candidate_ids=candidate_ids,
            limit=row_limit,
        )
        if linked:
            linked_rows[table.name] = {
                "link_column": link_column,
                "rows": linked,
            }

    return {
        "campaign": "DIAG-001 Generic Repair Diagnosis",
        "generated_at": datetime.now(UTC).isoformat(),
        "company_key": company_key,
        "boundary": READ_ONLY_BOUNDARY,
        "schema_contract": {
            "candidate_identity_column": identity_column,
            "candidate_identity_values": candidate_ids,
            "relevant_table_patterns": list(RELEVANT_TABLE_PATTERNS),
            "candidate_link_column_priority": list(CANDIDATE_LINK_COLUMN_PRIORITY),
        },
        "relevant_tables": [
            {
                "table_name": table.name,
                "columns": [{"name": column.name, "data_type": column.data_type} for column in table.columns],
                "searchable_columns": list(searchable_columns(table.column_names)),
                "candidate_link_column": choose_candidate_link_column(table.column_names),
            }
            for table in relevant_tables
        ],
        "representative_candidate_rows": candidate_rows,
        "rows_mentioning_company": mentioned_rows,
        "rows_linked_by_candidate_id": linked_rows,
        "generic_diagnosis_questions": [
            "Do we have a stable generic candidate identity adapter from physical table identity to domain candidate identity?",
            "Where are gate decisions persisted for this candidate, and are they discoverable without employer-specific assumptions?",
            "Does detail repair preserve rejected detail URL candidates and rejection reasons?",
            "Can detail discovery distinguish no jobs, no parseable detail URLs, no profile match, and no location/remote signal?",
            "Would the observed failure pattern explain peer candidates with detail_discovery_gap or weak_relevance_evidence?",
        ],
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    schema = payload["schema_contract"]
    relevant_tables = payload["relevant_tables"]
    mentioned = payload["rows_mentioning_company"]
    linked = payload["rows_linked_by_candidate_id"]

    lines = [
        "# DIAG-001 Generic Repair Diagnosis",
        "",
        f"Generated at: `{payload['generated_at']}`",
        f"Representative company key: `{payload['company_key']}`",
        "",
        "## Boundary",
        "",
        "This report is read-only. It does not perform external requests and does not write candidate, gate, evidence, connector, source, Bronze or Silver state.",
        "",
        "## Schema contract",
        "",
        f"- Candidate identity column: `{schema['candidate_identity_column']}`",
        f"- Candidate identity values: `{schema['candidate_identity_values']}`",
        f"- Relevant tables discovered: `{len(relevant_tables)}`",
        "",
        "## Relevant tables",
        "",
        "| Table | Searchable columns | Candidate link column |",
        "| --- | --- | --- |",
    ]

    for table in relevant_tables:
        lines.append(
            f"| `{table['table_name']}` | `{', '.join(table['searchable_columns']) or '-'}` | `{table['candidate_link_column'] or '-'}` |"
        )

    lines.extend([
        "",
        "## Representative candidate rows",
        "",
        f"Rows: `{len(payload['representative_candidate_rows'])}`",
        "",
        "## Data surfaces found",
        "",
        f"- Tables mentioning company key/text: `{len(mentioned)}`",
        f"- Tables linked by candidate identity: `{len(linked)}`",
        "",
        "## Generic diagnosis questions",
        "",
    ])
    for question in payload["generic_diagnosis_questions"]:
        lines.append(f"- {question}")

    lines.extend([
        "",
        "## Tables mentioning company",
        "",
    ])
    if not mentioned:
        lines.append("No rows found by company-text search.")
    else:
        for table_name, rows in mentioned.items():
            lines.append(f"- `{table_name}`: `{len(rows)}` row(s)")

    lines.extend([
        "",
        "## Tables linked by candidate identity",
        "",
    ])
    if not linked:
        lines.append("No rows found by candidate identity links.")
    else:
        for table_name, info in linked.items():
            lines.append(f"- `{table_name}` via `{info['link_column']}`: `{len(info['rows'])}` row(s)")

    return "\n".join(lines).rstrip() + "\n"


def safe_report_stem(label: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in label.strip())
    return "_".join(part for part in cleaned.split("_") if part) or "generic_repair_diagnosis"


def write_reports(payload: Mapping[str, Any], output_dir: Path, label: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = safe_report_stem(label)
    json_path = output_dir / f"{stem}_generic_repair_diagnosis.json"
    md_path = output_dir / f"{stem}_generic_repair_diagnosis.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "DIAG-001 read-only generic repair diagnosis. It introspects schema, "
            "candidate identity and evidence/gate surfaces for a representative company "
            "without applying employer-specific repair logic."
        )
    )
    parser.add_argument("--company-key", required=True)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--benchmark-label", default="generic_repair_diagnosis")
    parser.add_argument("--row-limit", type=int, default=30)
    parser.add_argument("--write-report", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    with connect_database() as conn:
        payload = build_diagnosis_payload(conn, company_key=args.company_key, row_limit=args.row_limit)

    print(
        "summary: "
        + json.dumps(
            {
                "company_key": payload["company_key"],
                "candidate_identity_column": payload["schema_contract"]["candidate_identity_column"],
                "candidate_identity_values": payload["schema_contract"]["candidate_identity_values"],
                "relevant_table_count": len(payload["relevant_tables"]),
                "tables_mentioning_company_count": len(payload["rows_mentioning_company"]),
                "tables_linked_by_candidate_id_count": len(payload["rows_linked_by_candidate_id"]),
            },
            sort_keys=True,
        )
    )

    if args.write_report:
        json_path, md_path = write_reports(payload, Path(args.output_dir), args.benchmark_label)
        print(f"json_report_written: {json_path}")
        print(f"markdown_report_written: {md_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
