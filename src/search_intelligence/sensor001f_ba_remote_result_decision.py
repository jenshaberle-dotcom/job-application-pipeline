from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

REQUIRED_METRICS: tuple[str, ...] = (
    "total_loaded_by_term",
    "inserted_count_by_term",
    "duplicate_count_by_term",
    "distinct_company_count",
    "new_company_count",
    "known_company_overlap_count",
    "remote_signal_count",
    "local_or_hannover_overlap_count",
    "profile_relevant_title_count",
    "irrelevant_title_count",
    "error_count",
)

DECISION_OPTIONS: tuple[str, ...] = (
    "activate_controlled_profile",
    "repeat_bounded_sample_with_repaired_terms",
    "keep_review_profile_inactive_and_monitor",
    "reject_or_archive_profile_as_noise",
    "repair_sensor001e_and_rerun_before_decision",
)


@dataclass(frozen=True)
class Sensor001FDecisionReport:
    overall_status: str
    source_status: str
    recommended_decision: str
    confidence: str
    reason: str
    required_metrics: tuple[str, ...]
    available_metrics: tuple[str, ...]
    missing_metrics: tuple[str, ...]
    decision_options: tuple[str, ...]
    metric_summary: Mapping[str, Any]
    findings: tuple[str, ...]
    next_action: str
    safety_boundary: Mapping[str, bool]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.update(
            {
                "schema_version": "sensor001f.ba_remote_nationwide_result_decision.v1",
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "work_item": "SENSOR-001F BA Remote/Nationwide Result Decision",
            }
        )
        return payload


def build_sensor001f_result_decision(sensor001e_report: Mapping[str, Any]) -> Sensor001FDecisionReport:
    source_status = str(sensor001e_report.get("overall_status") or "unknown")
    metrics = sensor001e_report.get("metrics")
    metric_summary = dict(metrics) if isinstance(metrics, Mapping) else {}
    available_metrics = tuple(key for key in REQUIRED_METRICS if key in metric_summary)
    missing_metrics = tuple(key for key in REQUIRED_METRICS if key not in metric_summary)
    safety_boundary = {
        "read_only_decision": True,
        "external_requests": False,
        "database_writes": False,
        "raw_jobs_write": False,
        "ingestion_run_write": False,
        "scheduler_mutation": False,
        "candidate_or_gate_mutation": False,
        "connector_activation": False,
        "bronze_silver_gold_mutation": False,
        "productive_activation": False,
    }

    if source_status == "execution_failed_before_sample":
        return Sensor001FDecisionReport(
            overall_status="decision_blocked_by_sensor001e_execution_failure",
            source_status=source_status,
            recommended_decision="repair_sensor001e_and_rerun_before_decision",
            confidence="high",
            reason="SENSOR-001E failed before any bounded sample data was collected; the result contains no market evidence.",
            required_metrics=REQUIRED_METRICS,
            available_metrics=available_metrics,
            missing_metrics=missing_metrics,
            decision_options=DECISION_OPTIONS,
            metric_summary=metric_summary,
            findings=(
                "Do not infer BA remote/nationwide quality from a pre-sample technical failure.",
                "No activation, rejection, term repair, or repeat-sample decision is justified from this artifact alone.",
                _format_upstream_error(sensor001e_report),
            ),
            next_action="Repair SENSOR-001E execution, rerun the bounded sample, then rerun SENSOR-001F.",
            safety_boundary=safety_boundary,
        )

    if source_status == "approval_required":
        return Sensor001FDecisionReport(
            overall_status="decision_blocked_until_sensor001e_execution",
            source_status=source_status,
            recommended_decision="do_not_decide_before_bounded_sample_result",
            confidence="high",
            reason="SENSOR-001E was not executed; approval-only readiness is not market evidence.",
            required_metrics=REQUIRED_METRICS,
            available_metrics=available_metrics,
            missing_metrics=missing_metrics,
            decision_options=DECISION_OPTIONS,
            metric_summary=metric_summary,
            findings=("SENSOR-001E still needs an explicitly approved bounded external sample run.",),
            next_action="Run SENSOR-001E with explicit approval, then rerun SENSOR-001F.",
            safety_boundary=safety_boundary,
        )

    if source_status not in {"sample_executed", "sample_executed_with_errors"}:
        return Sensor001FDecisionReport(
            overall_status="decision_blocked_by_unexpected_sensor001e_status",
            source_status=source_status,
            recommended_decision="inspect_sensor001e_result_before_decision",
            confidence="medium",
            reason=f"Unexpected SENSOR-001E status: {source_status}",
            required_metrics=REQUIRED_METRICS,
            available_metrics=available_metrics,
            missing_metrics=missing_metrics,
            decision_options=DECISION_OPTIONS,
            metric_summary=metric_summary,
            findings=("Inspect the upstream SENSOR-001E artifact before any product decision.",),
            next_action="Inspect SENSOR-001E output and repair the decision adapter if needed.",
            safety_boundary=safety_boundary,
        )

    if missing_metrics:
        return Sensor001FDecisionReport(
            overall_status="decision_blocked_by_missing_metrics",
            source_status=source_status,
            recommended_decision="repair_sensor001e_metrics_and_rerun_before_decision",
            confidence="high",
            reason="The bounded sample executed but did not expose all metrics required for a controlled decision.",
            required_metrics=REQUIRED_METRICS,
            available_metrics=available_metrics,
            missing_metrics=missing_metrics,
            decision_options=DECISION_OPTIONS,
            metric_summary=metric_summary,
            findings=("SENSOR-001F requires complete metric coverage before recommending activation, repeat, monitoring, or rejection.",),
            next_action="Repair SENSOR-001E metric export, rerun SENSOR-001E if needed, then rerun SENSOR-001F.",
            safety_boundary=safety_boundary,
        )

    return _decide_from_complete_metrics(source_status, metric_summary, safety_boundary)


def _decide_from_complete_metrics(
    source_status: str,
    metrics: Mapping[str, Any],
    safety_boundary: Mapping[str, bool],
) -> Sensor001FDecisionReport:
    total_loaded = _sum_metric(metrics.get("total_loaded_by_term"))
    would_insert = _sum_metric(metrics.get("inserted_count_by_term"))
    duplicates = _sum_metric(metrics.get("duplicate_count_by_term"))
    new_companies = int(metrics.get("new_company_count") or 0)
    remote_signals = int(metrics.get("remote_signal_count") or 0)
    relevant_titles = int(metrics.get("profile_relevant_title_count") or 0)
    irrelevant_titles = int(metrics.get("irrelevant_title_count") or 0)
    errors = int(metrics.get("error_count") or 0)

    findings = [
        f"sample_loaded={total_loaded}",
        f"would_insert={would_insert}",
        f"duplicates={duplicates}",
        f"new_companies={new_companies}",
        f"remote_signals={remote_signals}",
        f"profile_relevant_titles={relevant_titles}",
        f"irrelevant_titles={irrelevant_titles}",
        f"errors={errors}",
    ]

    if errors:
        return Sensor001FDecisionReport(
            overall_status="decision_requires_sample_repair",
            source_status=source_status,
            recommended_decision="repeat_bounded_sample_with_repaired_terms",
            confidence="medium",
            reason="The sample produced errors; repair the failing term(s) before activation or rejection.",
            required_metrics=REQUIRED_METRICS,
            available_metrics=REQUIRED_METRICS,
            missing_metrics=(),
            decision_options=DECISION_OPTIONS,
            metric_summary=dict(metrics),
            findings=tuple(findings),
            next_action="Repair failing sampled terms and repeat the bounded sample.",
            safety_boundary=safety_boundary,
        )

    if total_loaded == 0:
        recommended = "repeat_bounded_sample_with_repaired_terms"
        reason = "The sample returned no visible jobs; one bounded repeat with repaired terms is safer than rejection."
        confidence = "medium"
    elif new_companies > 0 and remote_signals > 0 and relevant_titles > irrelevant_titles:
        recommended = "activate_controlled_profile"
        reason = "The sample found new companies, remote signals, and more relevant than irrelevant titles."
        confidence = "medium"
    elif new_companies > 0 or relevant_titles > 0:
        recommended = "repeat_bounded_sample_with_repaired_terms"
        reason = "The sample has some signal but not enough quality for controlled activation."
        confidence = "medium"
    elif would_insert == 0 and duplicates >= total_loaded:
        recommended = "keep_review_profile_inactive_and_monitor"
        reason = "The sample is dominated by duplicates and does not justify activation."
        confidence = "medium"
    else:
        recommended = "keep_review_profile_inactive_and_monitor"
        reason = "The sample does not yet justify activation or rejection."
        confidence = "low"

    return Sensor001FDecisionReport(
        overall_status="decision_ready",
        source_status=source_status,
        recommended_decision=recommended,
        confidence=confidence,
        reason=reason,
        required_metrics=REQUIRED_METRICS,
        available_metrics=REQUIRED_METRICS,
        missing_metrics=(),
        decision_options=DECISION_OPTIONS,
        metric_summary=dict(metrics),
        findings=tuple(findings),
        next_action="Review the SENSOR-001F recommendation before any controlled activation or follow-up run.",
        safety_boundary=safety_boundary,
    )


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# SENSOR-001F BA Remote/Nationwide Result Decision",
        "",
        f"- overall_status: `{report.get('overall_status')}`",
        f"- source_status: `{report.get('source_status')}`",
        f"- recommended_decision: `{report.get('recommended_decision')}`",
        f"- confidence: `{report.get('confidence')}`",
        "",
        "## Reason",
        "",
        str(report.get("reason", "")),
        "",
        "## Metric coverage",
        "",
        f"- required_metrics: `{len(report.get('required_metrics', []))}`",
        f"- available_metrics: `{len(report.get('available_metrics', []))}`",
        f"- missing_metrics: `{report.get('missing_metrics', [])}`",
        "",
        "## Findings",
        "",
    ]
    for finding in report.get("findings", []):
        lines.append(f"- {finding}")
    lines.extend(["", "## Safety boundary", ""])
    for key, value in report.get("safety_boundary", {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Next action", "", str(report.get("next_action", "")), ""])
    return "\n".join(lines)


def latest_sensor001e_report_path(exports_dir: Path) -> Path:
    candidates = sorted(exports_dir.glob("sensor001e_ba_remote_bounded_sample_execution_*.json"))
    if not candidates:
        raise FileNotFoundError("No SENSOR-001E JSON export found.")
    return candidates[-1]


def _format_upstream_error(report: Mapping[str, Any]) -> str:
    error = report.get("database_error")
    if isinstance(error, Mapping):
        return f"Upstream error: {error.get('type')}: {error.get('message')}"
    return "Upstream error details are not available."


def _sum_metric(value: Any) -> int:
    if isinstance(value, Mapping):
        return sum(int(item or 0) for item in value.values())
    return int(value or 0)
