from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "generic002.benchmark_gap_closure_plan.v1"
WORK_ITEM = "GENERIC-002 Benchmark Gap Closure Plan"
GENERIC001_SCHEMA_PREFIX = "generic001.pipeline_generics_proof_gate"

CONTROL_ELIGIBLE_EVIDENCE_STRENGTH = frozenset({"strong_detail", "strong_origin"})
SAFE_STOP_ACTIONS = frozenset(
    {
        "no_useful_external_hint_no_candidate_creation",
        "provider_auth_failed_requires_key_review",
        "probe_error_requires_retry_or_review",
    }
)


@dataclass(frozen=True)
class ClosureStep:
    gap_id: str
    status: str
    required_next_step: str
    candidate_key: str | None = None
    candidate_name: str | None = None
    rationale: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def no_mutation_boundary() -> dict[str, bool]:
    return {
        "review_artifact_only": True,
        "external_requests": False,
        "database_reads": False,
        "database_writes": False,
        "candidate_creation": False,
        "candidate_promotion": False,
        "gate_decision": False,
        "connector_activation": False,
        "scheduler_mutation": False,
        "bronze_silver_gold_mutation": False,
    }


def mutation_counts() -> dict[str, int]:
    return {
        "created_candidates": 0,
        "automatic_candidate_promotions": 0,
        "written_gate_decisions": 0,
        "activated_connectors": 0,
        "scheduler_changes": 0,
        "bronze_silver_gold_writes": 0,
        "database_writes": 0,
        "external_requests": 0,
    }


def load_generic001_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("GENERIC-001 input JSON root must be an object.")
    schema_version = str(payload.get("schema_version") or "")
    if not schema_version.startswith(GENERIC001_SCHEMA_PREFIX):
        raise ValueError(f"Unexpected GENERIC-001 schema_version: {schema_version or '<missing>'}")
    return payload


def find_latest_generic001_report(exports_dir: Path = Path("exports")) -> Path | None:
    patterns = [
        "generic001_pipeline_generics_proof_gate/generic001_pipeline_generics_proof_gate.json",
        "generic001_pipeline_generics_proof_gate_*/generic001_pipeline_generics_proof_gate.json",
    ]
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(path for path in exports_dir.glob(pattern) if path.is_file())
    if not candidates:
        return None
    return max(candidates, key=lambda path: (_timestamp_from_parent(path), path.stat().st_mtime, str(path)))


def build_benchmark_gap_closure_plan(
    generic001_report: Mapping[str, Any],
    *,
    input_path: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    gap_ids = _string_list(generic001_report.get("gap_ids"))
    candidate_rows = _mapping_list(generic001_report.get("candidate_decision_table"))
    closure_steps = [_closure_step_for_gap(gap_id, candidate_rows) for gap_id in gap_ids]
    cli = build_rerun_command(closure_steps)
    blocked_gaps = [step.gap_id for step in closure_steps if step.status != "ready_to_close_with_existing_artifact"]
    ready_gaps = [step.gap_id for step in closure_steps if step.status == "ready_to_close_with_existing_artifact"]

    if not gap_ids:
        overall_status = "no_gaps_detected_ready_for_expand004_dry_run_review"
    elif blocked_gaps:
        overall_status = "not_ready_missing_benchmark_evidence"
    else:
        overall_status = "ready_to_rerun_generic001_with_explicit_controls"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at or datetime.now(timezone.utc).isoformat(),
        "work_item": WORK_ITEM,
        "overall_status": overall_status,
        "input_path": input_path,
        "input_schema_version": generic001_report.get("schema_version"),
        "input_overall_status": generic001_report.get("overall_status"),
        "safety_boundary": no_mutation_boundary(),
        "mutation_counts": mutation_counts(),
        "interpretation_boundary": (
            "GENERIC-002 converts GENERIC-001 benchmark gaps into a closure plan. It may recommend explicit control "
            "metadata or a new review artifact, but it does not infer hidden truth, create candidates, write gates, "
            "activate connectors, mutate Bronze/Silver/Gold, change scheduler behavior, read the database, or perform external requests."
        ),
        "summary": {
            "gap_count": len(gap_ids),
            "ready_to_close_gap_count": len(ready_gaps),
            "blocked_gap_count": len(blocked_gaps),
            "candidate_count": _mapping(generic001_report.get("summary")).get("candidate_count"),
            "ready_to_close_gaps": ready_gaps,
            "blocked_gaps": blocked_gaps,
        },
        "closure_steps": [step.as_dict() for step in closure_steps],
        "rerun_command": cli,
        "next_action": build_next_action(overall_status, closure_steps),
    }


def build_rerun_command(closure_steps: Sequence[ClosureStep]) -> str | None:
    positive_keys = [step.candidate_key for step in closure_steps if step.gap_id == "positive_control_coverage" and step.candidate_key]
    negative_keys = [step.candidate_key for step in closure_steps if step.gap_id == "negative_control_coverage" and step.candidate_key]
    if not positive_keys and not negative_keys:
        return None
    parts = ["python", "scripts/run_generic001_pipeline_generics_proof_gate.py"]
    for key in positive_keys:
        parts.extend(["--positive-control-key", str(key)])
    for key in negative_keys:
        parts.extend(["--negative-control-key", str(key)])
    return " ".join(parts)


def build_next_action(overall_status: str, closure_steps: Sequence[ClosureStep]) -> str:
    if overall_status == "no_gaps_detected_ready_for_expand004_dry_run_review":
        return "GENERIC-001 has no benchmark gaps; proceed to EXPAND-004 dry-run design only, not broad apply."
    if overall_status == "ready_to_rerun_generic001_with_explicit_controls":
        return "Rerun GENERIC-001 with the explicit control keys recommended by this plan, then review the new proof report."
    missing = [step.gap_id for step in closure_steps if step.status != "ready_to_close_with_existing_artifact"]
    return (
        "Do not proceed to EXPAND-004, Wave Search scaling, scheduler changes, or TOP5 product claims yet. "
        f"Close missing benchmark evidence first: {', '.join(missing) or '<unknown>'}."
    )


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# GENERIC-002 Benchmark Gap Closure Plan",
        "",
        f"- overall_status: `{report.get('overall_status')}`",
        f"- generated_at_utc: `{report.get('generated_at_utc')}`",
        f"- input_path: `{report.get('input_path')}`",
        f"- input_overall_status: `{report.get('input_overall_status')}`",
        "",
        "## Safety boundary",
        "",
    ]
    for key, value in _mapping(report.get("safety_boundary")).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Summary", ""])
    summary = _mapping(report.get("summary"))
    for key in ["gap_count", "ready_to_close_gap_count", "blocked_gap_count", "ready_to_close_gaps", "blocked_gaps"]:
        lines.append(f"- {key}: `{summary.get(key)}`")
    lines.extend(["", "## Closure steps", ""])
    lines.append("| Gap | Status | Candidate | Required next step |")
    lines.append("|---|---|---|---|")
    for step in _mapping_list(report.get("closure_steps")):
        candidate = step.get("candidate_key") or "-"
        lines.append(
            f"| {step.get('gap_id')} | {step.get('status')} | {candidate} | {step.get('required_next_step')} |"
        )
        rationale = str(step.get("rationale") or "").strip()
        if rationale:
            lines.append(f"|  |  |  | {rationale} |")
    lines.extend(["", "## Recommended GENERIC-001 rerun command", ""])
    command = report.get("rerun_command")
    if command:
        lines.append(f"    {command}")
    else:
        lines.append("No rerun command can close the current gaps from existing artifacts alone.")
    lines.extend(["", "## Next action", "", str(report.get("next_action") or ""), ""])
    return "\n".join(lines)


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "generic002_benchmark_gap_closure_plan.json"
    md_path = output_dir / "generic002_benchmark_gap_closure_plan.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def _closure_step_for_gap(gap_id: str, candidate_rows: Sequence[Mapping[str, Any]]) -> ClosureStep:
    if gap_id == "positive_control_coverage":
        candidate = _best_positive_control_candidate(candidate_rows)
        if candidate:
            return ClosureStep(
                gap_id=gap_id,
                status="ready_to_close_with_existing_artifact",
                candidate_key=str(candidate.get("company_key")),
                candidate_name=str(candidate.get("company_name")),
                required_next_step="rerun_generic001_with_explicit_positive_control_key",
                rationale=(
                    "A strong-evidence candidate is present in the current benchmark. Marking it as an explicit "
                    "positive control is operator metadata, not a hidden inference."
                ),
            )
        return ClosureStep(
            gap_id=gap_id,
            status="blocked_missing_strong_control_candidate",
            required_next_step="add_or_review_at_least_one_known_good_strong_evidence_candidate",
            rationale="No strong detail/origin candidate exists in the current GENERIC-001 decision table.",
        )

    if gap_id == "negative_control_coverage":
        candidate = _best_negative_control_candidate(candidate_rows)
        if candidate:
            return ClosureStep(
                gap_id=gap_id,
                status="ready_to_close_with_existing_artifact",
                candidate_key=str(candidate.get("company_key")),
                candidate_name=str(candidate.get("company_name")),
                required_next_step="rerun_generic001_with_explicit_negative_control_key",
                rationale="A safe-stop candidate is present and can be used as an explicit negative control.",
            )
        return ClosureStep(
            gap_id=gap_id,
            status="blocked_missing_safe_negative_control",
            required_next_step="capture_or_select_one_known_blocked_or_safe_stop_control_candidate",
            rationale=(
                "Weak-only candidates are not enough for a negative control. The benchmark needs a known blocked or "
                "safe-stop case such as no actionable evidence, provider auth blocked, or probe error requiring review."
            ),
        )

    if gap_id == "no_actionable_evidence_coverage":
        candidate = _best_no_actionable_candidate(candidate_rows)
        if candidate:
            return ClosureStep(
                gap_id=gap_id,
                status="ready_to_close_with_existing_artifact",
                candidate_key=str(candidate.get("company_key")),
                candidate_name=str(candidate.get("company_name")),
                required_next_step="rerun_or_review_generic001_with_existing_no_actionable_candidate",
                rationale="A no-actionable-evidence case exists in the current benchmark and can validate safe stop behavior.",
            )
        return ClosureStep(
            gap_id=gap_id,
            status="blocked_missing_no_actionable_evidence_case",
            required_next_step="produce_one_no_actionable_evidence_review_artifact_before_expand004",
            rationale=(
                "GENERIC-001 must see at least one clean stop case; otherwise broad expansion may only be validated "
                "against positive/weak cases and miss stop behavior."
            ),
        )

    return ClosureStep(
        gap_id=gap_id,
        status="blocked_unknown_gap",
        required_next_step="inspect_generic001_gap_and_extend_generic002_mapping",
        rationale="GENERIC-002 does not yet have explicit handling for this gap id.",
    )


def _best_positive_control_candidate(candidate_rows: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    ranked = sorted(candidate_rows, key=_positive_control_sort_key)
    for row in ranked:
        if _text(row.get("evidence_strength")) in CONTROL_ELIGIBLE_EVIDENCE_STRENGTH:
            return row
    return None


def _best_negative_control_candidate(candidate_rows: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    for row in candidate_rows:
        if _text(row.get("review_action")) in SAFE_STOP_ACTIONS:
            return row
        dimensions = set(_string_list(row.get("generics_dimensions")))
        if "no_actionable_evidence_candidate" in dimensions:
            return row
    return None


def _best_no_actionable_candidate(candidate_rows: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    for row in candidate_rows:
        if _text(row.get("review_action")) in SAFE_STOP_ACTIONS:
            return row
        dimensions = set(_string_list(row.get("generics_dimensions")))
        if "no_actionable_evidence_candidate" in dimensions:
            return row
    return None


def _positive_control_sort_key(row: Mapping[str, Any]) -> tuple[int, int, str]:
    evidence_strength = _text(row.get("evidence_strength"))
    identity_risk = _text(row.get("identity_risk"))
    strength_rank = 0 if evidence_strength == "strong_detail" else 1 if evidence_strength == "strong_origin" else 2
    identity_rank = 0 if identity_risk == "normal_identity_risk" else 1
    return (strength_rank, identity_rank, _text(row.get("company_key")))


def _timestamp_from_parent(path: Path) -> str:
    prefix = "generic001_pipeline_generics_proof_gate_"
    parent = path.parent.name
    return parent.removeprefix(prefix) if parent.startswith(prefix) else ""


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _mapping_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray)):
        return []
    return [str(item) for item in value if str(item).strip()]


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""
