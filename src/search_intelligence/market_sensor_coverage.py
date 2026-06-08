from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

LOCAL_TARGET_INTENT = "search_local_target_market"
REMOTE_NATIONWIDE_INTENT = "search_germany_wide_remote_options"

REMOTE_TERMS = (
    "remote",
    "homeoffice",
    "home office",
    "mobiles arbeiten",
    "mobile arbeit",
    "mobile work",
    "work from home",
    "hybrid",
)

NATIONWIDE_TERMS = (
    "deutschland",
    "deutschlandweit",
    "bundesweit",
    "germany",
    "nationwide",
    "remote",
)

LOCAL_TERMS = (
    "hannover",
    "hanover",
    "30629",
)


@dataclass(frozen=True)
class MarketSensorProfile:
    profile_key: str
    source_name: str
    search_location: str | None = None
    search_radius_km: int | None = None
    search_terms: tuple[str, ...] = ()
    is_active: bool = True
    supports_remote_filter: bool = False
    raw: Mapping[str, object] = field(default_factory=dict)

    @property
    def evidence_text(self) -> str:
        return " ".join(
            part
            for part in (
                self.profile_key,
                self.source_name,
                self.search_location or "",
                " ".join(self.search_terms),
            )
            if part
        )


@dataclass(frozen=True)
class CoverageDimensionResult:
    intent: str
    status: str
    matching_profiles: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class MarketSensorCoverageAssessment:
    source_name: str
    active_profile_count: int
    local_target: CoverageDimensionResult
    remote_nationwide_target: CoverageDimensionResult
    coverage_gaps: tuple[str, ...]
    next_action: str

    @property
    def status(self) -> str:
        return "pass" if not self.coverage_gaps else "gap_detected"

    def as_dict(self) -> dict[str, object]:
        return {
            "source_name": self.source_name,
            "status": self.status,
            "active_profile_count": self.active_profile_count,
            "local_target": {
                "intent": self.local_target.intent,
                "status": self.local_target.status,
                "matching_profiles": list(self.local_target.matching_profiles),
                "reason": self.local_target.reason,
            },
            "remote_nationwide_target": {
                "intent": self.remote_nationwide_target.intent,
                "status": self.remote_nationwide_target.status,
                "matching_profiles": list(self.remote_nationwide_target.matching_profiles),
                "reason": self.remote_nationwide_target.reason,
            },
            "coverage_gaps": list(self.coverage_gaps),
            "next_action": self.next_action,
        }


def normalize_text(value: object | None) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().replace("_", "-").split())


def contains_any(text: str, terms: Iterable[str]) -> bool:
    normalized = normalize_text(text)
    return any(term in normalized for term in terms)


def supports_local_target(profile: MarketSensorProfile, local_terms: Sequence[str] = LOCAL_TERMS) -> bool:
    if not profile.is_active:
        return False
    return contains_any(profile.evidence_text, local_terms)


def supports_remote_nationwide_target(profile: MarketSensorProfile) -> bool:
    if not profile.is_active:
        return False

    text = normalize_text(profile.evidence_text)
    has_remote_signal = contains_any(text, REMOTE_TERMS)
    has_nationwide_signal = contains_any(text, NATIONWIDE_TERMS)

    # A source capability flag alone is not enough; this check validates whether
    # the current sensor configuration actually expresses the remote/nationwide intent.
    return has_remote_signal and has_nationwide_signal


def assess_market_sensor_coverage(
    source_name: str,
    profiles: Sequence[MarketSensorProfile],
    *,
    local_terms: Sequence[str] = LOCAL_TERMS,
) -> MarketSensorCoverageAssessment:
    active_profiles = tuple(
        profile for profile in profiles if profile.source_name == source_name and profile.is_active
    )
    local_matches = tuple(
        profile.profile_key for profile in active_profiles if supports_local_target(profile, local_terms)
    )
    remote_matches = tuple(
        profile.profile_key for profile in active_profiles if supports_remote_nationwide_target(profile)
    )

    gaps: list[str] = []
    if not active_profiles:
        gaps.append("no_active_market_sensor_profile")
    if not local_matches:
        gaps.append("missing_local_target_market_profile")
    if not remote_matches:
        gaps.append("missing_germany_wide_remote_options_profile")

    local_result = CoverageDimensionResult(
        intent=LOCAL_TARGET_INTENT,
        status="covered" if local_matches else "missing",
        matching_profiles=local_matches,
        reason=(
            "At least one active profile contains local target evidence."
            if local_matches
            else "No active profile expresses the local target-market intent."
        ),
    )
    remote_result = CoverageDimensionResult(
        intent=REMOTE_NATIONWIDE_INTENT,
        status="covered" if remote_matches else "missing",
        matching_profiles=remote_matches,
        reason=(
            "At least one active profile expresses Germany-wide remote-option intent."
            if remote_matches
            else "No active profile expresses the Germany-wide remote-option intent."
        ),
    )

    if not gaps:
        next_action = "monitor_sensor_value_and_overlap"
    elif "missing_germany_wide_remote_options_profile" in gaps:
        next_action = "design_bounded_remote_nationwide_validation_profile_before_activation"
    else:
        next_action = "repair_market_sensor_coverage_configuration"

    return MarketSensorCoverageAssessment(
        source_name=source_name,
        active_profile_count=len(active_profiles),
        local_target=local_result,
        remote_nationwide_target=remote_result,
        coverage_gaps=tuple(gaps),
        next_action=next_action,
    )


def assess_all_market_sensors(
    profiles: Sequence[MarketSensorProfile],
) -> tuple[MarketSensorCoverageAssessment, ...]:
    source_names = sorted({profile.source_name for profile in profiles})
    return tuple(assess_market_sensor_coverage(source_name, profiles) for source_name in source_names)
