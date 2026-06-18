from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from src.search_intelligence.market_sensor_controlled_activation import (
    BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME,
    BA_SOURCE_NAME,
    EXPECTED_BA_REMOTE_TERMS,
    MarketSensorProfileState,
    MarketSensorTermState,
    build_ba_remote_controlled_activation_review,
)


@dataclass(frozen=True)
class BoundedSampleRunPlan:
    overall_status: str
    source_name: str
    review_status: str
    sample_terms: tuple[str, ...]
    sample_limits: Mapping[str, Any]
    measurement_plan: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    activation_changes: Mapping[str, Any]
    findings: tuple[str, ...]
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "sensor001d.ba_remote_nationwide_bounded_sample_run_plan.v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "work_item": "SENSOR-001D BA Remote/Nationwide Bounded Sample Run Plan",
            "source_name": self.source_name,
            "generic_requirement": (
                "Every market sensor that claims Germany-wide remote-option discovery must have a bounded "
                "sample-run plan before any productive scheduler activation."
            ),
            "safety_boundary": {
                "read_only_plan": True,
                "external_requests": False,
                "database_writes": False,
                "ingestion_run": False,
                "scheduler_mutation": False,
                "connector_activation": False,
                "candidate_or_gate_mutation": False,
                "productive_activation": False,
            },
            "overall_status": self.overall_status,
            "review_status": self.review_status,
            "sample_terms": list(self.sample_terms),
            "sample_limits": dict(self.sample_limits),
            "measurement_plan": list(self.measurement_plan),
            "stop_conditions": list(self.stop_conditions),
            "activation_changes": dict(self.activation_changes),
            "findings": list(self.findings),
            "next_action": self.next_action,
        }


def build_ba_remote_bounded_sample_run_plan(
    profiles: Iterable[MarketSensorProfileState],
    terms: Iterable[MarketSensorTermState],
    *,
    max_terms: int = 2,
) -> BoundedSampleRunPlan:
    profile_tuple = tuple(profiles)
    term_tuple = tuple(terms)
    review = build_ba_remote_controlled_activation_review(profile_tuple, term_tuple)
    review_payload = review.as_dict()
    review_status = str(review_payload["overall_status"])
    findings = list(review_payload.get("findings", []))

    if review_status != "review_profile_ready":
        return BoundedSampleRunPlan(
            overall_status="blocked_until_review_profile_ready",
            source_name=BA_SOURCE_NAME,
            review_status=review_status,
            sample_terms=(),
            sample_limits={
                "max_terms": 0,
                "page_size_per_term": 0,
                "max_result_requests": 0,
                "max_raw_results_seen": 0,
                "scheduler_changes_now": False,
            },
            measurement_plan=(),
            stop_conditions=("Do not run a sample before SENSOR-001C reports review_profile_ready.",),
            activation_changes={
                "run_sample_now": False,
                "activate_profile_now": False,
                "scheduler_changes_now": False,
                "database_writes_now": False,
                "reason": "The inactive review profile is not ready.",
            },
            findings=tuple(findings),
            next_action="Resolve SENSOR-001C review state first, then rerun SENSOR-001D.",
        )

    review_profile = _single_review_profile(profile_tuple)
    available_terms = tuple(
        term.search_term
        for term in term_tuple
        if term.profile_name == BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME and term.is_active
    )
    sample_terms = _select_sample_terms(available_terms, max_terms=max_terms)
    if not sample_terms:
        return BoundedSampleRunPlan(
            overall_status="configuration_mismatch",
            source_name=BA_SOURCE_NAME,
            review_status=review_status,
            sample_terms=(),
            sample_limits={
                "max_terms": 0,
                "page_size_per_term": 0,
                "max_result_requests": 0,
                "max_raw_results_seen": 0,
                "scheduler_changes_now": False,
            },
            measurement_plan=(),
            stop_conditions=("Review profile has no active terms available for a bounded sample plan.",),
            activation_changes={
                "run_sample_now": False,
                "activate_profile_now": False,
                "scheduler_changes_now": False,
                "database_writes_now": False,
                "reason": "No active review-profile terms are available.",
            },
            findings=("No active terms found for the BA remote/nationwide review profile.",),
            next_action="Repair review-profile search terms before planning a bounded sample.",
        )

    page_size = max(1, min(review_profile.page_size, 10))
    max_requests = len(sample_terms)

    return BoundedSampleRunPlan(
        overall_status="sample_plan_ready",
        source_name=BA_SOURCE_NAME,
        review_status=review_status,
        sample_terms=sample_terms,
        sample_limits={
            "max_terms": len(sample_terms),
            "page_size_per_term": page_size,
            "max_result_requests": max_requests,
            "max_raw_results_seen": max_requests * page_size,
            "profile_must_remain_inactive": True,
            "scheduler_changes_now": False,
            "sample_run_requires_explicit_operator_approval": True,
        },
        measurement_plan=(
            "Record total_loaded, inserted_count, duplicate_count, and error state per sampled term.",
            "Measure employer uniqueness and duplicate overlap against the existing Hannover BA profile.",
            "Measure role/profile relevance before treating the sample as source-value evidence.",
            "Measure location distribution and distinguish Germany-wide noise from plausible remote-in-Germany candidates.",
            "Measure remote/hybrid signal quality downstream; BA remote filtering is not confirmed as server-side capability.",
            "Do not promote the review profile to active based on volume alone.",
        ),
        stop_conditions=(
            "Stop if the review profile becomes active before explicit approval.",
            "Stop if the sample would require scheduler changes.",
            "Stop if the sample exceeds the planned term/page-size bounds.",
            "Stop if results are mostly irrelevant or location distribution shows broad non-target noise without remote evidence.",
            "Stop if the run cannot report duplicate and insert counts per term.",
        ),
        activation_changes={
            "run_sample_now": False,
            "activate_profile_now": False,
            "scheduler_changes_now": False,
            "database_writes_now": False,
            "next_work_item": "SENSOR-001E BA Remote/Nationwide Bounded Sample Execution Review",
            "reason": (
                "SENSOR-001D only creates a bounded sample-run plan. "
                "Any actual API/ingestion call requires a later explicit operator-approved work item."
            ),
        },
        findings=(
            "Inactive BA remote/nationwide review profile is ready.",
            "Bounded sample should start with high-signal terms only, not all terms.",
            "The plan remains generic for market sensors: bounded sample, measurable yield, no scheduler activation.",
        ),
        next_action=(
            "Review the sample terms and limits. If approved, implement a separate bounded sample execution/review "
            "that records yield metrics without activating the scheduler."
        ),
    )


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# SENSOR-001D BA Remote/Nationwide Bounded Sample Run Plan",
        "",
        f"- overall_status: `{report.get('overall_status')}`",
        f"- review_status: `{report.get('review_status')}`",
        f"- source_name: `{report.get('source_name')}`",
        f"- generated_at_utc: `{report.get('generated_at_utc')}`",
        "",
        "## Sample terms",
        "",
    ]
    sample_terms = report.get("sample_terms", [])
    if sample_terms:
        for term in sample_terms:
            lines.append(f"- {term}")
    else:
        lines.append("- none")

    lines.extend(["", "## Sample limits", ""])
    for key, value in report.get("sample_limits", {}).items():
        lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Measurement plan", ""])
    for item in report.get("measurement_plan", []):
        lines.append(f"- {item}")

    lines.extend(["", "## Stop conditions", ""])
    for item in report.get("stop_conditions", []):
        lines.append(f"- {item}")

    lines.extend(["", "## Findings", ""])
    for item in report.get("findings", []):
        lines.append(f"- {item}")

    lines.extend(["", "## Next action", "", str(report.get("next_action", "")), ""])
    return "\n".join(lines)


def _single_review_profile(profiles: tuple[MarketSensorProfileState, ...]) -> MarketSensorProfileState:
    review_profiles = tuple(
        profile
        for profile in profiles
        if profile.profile_name == BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME
    )
    if len(review_profiles) != 1:
        raise ValueError("Expected exactly one BA remote/nationwide review profile.")
    return review_profiles[0]


def _select_sample_terms(available_terms: tuple[str, ...], *, max_terms: int) -> tuple[str, ...]:
    if max_terms <= 0:
        return ()
    available_set = {term.casefold(): term for term in available_terms}
    selected: list[str] = []
    for expected in EXPECTED_BA_REMOTE_TERMS:
        match = available_set.get(expected.casefold())
        if match:
            selected.append(match)
        if len(selected) >= max_terms:
            break
    return tuple(selected)
