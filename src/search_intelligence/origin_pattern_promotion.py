"""Promotion rules for origin observation learning.

Observation is learning input only. This module promotes repeated or high-signal
observation candidates into a controlled vocabulary that other discovery agents
may use as search/extraction strategy. Promotion still does not pass gates,
activate sources, write Bronze/Silver data or bypass explicit candidate review.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

PROMOTION_BOUNDARY = {
    "learning_input_only": True,
    "no_gate_decision": True,
    "no_candidate_status_mutation": True,
    "no_connector_artifact_generation": True,
    "no_connector_registration": True,
    "no_source_activation": True,
    "no_bronze_write": True,
    "no_silver_write": True,
    "no_scheduler_change": True,
    "no_csv_or_export_input": True,
    "pattern_usage_requires_promotion": True,
}

SAFE_URL_PATH_PATTERNS = {
    "/job/...",
    "/jobs/...",
    "/stellen/...",
    "/vacancy/...",
    "/career/...",
    "/search/...",
}

SAFE_ATS_FAMILIES = {
    "Greenhouse",
    "Lever",
    "Personio",
    "Phenom",
    "SAP SuccessFactors",
    "SmartRecruiters",
    "Workday",
    "Jobvite",
}

STRONG_LOCATION_SIGNALS = {
    "hannover",
    "deutschlandweit",
    "bundesweit",
    "germany-wide",
    "germany wide",
    "standort deutschlandweit",
    "standort: deutschlandweit",
}

STRONG_REMOTE_SIGNALS = {
    "remote",
    "remote deutschland",
    "remote germany",
    "homeoffice",
    "home office",
    "home-office",
    "mobiles arbeiten",
    "mobile work",
    "work from home",
    "work from anywhere in germany",
}

MULTI_LOCATION_SIGNALS = {
    "+ weitere",
    "+ weitere standorte",
}

SAFE_PROFILE_SIGNALS = {
    "data engineer",
    "data engineering",
    "analytics engineer",
    "databricks",
    "data & analytics",
    "python",
    "sql",
}

AMBIGUOUS_PROFILE_SIGNALS = {
    "bi",
}

PROMOTABLE_PATTERN_TYPES = {
    "url_path_pattern",
    "ats_family",
    "json_ld_jobposting",
    "location_signal",
    "remote_signal",
    "profile_signal",
    "structural_marker",
}


@dataclass(frozen=True)
class ObservedPattern:
    pattern_type: str
    pattern_value: str
    evidence_count: int
    confidence: float
    current_status: str = "observed"


@dataclass(frozen=True)
class PromotionDecision:
    pattern_type: str
    pattern_value: str
    promotion_status: str
    confidence: float
    reason: str
    signal_strength: str = "supporting"
    pattern_category: str = "diagnostics_only"
    usage_scope: str = "diagnostics_only"
    usable_by_url_finder: bool = False
    usable_by_relevance_probe: bool = False


def normalize_signal(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _title_case_known(value: str) -> str:
    normalized = normalize_signal(value)
    for family in SAFE_ATS_FAMILIES:
        if normalize_signal(family) == normalized:
            return family
    return str(value or "").strip()


def promote_observed_pattern(pattern: ObservedPattern, *, min_signal_evidence: int = 1) -> PromotionDecision:
    """Classify one observed pattern candidate.

    Promotion is intentionally conservative for signals and more permissive for
    URL/ATS structure because URL/ATS patterns influence search strategy rather
    than directly passing candidate relevance gates.
    """

    pattern_type = str(pattern.pattern_type or "").strip()
    raw_value = str(pattern.pattern_value or "").strip()
    normalized = normalize_signal(raw_value)
    evidence_count = int(pattern.evidence_count or 0)
    base_confidence = max(0.0, min(float(pattern.confidence or 0.0), 1.0))

    if not pattern_type or not normalized or pattern_type not in PROMOTABLE_PATTERN_TYPES:
        return PromotionDecision(
            pattern_type=pattern_type,
            pattern_value=raw_value,
            promotion_status="rejected",
            confidence=base_confidence,
            reason="pattern type or value is not eligible for promotion",
        )

    if pattern_type == "url_path_pattern":
        value = normalized if normalized.startswith("/") else raw_value
        if value in SAFE_URL_PATH_PATTERNS:
            detail_patterns = {"/job/...", "/stellen/...", "/vacancy/..."}
            listing_patterns = {"/jobs/...", "/search/...", "/career/..."}
            is_detail_pattern = value in detail_patterns
            return PromotionDecision(
                pattern_type=pattern_type,
                pattern_value=value,
                promotion_status="promoted",
                confidence=max(base_confidence, 0.72),
                reason=(
                    "safe detail URL pattern may improve bounded job-detail discovery strategy"
                    if is_detail_pattern
                    else "safe listing/search URL pattern may improve bounded origin URL discovery strategy"
                ),
                signal_strength="strategy",
                pattern_category="url_detail_pattern" if is_detail_pattern else "url_listing_pattern",
                usage_scope="detail_url_discovery" if is_detail_pattern else "listing_url_discovery",
                usable_by_url_finder=True,
                usable_by_relevance_probe=False,
            )
        return PromotionDecision(
            pattern_type,
            raw_value,
            "candidate",
            base_confidence,
            "URL pattern needs more observations before use",
            pattern_category="url_pattern_candidate",
            usage_scope="diagnostics_only",
        )

    if pattern_type == "ats_family":
        value = _title_case_known(raw_value)
        if value in SAFE_ATS_FAMILIES:
            return PromotionDecision(
                pattern_type=pattern_type,
                pattern_value=value,
                promotion_status="promoted",
                confidence=max(base_confidence, 0.70),
                reason="known ATS family may guide bounded URL discovery and parsing strategy",
                signal_strength="strategy",
                pattern_category="ats_family",
                usage_scope="url_finder_strategy",
                usable_by_url_finder=True,
                usable_by_relevance_probe=False,
            )
        return PromotionDecision(
            pattern_type,
            raw_value,
            "candidate",
            base_confidence,
            "ATS marker needs review before use",
            pattern_category="ats_family_candidate",
            usage_scope="diagnostics_only",
        )

    if pattern_type == "json_ld_jobposting":
        if normalized == "present":
            return PromotionDecision(
                pattern_type=pattern_type,
                pattern_value="present",
                promotion_status="promoted",
                confidence=max(base_confidence, 0.75),
                reason="schema.org JobPosting JSON-LD is safe structural evidence for job-detail discovery",
                signal_strength="strategy",
                pattern_category="structured_jobposting_marker",
                usage_scope="detail_url_discovery",
                usable_by_url_finder=False,
                usable_by_relevance_probe=False,
            )
        return PromotionDecision(
            pattern_type,
            raw_value,
            "candidate",
            base_confidence,
            "JSON-LD marker is not recognized",
            pattern_category="structured_marker_candidate",
            usage_scope="diagnostics_only",
        )

    if pattern_type == "location_signal":
        if normalized in STRONG_LOCATION_SIGNALS:
            category = "location_exact_signal" if normalized == "hannover" else "location_germany_wide_signal"
            return PromotionDecision(
                pattern_type=pattern_type,
                pattern_value=normalized,
                promotion_status="promoted",
                confidence=max(base_confidence, 0.82),
                reason="observed strong location/Germany-wide signal promoted for relevance extraction",
                signal_strength="strong",
                pattern_category=category,
                usage_scope="relevance_location",
                usable_by_relevance_probe=True,
            )
        if normalized in MULTI_LOCATION_SIGNALS and evidence_count >= min_signal_evidence:
            return PromotionDecision(
                pattern_type=pattern_type,
                pattern_value=normalized,
                promotion_status="promoted",
                confidence=max(base_confidence, 0.68),
                reason="observed multi-location indicator promoted as location evidence; it is not a remote-work signal and still requires profile evidence",
                signal_strength="medium",
                pattern_category="location_multi_signal",
                usage_scope="relevance_location",
                usable_by_relevance_probe=True,
            )
        return PromotionDecision(
            pattern_type,
            raw_value,
            "candidate",
            base_confidence,
            "location signal needs more observations before use",
            pattern_category="location_signal_candidate",
            usage_scope="diagnostics_only",
        )

    if pattern_type == "remote_signal":
        if normalized in STRONG_REMOTE_SIGNALS:
            return PromotionDecision(
                pattern_type=pattern_type,
                pattern_value=normalized,
                promotion_status="promoted",
                confidence=max(base_confidence, 0.78),
                reason="observed remote/flexible-work signal promoted for relevance extraction",
                signal_strength="medium" if normalized in {"remote", "homeoffice", "home office", "home-office"} else "strong",
                pattern_category="remote_work_signal",
                usage_scope="relevance_remote",
                usable_by_relevance_probe=True,
            )
        if normalized in MULTI_LOCATION_SIGNALS:
            return PromotionDecision(
                pattern_type=pattern_type,
                pattern_value=normalized,
                promotion_status="candidate",
                confidence=base_confidence,
                reason="multi-location wording is not a remote-work signal; keep as location signal candidate only",
                signal_strength="supporting",
                pattern_category="location_multi_signal",
                usage_scope="diagnostics_only",
                usable_by_relevance_probe=False,
            )
        return PromotionDecision(
            pattern_type,
            raw_value,
            "candidate",
            base_confidence,
            "remote signal needs more observations before use",
            pattern_category="remote_signal_candidate",
            usage_scope="diagnostics_only",
        )

    if pattern_type == "profile_signal":
        if normalized in SAFE_PROFILE_SIGNALS:
            role_signals = {"data engineer", "data engineering", "analytics engineer"}
            skill_signals = {"databricks", "data & analytics", "python", "sql"}
            return PromotionDecision(
                pattern_type=pattern_type,
                pattern_value=normalized,
                promotion_status="promoted",
                confidence=max(base_confidence, 0.70),
                reason="observed profile signal is within the known search-intelligence profile vocabulary",
                signal_strength="strong" if normalized in {"data engineer", "data engineering", "databricks", "data & analytics"} else "medium",
                pattern_category="profile_role_signal" if normalized in role_signals else ("profile_skill_signal" if normalized in skill_signals else "profile_supporting_signal"),
                usage_scope="relevance_profile",
                usable_by_relevance_probe=True,
            )
        if normalized in AMBIGUOUS_PROFILE_SIGNALS:
            return PromotionDecision(
                pattern_type=pattern_type,
                pattern_value=normalized,
                promotion_status="candidate",
                confidence=base_confidence,
                reason="short or ambiguous profile signal remains candidate until stronger contextual evidence exists",
                signal_strength="supporting",
                pattern_category="profile_ambiguous_signal",
                usage_scope="diagnostics_only",
                usable_by_relevance_probe=False,
            )
        return PromotionDecision(
            pattern_type,
            raw_value,
            "candidate",
            base_confidence,
            "profile signal remains an observed candidate",
            pattern_category="profile_signal_candidate",
            usage_scope="diagnostics_only",
        )

    if pattern_type == "structural_marker":
        if normalized.startswith(("page_type:", "ats:", "json_ld:")) or normalized in {"visible_job_links", "many_visible_job_links"}:
            return PromotionDecision(
                pattern_type=pattern_type,
                pattern_value=raw_value,
                promotion_status="promoted" if evidence_count >= 1 else "candidate",
                confidence=max(base_confidence, 0.62),
                reason="safe structural marker may support observation summaries and discovery diagnostics",
                signal_strength="supporting",
                pattern_category="structural_marker",
                usage_scope="diagnostics_only",
                usable_by_url_finder=True,
                usable_by_relevance_probe=False,
            )

    return PromotionDecision(
        pattern_type,
        raw_value,
        "candidate",
        base_confidence,
        "pattern remains observed candidate",
        pattern_category="unclassified_candidate",
        usage_scope="diagnostics_only",
    )


def promoted_terms_by_type(patterns: Iterable[ObservedPattern]) -> dict[str, tuple[str, ...]]:
    """Return promoted signal values grouped by observation pattern type."""

    grouped: dict[str, list[str]] = {"profile_signal": [], "location_signal": [], "remote_signal": [], "url_path_pattern": []}
    for pattern in patterns:
        decision = promote_observed_pattern(pattern)
        if decision.promotion_status != "promoted":
            continue
        if decision.pattern_type in grouped and decision.pattern_value not in grouped[decision.pattern_type]:
            grouped[decision.pattern_type].append(decision.pattern_value)
    return {key: tuple(values) for key, values in grouped.items()}
