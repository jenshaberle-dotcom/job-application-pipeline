from __future__ import annotations

import argparse
import json
import os
import re
from urllib.parse import urlparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from scripts.run_employer_origin_gate_agent import GateOutcome


REQUIRED_PRECONDITION_GATES = (
    "company_candidate",
    "source_discovery",
    "risk_gate",
    "technical_reachability_gate",
    "scope_gate",
    "defensive_preview_gate",
    "relevance_gate",
    "detail_evidence_gate",
    "incremental_uniqueness_gate",
)

CONNECTOR_CANDIDATE_GATE = "connector_candidate_gate"
DEFAULT_OUTPUT_DIR = Path("exports/s2u_employer_origin_connector_candidate_agent")


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: str
    dbname: str
    user: str
    password: str

    @classmethod
    def from_environment(cls) -> "DatabaseConfig":
        return cls(
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=os.environ.get("POSTGRES_PORT", "5432"),
            dbname=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
        )

    def dsn(self) -> str:
        return (
            f"host={self.host} "
            f"port={self.port} "
            f"dbname={self.dbname} "
            f"user={self.user} "
            f"password={self.password}"
        )


@dataclass(frozen=True)
class SourceCandidate:
    id: int
    company_key: str
    company_name: str
    candidate_url: str
    source_name_candidate: str
    source_family_candidate: str
    source_target_candidate: str | None
    source_type_candidate: str
    status: str
    risk_level: str


def snake_case(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return re.sub(r"_+", "_", normalized).strip("_")


def pascal_case(value: str) -> str:
    parts = [part for part in snake_case(value).split("_") if part]
    return "".join(part.capitalize() for part in parts)


def summarize_gate_state(gates: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        name: {
            "gate_status": gate.get("gate_status"),
            "decision": gate.get("decision"),
            "stop_reason": gate.get("stop_reason"),
        }
        for name, gate in sorted(gates.items(), key=lambda item: item[1].get("gate_order") or 999)
    }


def missing_or_unpassed_preconditions(gates: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []

    for gate_name in REQUIRED_PRECONDITION_GATES:
        gate = gates.get(gate_name)
        if gate is None:
            missing.append(
                {
                    "gate_name": gate_name,
                    "problem": "missing_gate",
                    "gate_status": None,
                    "decision": None,
                }
            )
            continue

        if gate.get("gate_status") != "passed":
            missing.append(
                {
                    "gate_name": gate_name,
                    "problem": "gate_not_passed",
                    "gate_status": gate.get("gate_status"),
                    "decision": gate.get("decision"),
                    "stop_reason": gate.get("stop_reason"),
                }
            )

    return missing


NON_JOB_DETAIL_URL_FRAGMENTS = (
    "/privacy",
    "/datenschutz",
    "/impressum",
    "/imprint",
    "/cookie",
    "/kontakt",
    "/contact",
    "/faq",
    "/your_career_opportunities",
)

GENERIC_DETAIL_LAST_SEGMENTS = (
    "career",
    "careers",
    "karriere",
    "job",
    "jobs",
    "job_board",
    "stellen",
    "stellenangebote",
    "offene-stellen",
    "stellen-finden",
)

JOB_DETAIL_PATH_MARKERS = (
    "/jobs/",
    "/job/",
    "/stellenangebote/",
    "/offene-stellen/",
    "/stellen-finden/",
    "/karriere/offene-stellen/",
    "/karriere/jobs/",
)


def concrete_job_detail_url(url: str) -> bool:
    """Return True only for concrete job-detail URLs, not career roots or legal pages."""
    if not url.startswith(("http://", "https://")):
        return False

    parsed = urlparse(url)
    path = re.sub(r"/+", "/", parsed.path.casefold()).rstrip("/")
    if not path:
        return False

    if any(fragment in path for fragment in NON_JOB_DETAIL_URL_FRAGMENTS):
        return False

    last_segment = path.rsplit("/", 1)[-1]
    if last_segment in GENERIC_DETAIL_LAST_SEGMENTS:
        return False

    if not any(marker in f"{path}/" for marker in JOB_DETAIL_PATH_MARKERS):
        return False

    if len(last_segment) < 6:
        return False

    return "-" in last_segment or "_" in last_segment or any(ch.isdigit() for ch in last_segment)

def raw_detail_urls_from_gate_evidence(gates: dict[str, dict[str, Any]]) -> list[str]:
    detail_gate = gates.get("detail_evidence_gate") or {}
    evidence = detail_gate.get("evidence") or {}
    details = evidence.get("details") or []

    urls: list[str] = []
    seen: set[str] = set()

    for detail in details:
        if not isinstance(detail, dict):
            continue
        url = str(detail.get("url") or "")
        if not url.startswith(("http://", "https://")):
            continue
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)

    return urls


def detail_urls_from_gate_evidence(gates: dict[str, dict[str, Any]]) -> list[str]:
    return [url for url in raw_detail_urls_from_gate_evidence(gates) if concrete_job_detail_url(url)]


def rejected_detail_urls_from_gate_evidence(gates: dict[str, dict[str, Any]]) -> list[str]:
    return [url for url in raw_detail_urls_from_gate_evidence(gates) if not concrete_job_detail_url(url)]


def uniqueness_summary_from_gate_evidence(gates: dict[str, dict[str, Any]]) -> dict[str, Any]:
    gate = gates.get("incremental_uniqueness_gate") or {}
    evidence = gate.get("evidence") or {}
    return {
        "detail_candidates_considered": evidence.get("detail_candidates_considered"),
        "existing_evidence_rows_considered": evidence.get("existing_evidence_rows_considered"),
        "uniqueness_counts": evidence.get("uniqueness_counts") or {},
        "results": evidence.get("results") or [],
    }


def build_connector_candidate_spec(
    candidate: SourceCandidate,
    gates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    module_name = snake_case(candidate.source_family_candidate)
    class_name = f"{pascal_case(candidate.source_family_candidate)}Connector"
    detail_urls = detail_urls_from_gate_evidence(gates)
    uniqueness_summary = uniqueness_summary_from_gate_evidence(gates)

    return {
        "candidate": {
            "candidate_id": candidate.id,
            "company_key": candidate.company_key,
            "company_name": candidate.company_name,
            "candidate_url": candidate.candidate_url,
            "source_name_candidate": candidate.source_name_candidate,
            "source_family_candidate": candidate.source_family_candidate,
            "source_target_candidate": candidate.source_target_candidate,
            "source_type_candidate": candidate.source_type_candidate,
            "risk_level": candidate.risk_level,
        },
        "recommended_connector": {
            "module_path": f"src/connectors/{module_name}.py",
            "test_path": f"tests/test_{module_name}_connector.py",
            "class_name": class_name,
            "source_name": candidate.source_name_candidate,
            "source_family": candidate.source_family_candidate,
            "source_target": candidate.source_target_candidate,
            "source_type": candidate.source_type_candidate,
        },
        "bounded_implementation_contract": {
            "network_scope": "single employer-origin career listing plus bounded same-domain detail pages",
            "max_listing_pages": 1,
            "max_detail_pages_from_gate_evidence": len(detail_urls),
            "browser_automation_allowed": False,
            "raw_html_persistence_allowed": False,
            "bronze_persistence_approved_by_this_gate": False,
            "recurring_ingestion_approved_by_this_gate": False,
            "generated_exports_are_process_inputs": False,
        },
        "required_raw_job_evidence_fields": [
            "source_name",
            "external_job_id",
            "title",
            "company_name",
            "location",
            "detail_url",
            "source_type",
            "source_family",
            "source_target",
            "matched_terms",
        ],
        "detail_evidence": {
            "detail_urls": detail_urls,
        },
        "incremental_uniqueness": uniqueness_summary,
        "stop_conditions_for_implementation": [
            "authentication, captcha or bot-defense challenge required",
            "source requires broad crawling or unbounded pagination",
            "detail pages cannot provide stable title/company/location/detail_url evidence",
            "local relevance filtering cannot preserve matched term evidence",
            "source semantics cannot be represented as employer_origin_career_site or employer_origin_ats_backed_career_site",
            "connector would need CSV/Excel/generated export artifacts as inputs",
        ],
        "minimum_tests_for_connector_pr": [
            "parses representative listing/detail evidence",
            "produces stable external_job_id values without using generated exports",
            "preserves matched_terms and source metadata in raw_data",
            "uses source_type employer_origin_career_site or employer_origin_ats_backed_career_site",
            "keeps request scope bounded and defensive",
            "does not activate recurring ingestion without a separate controlled activation gate",
        ],
    }


def connector_candidate_outcome(
    candidate: SourceCandidate,
    gates: dict[str, dict[str, Any]],
) -> GateOutcome:
    missing = missing_or_unpassed_preconditions(gates)

    if missing:
        return GateOutcome(
            gate_name=CONNECTOR_CANDIDATE_GATE,
            gate_status="manual_review_required",
            decision="manual_review_required",
            stop_reason="precondition gates are not all passed",
            evidence={
                "missing_or_unpassed_preconditions": missing,
                "gate_state_summary": summarize_gate_state(gates),
            },
        )

    if not candidate.source_type_candidate.startswith("employer_origin_"):
        return GateOutcome(
            gate_name=CONNECTOR_CANDIDATE_GATE,
            gate_status="failed",
            decision="abort_documented",
            stop_reason="candidate source type is not an employer-origin source type",
            evidence={
                "source_type_candidate": candidate.source_type_candidate,
                "gate_state_summary": summarize_gate_state(gates),
            },
        )


    valid_detail_urls = detail_urls_from_gate_evidence(gates)
    rejected_detail_urls = rejected_detail_urls_from_gate_evidence(gates)
    if not valid_detail_urls:
        return GateOutcome(
            gate_name=CONNECTOR_CANDIDATE_GATE,
            gate_status="manual_review_required",
            decision="manual_review_required",
            stop_reason="detail evidence does not contain concrete job-detail URLs",
            evidence={
                "raw_detail_urls": raw_detail_urls_from_gate_evidence(gates),
                "rejected_detail_urls": rejected_detail_urls,
                "gate_state_summary": summarize_gate_state(gates),
            },
        )

    spec = build_connector_candidate_spec(candidate, gates)

    return GateOutcome(
        gate_name=CONNECTOR_CANDIDATE_GATE,
        gate_status="passed",
        decision="passed",
        stop_reason=None,
        evidence={
            "connector_candidate_spec": spec,
            "gate_state_summary": summarize_gate_state(gates),
        },
    )


class GateStateRepository:
    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self.conn = conn

    def load_candidate(self, *, candidate_id: int | None, company_key: str | None) -> SourceCandidate:
        if candidate_id is None and not company_key:
            raise ValueError("Either candidate_id or company_key is required.")

        with self.conn.cursor(row_factory=dict_row) as cur:
            if candidate_id is not None:
                cur.execute(
                    """
                    select *
                    from employer_origin_source_candidates
                    where id = %s
                    """,
                    (candidate_id,),
                )
            else:
                cur.execute(
                    """
                    select *
                    from employer_origin_source_candidates
                    where company_key = %s
                    order by id desc
                    limit 1
                    """,
                    (company_key,),
                )
            row = cur.fetchone()

        if row is None:
            raise ValueError("No employer-origin source candidate found.")

        return SourceCandidate(
            id=int(row["id"]),
            company_key=str(row["company_key"]),
            company_name=str(row["company_name"]),
            candidate_url=str(row["candidate_url"]),
            source_name_candidate=str(row["source_name_candidate"]),
            source_family_candidate=str(row["source_family_candidate"]),
            source_target_candidate=row.get("source_target_candidate"),
            source_type_candidate=str(row["source_type_candidate"]),
            status=str(row["status"]),
            risk_level=str(row["risk_level"]),
        )

    def load_gate_reviews(self, candidate_id: int) -> dict[str, dict[str, Any]]:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select
                    id,
                    gate_name,
                    gate_order,
                    is_hard_gate,
                    gate_status,
                    decision,
                    stop_reason,
                    evidence
                from employer_origin_candidate_gate_reviews
                where candidate_id = %s
                order by gate_order
                """,
                (candidate_id,),
            )
            rows = cur.fetchall()

        return {str(row["gate_name"]): dict(row) for row in rows}

    def record_gate(self, candidate_id: int, outcome: GateOutcome, reviewed_by: str) -> None:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select id, gate_status, decision, stop_reason, evidence
                from employer_origin_candidate_gate_reviews
                where candidate_id = %s
                  and gate_name = %s
                """,
                (candidate_id, outcome.gate_name),
            )
            previous = cur.fetchone()
            if previous is None:
                raise ValueError(f"Missing gate {outcome.gate_name} for candidate_id={candidate_id}")

            previous_state = dict(previous)

            cur.execute(
                """
                update employer_origin_candidate_gate_reviews
                set
                    gate_status = %s,
                    decision = %s,
                    stop_reason = %s,
                    evidence = %s::jsonb,
                    reviewed_at = now(),
                    reviewed_by = %s,
                    updated_at = now()
                where candidate_id = %s
                  and gate_name = %s
                returning id
                """,
                (
                    outcome.gate_status,
                    outcome.decision,
                    outcome.stop_reason,
                    json.dumps(outcome.evidence, ensure_ascii=False),
                    reviewed_by,
                    candidate_id,
                    outcome.gate_name,
                ),
            )
            updated = cur.fetchone()
            gate_review_id = int(updated["id"])

            cur.execute(
                """
                insert into employer_origin_candidate_gate_events (
                    candidate_id,
                    gate_review_id,
                    event_type,
                    previous_state,
                    new_state,
                    event_reason,
                    created_by
                )
                values (%s, %s, 'gate_updated', %s::jsonb, %s::jsonb, %s, %s)
                """,
                (
                    candidate_id,
                    gate_review_id,
                    json.dumps(previous_state, default=str, ensure_ascii=False),
                    json.dumps(
                        {
                            "gate_name": outcome.gate_name,
                            "gate_status": outcome.gate_status,
                            "decision": outcome.decision,
                            "stop_reason": outcome.stop_reason,
                            "evidence": outcome.evidence,
                        },
                        ensure_ascii=False,
                    ),
                    "connector-candidate gate-agent run",
                    reviewed_by,
                ),
            )

        self.conn.commit()

    def update_candidate_status(self, candidate_id: int, status: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                update employer_origin_source_candidates
                set status = %s,
                    updated_at = now()
                where id = %s
                """,
                (status, candidate_id),
            )
        self.conn.commit()


def write_review_report(
    *,
    output_dir: Path,
    candidate: SourceCandidate,
    outcome: GateOutcome,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    base_name = snake_case(candidate.company_key)
    json_path = output_dir / f"{base_name}_connector_candidate_review.json"
    md_path = output_dir / f"{base_name}_connector_candidate_review.md"

    payload = {
        "candidate_id": candidate.id,
        "company_key": candidate.company_key,
        "source_name_candidate": candidate.source_name_candidate,
        "gate_name": outcome.gate_name,
        "gate_status": outcome.gate_status,
        "decision": outcome.decision,
        "stop_reason": outcome.stop_reason,
        "evidence": outcome.evidence,
        "output_boundary": [
            "This report is a human-readable review artifact.",
            "It is not a pipeline input.",
            "DB-backed gate state remains the source of truth.",
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    spec = outcome.evidence.get("connector_candidate_spec") or {}
    recommended = spec.get("recommended_connector") or {}
    uniqueness = spec.get("incremental_uniqueness") or {}

    md_lines = [
        f"# S2U Connector Candidate Review — {candidate.company_key}",
        "",
        "## Boundary",
        "",
        "This report is a human-readable output only. DB-backed gate state is the source of truth.",
        "",
        "## Decision",
        "",
        f"- gate: `{outcome.gate_name}`",
        f"- status: `{outcome.gate_status}`",
        f"- decision: `{outcome.decision}`",
        f"- stop reason: {outcome.stop_reason or '-'}",
        "",
        "## Recommended Connector",
        "",
        f"- module: `{recommended.get('module_path', '-')}`",
        f"- class: `{recommended.get('class_name', '-')}`",
        f"- source: `{recommended.get('source_name', candidate.source_name_candidate)}`",
        f"- source type: `{recommended.get('source_type', candidate.source_type_candidate)}`",
        "",
        "## Incremental Uniqueness",
        "",
        f"- detail candidates considered: {uniqueness.get('detail_candidates_considered', '-')}",
        f"- existing evidence rows considered: {uniqueness.get('existing_evidence_rows_considered', '-')}",
        f"- uniqueness counts: `{json.dumps(uniqueness.get('uniqueness_counts', {}), ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Next Boundary",
        "",
        "A connector implementation still requires an explicit implementation PR. This gate does not activate ingestion or approve recurring runs.",
        "",
    ]

    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    return json_path, md_path


def run_agent(args: argparse.Namespace) -> int:
    with psycopg.connect(DatabaseConfig.from_environment().dsn()) as conn:
        repo = GateStateRepository(conn)
        candidate = repo.load_candidate(candidate_id=args.candidate_id, company_key=args.company_key)
        gates = repo.load_gate_reviews(candidate.id)
        outcome = connector_candidate_outcome(candidate, gates)

        repo.record_gate(candidate.id, outcome, args.reviewed_by)

        if outcome.gate_status == "passed":
            repo.update_candidate_status(candidate.id, "connector_candidate")
        else:
            repo.update_candidate_status(candidate.id, "manual_review_required")

        print(f"candidate_id: {candidate.id}")
        print(f"candidate: {candidate.company_key} | {candidate.source_name_candidate}")
        print(f"{outcome.gate_name}: {outcome.gate_status} / {outcome.decision}")
        if outcome.stop_reason:
            print(f"STOP: {outcome.stop_reason}")

        if args.write_report:
            json_path, md_path = write_review_report(
                output_dir=Path(args.output_dir),
                candidate=candidate,
                outcome=outcome,
            )
            print("Exported review artifacts:")
            print(f"- {json_path}")
            print(f"- {md_path}")

        if outcome.gate_status == "passed":
            print("NEXT: connector implementation PR is justified, but activation and Bronze persistence remain separate gates.")

        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the employer-origin connector-candidate gate agent."
    )
    candidate = parser.add_mutually_exclusive_group(required=True)
    candidate.add_argument("--candidate-id", type=int)
    candidate.add_argument("--company-key")

    parser.add_argument("--reviewed-by", default="agent_mvp")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-report", dest="write_report", action="store_false")
    parser.set_defaults(write_report=True)
    return parser


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
