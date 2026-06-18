from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

SCHEMA_VERSION = "generic001.pipeline_generics_proof_gate.v1"
WORK_ITEM = "GENERIC-001 Pipeline Generics Proof Gate"
EXPAND003_SCHEMA_PREFIX = "expand003.candidate_review_delta_report"
SENSOR001H_SCHEMA_PREFIX = "sensor001h.ba_remote_post_activation_monitoring"
SENSOR001E_SCHEMA_PREFIX = "sensor001e.ba_remote_nationwide_bounded_sample_execution"

MIN_CANDIDATES = 8
MAX_RECOMMENDED_CANDIDATES = 12
MIN_STRONG_CANDIDATES = 4
MIN_WEAK_CANDIDATES = 3
MIN_AMBIGUOUS_IDENTITY_CANDIDATES = 2
MIN_PROVIDER_BACKED_CANDIDATES = 1
MIN_NO_ACTIONABLE_EVIDENCE_CANDIDATES = 1
MIN_POSITIVE_CONTROL_CANDIDATES = 1
MIN_NEGATIVE_CONTROL_CANDIDATES = 1

STRONG_EVIDENCE = frozenset({"strong_detail", "strong_origin"})
WEAK_EVIDENCE = frozenset({"weak_market_signal"})
NO_ACTION_REVIEW_ACTIONS = frozenset(
    {
        "no_useful_external_hint_no_candidate_creation",
        "provider_auth_failed_requires_key_review",
        "probe_error_requires_retry_or_review",
    }
)
PROVIDER_HOST_FRAGMENTS = frozenset(
    {
        "personio",
        "onlyfy",
        "workday",
        "greenhouse",
        "lever",
        "smartrecruiters",
        "zohorecruit",
        "successfactors",
        "ashbyhq",
        "bamboohr",
        "join.com",
        "recruitee",
        "softgarden",
        "talent-soft",
    }
)
CAREER_PATH_FRAGMENTS = frozenset({"career", "careers", "karriere", "jobs", "stellen", "stellenangebote"})
LEGAL_FORM_TOKENS = frozenset({"ag", "gmbh", "mbh", "se", "kg", "ohg", "ltd", "inc", "llc"})


@dataclass(frozen=True)
class CoverageCheck:
    check_id: str
    label: str
    observed_count: int
    required_count: int
    passed: bool
    evidence_keys: tuple[str, ...]
    notes: str

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence_keys"] = list(self.evidence_keys)
        return data


@dataclass(frozen=True)
class CandidateGenericsItem:
    company_key: str
    company_name: str
    review_action: str
    evidence_strength: str
    generics_dimensions: tuple[str, ...]
    identity_risk: str
    allowed_next_step: str
    blocked_next_steps: tuple[str, ...]
    human_review_required: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["generics_dimensions"] = list(self.generics_dimensions)
        data["blocked_next_steps"] = list(self.blocked_next_steps)
        return data


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


def load_expand003_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("EXPAND-003 input JSON root must be an object.")
    schema_version = str(payload.get("schema_version") or "")
    if not schema_version.startswith(EXPAND003_SCHEMA_PREFIX):
        raise ValueError(f"Unexpected EXPAND-003 schema_version: {schema_version or '<missing>'}")
    return payload


def load_optional_sensor_report(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Sensor input JSON root must be an object.")
    schema_version = str(payload.get("schema_version") or "")
    if not (
        schema_version.startswith(SENSOR001H_SCHEMA_PREFIX)
        or schema_version.startswith(SENSOR001E_SCHEMA_PREFIX)
    ):
        raise ValueError(f"Unexpected sensor schema_version: {schema_version or '<missing>'}")
    return payload


def _expand003_export_sort_key(path: Path) -> tuple[str, float, str]:
    parent_name = path.parent.name
    timestamp = ""
    prefix = "expand003_candidate_review_delta_report_"
    if parent_name.startswith(prefix):
        timestamp = parent_name.removeprefix(prefix)
    return (timestamp, path.stat().st_mtime, str(path))


def find_latest_expand003_report(exports_dir: Path = Path("exports")) -> Path | None:
    candidates = [
        path
        for path in exports_dir.glob("expand003_candidate_review_delta_report*/expand003_candidate_review_delta_report.json")
        if path.is_file()
    ]
    default = exports_dir / "expand003_candidate_review_delta_report" / "expand003_candidate_review_delta_report.json"
    if default.exists() and default not in candidates:
        candidates.append(default)
    if not candidates:
        return None
    return max(candidates, key=_expand003_export_sort_key)


def find_latest_sensor_report(exports_dir: Path = Path("exports")) -> Path | None:
    patterns = [
        "sensor001h_ba_remote_post_activation_monitoring_*.json",
        "sensor001e_ba_remote_bounded_sample_execution_*.json",
    ]
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(path for path in exports_dir.glob(pattern) if path.is_file())
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def build_generic_pipeline_proof_report(
    expand003_report: Mapping[str, Any],
    *,
    expand003_path: str | None = None,
    sensor_report: Mapping[str, Any] | None = None,
    sensor_path: str | None = None,
    positive_control_keys: Sequence[str] = (),
    negative_control_keys: Sequence[str] = (),
    generated_at: str | None = None,
) -> dict[str, Any]:
    candidate_items = [_mapping(row) for row in _mapping_list(expand003_report.get("candidate_review_items"))]
    generics_items = build_candidate_generics_items(candidate_items, positive_control_keys, negative_control_keys)
    coverage_checks = build_coverage_checks(generics_items)
    gap_ids = [check.check_id for check in coverage_checks if not check.passed]
    summary = build_summary(generics_items, coverage_checks, sensor_report)

    if not candidate_items:
        overall_status = "input_missing_or_empty"
    elif gap_ids:
        overall_status = "not_passed_needs_benchmark_gap_closure"
    else:
        overall_status = "passed_review_artifact_only"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at or datetime.now(timezone.utc).isoformat(),
        "work_item": WORK_ITEM,
        "overall_status": overall_status,
        "input_path": expand003_path,
        "input_schema_version": expand003_report.get("schema_version"),
        "input_generated_at_utc": expand003_report.get("generated_at_utc"),
        "sensor_input_path": sensor_path,
        "sensor_schema_version": sensor_report.get("schema_version") if isinstance(sensor_report, Mapping) else None,
        "safety_boundary": no_mutation_boundary(),
        "mutation_counts": mutation_counts(),
        "interpretation_boundary": (
            "GENERIC-001 is a proof gate over existing review artifacts. It checks whether the current benchmark is broad "
            "and explainable enough for later controlled candidate creation or wave-search work. It does not create "
            "candidates, write gate decisions, activate connectors, mutate Bronze/Silver/Gold, change scheduler behavior, "
            "read the database, or perform external requests."
        ),
        "benchmark_requirements": benchmark_requirements(),
        "summary": summary,
        "coverage_checks": [check.as_dict() for check in coverage_checks],
        "candidate_decision_table": [item.as_dict() for item in generics_items],
        "gap_ids": gap_ids,
        "generic_gaps_discovered": build_gap_notes(coverage_checks),
        "follow_up_recommendations": build_follow_up_recommendations(coverage_checks, summary),
        "next_action": build_next_action(overall_status, gap_ids),
    }


def benchmark_requirements() -> dict[str, int | str]:
    return {
        "candidate_count_min": MIN_CANDIDATES,
        "candidate_count_recommended_max": MAX_RECOMMENDED_CANDIDATES,
        "strong_candidate_count_min": MIN_STRONG_CANDIDATES,
        "weak_candidate_count_min": MIN_WEAK_CANDIDATES,
        "ambiguous_identity_candidate_count_min": MIN_AMBIGUOUS_IDENTITY_CANDIDATES,
        "provider_backed_candidate_count_min": MIN_PROVIDER_BACKED_CANDIDATES,
        "no_actionable_evidence_candidate_count_min": MIN_NO_ACTIONABLE_EVIDENCE_CANDIDATES,
        "positive_control_candidate_count_min": MIN_POSITIVE_CONTROL_CANDIDATES,
        "negative_control_candidate_count_min": MIN_NEGATIVE_CONTROL_CANDIDATES,
        "operator_control_note": "Positive/negative controls must be explicit benchmark metadata or CLI arguments, not inferred silently.",
    }


def build_candidate_generics_items(
    candidate_items: Sequence[Mapping[str, Any]],
    positive_control_keys: Sequence[str] = (),
    negative_control_keys: Sequence[str] = (),
) -> list[CandidateGenericsItem]:
    positive_controls = {key.strip().lower() for key in positive_control_keys if key.strip()}
    negative_controls = {key.strip().lower() for key in negative_control_keys if key.strip()}
    items: list[CandidateGenericsItem] = []
    for row in candidate_items:
        company_key = _text(row.get("company_key"), default="unknown_company")
        company_name = _text(row.get("company_name"), default=company_key)
        review_action = _text(row.get("review_action"), default="unknown_review_action")
        evidence_strength = _text(row.get("evidence_strength"), default="unknown_evidence_strength")
        strong_urls = _string_list(row.get("top_strong_urls"))
        weak_urls = _string_list(row.get("top_weak_urls"))
        dimensions = _candidate_dimensions(
            company_key=company_key,
            company_name=company_name,
            review_action=review_action,
            evidence_strength=evidence_strength,
            strong_urls=strong_urls,
            weak_urls=weak_urls,
            positive_controls=positive_controls,
            negative_controls=negative_controls,
        )
        identity_risk = _identity_risk(company_key, company_name, strong_urls)
        allowed_next_step = _allowed_next_step(review_action, evidence_strength)
        blocked_next_steps = _blocked_next_steps(review_action, evidence_strength)
        items.append(
            CandidateGenericsItem(
                company_key=company_key,
                company_name=company_name,
                review_action=review_action,
                evidence_strength=evidence_strength,
                generics_dimensions=tuple(dimensions),
                identity_risk=identity_risk,
                allowed_next_step=allowed_next_step,
                blocked_next_steps=blocked_next_steps,
                human_review_required=True,
                reason=_reason(review_action, evidence_strength, dimensions),
            )
        )
    return sorted(items, key=lambda item: (item.company_name.lower(), item.company_key))


def build_coverage_checks(items: Sequence[CandidateGenericsItem]) -> list[CoverageCheck]:
    by_dimension: dict[str, list[str]] = {}
    for item in items:
        for dimension in item.generics_dimensions:
            by_dimension.setdefault(dimension, []).append(item.company_key)

    def check(check_id: str, label: str, dimension: str, required: int, notes: str) -> CoverageCheck:
        keys = tuple(sorted(set(by_dimension.get(dimension, []))))
        return CoverageCheck(
            check_id=check_id,
            label=label,
            observed_count=len(keys),
            required_count=required,
            passed=len(keys) >= required,
            evidence_keys=keys,
            notes=notes,
        )

    candidate_keys = tuple(sorted({item.company_key for item in items}))
    checks = [
        CoverageCheck(
            check_id="benchmark_candidate_count",
            label="8 to 12 reviewed benchmark candidates",
            observed_count=len(candidate_keys),
            required_count=MIN_CANDIDATES,
            passed=MIN_CANDIDATES <= len(candidate_keys) <= MAX_RECOMMENDED_CANDIDATES,
            evidence_keys=candidate_keys,
            notes="The initial proof gate should stay small and controlled, not broad production-like throughput.",
        ),
        check(
            "strong_candidate_count",
            "At least four strong candidates",
            "strong_evidence_candidate",
            MIN_STRONG_CANDIDATES,
            "Strong includes strong_detail and strong_origin review outcomes from EXPAND-003.",
        ),
        check(
            "weak_candidate_count",
            "At least three weak/noise candidates",
            "weak_only_candidate",
            MIN_WEAK_CANDIDATES,
            "Weak-only candidates test whether the pipeline can stop without creating candidates from aggregator/market hints.",
        ),
        check(
            "clear_career_origin_coverage",
            "Employer-origin site with career/jobs domain/path",
            "clear_career_origin",
            1,
            "Evidence should include at least one company-origin career/jobs URL.",
        ),
        check(
            "provider_backed_origin_coverage",
            "ATS/provider-backed origin URL",
            "provider_backed_origin",
            MIN_PROVIDER_BACKED_CANDIDATES,
            "Provider-backed evidence covers systems such as Personio, Onlyfy, Workday, Greenhouse, Lever, ZohoRecruit, SmartRecruiters and similar.",
        ),
        check(
            "ambiguous_identity_coverage",
            "Acronym / alias / identity-risk candidates",
            "ambiguous_identity_candidate",
            MIN_AMBIGUOUS_IDENTITY_CANDIDATES,
            "Identity-risk candidates test false-positive handling for acronyms, aliases, numeric names, generic names or mismatched evidence.",
        ),
        check(
            "no_actionable_evidence_coverage",
            "Candidate with no actionable evidence",
            "no_actionable_evidence_candidate",
            MIN_NO_ACTIONABLE_EVIDENCE_CANDIDATES,
            "The benchmark must include at least one clean stop/no-evidence case.",
        ),
        check(
            "positive_control_coverage",
            "Known positive control candidate",
            "positive_control_candidate",
            MIN_POSITIVE_CONTROL_CANDIDATES,
            "Positive controls must be explicit benchmark inputs, not inferred from company names.",
        ),
        check(
            "negative_control_coverage",
            "Known stopped/blocked negative control candidate",
            "negative_control_candidate",
            MIN_NEGATIVE_CONTROL_CANDIDATES,
            "Negative controls must be explicit benchmark inputs, not inferred silently.",
        ),
    ]
    return checks


def build_summary(
    items: Sequence[CandidateGenericsItem],
    coverage_checks: Sequence[CoverageCheck],
    sensor_report: Mapping[str, Any] | None,
) -> dict[str, Any]:
    dimension_counter: Counter[str] = Counter()
    action_counter: Counter[str] = Counter()
    evidence_counter: Counter[str] = Counter()
    identity_counter: Counter[str] = Counter()
    for item in items:
        action_counter[item.review_action] += 1
        evidence_counter[item.evidence_strength] += 1
        identity_counter[item.identity_risk] += 1
        dimension_counter.update(item.generics_dimensions)

    failed_checks = [check.check_id for check in coverage_checks if not check.passed]
    sensor_summary = _sensor_summary(sensor_report)
    return {
        "candidate_count": len(items),
        "passed_check_count": sum(1 for check in coverage_checks if check.passed),
        "failed_check_count": len(failed_checks),
        "failed_checks": failed_checks,
        "dimension_counts": dict(sorted(dimension_counter.items())),
        "review_action_counts": dict(sorted(action_counter.items())),
        "evidence_strength_counts": dict(sorted(evidence_counter.items())),
        "identity_risk_counts": dict(sorted(identity_counter.items())),
        "mutation_counts": mutation_counts(),
        "source_sensor_context": sensor_summary,
    }


def build_gap_notes(coverage_checks: Sequence[CoverageCheck]) -> list[str]:
    notes: list[str] = []
    for check in coverage_checks:
        if check.passed:
            continue
        notes.append(
            f"{check.check_id}: observed {check.observed_count}, required {check.required_count}. {check.notes}"
        )
    return notes


def build_follow_up_recommendations(coverage_checks: Sequence[CoverageCheck], summary: Mapping[str, Any]) -> list[str]:
    failed = {check.check_id for check in coverage_checks if not check.passed}
    recommendations: list[str] = []
    if "no_actionable_evidence_coverage" in failed:
        recommendations.append("Add at least one clean no-actionable-evidence candidate to the next benchmark before broad candidate apply.")
    if "positive_control_coverage" in failed or "negative_control_coverage" in failed:
        recommendations.append("Provide explicit positive and negative control candidate keys via benchmark metadata or CLI arguments; do not infer controls silently.")
    if "ambiguous_identity_coverage" in failed:
        recommendations.append("Add or retain acronym/alias/identity-risk companies and verify that explanations distinguish identity uncertainty from evidence strength.")
    if "provider_backed_origin_coverage" in failed:
        recommendations.append("Include at least one ATS/provider-backed origin URL candidate such as Personio, Onlyfy, Workday, Greenhouse, Lever or ZohoRecruit.")
    if "strong_candidate_count" in failed:
        recommendations.append("Run another controlled evidence review only for the benchmark, not broad candidate throughput, until at least four strong candidates are present.")
    if "weak_candidate_count" in failed:
        recommendations.append("Keep weak-only/noise candidates in the proof set so stop behavior is validated, not only success paths.")
    sensor = summary.get("source_sensor_context") if isinstance(summary, Mapping) else None
    if isinstance(sensor, Mapping) and sensor.get("status") == "available_with_failures":
        recommendations.append("Review BA remote/nationwide source failures before using it as a production-like market sensor input.")
    if not recommendations:
        recommendations.append("GENERIC-001 benchmark coverage is sufficient for a separate controlled candidate creation dry-run; still keep apply/write steps separate.")
    return recommendations


def build_next_action(overall_status: str, gap_ids: Sequence[str]) -> str:
    if overall_status == "passed_review_artifact_only":
        return "Proceed to EXPAND-004 Controlled Candidate Creation Dry-Run as a separate no-write or explicit-write-gated work item."
    if "positive_control_coverage" in gap_ids or "negative_control_coverage" in gap_ids:
        return "Close explicit benchmark-control gaps first, then rerun GENERIC-001 before any candidate apply or wave-search scaling."
    if gap_ids:
        return "Expand or rebalance the benchmark set to close GENERIC-001 gaps, then rerun the proof gate."
    return "Provide a non-empty EXPAND-003 candidate review report."


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# GENERIC-001 Pipeline Generics Proof Gate",
        "",
        f"- overall_status: `{report.get('overall_status')}`",
        f"- generated_at_utc: `{report.get('generated_at_utc')}`",
        f"- input_path: `{report.get('input_path')}`",
        f"- sensor_input_path: `{report.get('sensor_input_path')}`",
        "",
        "## Safety boundary",
        "",
    ]
    for key, value in _mapping(report.get("safety_boundary")).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Summary", ""])
    summary = _mapping(report.get("summary"))
    for key in ["candidate_count", "passed_check_count", "failed_check_count", "failed_checks"]:
        lines.append(f"- {key}: `{summary.get(key)}`")
    lines.extend(["", "### Dimension counts", ""])
    for key, value in _mapping(summary.get("dimension_counts")).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Coverage checks", ""])
    lines.append("| Check | Observed | Required | Status | Evidence keys |")
    lines.append("|---|---:|---:|---|---|")
    for check in _mapping_list(report.get("coverage_checks")):
        status = "pass" if check.get("passed") else "gap"
        keys = ", ".join(_string_list(check.get("evidence_keys"))) or "-"
        lines.append(
            f"| {check.get('check_id')} | {check.get('observed_count')} | {check.get('required_count')} | {status} | {keys} |"
        )
    lines.extend(["", "## Candidate decision table", ""])
    lines.append("| Company | Evidence | Identity risk | Dimensions | Allowed next step | Blocked next steps |")
    lines.append("|---|---|---|---|---|---|")
    for item in _mapping_list(report.get("candidate_decision_table")):
        dimensions = ", ".join(_string_list(item.get("generics_dimensions"))) or "-"
        blocked = ", ".join(_string_list(item.get("blocked_next_steps"))) or "-"
        lines.append(
            f"| {item.get('company_name')} | {item.get('evidence_strength')} | {item.get('identity_risk')} | {dimensions} | {item.get('allowed_next_step')} | {blocked} |"
        )
    lines.extend(["", "## Generic gaps discovered", ""])
    gaps = _string_list(report.get("generic_gaps_discovered"))
    if gaps:
        for gap in gaps:
            lines.append(f"- {gap}")
    else:
        lines.append("- No generic benchmark coverage gaps detected by this review artifact.")
    lines.extend(["", "## Follow-up recommendations", ""])
    for recommendation in _string_list(report.get("follow_up_recommendations")):
        lines.append(f"- {recommendation}")
    lines.extend(["", "## Next action", "", str(report.get("next_action") or "")])
    lines.append("")
    return "\n".join(lines)


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "generic001_pipeline_generics_proof_gate.json"
    csv_path = output_dir / "generic001_pipeline_generics_candidate_decision_table.csv"
    md_path = output_dir / "generic001_pipeline_generics_proof_gate.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    write_candidate_decision_csv(csv_path, _mapping_list(report.get("candidate_decision_table")))
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "csv": str(csv_path), "markdown": str(md_path)}


def write_candidate_decision_csv(path: Path, items: Sequence[Mapping[str, Any]]) -> None:
    fieldnames = [
        "company_key",
        "company_name",
        "review_action",
        "evidence_strength",
        "identity_risk",
        "generics_dimensions",
        "allowed_next_step",
        "blocked_next_steps",
        "human_review_required",
        "reason",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            row = {key: item.get(key) for key in fieldnames}
            row["generics_dimensions"] = ";".join(_string_list(item.get("generics_dimensions")))
            row["blocked_next_steps"] = ";".join(_string_list(item.get("blocked_next_steps")))
            writer.writerow(row)


def _candidate_dimensions(
    *,
    company_key: str,
    company_name: str,
    review_action: str,
    evidence_strength: str,
    strong_urls: Sequence[str],
    weak_urls: Sequence[str],
    positive_controls: set[str],
    negative_controls: set[str],
) -> list[str]:
    dimensions: list[str] = []
    if evidence_strength in STRONG_EVIDENCE:
        dimensions.append("strong_evidence_candidate")
    if evidence_strength in WEAK_EVIDENCE:
        dimensions.append("weak_only_candidate")
    if review_action in NO_ACTION_REVIEW_ACTIONS:
        dimensions.append("no_actionable_evidence_candidate")
    if company_key.lower() in positive_controls:
        dimensions.append("positive_control_candidate")
    if company_key.lower() in negative_controls:
        dimensions.append("negative_control_candidate")
    if _is_ambiguous_identity(company_key, company_name, list(strong_urls)):
        dimensions.append("ambiguous_identity_candidate")
    if any(_is_provider_url(url) for url in strong_urls):
        dimensions.append("provider_backed_origin")
    if any(_is_career_origin_url(url) for url in strong_urls):
        dimensions.append("clear_career_origin")
    if strong_urls and any(_is_company_host_signal(company_name, url) for url in strong_urls):
        dimensions.append("company_specific_origin_or_detail")
    return sorted(set(dimensions))


def _identity_risk(company_key: str, company_name: str, urls: Sequence[str]) -> str:
    if _is_ambiguous_identity(company_key, company_name, urls):
        return "identity_review_required"
    return "normal_identity_risk"


def _is_ambiguous_identity(company_key: str, company_name: str, urls: Sequence[str]) -> bool:
    normalized_key = company_key.replace("_", "").replace("-", "").lower()
    name = company_name.strip()
    tokens = [token.strip(".,()[]{}") for token in name.replace("-", " ").split()]
    uppercase_tokens = [
        token
        for token in tokens
        if len(token) >= 2 and token.isupper() and token.lower() not in LEGAL_FORM_TOKENS
    ]
    has_parenthetical_alias = "(" in name and ")" in name
    starts_with_digit = bool(name[:1].isdigit() or company_key[:1].isdigit())
    short_or_generic_key = len(normalized_key) <= 5 or normalized_key in {"bge", "etl", "apo", "cancom"}
    url_mismatch_signal = False
    for url in urls[:5]:
        host = urlparse(url).netloc.lower()
        if _is_provider_url(url):
            continue
        if host and normalized_key and normalized_key not in host.replace("-", "").replace(".", ""):
            if any(fragment in host for fragment in ("linkedin", "stepstone", "glassdoor", "xing", "dailyremote", "arbeitnow")):
                url_mismatch_signal = True
    return has_parenthetical_alias or starts_with_digit or len(uppercase_tokens) >= 1 or short_or_generic_key or url_mismatch_signal


def _is_provider_url(url: str) -> bool:
    lowered = url.lower()
    return any(fragment in lowered for fragment in PROVIDER_HOST_FRAGMENTS)


def _is_career_origin_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if not host:
        return False
    return any(fragment in host or fragment in path for fragment in CAREER_PATH_FRAGMENTS)


def _is_company_host_signal(company_name: str, url: str) -> bool:
    company_tokens = [
        token.lower().strip(".,()[]{}")
        for token in company_name.replace("-", " ").split()
        if len(token.strip(".,()[]{}")) >= 4
    ]
    host = urlparse(url).netloc.lower().replace("-", "").replace(".", "")
    return any(token.replace("ü", "u").replace("ä", "a").replace("ö", "o") in host for token in company_tokens)


def _allowed_next_step(review_action: str, evidence_strength: str) -> str:
    if evidence_strength == "strong_detail":
        return "human_evidence_review_then_possible_dry_run_candidate_creation"
    if evidence_strength == "strong_origin":
        return "human_origin_review_or_detail_followup"
    if review_action in NO_ACTION_REVIEW_ACTIONS:
        return "stop_or_retry_review_only"
    if evidence_strength == "weak_market_signal":
        return "weak_signal_review_only_no_candidate_creation"
    return "human_review_required_before_any_next_step"


def _blocked_next_steps(review_action: str, evidence_strength: str) -> tuple[str, ...]:
    blocked = [
        "automatic_candidate_creation",
        "automatic_gate_decision",
        "connector_activation",
        "scheduler_change",
        "bronze_silver_gold_mutation",
    ]
    if evidence_strength != "strong_detail":
        blocked.append("candidate_creation_without_new_evidence")
    if review_action in NO_ACTION_REVIEW_ACTIONS or evidence_strength == "weak_market_signal":
        blocked.append("candidate_creation_from_current_evidence")
    return tuple(blocked)


def _reason(review_action: str, evidence_strength: str, dimensions: Sequence[str]) -> str:
    if "positive_control_candidate" in dimensions or "negative_control_candidate" in dimensions:
        return "Explicit benchmark control; use for proof calibration only."
    if evidence_strength == "strong_detail":
        return "Strong detail evidence exists, but this proof gate still requires human review before any apply step."
    if evidence_strength == "strong_origin":
        return "Strong origin evidence exists; detail/job evidence remains a separate follow-up before candidate creation."
    if evidence_strength == "weak_market_signal":
        return "Only weak market or aggregator evidence is present; stop behavior is being validated."
    if review_action in NO_ACTION_REVIEW_ACTIONS:
        return "No actionable evidence or a blocking probe condition is present; this validates safe stop behavior."
    return "Review action is not recognized as sufficient for automated decisions; keep human review boundary."


def _sensor_summary(sensor_report: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(sensor_report, Mapping):
        return {"status": "not_provided"}
    metric_summary = _mapping(sensor_report.get("metric_summary"))
    failed_run_count = int(metric_summary.get("failed_run_count") or 0)
    status = "available_with_failures" if failed_run_count else "available_no_failures_observed"
    return {
        "status": status,
        "schema_version": sensor_report.get("schema_version"),
        "overall_status": sensor_report.get("overall_status"),
        "source_status": sensor_report.get("source_status"),
        "ingestion_run_count": metric_summary.get("ingestion_run_count"),
        "total_loaded": metric_summary.get("total_loaded"),
        "inserted_count": metric_summary.get("inserted_count"),
        "duplicate_count": metric_summary.get("duplicate_count"),
        "failed_run_count": failed_run_count,
        "observed_terms": metric_summary.get("observed_terms"),
        "duplicate_count_by_provenance": metric_summary.get("duplicate_count_by_provenance"),
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _mapping_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [dict(row) for row in value if isinstance(row, Mapping)]


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray)):
        return []
    return [str(item) for item in value if str(item).strip()]


def _text(value: Any, *, default: str = "") -> str:
    text = str(value).strip() if value is not None else ""
    return text or default
