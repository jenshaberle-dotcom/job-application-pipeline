from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "expand003.candidate_review_delta_report.v1"
WORK_ITEM = "EXPAND-003 Result Interpretation / Candidate Review Delta Report"
INPUT_SCHEMA_PREFIX = "expand002.controlled_external_probe_trial_run"
NO_MUTATION_BOUNDARY = (
    "result_interpretation_review_artifact_only_no_candidate_creation_no_gate_decision_no_connector_activation"
)

STRONG_URL_CLASSES = frozenset(
    {
        "company_origin_or_career_url",
        "company_specific_job_detail_url",
        "origin_provider_url",
    }
)
DETAIL_URL_CLASSES = frozenset({"company_specific_job_detail_url"})
ORIGIN_URL_CLASSES = frozenset({"company_origin_or_career_url", "origin_provider_url"})
WEAK_URL_CLASSES = frozenset({"aggregator_or_market_url"})
GENERIC_URL_CLASSES = frozenset({"unrelated_or_generic_url"})

READY_ACTION = "ready_for_human_evidence_review"
DETAIL_FOLLOWUP_ACTION = "ready_for_detail_followup_review"
WEAK_ACTION = "weak_external_hint_no_candidate_creation"
NO_ACTION = "no_useful_external_hint_no_candidate_creation"
AUTH_ACTION = "provider_auth_failed_requires_key_review"
ERROR_ACTION = "probe_error_requires_retry_or_review"


@dataclass(frozen=True)
class CandidateReviewItem:
    trial_id: str
    company_key: str
    company_name: str
    review_action: str
    review_priority: int
    evidence_strength: str
    reason: str
    strong_url_count: int
    weak_url_count: int
    generic_url_count: int
    company_origin_or_career_url_count: int
    company_specific_job_detail_url_count: int
    origin_provider_url_count: int
    top_strong_urls: tuple[str, ...]
    top_weak_urls: tuple[str, ...]
    evidence_hints: dict[str, int]
    candidate_creation_allowed_by_this_report: bool = False
    gate_decision_allowed_by_this_report: bool = False
    connector_activation_allowed_by_this_report: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["top_strong_urls"] = list(self.top_strong_urls)
        data["top_weak_urls"] = list(self.top_weak_urls)
        return data


def no_mutation_boundary() -> dict[str, bool]:
    return {
        "read_only_artifact_run": True,
        "database_writes": False,
        "pipeline_mutation": False,
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
    }


def load_expand002_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Input JSON root must be an object.")
    schema_version = str(payload.get("schema_version") or "")
    if not schema_version.startswith(INPUT_SCHEMA_PREFIX):
        raise ValueError(f"Unexpected input schema_version: {schema_version or '<missing>'}")
    return payload


def find_latest_expand002_report(exports_dir: Path = Path("exports")) -> Path | None:
    candidates: list[Path] = []
    candidates.extend(exports_dir.glob("expand002_controlled_external_probe_trial_run_*/expand002_controlled_external_probe_trial_run.json"))
    default = exports_dir / "expand002_controlled_external_probe_trial_run" / "expand002_controlled_external_probe_trial_run.json"
    if default.exists():
        candidates.append(default)
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def build_candidate_review_delta_report(
    expand002_report: Mapping[str, Any],
    *,
    input_path: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    probe_results = _mapping_list(expand002_report.get("probe_results"))
    candidate_items = build_candidate_review_items(probe_results)
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at or datetime.now(timezone.utc).isoformat(),
        "work_item": WORK_ITEM,
        "input_path": input_path,
        "input_schema_version": expand002_report.get("schema_version"),
        "input_generated_at_utc": expand002_report.get("generated_at_utc"),
        "safety_boundary": no_mutation_boundary(),
        "interpretation_boundary": (
            "This report interprets EXPAND-002 external probe review artifacts. It ranks candidates for human review only. "
            "It never creates candidates, writes gate decisions, activates connectors, mutates Bronze/Silver/Gold, "
            "writes database state, or changes scheduler behavior. Strong evidence means review priority, not gate truth."
        ),
        "mutation_counts": mutation_counts(),
        "input_summary": dict(expand002_report.get("summary", {})) if isinstance(expand002_report.get("summary"), Mapping) else {},
        "summary": build_summary(candidate_items),
        "candidate_review_items": [item.as_dict() for item in candidate_items],
    }
    return report


def build_candidate_review_items(probe_results: Sequence[Mapping[str, Any]]) -> list[CandidateReviewItem]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in probe_results:
        trial_id = _text(row.get("trial_id"), default="unknown_trial")
        grouped[trial_id].append(row)

    items: list[CandidateReviewItem] = []
    for trial_id, rows in grouped.items():
        first = rows[0]
        evidence_hints = Counter(_text(row.get("evidence_hint"), default="unknown") for row in rows)
        class_counter: Counter[str] = Counter()
        strong_urls: list[str] = []
        weak_urls: list[str] = []
        for row in rows:
            urls = _string_list(row.get("urls"))
            classes = _string_list(row.get("url_evidence_classes"))
            for url, url_class in zip(urls, classes):
                class_counter[url_class] += 1
                if url_class in STRONG_URL_CLASSES:
                    strong_urls.append(url)
                elif url_class in WEAK_URL_CLASSES:
                    weak_urls.append(url)

        has_auth_failure = any(hint in {"provider_auth_failed_requires_key_review", "blocked_after_provider_auth_failure"} for hint in evidence_hints)
        has_request_failure = any(_text(row.get("status"), default="") == "request_failed" for row in rows)
        detail_count = sum(class_counter[item] for item in DETAIL_URL_CLASSES)
        origin_count = class_counter["company_origin_or_career_url"]
        provider_count = class_counter["origin_provider_url"]
        strong_count = sum(class_counter[item] for item in STRONG_URL_CLASSES)
        weak_count = sum(class_counter[item] for item in WEAK_URL_CLASSES)
        generic_count = sum(class_counter[item] for item in GENERIC_URL_CLASSES)

        if has_auth_failure:
            review_action = AUTH_ACTION
            review_priority = 90
            evidence_strength = "blocked"
            reason = "Provider authentication failure prevents evidence interpretation; review provider configuration before retry."
        elif has_request_failure:
            review_action = ERROR_ACTION
            review_priority = 80
            evidence_strength = "error"
            reason = "At least one probe failed; retry or inspect before any candidate decision."
        elif detail_count > 0:
            review_action = READY_ACTION
            review_priority = 10
            evidence_strength = "strong_detail"
            reason = "Company-specific job/detail evidence exists; route to human evidence review only."
        elif origin_count + provider_count > 0:
            review_action = DETAIL_FOLLOWUP_ACTION
            review_priority = 20
            evidence_strength = "strong_origin"
            reason = "Company-origin or recruiting-provider evidence exists, but detail/job evidence still needs human review or follow-up."
        elif weak_count > 0:
            review_action = WEAK_ACTION
            review_priority = 60
            evidence_strength = "weak_market_signal"
            reason = "Only weak market/aggregator evidence was found; do not create candidate from this report."
        else:
            review_action = NO_ACTION
            review_priority = 70
            evidence_strength = "none"
            reason = "No useful external evidence was found; keep as no-action review artifact."

        items.append(
            CandidateReviewItem(
                trial_id=trial_id,
                company_key=_text(first.get("company_key"), default="unknown_company"),
                company_name=_text(first.get("company_name"), default=_text(first.get("company_key"), default="unknown_company")),
                review_action=review_action,
                review_priority=review_priority,
                evidence_strength=evidence_strength,
                reason=reason,
                strong_url_count=strong_count,
                weak_url_count=weak_count,
                generic_url_count=generic_count,
                company_origin_or_career_url_count=origin_count,
                company_specific_job_detail_url_count=detail_count,
                origin_provider_url_count=provider_count,
                top_strong_urls=tuple(_dedupe(strong_urls)[:5]),
                top_weak_urls=tuple(_dedupe(weak_urls)[:5]),
                evidence_hints=dict(sorted(evidence_hints.items())),
            )
        )

    return sorted(items, key=lambda item: (item.review_priority, item.company_name.lower(), item.company_key))


def build_summary(items: Sequence[CandidateReviewItem]) -> dict[str, Any]:
    action_counts = Counter(item.review_action for item in items)
    return {
        "candidate_count": len(items),
        "ready_for_human_evidence_review_count": action_counts[READY_ACTION],
        "ready_for_detail_followup_review_count": action_counts[DETAIL_FOLLOWUP_ACTION],
        "weak_external_hint_no_candidate_creation_count": action_counts[WEAK_ACTION],
        "no_useful_external_hint_no_candidate_creation_count": action_counts[NO_ACTION],
        "provider_auth_failed_requires_key_review_count": action_counts[AUTH_ACTION],
        "probe_error_requires_retry_or_review_count": action_counts[ERROR_ACTION],
        "strong_url_count": sum(item.strong_url_count for item in items),
        "weak_url_count": sum(item.weak_url_count for item in items),
        "generic_url_count": sum(item.generic_url_count for item in items),
        "candidate_creation_count": 0,
        "gate_decision_count": 0,
        "connector_activation_count": 0,
        "database_write_count": 0,
    }


def write_outputs(report: Mapping[str, Any], export_dir: Path) -> dict[str, str]:
    export_dir.mkdir(parents=True, exist_ok=True)
    json_path = export_dir / "expand003_candidate_review_delta_report.json"
    csv_path = export_dir / "expand003_candidate_review_delta_report.csv"
    md_path = export_dir / "expand003_candidate_review_delta_report.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    write_candidate_review_csv(csv_path, _mapping_list(report.get("candidate_review_items")))
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "csv": str(csv_path), "markdown": str(md_path)}


def write_candidate_review_csv(path: Path, items: Sequence[Mapping[str, Any]]) -> None:
    fieldnames = [
        "review_priority",
        "company_name",
        "company_key",
        "review_action",
        "evidence_strength",
        "strong_url_count",
        "weak_url_count",
        "generic_url_count",
        "company_origin_or_career_url_count",
        "company_specific_job_detail_url_count",
        "origin_provider_url_count",
        "top_strong_urls",
        "top_weak_urls",
        "reason",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            writer.writerow(
                {
                    key: "; ".join(str(v) for v in item.get(key, []))
                    if key in {"top_strong_urls", "top_weak_urls"} and isinstance(item.get(key), list)
                    else item.get(key, "")
                    for key in fieldnames
                }
            )


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {}) if isinstance(report.get("summary"), Mapping) else {}
    items = _mapping_list(report.get("candidate_review_items"))
    lines: list[str] = []
    lines.append("# EXPAND-003 Candidate Review Delta Report")
    lines.append("")
    lines.append("## Boundary")
    lines.append("")
    lines.append(
        "Review artifact only. This report does not create candidates, write gate decisions, activate connectors, "
        "mutate Bronze/Silver/Gold, write DB state, or change scheduler behavior."
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    for key in [
        "candidate_count",
        "ready_for_human_evidence_review_count",
        "ready_for_detail_followup_review_count",
        "weak_external_hint_no_candidate_creation_count",
        "no_useful_external_hint_no_candidate_creation_count",
        "strong_url_count",
        "weak_url_count",
        "generic_url_count",
        "candidate_creation_count",
        "gate_decision_count",
        "connector_activation_count",
        "database_write_count",
    ]:
        lines.append(f"- {key}: {summary.get(key, 0)}")
    lines.append("")
    lines.append("## Candidate Review Queue")
    lines.append("")
    if not items:
        lines.append("No candidate review items available.")
    else:
        lines.append("| Priority | Company | Action | Evidence | Strong URLs | Weak URLs | Reason |")
        lines.append("| ---: | --- | --- | --- | ---: | ---: | --- |")
        for item in items:
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(item.get("review_priority", "")),
                        _md_cell(item.get("company_name")),
                        _md_cell(item.get("review_action")),
                        _md_cell(item.get("evidence_strength")),
                        str(item.get("strong_url_count", 0)),
                        str(item.get("weak_url_count", 0)),
                        _md_cell(item.get("reason")),
                    ]
                )
                + " |"
            )
    lines.append("")
    lines.append("## Strong Evidence URLs")
    lines.append("")
    for item in items:
        urls = _string_list(item.get("top_strong_urls"))
        if not urls:
            continue
        lines.append(f"### {_text(item.get('company_name'), default='unknown')}")
        for url in urls:
            lines.append(f"- {url}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _dedupe(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _text(value: Any, *, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _md_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
