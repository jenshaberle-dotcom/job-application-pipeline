
#!/usr/bin/env python3
"""PROVIDER-001B read-only provider evidence discovery.

The report scans existing repository/DB evidence for provider-backed origin
signals. It never calls external URLs and never writes pipeline state. It is a
review artifact for closing the provider_backed_origin_coverage gap before any
controlled apply gate work.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import quote

SCHEMA_VERSION = "provider001b.provider_evidence_discovery.v1"
DEFAULT_RELATIONS = (
    "employer_origin_source_candidates",
    "candidate_origin_url_persistence_reviews",
    "employer_origin_candidate_gate_reviews",
    "employer_origin_candidate_gate_events",
    "origin_observed_pattern_candidates",
    "origin_observed_patterns",
    "source_targets",
    "raw_jobs",
    "silver_jobs",
    "stop_control_evidence_reviews",
)
TEXT_COLUMN_HINTS = (
    "url",
    "host",
    "domain",
    "source",
    "provider",
    "candidate",
    "company",
    "employer",
    "evidence",
    "reason",
    "job",
    "title",
    "description",
    "status",
)
IDENTITY_COLUMN_CANDIDATES = (
    "candidate_key",
    "company_key",
    "employer_key",
    "company_name",
    "employer_name",
    "organization_name",
    "source_name",
    "name",
)
URL_RE = re.compile(r"https?://[^\s)\]}>\"']+", re.IGNORECASE)
HOST_RE = re.compile(r"(?<![\w.-])([a-z0-9-]+(?:\.[a-z0-9-]+)+)(?![\w.-])", re.IGNORECASE)

PROVIDER_PATTERNS: tuple[dict[str, object], ...] = (
    {"provider": "greenhouse", "family": "ats", "confidence": 0.98, "patterns": (r"greenhouse\.io", r"boards\.greenhouse\.io")},
    {"provider": "personio", "family": "ats", "confidence": 0.98, "patterns": (r"personio\.(?:de|com)", r"jobs\.personio\.")},
    {"provider": "workday", "family": "ats", "confidence": 0.96, "patterns": (r"myworkdayjobs\.com", r"workdayjobs\.com")},
    {"provider": "successfactors", "family": "ats", "confidence": 0.96, "patterns": (r"successfactors\.(?:com|eu)", r"sapsf\.")},
    {"provider": "smartrecruiters", "family": "ats", "confidence": 0.96, "patterns": (r"smartrecruiters\.com",)},
    {"provider": "lever", "family": "ats", "confidence": 0.96, "patterns": (r"lever\.co", r"jobs\.lever\.co")},
    {"provider": "ashby", "family": "ats", "confidence": 0.96, "patterns": (r"ashbyhq\.com", r"jobs\.ashbyhq\.com")},
    {"provider": "recruitee", "family": "ats", "confidence": 0.94, "patterns": (r"recruitee\.com", r"recruitee\.io")},
    {"provider": "workable", "family": "ats", "confidence": 0.94, "patterns": (r"workable\.com", r"apply\.workable\.com")},
    {"provider": "softgarden", "family": "ats", "confidence": 0.94, "patterns": (r"softgarden\.(?:de|io)",)},
    {"provider": "dvinci", "family": "ats", "confidence": 0.94, "patterns": (r"dvinci\.(?:de|com)", r"dvinci-hr\.com")},
    {"provider": "onlyfy", "family": "ats", "confidence": 0.92, "patterns": (r"onlyfy\.io", r"prescreen\.io")},
    {"provider": "join", "family": "ats", "confidence": 0.9, "patterns": (r"join\.com", r"join\.com/companies")},
    {"provider": "talention", "family": "ats", "confidence": 0.9, "patterns": (r"talention\.com",)},
    {"provider": "umantis", "family": "ats", "confidence": 0.9, "patterns": (r"umantis\.com", r"haufe-umantis")},
    {"provider": "icims", "family": "ats", "confidence": 0.9, "patterns": (r"icims\.com", r"careers-.*\.icims\.com")},
    {"provider": "oracle", "family": "ats", "confidence": 0.88, "patterns": (r"oraclecloud\.com", r"fa-ext\.oraclecloud\.com")},
    {"provider": "breezy", "family": "ats", "confidence": 0.88, "patterns": (r"breezy\.hr",)},
    {"provider": "comeet", "family": "ats", "confidence": 0.88, "patterns": (r"comeet\.com",)},
    {"provider": "jobbase", "family": "ats", "confidence": 0.86, "patterns": (r"jobbase\.io",)},
)

@dataclass(frozen=True)
class ProviderSignal:
    provider: str
    family: str
    confidence: float
    matched_pattern: str
    matched_value: str

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "family": self.family,
            "confidence": self.confidence,
            "matched_pattern": self.matched_pattern,
            "matched_value": self.matched_value[:240],
        }


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def safety_boundary() -> dict[str, bool]:
    return {
        "read_only": True,
        "external_requests": False,
        "database_writes": False,
        "pipeline_mutation": False,
        "candidate_or_gate_mutation": False,
        "connector_activation": False,
    }


DB_ENV_NAMES = (
    "JOB_PIPELINE_DATABASE_URL",
    "JOB_PIPELINE_DB_DSN",
    "JOB_PIPELINE_DB_URL",
    "DATABASE_URL",
    "DATABASE_DSN",
    "POSTGRES_DSN",
    "POSTGRES_URL",
    "DB_DSN",
    "DB_URL",
)
ENV_FILE_CANDIDATES = (
    ".env",
    ".env.local",
    "config/.env",
    "docker/.env",
)
COMPOSE_FILE_CANDIDATES = (
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "infra/docker-compose.yml",
    "infra/docker-compose.yaml",
)
ENV_REF_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-(.*?))?\}|\$([A-Za-z_][A-Za-z0-9_]*)")


def clean_env_value(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith("export "):
        cleaned = cleaned[len("export "):].strip()
    if cleaned.startswith("-"):
        cleaned = cleaned[1:].strip()
    if (cleaned.startswith("'") and cleaned.endswith("'")) or (cleaned.startswith('"') and cleaned.endswith('"')):
        cleaned = cleaned[1:-1]
    return cleaned.strip()


def load_env_file_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for relative in ENV_FILE_CANDIDATES:
        path = Path(relative)
        if not path.exists() or not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                continue
            values[key] = clean_env_value(value)
    return values


def expand_env_references(value: str, file_values: Mapping[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(3) or ""
        default = match.group(2)
        return os.environ.get(name) or file_values.get(name) or (default if default is not None else "")

    return ENV_REF_RE.sub(replace, clean_env_value(value)).strip()


def env_value_from_known_names(file_values: Mapping[str, str]) -> str | None:
    for name in DB_ENV_NAMES:
        value = os.environ.get(name) or file_values.get(name)
        if value:
            expanded = expand_env_references(value, file_values)
            if expanded:
                return expanded
    return None


def compose_value(text: str, name: str, file_values: Mapping[str, str]) -> str | None:
    pattern = re.compile(rf"(?:^|[\s\-]){re.escape(name)}\s*(?::|=)\s*([^\n#]+)", re.MULTILINE)
    for match in pattern.finditer(text):
        value = expand_env_references(match.group(1), file_values)
        if value:
            return value
    return None


def compose_port(text: str) -> str:
    for pattern in (r"['\"]?(\d+):5432['\"]?", r"published:\s*['\"]?(\d+)['\"]?"):
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return "5432"


def database_url_from_compose(file_values: Mapping[str, str]) -> str | None:
    for relative in COMPOSE_FILE_CANDIDATES:
        path = Path(relative)
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if "postgres" not in text.lower():
            continue
        user = compose_value(text, "POSTGRES_USER", file_values)
        password = compose_value(text, "POSTGRES_PASSWORD", file_values)
        database = compose_value(text, "POSTGRES_DB", file_values)
        if not (user and password and database):
            continue
        port = compose_port(text)
        return "postgresql://{user}:{password}@localhost:{port}/{database}".format(
            user=quote(user, safe=""),
            password=quote(password, safe=""),
            port=port,
            database=quote(database, safe=""),
        )
    return None


def database_url_from_env() -> str | None:
    """Resolve the local DB DSN without printing secrets.

    Resolution order:
    1. Standard and project-specific environment variables.
    2. The same names from common local env files.
    3. A local Docker Compose Postgres service with explicit POSTGRES_* values.
    """

    file_values = load_env_file_values()
    return env_value_from_known_names(file_values) or database_url_from_compose(file_values)

def extract_urls(text: str) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for match in URL_RE.finditer(text or ""):
        url = match.group(0).rstrip(".,;:")
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def extract_hosts(text: str) -> list[str]:
    seen: set[str] = set()
    hosts: list[str] = []
    for match in HOST_RE.finditer(text or ""):
        host = match.group(1).lower().strip(".")
        if host not in seen:
            seen.add(host)
            hosts.append(host)
    return hosts


def classify_provider_signal(text: str) -> list[ProviderSignal]:
    haystack = (text or "").lower()
    signals: list[ProviderSignal] = []
    seen: set[tuple[str, str]] = set()
    for provider_def in PROVIDER_PATTERNS:
        provider = str(provider_def["provider"])
        family = str(provider_def["family"])
        confidence = float(provider_def["confidence"])
        for pattern in provider_def["patterns"]:  # type: ignore[index]
            regex = re.compile(str(pattern), re.IGNORECASE)
            match = regex.search(haystack)
            if not match:
                continue
            key = (provider, str(pattern))
            if key in seen:
                continue
            seen.add(key)
            start = max(match.start() - 80, 0)
            end = min(match.end() + 120, len(haystack))
            signals.append(
                ProviderSignal(
                    provider=provider,
                    family=family,
                    confidence=confidence,
                    matched_pattern=str(pattern),
                    matched_value=haystack[start:end],
                )
            )
    return sorted(signals, key=lambda signal: (-signal.confidence, signal.provider))


def infer_identity(row: Mapping[str, Any]) -> str:
    for column in IDENTITY_COLUMN_CANDIDATES:
        value = row.get(column)
        if value not in (None, ""):
            return str(value)
    for column, value in row.items():
        lowered = column.lower()
        if any(token in lowered for token in ("candidate", "company", "employer", "source")) and value not in (None, ""):
            return str(value)
    return "unknown_identity"


def select_text_columns(columns: Iterable[str]) -> list[str]:
    selected: list[str] = []
    for column in columns:
        lowered = column.lower()
        if any(hint in lowered for hint in TEXT_COLUMN_HINTS):
            selected.append(column)
    return selected


def row_text(row: Mapping[str, Any], columns: Iterable[str]) -> str:
    parts: list[str] = []
    for column in columns:
        value = row.get(column)
        if value in (None, ""):
            continue
        parts.append(f"{column}={value}")
    return " | ".join(parts)


def evidence_strength(signals: list[ProviderSignal], urls: list[str], hosts: list[str]) -> str:
    if not signals:
        return "none"
    top = max(signal.confidence for signal in signals)
    if top >= 0.95 and urls:
        return "strong_provider_url"
    if top >= 0.9 and (urls or hosts):
        return "medium_provider_host"
    return "weak_provider_text"


def connect_and_collect_records(relations: tuple[str, ...], limit_per_relation: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    dsn = database_url_from_env()
    if not dsn:
        return (
            {
                "status": "skipped",
                "reason": "No DB DSN found via env aliases, local env files, or Docker Compose Postgres configuration.",
                "read_only_transaction": False,
            },
            [],
        )
    try:
        import psycopg
        from psycopg import sql
    except ImportError as exc:
        return (
            {
                "status": "unavailable",
                "reason": f"psycopg import failed: {exc}",
                "read_only_transaction": False,
            },
            [],
        )

    records: list[dict[str, Any]] = []
    relation_summaries: dict[str, Any] = {}
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
                available_relations = {row[0] for row in cursor.fetchall()}
                for relation in relations:
                    if relation not in available_relations:
                        relation_summaries[relation] = {"status": "missing"}
                        continue
                    cursor.execute(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = %s
                        ORDER BY ordinal_position
                        """,
                        (relation,),
                    )
                    columns = [row[0] for row in cursor.fetchall()]
                    selected_columns = select_text_columns(columns)
                    if not selected_columns:
                        relation_summaries[relation] = {
                            "status": "skipped",
                            "reason": "No text/url/source/evidence columns selected by conservative hints.",
                            "column_count": len(columns),
                        }
                        continue
                    query = sql.SQL("SELECT {fields} FROM {relation} LIMIT %s").format(
                        fields=sql.SQL(", ").join(sql.Identifier(column) for column in selected_columns),
                        relation=sql.Identifier(relation),
                    )
                    cursor.execute(query, (limit_per_relation,))
                    rows = cursor.fetchall()
                    relation_summaries[relation] = {
                        "status": "scanned",
                        "selected_columns": selected_columns,
                        "rows_scanned": len(rows),
                    }
                    for index, values in enumerate(rows, start=1):
                        row = dict(zip(selected_columns, values))
                        text = row_text(row, selected_columns)
                        records.append(
                            {
                                "relation": relation,
                                "row_index": index,
                                "identity": infer_identity(row),
                                "text": text,
                                "columns": selected_columns,
                            }
                        )
                connection.rollback()
        return (
            {
                "status": "pass",
                "reason": "DB evidence scan completed in a read-only transaction.",
                "read_only_transaction": True,
                "relations_requested": list(relations),
                "relation_summaries": relation_summaries,
            },
            records,
        )
    except Exception as exc:  # pragma: no cover - defensive local environment reporting
        return (
            {
                "status": "unavailable",
                "reason": f"DB evidence scan failed: {exc}",
                "read_only_transaction": False,
            },
            [],
        )


def build_evidence_hits(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for record in records:
        text = str(record.get("text") or "")
        signals = classify_provider_signal(text)
        urls = extract_urls(text)
        hosts = extract_hosts(text)
        if not signals:
            continue
        hits.append(
            {
                "relation": record.get("relation"),
                "row_index": record.get("row_index"),
                "identity": record.get("identity"),
                "evidence_strength": evidence_strength(signals, urls, hosts),
                "providers": [signal.to_dict() for signal in signals],
                "urls": urls[:10],
                "hosts": hosts[:10],
                "text_preview": text[:500],
            }
        )
    return hits


def summarize_hits(records: list[dict[str, Any]], hits: list[dict[str, Any]]) -> dict[str, Any]:
    provider_counter: Counter[str] = Counter()
    relation_counter: Counter[str] = Counter()
    strength_counter: Counter[str] = Counter()
    identities: defaultdict[str, set[str]] = defaultdict(set)
    for hit in hits:
        relation_counter[str(hit.get("relation"))] += 1
        strength_counter[str(hit.get("evidence_strength"))] += 1
        identity = str(hit.get("identity") or "unknown_identity")
        hit_provider_names: set[str] = set()
        for provider in hit.get("providers") or []:
            provider_name = str(provider.get("provider") or "").strip()
            if not provider_name:
                continue
            hit_provider_names.add(provider_name)
            identities[identity].add(provider_name)
        for provider_name in sorted(hit_provider_names):
            provider_counter[provider_name] += 1
    return {
        "records_scanned": len(records),
        "provider_hit_count": len(hits),
        "provider_hit_rate": round(len(hits) / len(records), 4) if records else 0.0,
        "providers": dict(provider_counter.most_common()),
        "relations_with_hits": dict(relation_counter.most_common()),
        "evidence_strengths": dict(strength_counter.most_common()),
        "distinct_identities_with_provider_signal": len(identities),
        "top_identities": [
            {"identity": identity, "providers": sorted(providers)}
            for identity, providers in sorted(identities.items(), key=lambda item: (-len(item[1]), item[0]))[:25]
        ],
    }


def build_report(records: list[dict[str, Any]], database_status: dict[str, Any]) -> dict[str, Any]:
    hits = build_evidence_hits(records)
    summary = summarize_hits(records, hits)
    status = "pass" if database_status.get("status") in {"pass", "skipped", "unavailable"} else "warn"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": iso_now(),
        "status": status,
        "boundary": "review_output_only_not_pipeline_input",
        "safety_boundary": safety_boundary(),
        "gap_under_review": "provider_backed_origin_coverage",
        "database": database_status,
        "provider_catalog": [
            {
                "provider": item["provider"],
                "family": item["family"],
                "confidence": item["confidence"],
                "patterns": item["patterns"],
            }
            for item in PROVIDER_PATTERNS
        ],
        "summary": summary,
        "provider_hits": hits[:250],
        "truncation": {
            "provider_hits_returned": min(len(hits), 250),
            "provider_hits_total": len(hits),
        },
        "next_recommended_work": {
            "work_item": "PROVIDER-001C Provider Coverage Decision Bundle",
            "reason": "Use the read-only provider evidence report to decide whether the provider-backed origin coverage gap is closed, needs a bounded external probe boundary, or should remain explicitly open before APPLY-001.",
            "requires_user_decision": True,
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary") or {}
    database = report.get("database") or {}
    providers = summary.get("providers") or {}
    relations = summary.get("relations_with_hits") or {}
    strengths = summary.get("evidence_strengths") or {}
    top_identities = summary.get("top_identities") or []
    lines = [
        "# PROVIDER-001B Provider Evidence Discovery",
        "",
        f"Generated: `{report.get('generated_at_utc')}`",
        f"Schema: `{report.get('schema_version')}`",
        f"Status: `{report.get('status')}`",
        f"Boundary: `{report.get('boundary')}`",
        f"Gap under review: `{report.get('gap_under_review')}`",
        "",
        "## Safety boundary",
        "",
    ]
    for key, value in (report.get("safety_boundary") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Database scan",
            "",
            f"- Status: `{database.get('status')}`",
            f"- Reason: {database.get('reason')}",
            f"- Read-only transaction: `{database.get('read_only_transaction')}`",
            "",
            "## Coverage summary",
            "",
            f"- Records scanned: `{summary.get('records_scanned')}`",
            f"- Provider hits: `{summary.get('provider_hit_count')}`",
            f"- Provider hit rate: `{summary.get('provider_hit_rate')}`",
            f"- Distinct identities with provider signal: `{summary.get('distinct_identities_with_provider_signal')}`",
            "",
            "### Providers",
            "",
        ]
    )
    lines.extend([f"- `{provider}`: `{count}`" for provider, count in providers.items()] or ["- none"])
    lines.extend(["", "### Relations with hits", ""])
    lines.extend([f"- `{relation}`: `{count}`" for relation, count in relations.items()] or ["- none"])
    lines.extend(["", "### Evidence strengths", ""])
    lines.extend([f"- `{strength}`: `{count}`" for strength, count in strengths.items()] or ["- none"])
    lines.extend(["", "### Top identities", ""])
    for item in top_identities[:15]:
        lines.append(f"- `{item.get('identity')}` -> `{', '.join(item.get('providers') or [])}`")
    if not top_identities:
        lines.append("- none")
    next_work = report.get("next_recommended_work") or {}
    lines.extend(
        [
            "",
            "## Next recommended work",
            "",
            f"- Work item: `{next_work.get('work_item')}`",
            f"- Requires user decision: `{next_work.get('requires_user_decision')}`",
            f"- Reason: {next_work.get('reason')}",
            "",
            "## Interpretation boundary",
            "",
            "This report is evidence discovery only. It does not approve candidates, activate connectors, mutate gates, or prove that external provider pages are currently reachable. If current reachability is needed, promote a separate bounded probe under COMPLIANCE-001A first.",
            "",
        ]
    )
    return "\n".join(lines)


def write_reports(report: Mapping[str, Any], output_dir: Path, stamp: str) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"provider001b_provider_evidence_discovery_{stamp}.json"
    markdown_path = output_dir / f"provider001b_provider_evidence_discovery_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PROVIDER-001B read-only provider evidence discovery.")
    parser.add_argument("--output-dir", default=None, help="Output directory. Defaults to a run-scoped folder under exports/.")
    parser.add_argument("--include-db", action="store_true", help="Read existing DB evidence in a read-only transaction when a DSN is available.")
    parser.add_argument("--require-db", action="store_true", help="Fail the report when --include-db cannot complete a read-only DB scan.")
    parser.add_argument("--limit-per-relation", type=int, default=2000, help="Maximum rows to scan per selected relation.")
    parser.add_argument("--json", action="store_true", help="Print full JSON report to stdout.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stamp = utc_timestamp()
    output_dir = Path(args.output_dir or Path("exports") / f"provider001b_provider_evidence_discovery_{stamp}")
    if args.include_db:
        database_status, records = connect_and_collect_records(DEFAULT_RELATIONS, args.limit_per_relation)
    else:
        database_status = {
            "status": "skipped",
            "reason": "DB scan disabled. Pass --include-db to scan existing evidence in a read-only transaction.",
            "read_only_transaction": False,
        }
        records = []
    report = build_report(records, database_status)
    if args.require_db and database_status.get("status") != "pass":
        report["status"] = "fail"
        report["next_recommended_work"] = {
            "work_item": "PROVIDER-001B DB Configuration Repair",
            "reason": "A DB-backed evidence run was required but the read-only DB scan did not complete. Repair local DSN discovery or provide a supported DB env var before using PROVIDER-001B as evidence.",
            "requires_user_decision": False,
        }
    written = write_reports(report, output_dir, stamp)
    print("# PROVIDER-001B Provider Evidence Discovery")
    print(f"status={report['status']}")
    print(f"db_status={database_status.get('status')}")
    print(f"records_scanned={report['summary']['records_scanned']}")
    print(f"provider_hits={report['summary']['provider_hit_count']}")
    print(f"json={written['json']}")
    print(f"markdown={written['markdown']}")
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] in {"pass", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
