from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config

DEFAULT_OUTPUT_DIR = Path("exports/pipeline_stop_reassessment")
DEFAULT_BENCHMARK_LABEL = "pipeline_stop_reassessment"

TERMINAL_GATE_STATUSES = {"blocked", "manual_review_required", "failed", "deferred"}
TERMINAL_GATE_DECISIONS = {"abort_documented", "manual_review_required", "failed", "deferred"}
STOPPER_CANDIDATE_STATUSES = {"abort_documented", "manual_review_required"}
MISSING_URL_MARKERS = {"", "none", "null"}
ACCESS_RISK_MARKERS = (
    "bot-defense",
    "bot defense",
    "access-risk",
    "access risk",
    "captcha",
    "recaptcha",
    "authentication",
    "cloudflare",
    "blocked by",
)
DETAIL_EVIDENCE_MARKERS = (
    "no concrete detail pages",
    "no validated detail page",
    "no concrete detail urls",
    "detail evidence",
    "target-location",
    "target/remote",
)
SOURCE_URL_RECOVERY_MARKERS = (
    "no reachable company-related career/job url",
    "source url recovery",
    "http 404",
    "not found",
    "request failed",
)

READ_ONLY_BOUNDARY: dict[str, bool] = {
    "read_only_stop_validity_audit": True,
    "no_candidate_status_write": True,
    "no_candidate_url_write": True,
    "no_gate_review_write": True,
    "no_evidence_write": True,
    "no_connector_artifact_write": True,
    "no_connector_registration": True,
    "no_source_activation": True,
    "stage2_commands_are_planned_not_executed_by_default": True,
}


@dataclass(frozen=True)
class StopCandidate:
    candidate_id: int
    company_key: str
    company_name: str
    candidate_url: str | None
    source_name_candidate: str
    source_family_candidate: str
    source_target_candidate: str | None
    source_type_candidate: str
    status: str
    risk_level: str


@dataclass(frozen=True)
class StopGate:
    gate_name: str
    gate_status: str | None
    decision: str | None
    stop_reason: str | None
    evidence: dict[str, Any]


@dataclass(frozen=True)
class Stage2RepairPlan:
    action: str
    dry_run_command: str | None
    apply_command: str | None
    execution_requires_explicit_apply: bool
    rationale: str


@dataclass(frozen=True)
class StopAssessment:
    candidate: StopCandidate
    stop_signals: list[dict[str, Any]]
    stop_validity: str
    false_negative_risk: str
    confidence_score: float
    confidence_reason: str
    recommended_action: str
    stage2_repair_plan: Stage2RepairPlan | None


def _shell_command(parts: list[str]) -> str:
    return " ".join(parts)


def has_usable_candidate_url(candidate: StopCandidate) -> bool:
    return (candidate.candidate_url or "").strip().lower() not in MISSING_URL_MARKERS


def text_contains_any(value: str | None, markers: tuple[str, ...]) -> bool:
    lowered = (value or "").lower()
    return any(marker in lowered for marker in markers)


def gate_is_stop(gate: StopGate) -> bool:
    return (gate.gate_status or "") in TERMINAL_GATE_STATUSES or (gate.decision or "") in TERMINAL_GATE_DECISIONS


def collect_stop_signals(candidate: StopCandidate, gates: dict[str, StopGate]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    if candidate.status in STOPPER_CANDIDATE_STATUSES:
        signals.append({"kind": "candidate_status", "value": candidate.status})
    if candidate.risk_level == "blocked":
        signals.append({"kind": "candidate_risk_level", "value": candidate.risk_level})
    if not has_usable_candidate_url(candidate) and candidate.status != "active_controlled":
        signals.append({"kind": "missing_candidate_url", "value": "candidate_url is missing"})

    for gate in sorted(gates.values(), key=lambda item: item.gate_name):
        if gate_is_stop(gate) or gate.stop_reason:
            signals.append(
                {
                    "kind": "gate_stop",
                    "gate_name": gate.gate_name,
                    "gate_status": gate.gate_status,
                    "decision": gate.decision,
                    "stop_reason": gate.stop_reason,
                }
            )
    return signals


def signals_contain_access_risk(signals: list[dict[str, Any]]) -> bool:
    return any(text_contains_any(str(signal.get("stop_reason") or signal.get("value") or ""), ACCESS_RISK_MARKERS) for signal in signals)


def signals_contain_detail_evidence_gap(signals: list[dict[str, Any]]) -> bool:
    return any(text_contains_any(str(signal.get("stop_reason") or ""), DETAIL_EVIDENCE_MARKERS) for signal in signals)


def signals_contain_source_url_gap(signals: list[dict[str, Any]]) -> bool:
    return any(text_contains_any(str(signal.get("stop_reason") or ""), SOURCE_URL_RECOVERY_MARKERS) for signal in signals)


def detail_repair_plan(candidate: StopCandidate, *, target_location: str, reviewed_by: str) -> Stage2RepairPlan:
    base = [
        "python",
        "-m",
        "scripts.run_employer_origin_detail_evidence_repair_agent",
        "--company-key",
        candidate.company_key,
        "--target-location",
        target_location,
        "--reviewed-by",
        reviewed_by,
    ]
    return Stage2RepairPlan(
        action="run_bounded_detail_evidence_repair",
        dry_run_command=_shell_command([*base, "--dry-run"]),
        apply_command=_shell_command(base),
        execution_requires_explicit_apply=True,
        rationale="re-run the bounded detail-evidence repair after the stop validity audit flags a potentially stale or over-sensitive stop",
    )


def source_url_recovery_plan(candidate: StopCandidate, *, target_location: str, reviewed_by: str) -> Stage2RepairPlan:
    base = [
        "python",
        "-m",
        "scripts.run_employer_origin_source_url_recovery_agent",
        "--company-key",
        candidate.company_key,
        "--target-location",
        target_location,
        "--reviewed-by",
        reviewed_by,
        "--run-gate-review-after-recovery",
    ]
    return Stage2RepairPlan(
        action="run_bounded_source_url_recovery",
        dry_run_command=_shell_command(base),
        apply_command=_shell_command([*base, "--apply"]),
        execution_requires_explicit_apply=True,
        rationale="recover or validate a concrete source URL before retrying downstream gates",
    )


def chain_plan(candidate: StopCandidate, *, target_location: str, reviewed_by: str) -> Stage2RepairPlan:
    base = [
        "python",
        "-m",
        "scripts.run_employer_origin_agent_chain",
        "--company-key",
        candidate.company_key,
        "--target-location",
        target_location,
        "--reviewed-by",
        reviewed_by,
        "--attempt-repair",
    ]
    return Stage2RepairPlan(
        action="run_canonical_chain_with_repair",
        dry_run_command=_shell_command([*base, "--plan-only"]),
        apply_command=_shell_command(base),
        execution_requires_explicit_apply=True,
        rationale="delegate the repaired or ambiguous stopper back to the canonical chain after explicit operator approval",
    )


def assess_stop_validity(
    candidate: StopCandidate,
    gates: dict[str, StopGate],
    *,
    target_location: str,
    reviewed_by: str,
) -> StopAssessment | None:
    signals = collect_stop_signals(candidate, gates)
    if not signals:
        return None

    has_url = has_usable_candidate_url(candidate)
    access_risk = signals_contain_access_risk(signals)
    detail_gap = signals_contain_detail_evidence_gap(signals)
    source_url_gap = signals_contain_source_url_gap(signals) or not has_url

    if access_risk and has_url:
        return StopAssessment(
            candidate=candidate,
            stop_signals=signals,
            stop_validity="needs_reassessment_likely_over_sensitive",
            false_negative_risk="high",
            confidence_score=0.82,
            confidence_reason=(
                "access-risk/bot-defense markers are present, but the candidate has a concrete URL; "
                "this may be a stale or over-sensitive stop caused by consent, form or footer markers rather than a real content challenge"
            ),
            recommended_action="stage2_dry_run_detail_repair_then_apply_if_evidence_is_supported",
            stage2_repair_plan=detail_repair_plan(candidate, target_location=target_location, reviewed_by=reviewed_by),
        )

    if source_url_gap:
        return StopAssessment(
            candidate=candidate,
            stop_signals=signals,
            stop_validity="unconfirmed_stop_recovery_needed",
            false_negative_risk="medium",
            confidence_score=0.74,
            confidence_reason="the stop is tied to missing/unreachable source URL evidence; recovery should be attempted before treating it as a final stopper",
            recommended_action="stage2_dry_run_source_url_recovery_then_apply_if_selected_url_is_safe",
            stage2_repair_plan=source_url_recovery_plan(candidate, target_location=target_location, reviewed_by=reviewed_by),
        )

    if detail_gap and has_url:
        return StopAssessment(
            candidate=candidate,
            stop_signals=signals,
            stop_validity="unconfirmed_detail_evidence_gap",
            false_negative_risk="medium",
            confidence_score=0.70,
            confidence_reason="a detail-evidence stop exists on a candidate with a concrete source URL; bounded repair may still find supported details after logic improvements",
            recommended_action="stage2_dry_run_detail_repair_then_apply_if_evidence_is_supported",
            stage2_repair_plan=detail_repair_plan(candidate, target_location=target_location, reviewed_by=reviewed_by),
        )

    if candidate.status == "abort_documented" or candidate.risk_level == "blocked":
        return StopAssessment(
            candidate=candidate,
            stop_signals=signals,
            stop_validity="stop_valid_until_new_evidence",
            false_negative_risk="medium",
            confidence_score=0.66,
            confidence_reason="candidate has a documented abort/block boundary, but no specific recoverable pattern was recognized by this agent",
            recommended_action="stage2_plan_canonical_chain_only_after_operator_review",
            stage2_repair_plan=chain_plan(candidate, target_location=target_location, reviewed_by=reviewed_by),
        )

    return StopAssessment(
        candidate=candidate,
        stop_signals=signals,
        stop_validity="manual_review_stopper",
        false_negative_risk="low",
        confidence_score=0.62,
        confidence_reason="stop evidence exists, but no automated reassessment pattern matched",
        recommended_action="manual_review_before_repair",
        stage2_repair_plan=None,
    )


def assessment_payload(assessment: StopAssessment) -> dict[str, Any]:
    payload = asdict(assessment)
    payload["stage2_has_repair_plan"] = assessment.stage2_repair_plan is not None
    return payload


def summarize_assessments(assessments: list[StopAssessment]) -> dict[str, Any]:
    validity_counts = Counter(item.stop_validity for item in assessments)
    risk_counts = Counter(item.false_negative_risk for item in assessments)
    action_counts = Counter(item.recommended_action for item in assessments)
    stage2_items = [item for item in assessments if item.stage2_repair_plan is not None]
    first_dry_run = next((item.stage2_repair_plan.dry_run_command for item in stage2_items if item.stage2_repair_plan and item.stage2_repair_plan.dry_run_command), None)
    first_apply = next((item.stage2_repair_plan.apply_command for item in stage2_items if item.stage2_repair_plan and item.stage2_repair_plan.apply_command), None)
    return {
        "stopper_count": len(assessments),
        "stage2_repair_plan_count": len(stage2_items),
        "high_false_negative_risk_count": risk_counts.get("high", 0),
        "medium_false_negative_risk_count": risk_counts.get("medium", 0),
        "stop_validity_counts": dict(sorted(validity_counts.items())),
        "false_negative_risk_counts": dict(sorted(risk_counts.items())),
        "recommended_action_counts": dict(sorted(action_counts.items())),
        "first_stage2_dry_run_command": first_dry_run,
        "first_stage2_apply_command": first_apply,
    }


def report_payload(
    assessments: list[StopAssessment],
    *,
    benchmark_label: str,
    target_location: str,
    reviewed_by: str,
) -> dict[str, Any]:
    return {
        "campaign": "Pipeline Stopper Reassessment Agent",
        "benchmark_label": benchmark_label,
        "target_location": target_location,
        "reviewed_by": reviewed_by,
        "boundary": READ_ONLY_BOUNDARY,
        "report_contract": {
            "stage1_stop_validity_audit": "classifies whether existing stop signals look valid, stale, over-sensitive, or recoverable",
            "stage2_repair_plan": "planned dry-run/apply commands for recoverable stoppers; not executed unless an operator explicitly runs/apply-enables them",
            "false_negative_risk": "risk that the current stop hides a relevant candidate due to over-sensitive pipeline logic",
            "no_automatic_unblocking": "this report never changes candidate status, gate status, URLs, evidence, connector files, source registration, or scheduler state",
        },
        "summary": summarize_assessments(assessments),
        "items": [assessment_payload(item) for item in assessments],
    }


def render_markdown_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        f"# {payload['campaign']}",
        "",
        f"Benchmark label: `{payload['benchmark_label']}`",
        f"Target location: `{payload['target_location']}`",
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
            f"- Stopper count: `{summary['stopper_count']}`",
            f"- Stage 2 repair plan count: `{summary['stage2_repair_plan_count']}`",
            f"- High false-negative-risk count: `{summary['high_false_negative_risk_count']}`",
            f"- Medium false-negative-risk count: `{summary['medium_false_negative_risk_count']}`",
            "",
            "### Stop validity",
            "",
        ]
    )
    for key, count in summary["stop_validity_counts"].items():
        lines.append(f"- `{key}`: `{count}`")

    if summary["first_stage2_dry_run_command"]:
        lines.extend(["", "## First Stage 2 dry-run command", "", "    " + summary["first_stage2_dry_run_command"]])
    if summary["first_stage2_apply_command"]:
        lines.extend(["", "## First Stage 2 apply command", "", "    " + summary["first_stage2_apply_command"]])

    lines.extend(["", "## Stopper assessments", ""])
    for item in payload["items"]:
        candidate = item["candidate"]
        plan = item.get("stage2_repair_plan")
        lines.extend(
            [
                f"### {candidate['company_key']}",
                "",
                f"- Candidate ID: `{candidate['candidate_id']}`",
                f"- Company: `{candidate['company_name']}`",
                f"- Status: `{candidate['status']}`",
                f"- Risk level: `{candidate['risk_level']}`",
                f"- Candidate URL: `{candidate.get('candidate_url') or '-'}`",
                f"- Stop validity: `{item['stop_validity']}`",
                f"- False-negative risk: `{item['false_negative_risk']}`",
                f"- Confidence: `{item['confidence_score']}` — {item['confidence_reason']}",
                f"- Recommended action: `{item['recommended_action']}`",
            ]
        )
        if plan:
            lines.extend(
                [
                    "- Stage 2 dry-run command:",
                    "",
                    "    " + (plan.get("dry_run_command") or "-"),
                    "- Stage 2 apply command:",
                    "",
                    "    " + (plan.get("apply_command") or "-"),
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def safe_label(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value).strip("_")
    return cleaned or DEFAULT_BENCHMARK_LABEL


def write_reports(payload: dict[str, Any], output_dir: Path, label: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe = safe_label(label)
    json_path = output_dir / f"{safe}_stop_reassessment.json"
    md_path = output_dir / f"{safe}_stop_reassessment.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown_report(payload), encoding="utf-8")
    return json_path, md_path


class StopperRepository:
    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self.conn = conn

    def load_candidates(self, company_key: str | None = None) -> list[StopCandidate]:
        where_clause = ""
        params: tuple[Any, ...] = ()
        if company_key:
            where_clause = "where company_key = %s"
            params = (company_key,)

        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                select
                    id,
                    company_key,
                    company_name,
                    candidate_url,
                    source_name_candidate,
                    source_family_candidate,
                    source_target_candidate,
                    source_type_candidate,
                    status,
                    risk_level
                from employer_origin_source_candidates
                {where_clause}
                order by company_key, id
                """,
                params,
            )
            rows = cur.fetchall()

        return [
            StopCandidate(
                candidate_id=int(row["id"]),
                company_key=str(row["company_key"]),
                company_name=str(row["company_name"]),
                candidate_url=row["candidate_url"],
                source_name_candidate=str(row["source_name_candidate"]),
                source_family_candidate=str(row["source_family_candidate"]),
                source_target_candidate=row["source_target_candidate"],
                source_type_candidate=str(row["source_type_candidate"]),
                status=str(row["status"]),
                risk_level=str(row["risk_level"]),
            )
            for row in rows
        ]

    def load_latest_gate_reviews(self, candidate_id: int) -> dict[str, StopGate]:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                select distinct on (gate_name)
                    gate_name,
                    gate_status,
                    decision,
                    stop_reason,
                    evidence
                from employer_origin_candidate_gate_reviews
                where candidate_id = %s
                order by gate_name, updated_at desc, id desc
                """,
                (candidate_id,),
            )
            rows = cur.fetchall()

        return {
            str(row["gate_name"]): StopGate(
                gate_name=str(row["gate_name"]),
                gate_status=row["gate_status"],
                decision=row["decision"],
                stop_reason=row["stop_reason"],
                evidence=dict(row["evidence"] or {}),
            )
            for row in rows
        }


def execute_stage2_command(command: str) -> int:
    parts = command.split()
    print("running_stage2:", command)
    completed = subprocess.run(parts, check=False, capture_output=True, text=True)
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    return int(completed.returncode)


def run_agent(args: argparse.Namespace) -> int:
    with psycopg.connect(**get_database_config()) as conn:
        repo = StopperRepository(conn)
        candidates = repo.load_candidates(args.company_key)
        gates_by_candidate_id = {candidate.candidate_id: repo.load_latest_gate_reviews(candidate.candidate_id) for candidate in candidates}

    assessments = [
        assessment
        for candidate in candidates
        if (assessment := assess_stop_validity(
            candidate,
            gates_by_candidate_id.get(candidate.candidate_id, {}),
            target_location=args.target_location,
            reviewed_by=args.reviewed_by,
        ))
        is not None
    ]

    payload = report_payload(
        assessments,
        benchmark_label=args.benchmark_label,
        target_location=args.target_location,
        reviewed_by=args.reviewed_by,
    )

    print("summary:", json.dumps(payload["summary"], sort_keys=True, ensure_ascii=False))
    if args.company_key and not assessments:
        print(f"no_current_stop_signal: {args.company_key}")

    if args.write_report:
        json_path, md_path = write_reports(payload, args.output_dir, args.benchmark_label)
        print("json_report_written:", json_path)
        print("markdown_report_written:", md_path)

    if args.print_stage2_command:
        print("stage2_dry_run_command:")
        print(payload["summary"]["first_stage2_dry_run_command"] or "-")
        print("stage2_apply_command:")
        print(payload["summary"]["first_stage2_apply_command"] or "-")

    if args.execute_stage2:
        if not args.allow_write_actions:
            raise SystemExit("--execute-stage2 requires --allow-write-actions to avoid accidental pipeline mutation.")
        command = payload["summary"]["first_stage2_apply_command"]
        if not command:
            print("stage2_result: no_repair_plan")
            return 0
        return execute_stage2_command(command)

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only pipeline stopper reassessment agent. It audits whether current stops look valid, "
            "stale, over-sensitive, or recoverable, and emits Stage 2 dry-run/apply repair plans."
        )
    )
    parser.add_argument("--company-key")
    parser.add_argument("--target-location", default="hannover")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--benchmark-label", default=DEFAULT_BENCHMARK_LABEL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--print-stage2-command", action="store_true")
    parser.add_argument("--execute-stage2", action="store_true")
    parser.add_argument("--allow-write-actions", action="store_true")
    return parser


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
