"""MARKET-003 external market observation foundation.

Manual market observations are explicit learning inputs for recall and blind-spot
analysis. Dry-run planning and review are read-only; persistence is explicit-write-only
and limited to `market_evidence`. Manual observations are not jobs, not Bronze
records, not source activations, not gate decisions and not connector evidence by
themselves.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from src.normalization.company_keys import normalize_company_key

ALLOWED_OBSERVATION_CHANNELS = {
    "linkedin",
    "xing",
    "indeed",
    "stepstone_manual",
    "recruiter",
    "job_fair",
    "company_career_page_manual",
    "personal_research",
    "other_manual_source",
}

ALLOWED_RELEVANCE_SIGNALS = {
    "unknown",
    "weak",
    "medium",
    "strong",
}

ALLOWED_REMOTE_SIGNALS = {
    "unknown",
    "onsite_only",
    "hybrid",
    "remote_possible",
    "remote_first",
}


@dataclass(frozen=True)
class ManualMarketObservationInput:
    """One user-observed market signal before persistence."""

    company_name: str
    title: str
    observation_channel: str
    observation_source: str = "manual_market_observation"
    evidence_url: str | None = None
    search_term: str | None = None
    search_profile_name: str | None = None
    observed_at: str | None = None
    location: str | None = None
    remote_signal: str = "unknown"
    relevance_signal: str = "unknown"
    note: str | None = None
    recorded_by: str = "jens"


@dataclass(frozen=True)
class ManualMarketObservationPlan:
    """Reviewable persistence plan for one manual observation."""

    company_key: str
    company_name: str
    title: str
    evidence_kind: str
    source_name: str
    evidence_source: str
    evidence_url: str | None
    search_profile_name: str | None
    search_term: str | None
    source_seen_at: str | None
    evidence_payload: Mapping[str, Any]
    insert_allowed: bool
    action: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "evidence_payload": dict(self.evidence_payload),
        }


@dataclass(frozen=True)
class ManualMarketObservationReview:
    """Small read-model summary for manual observations."""

    observation_count: int
    distinct_company_count: int
    channel_counts: Mapping[str, int]
    relevance_counts: Mapping[str, int]
    remote_signal_counts: Mapping[str, int]
    strong_relevant_company_count: int
    safety_boundary: Mapping[str, bool]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "market003.external_market_observations.v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "work_item": "MARKET-003 External Market Observation Foundation",
            "observation_count": self.observation_count,
            "distinct_company_count": self.distinct_company_count,
            "channel_counts": dict(self.channel_counts),
            "relevance_counts": dict(self.relevance_counts),
            "remote_signal_counts": dict(self.remote_signal_counts),
            "strong_relevant_company_count": self.strong_relevant_company_count,
            "safety_boundary": dict(self.safety_boundary),
            "next_action": suggest_next_market003_action(self),
        }


def market003_safety_boundary() -> dict[str, bool]:
    return {
        "manual_market_observation_only": True,
        "dry_run_by_default": True,
        "database_write_requires_explicit_write_flag": True,
        "database_write_scope_market_evidence_only": True,
        "job_ingestion": False,
        "bronze_write": False,
        "silver_gold_mutation": False,
        "source_activation": False,
        "scheduler_change": False,
        "candidate_creation": False,
        "gate_decision": False,
        "connector_build_or_registration": False,
        "csv_or_export_as_pipeline_input": False,
    }


def build_manual_market_observation_plan(
    observation: ManualMarketObservationInput,
) -> ManualMarketObservationPlan:
    company_name = observation.company_name.strip()
    title = observation.title.strip()
    channel = _normalize_choice(observation.observation_channel, ALLOWED_OBSERVATION_CHANNELS, "observation_channel")
    relevance = _normalize_choice(observation.relevance_signal, ALLOWED_RELEVANCE_SIGNALS, "relevance_signal")
    remote = _normalize_choice(observation.remote_signal, ALLOWED_REMOTE_SIGNALS, "remote_signal")
    company_key = normalize_company_key(company_name)
    insert_allowed = bool(company_key and title)
    payload = {
        "recorded_by": observation.recorded_by,
        "input_mode": "manual_market_observation",
        "observation_origin": "external_market_observation",
        "observation_channel": channel,
        "relevance_signal": relevance,
        "remote_signal": remote,
        "location": observation.location,
        "note": observation.note,
        "boundary": market003_safety_boundary(),
        "decision_boundary": "learning_signal_only_not_gate_truth",
    }
    return ManualMarketObservationPlan(
        company_key=company_key,
        company_name=company_name,
        title=title,
        evidence_kind="manual_market_observation",
        source_name=channel,
        evidence_source=observation.observation_source.strip() or "manual_market_observation",
        evidence_url=observation.evidence_url,
        search_profile_name=observation.search_profile_name,
        search_term=observation.search_term,
        source_seen_at=observation.observed_at,
        evidence_payload=payload,
        insert_allowed=insert_allowed,
        action="insert_manual_market_observation" if insert_allowed else "reject_incomplete_manual_observation",
        reason=(
            "manual observation is a bounded learning signal and may feed later review"
            if insert_allowed
            else "company_name and title are required for a useful manual observation"
        ),
    )


def build_manual_market_observation_review(
    rows: list[Mapping[str, Any]],
) -> ManualMarketObservationReview:
    company_keys: set[str] = set()
    channel_counts: dict[str, int] = {}
    relevance_counts: dict[str, int] = {}
    remote_counts: dict[str, int] = {}
    strong_companies: set[str] = set()

    for row in rows:
        company_key = str(row.get("normalized_company_key") or row.get("company_key") or "").strip()
        if company_key:
            company_keys.add(company_key)
        evidence = row.get("evidence") or {}
        if not isinstance(evidence, Mapping):
            evidence = {}
        channel = str(row.get("source_name") or evidence.get("observation_channel") or "unknown")
        relevance = str(evidence.get("relevance_signal") or "unknown")
        remote = str(evidence.get("remote_signal") or "unknown")
        channel_counts[channel] = channel_counts.get(channel, 0) + 1
        relevance_counts[relevance] = relevance_counts.get(relevance, 0) + 1
        remote_counts[remote] = remote_counts.get(remote, 0) + 1
        if relevance == "strong" and company_key:
            strong_companies.add(company_key)

    return ManualMarketObservationReview(
        observation_count=len(rows),
        distinct_company_count=len(company_keys),
        channel_counts=dict(sorted(channel_counts.items())),
        relevance_counts=dict(sorted(relevance_counts.items())),
        remote_signal_counts=dict(sorted(remote_counts.items())),
        strong_relevant_company_count=len(strong_companies),
        safety_boundary=market003_safety_boundary(),
    )


def suggest_next_market003_action(review: ManualMarketObservationReview) -> str:
    if review.observation_count == 0:
        return "record_manual_market_observations_before_recall_interpretation"
    if review.strong_relevant_company_count > 0:
        return "run_candidate_expansion_review_without_automatic_promotion"
    return "continue_collecting_manual_market_observations_and_quality_review"


def render_market003_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# MARKET-003 External Market Observation Foundation",
        "",
        f"- schema_version: `{report.get('schema_version')}`",
        f"- generated_at_utc: `{report.get('generated_at_utc')}`",
        f"- work_item: `{report.get('work_item')}`",
        "",
        "## Summary",
        "",
        f"- observation_count: `{report.get('observation_count')}`",
        f"- distinct_company_count: `{report.get('distinct_company_count')}`",
        f"- strong_relevant_company_count: `{report.get('strong_relevant_company_count')}`",
        "",
        "## Safety boundary",
        "",
    ]
    for key, value in report.get("safety_boundary", {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Channels", ""])
    for key, value in report.get("channel_counts", {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Relevance signals", ""])
    for key, value in report.get("relevance_counts", {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Remote signals", ""])
    for key, value in report.get("remote_signal_counts", {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Next action", "", str(report.get("next_action", "")), ""])
    return "\n".join(lines)


def _normalize_choice(value: str, allowed: set[str], label: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized not in allowed:
        raise ValueError(f"Unsupported {label}: {value!r}. Allowed: {', '.join(sorted(allowed))}")
    return normalized
