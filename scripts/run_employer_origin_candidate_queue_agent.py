from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from scripts.aggregator_discovery_policy import (
    KnownEmployerCandidate,
    candidate_recheck_decision,
)
from scripts.run_employer_origin_agent_chain import (
    CONNECTOR_CANDIDATE_GATE,
    GateReview,
    connector_artifacts_exist,
    next_decision,
)


SOURCE_LIFECYCLE_GATE = "source_lifecycle_tracking"

DEFAULT_OUTPUT_DIR = Path("exports/eo_chain_candidate_readiness")
DEFAULT_BENCHMARK_LABEL = "eo_chain_candidate_readiness"

READ_ONLY_BOUNDARY: dict[str, bool] = {
    "read_only_candidate_chain_planning": True,
    "no_candidate_url_write": True,
    "no_gate_review_write": True,
    "no_evidence_write": True,
    "no_connector_artifact_write": True,
    "no_connector_registration": True,
    "no_source_activation": True,
    "no_scheduler_change": True,
}

ACTION_SAFETY_ZONE: dict[str, str] = {
    "monitor_source_lifecycle": "SZ0_READ_ONLY",
    "run_source_lifecycle_tracking": "SZ2_EVIDENCE_AND_GATES",
    "run_registration_execution_plan_agent": "SZ3_CONNECTOR_REGISTRATION_PLAN",
    "run_connector_validation_agent": "SZ3_CONNECTOR_ARTIFACT_REVIEW",
    "run_connector_artifact_generator": "SZ3_CONNECTOR_ARTIFACT_REVIEW",
    "run_connector_build_readiness_agent": "SZ2_EVIDENCE_AND_GATES",
    "run_connector_candidate_gate": "SZ2_EVIDENCE_AND_GATES",
    "run_employer_origin_recheck": "SZ2_EVIDENCE_AND_GATES",
    "run_detail_evidence_repair": "SZ2_EVIDENCE_AND_GATES",
    "manual_review_stop": "SZ2_EVIDENCE_AND_GATES",
    "run_pipeline_stop_reassessment": "SZ0_READ_ONLY",
    "stop_explicit_approval_required": "SZ4_HUMAN_APPROVAL_REQUIRED",
    "stop_manual_review_required": "SZ2_EVIDENCE_AND_GATES",
}


@dataclass(frozen=True)
class CandidateSummary:
    candidate_id: int
    company_key: str
    company_name: str
    source_name_candidate: str
    source_family_candidate: str
    status: str
    risk_level: str
    latest_gate_order: int | None
    latest_gate_name: str | None
    blocked_gate_count: int
    manual_review_gate_count: int
    passed_gate_count: int
    total_gate_count: int
    latest_gate_status: str | None = None
    latest_stop_reason: str | None = None
    latest_reviewed_at: str | None = None
    candidate_url: str | None = None


@dataclass(frozen=True)
class QueueItem:
    candidate: CandidateSummary
    next_action: str
    reason: str
    priority: int
    command: str | None


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


def gate_from_row(row: dict[str, Any]) -> GateReview:
    return GateReview(
        gate_name=str(row["gate_name"]),
        gate_status=str(row["gate_status"]),
        decision=str(row["decision"]),
        stop_reason=row["stop_reason"],
        evidence=dict(row.get("evidence") or {}),
    )


def build_chain_command(
    *,
    company_key: str,
    target_location: str,
    reviewed_by: str,
    attempt_repair: bool,
    write_connector: bool = False,
) -> str:
    parts = [
        "python",
        "-m",
        "scripts.run_employer_origin_agent_chain",
        "--company-key",
        company_key,
        "--target-location",
        target_location,
        "--reviewed-by",
        reviewed_by,
    ]
    if attempt_repair:
        parts.append("--attempt-repair")
    if write_connector:
        parts.append("--write-connector")
    return " ".join(parts)


def build_stopper_reassessment_command(
    *,
    company_key: str,
    target_location: str,
    reviewed_by: str,
) -> str:
    return (
        "python -m scripts.run_pipeline_stop_reassessment_agent "
        f"--company-key {company_key} "
        f"--target-location {target_location} "
        f"--reviewed-by {reviewed_by} "
        "--write-report --print-stage2-command"
    )


def build_lifecycle_command(*, company_key: str, reviewed_by: str) -> str:
    return (
        "python -m scripts.run_employer_origin_source_lifecycle_tracking_agent "
        f"--company-key {company_key} --reviewed-by {reviewed_by}"
    )


def completed_active_controlled_source(
    candidate: CandidateSummary,
    gates: dict[str, GateReview],
) -> bool:
    if candidate.status != "active_controlled":
        return False

    lifecycle_gate = gates.get(SOURCE_LIFECYCLE_GATE)
    if lifecycle_gate is None or lifecycle_gate.gate_status != "passed":
        return False

    return all(
        gate.gate_status not in {"blocked", "manual_review_required"}
        for gate in gates.values()
    )

def detail_evidence_repair_exhausted(gates: dict[str, GateReview]) -> bool:
    detail_gate = gates.get("detail_evidence_gate")
    if detail_gate is None:
        return False

    stop_reason = (detail_gate.stop_reason or "").lower()
    return (
        detail_gate.gate_status == "manual_review_required"
        and "bounded repair found no concrete detail pages" in stop_reason
    )

def lifecycle_gate_missing_or_not_passed(gates: dict[str, GateReview]) -> bool:
    lifecycle = gates.get(SOURCE_LIFECYCLE_GATE)
    return lifecycle is None or lifecycle.gate_status != "passed"


def candidate_has_blocked_operational_boundary(candidate: CandidateSummary) -> bool:
    return candidate.status == "abort_documented" or candidate.risk_level == "blocked"


def review_boundary_reason(item: QueueItem) -> str | None:
    candidate = item.candidate

    if item.next_action.startswith("stop_") or item.next_action == "manual_review_stop":
        return f"next_action={item.next_action}"
    if candidate.status in {"manual_review_required", "abort_documented"}:
        return f"candidate_status={candidate.status}"
    if candidate.risk_level == "blocked":
        return "risk_level=blocked"
    if candidate.latest_gate_status in {"manual_review_required", "blocked"}:
        return f"latest_gate_status={candidate.latest_gate_status}"
    if candidate.manual_review_gate_count > 0:
        return "manual_review_gate_count>0"
    if candidate.latest_stop_reason:
        return "latest_stop_reason_present"

    return None


def requires_operator_review_or_stop(item: QueueItem) -> bool:
    return review_boundary_reason(item) is not None


def recheck_gate_fallback(gates: dict[str, GateReview]) -> GateReview | None:
    """Pick a lifecycle-relevant gate for recheck classification when the DB
    summary does not already contain latest gate metadata.

    The database query provides latest_* fields for real queue runs. Unit tests and
    direct function calls may pass only a gate dictionary. The fallback keeps the
    recheck policy based on actual gate evidence instead of silently stopping at
    the generic chain decision.
    """

    for gate in gates.values():
        if gate.gate_status in {"manual_review_required", "blocked"}:
            return gate
    return None


def known_candidate_from_summary(
    candidate: CandidateSummary,
    gates: dict[str, GateReview] | None = None,
) -> KnownEmployerCandidate:
    fallback = recheck_gate_fallback(gates or {})

    return KnownEmployerCandidate(
        candidate_id=candidate.candidate_id,
        company_key=candidate.company_key,
        company_name=candidate.company_name,
        source_name_candidate=candidate.source_name_candidate,
        source_family_candidate=candidate.source_family_candidate,
        status=candidate.status,
        risk_level=candidate.risk_level,
        latest_gate_name=candidate.latest_gate_name or (fallback.gate_name if fallback else None),
        latest_gate_status=candidate.latest_gate_status or (fallback.gate_status if fallback else None),
        latest_stop_reason=candidate.latest_stop_reason or (fallback.stop_reason if fallback else None),
        latest_reviewed_at=candidate.latest_reviewed_at,
    )


def classify_queue_item(
    candidate: CandidateSummary,
    gates: dict[str, GateReview],
    *,
    target_location: str,
    reviewed_by: str,
    allow_repair: bool,
) -> QueueItem:
    if completed_active_controlled_source(candidate, gates):
        return QueueItem(
            candidate=candidate,
            next_action="monitor_source_lifecycle",
            reason="source is active_controlled and all tracked gates are passed",
            priority=100,
            command=None,
        )

    if candidate.status == "active_controlled" and lifecycle_gate_missing_or_not_passed(gates):
        return QueueItem(
            candidate=candidate,
            next_action="run_source_lifecycle_tracking",
            reason="active controlled source is missing a passed lifecycle gate",
            priority=10,
            command=build_lifecycle_command(
                company_key=candidate.company_key,
                reviewed_by=reviewed_by,
            ),
        )

    if candidate_has_blocked_operational_boundary(candidate):
        return QueueItem(
            candidate=candidate,
            next_action="run_pipeline_stop_reassessment",
            reason=(
                "candidate has a blocked operational boundary; route to the dedicated "
                "stopper reassessment agent before treating the stop as final "
                f"(status={candidate.status}, risk_level={candidate.risk_level})"
            ),
            priority=36,
            command=build_stopper_reassessment_command(
                company_key=candidate.company_key,
                target_location=target_location,
                reviewed_by=reviewed_by,
            ),
        )

    if detail_evidence_repair_exhausted(gates):
        return QueueItem(
            candidate=candidate,
            next_action="run_pipeline_stop_reassessment",
            reason=(
                "detail evidence repair was already attempted without supported details; "
                "route the stopper to the reassessment agent before manual closure"
            ),
            priority=37,
            command=build_stopper_reassessment_command(
                company_key=candidate.company_key,
                target_location=target_location,
                reviewed_by=reviewed_by,
            ),
        )

    recheck_eligible, recheck_reason = candidate_recheck_decision(
        known_candidate_from_summary(candidate, gates)
    )
    if recheck_eligible:
        return QueueItem(
            candidate=candidate,
            next_action="run_employer_origin_recheck",
            reason=recheck_reason or "candidate is eligible for recheck",
            priority=35,
            command=build_chain_command(
                company_key=candidate.company_key,
                target_location=target_location,
                reviewed_by=reviewed_by,
                attempt_repair=allow_repair,
                write_connector=False,
            ),
        )

    chain_decision = next_decision(
        gates,
        company_key=candidate.company_key,
        target_location=target_location,
        reviewed_by=reviewed_by,
        attempt_repair=allow_repair,
        write_connector=False,
        artifacts_exist=connector_artifacts_exist(candidate.source_family_candidate),
    )

    command = None
    if not chain_decision.action.startswith("stop_"):
        command = build_chain_command(
            company_key=candidate.company_key,
            target_location=target_location,
            reviewed_by=reviewed_by,
            attempt_repair=allow_repair,
            write_connector=False,
        )

    priority_by_action = {
        "run_registration_execution_plan_agent": 12,
        "run_connector_validation_agent": 15,
        "run_connector_artifact_generator": 20,
        "run_connector_build_readiness_agent": 25,
        "run_connector_candidate_gate": 30,
        "run_employer_origin_recheck": 35,
        "run_detail_evidence_repair": 40,
        "stop_explicit_approval_required": 85,
        "stop_manual_review_required": 90,
    }

    return QueueItem(
        candidate=candidate,
        next_action=chain_decision.action,
        reason=chain_decision.reason,
        priority=priority_by_action.get(chain_decision.action, 80),
        command=command,
    )


def sort_queue_items(items: list[QueueItem]) -> list[QueueItem]:
    return sorted(
        items,
        key=lambda item: (
            item.priority,
            item.candidate.company_key,
            item.candidate.candidate_id,
        ),
    )


def render_queue(items: list[QueueItem], *, limit: int | None = None) -> list[str]:
    selected = items[:limit] if limit is not None else items
    lines = [
        "Employer-Origin Candidate Queue",
        f"candidate_count: {len(items)}",
    ]

    for item in selected:
        candidate = item.candidate
        lines.extend(
            [
                "---",
                f"candidate_id: {candidate.candidate_id}",
                f"company_key: {candidate.company_key}",
                f"source_name_candidate: {candidate.source_name_candidate}",
                f"status: {candidate.status}",
                f"risk_level: {candidate.risk_level}",
                f"candidate_url: {candidate.candidate_url or '-'}",
                f"latest_gate: {candidate.latest_gate_name or '-'} / {candidate.latest_gate_status or '-'}",
                f"passed/manual/blocked/total gates: "
                f"{candidate.passed_gate_count}/"
                f"{candidate.manual_review_gate_count}/"
                f"{candidate.blocked_gate_count}/"
                f"{candidate.total_gate_count}",
                f"next_action: {item.next_action}",
                f"safety_zone: {ACTION_SAFETY_ZONE.get(item.next_action, 'SZ_UNKNOWN_REVIEW_REQUIRED')}",
                f"reason: {item.reason}",
            ]
        )
        if item.command:
            lines.append(f"command: {item.command}")

    return lines


def summarize_queue(items: list[QueueItem]) -> dict[str, Any]:
    action_counts = Counter(item.next_action for item in items)
    status_counts = Counter(item.candidate.status for item in items)
    safety_zone_counts = Counter(ACTION_SAFETY_ZONE.get(item.next_action, "SZ_UNKNOWN_REVIEW_REQUIRED") for item in items)
    command_items = [item for item in items if item.command]

    return {
        "candidate_count": len(items),
        "actionable_command_count": len(command_items),
        "manual_review_or_stop_count": sum(
            1 for item in items if requires_operator_review_or_stop(item)
        ),
        "monitor_only_count": action_counts.get("monitor_source_lifecycle", 0),
        "action_counts": dict(sorted(action_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "safety_zone_counts": dict(sorted(safety_zone_counts.items())),
        "first_actionable_command": command_items[0].command if command_items else None,
    }


def queue_item_payload(item: QueueItem) -> dict[str, Any]:
    payload = asdict(item)
    payload["safety_zone"] = ACTION_SAFETY_ZONE.get(item.next_action, "SZ_UNKNOWN_REVIEW_REQUIRED")
    payload["is_actionable"] = item.command is not None
    payload["requires_operator_review"] = requires_operator_review_or_stop(item)
    payload["review_boundary_reason"] = review_boundary_reason(item)
    return payload


def report_payload(
    items: list[QueueItem],
    *,
    benchmark_label: str,
    target_location: str,
    reviewed_by: str,
    allow_repair: bool,
) -> dict[str, Any]:
    return {
        "campaign": "EO Candidate Chain Readiness Plan",
        "benchmark_label": benchmark_label,
        "target_location": target_location,
        "reviewed_by": reviewed_by,
        "allow_repair": allow_repair,
        "boundary": READ_ONLY_BOUNDARY,
        "report_contract": {
            "queue_items": "ordered candidate-level next-safe-action recommendations; not an apply list",
            "command": "planned command only; never executed by this report",
            "manual_review_or_stop_count": "candidates with stop actions, blocked boundaries, manual-review state, or existing review/stop evidence",
            "requires_operator_review": "item-level flag for candidates that need operator attention before treating the planned command as routine progress",
            "first_actionable_command": "operator convenience for the first safe follow-up command, not automatic execution",
        },
        "summary": summarize_queue(items),
        "items": [queue_item_payload(item) for item in items],
    }


def render_markdown_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        f"# {payload['campaign']}",
        "",
        f"Benchmark label: `{payload['benchmark_label']}`",
        f"Target location: `{payload['target_location']}`",
        f"Allow repair: `{payload['allow_repair']}`",
        "",
        "## Boundary",
        "",
    ]
    for key, value in payload["boundary"].items():
        lines.append(f"- `{key}`: `{value}`")

    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Candidate count: `{summary['candidate_count']}`",
            f"- Actionable command count: `{summary['actionable_command_count']}`",
            f"- Manual review / stop count: `{summary['manual_review_or_stop_count']}`",
            f"- Monitor-only count: `{summary['monitor_only_count']}`",
            "",
            "### Action counts",
            "",
        ]
    )
    for action, count in summary["action_counts"].items():
        lines.append(f"- `{action}`: `{count}`")

    lines.extend(["", "### Safety zones", ""])
    for zone, count in summary["safety_zone_counts"].items():
        lines.append(f"- `{zone}`: `{count}`")

    if summary["first_actionable_command"]:
        lines.extend(
            [
                "",
                "## First actionable command",
                "",
                "    " + summary["first_actionable_command"],
            ]
        )

    lines.extend(["", "## Queue items", ""])
    for item in payload["items"]:
        candidate = item["candidate"]
        lines.extend(
            [
                f"### {candidate['company_key']}",
                "",
                f"- Candidate ID: `{candidate['candidate_id']}`",
                f"- Company: `{candidate['company_name']}`",
                f"- Status: `{candidate['status']}`",
                f"- Candidate URL: `{candidate.get('candidate_url') or '-'}`",
                f"- Gates passed/manual/blocked/total: "
                f"`{candidate['passed_gate_count']}/"
                f"{candidate['manual_review_gate_count']}/"
                f"{candidate['blocked_gate_count']}/"
                f"{candidate['total_gate_count']}`",
                f"- Next action: `{item['next_action']}`",
                f"- Safety zone: `{item['safety_zone']}`",
                f"- Requires operator review: `{item['requires_operator_review']}`",
                f"- Review boundary reason: `{item.get('review_boundary_reason') or '-'}`",
                f"- Reason: {item['reason']}",
            ]
        )
        if item["command"]:
            lines.extend(["- Planned command:", "", "    " + item["command"], ""])

    return "\n".join(lines).rstrip() + "\n"


def write_reports(payload: dict[str, Any], output_dir: Path, label: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_label = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in label).strip("_")
    if not safe_label:
        safe_label = DEFAULT_BENCHMARK_LABEL
    json_path = output_dir / f"{safe_label}_candidate_chain_readiness.json"
    md_path = output_dir / f"{safe_label}_candidate_chain_readiness.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown_report(payload), encoding="utf-8")
    return json_path, md_path


class QueueRepository:
    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self.conn = conn

    def load_candidates(self) -> list[CandidateSummary]:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select
                    c.id as candidate_id,
                    c.company_key,
                    c.company_name,
                    c.source_name_candidate,
                    c.source_family_candidate,
                    c.status,
                    c.risk_level,
                    c.candidate_url,
                    max(g.gate_order)::int as latest_gate_order,
                    (
                        array_agg(g.gate_name order by g.gate_order desc, g.updated_at desc, g.id desc)
                        filter (where g.gate_name is not null)
                    )[1] as latest_gate_name,
                    (
                        array_agg(g.gate_status order by g.gate_order desc, g.updated_at desc, g.id desc)
                        filter (where g.gate_status is not null)
                    )[1] as latest_gate_status,
                    (
                        array_agg(g.stop_reason order by g.gate_order desc, g.updated_at desc, g.id desc)
                        filter (where g.stop_reason is not null)
                    )[1] as latest_stop_reason,
                    (
                        array_agg(g.reviewed_at::text order by g.gate_order desc, g.updated_at desc, g.id desc)
                        filter (where g.reviewed_at is not null)
                    )[1] as latest_reviewed_at,
                    count(*) filter (where g.gate_status = 'blocked')::int as blocked_gate_count,
                    count(*) filter (where g.gate_status = 'manual_review_required')::int as manual_review_gate_count,
                    count(*) filter (where g.gate_status = 'passed')::int as passed_gate_count,
                    count(g.id)::int as total_gate_count
                from employer_origin_source_candidates c
                left join employer_origin_candidate_gate_reviews g
                    on g.candidate_id = c.id
                group by
                    c.id,
                    c.company_key,
                    c.company_name,
                    c.source_name_candidate,
                    c.source_family_candidate,
                    c.status,
                    c.risk_level,
                    c.candidate_url
                order by c.company_key
                """
            )
            rows = cur.fetchall()

        return [
            CandidateSummary(
                candidate_id=int(row["candidate_id"]),
                company_key=str(row["company_key"]),
                company_name=str(row["company_name"]),
                source_name_candidate=str(row["source_name_candidate"]),
                source_family_candidate=str(row["source_family_candidate"]),
                status=str(row["status"]),
                risk_level=str(row["risk_level"]),
                latest_gate_order=row["latest_gate_order"],
                latest_gate_name=row["latest_gate_name"],
                latest_gate_status=row["latest_gate_status"],
                latest_stop_reason=row["latest_stop_reason"],
                latest_reviewed_at=row["latest_reviewed_at"],
                candidate_url=row["candidate_url"],
                blocked_gate_count=int(row["blocked_gate_count"]),
                manual_review_gate_count=int(row["manual_review_gate_count"]),
                passed_gate_count=int(row["passed_gate_count"]),
                total_gate_count=int(row["total_gate_count"]),
            )
            for row in rows
        ]

    def load_gate_reviews(self, candidate_id: int) -> dict[str, GateReview]:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select
                    gate_name,
                    gate_status,
                    decision,
                    stop_reason,
                    evidence
                from employer_origin_candidate_gate_reviews
                where candidate_id = %s
                """,
                (candidate_id,),
            )
            rows = cur.fetchall()

        return {str(row["gate_name"]): gate_from_row(row) for row in rows}


def build_queue(
    candidates: list[CandidateSummary],
    gates_by_candidate_id: dict[int, dict[str, GateReview]],
    *,
    target_location: str,
    reviewed_by: str,
    allow_repair: bool,
) -> list[QueueItem]:
    items = [
        classify_queue_item(
            candidate,
            gates_by_candidate_id.get(candidate.candidate_id, {}),
            target_location=target_location,
            reviewed_by=reviewed_by,
            allow_repair=allow_repair,
        )
        for candidate in candidates
    ]

    return sort_queue_items(items)


def run_agent(args: argparse.Namespace) -> int:
    with psycopg.connect(DatabaseConfig.from_environment().dsn()) as conn:
        repo = QueueRepository(conn)
        candidates = repo.load_candidates()
        gates_by_candidate_id = {
            candidate.candidate_id: repo.load_gate_reviews(candidate.candidate_id)
            for candidate in candidates
        }

    queue = build_queue(
        candidates,
        gates_by_candidate_id,
        target_location=args.target_location,
        reviewed_by=args.reviewed_by,
        allow_repair=args.allow_repair,
    )

    for line in render_queue(queue, limit=args.limit):
        print(line)

    payload = report_payload(
        queue,
        benchmark_label=args.benchmark_label,
        target_location=args.target_location,
        reviewed_by=args.reviewed_by,
        allow_repair=args.allow_repair,
    )

    if args.write_report:
        json_path, md_path = write_reports(payload, args.output_dir, args.benchmark_label)
        print("---")
        print("summary:", json.dumps(payload["summary"], sort_keys=True, ensure_ascii=False))
        print("json_report_written:", json_path)
        print("markdown_report_written:", md_path)

    if args.print_next_command:
        next_command = payload["summary"]["first_actionable_command"]
        print("---")
        print("next_command:")
        print(next_command or "-")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "DB-backed queue view for employer-origin candidates. "
            "It proposes the next bounded agent command without executing it."
        )
    )
    parser.add_argument("--target-location", default="hannover")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--allow-repair", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--print-next-command", action="store_true")
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--benchmark-label", default=DEFAULT_BENCHMARK_LABEL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
