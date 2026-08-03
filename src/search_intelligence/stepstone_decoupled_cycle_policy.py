"""Decoupled StepStone baseline, suppression, origin-refresh and vocabulary policy.

This module performs no network or database I/O. It separates four control
planes that were previously conflated under one company cooldown:

- baseline cadence: when an unfiltered page-one census is due;
- stable suppression: which dominant baseline companies remain filtered until
  the next valid baseline replaces the set;
- origin refresh deduplication: when a dominant known company may trigger its
  employer-origin connector without creating refresh spam;
- vocabulary freshness: compact company/title observations that may bring the
  next baseline forward.

The policy remains inactive until the StepStone query transport and supported
filter capacity are validated and explicitly approved.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Literal

from src.normalization.company_keys import normalize_company_key
from src.search_intelligence.stepstone_company_discovery_cycle import company_not_alias

RunMode = Literal["baseline", "filtered"]
OriginRefreshAction = Literal[
    "trigger_origin_refresh",
    "deduplicated_refresh_pending",
    "deduplicated_refresh_cooldown",
    "origin_discovery_signal",
]


@dataclass(frozen=True)
class BaselineCompanyObservation:
    company_key: str
    company_name: str
    card_count: int
    first_position: int


@dataclass(frozen=True)
class StepStoneCardVocabularyObservation:
    company_key: str
    company_name: str
    raw_title: str
    job_key: str | None = None


@dataclass(frozen=True)
class DecoupledCyclePolicy:
    requested_filter_count: int
    baseline_refresh_interval_hours: int
    max_filtered_runs_between_baselines: int
    vocabulary_staleness_hours: int
    origin_refresh_cooldown_hours: int
    dominance_min_cards: int
    dominance_min_share: float
    policy_version: str

    def __post_init__(self) -> None:
        if self.requested_filter_count < 1:
            raise ValueError("requested_filter_count must be positive")
        if self.baseline_refresh_interval_hours < 1:
            raise ValueError("baseline_refresh_interval_hours must be positive")
        if self.max_filtered_runs_between_baselines < 1:
            raise ValueError("max_filtered_runs_between_baselines must be positive")
        if self.vocabulary_staleness_hours < 1:
            raise ValueError("vocabulary_staleness_hours must be positive")
        if self.origin_refresh_cooldown_hours < 0:
            raise ValueError("origin_refresh_cooldown_hours must be non-negative")
        if self.dominance_min_cards < 1:
            raise ValueError("dominance_min_cards must be positive")
        if not 0 < self.dominance_min_share <= 1:
            raise ValueError("dominance_min_share must be in (0, 1]")
        if not self.policy_version.strip():
            raise ValueError("policy_version must not be empty")


@dataclass(frozen=True)
class BaselineCycleState:
    last_baseline_at: datetime | None
    next_baseline_due_at: datetime | None
    filtered_runs_since_baseline: int = 0
    vocabulary_refresh_due: bool = False
    novelty_degraded: bool = False
    transport_health_degraded: bool = False

    def __post_init__(self) -> None:
        if self.filtered_runs_since_baseline < 0:
            raise ValueError("filtered_runs_since_baseline must be non-negative")


@dataclass(frozen=True)
class StepStoneRunModeDecision:
    mode: RunMode
    reason: str
    uses_active_suppression_set: bool


@dataclass(frozen=True)
class SuppressionSetItem:
    company_key: str
    company_name: str
    filter_alias: str
    baseline_card_count: int
    baseline_card_share: float
    first_position: int
    selection_rank: int


@dataclass(frozen=True)
class StableSuppressionSet:
    baseline_review_id: int | None
    baseline_observed_count: int
    baseline_distinct_company_count: int
    requested_filter_count: int
    selected_filter_count: int
    policy_version: str
    items: tuple[SuppressionSetItem, ...]

    @property
    def company_keys(self) -> tuple[str, ...]:
        return tuple(item.company_key for item in self.items)

    @property
    def aliases(self) -> tuple[str, ...]:
        return tuple(item.filter_alias for item in self.items)


@dataclass(frozen=True)
class OriginConnectorState:
    company_key: str
    has_origin_connector: bool
    refresh_pending: bool = False
    refresh_cooldown_until: datetime | None = None


@dataclass(frozen=True)
class OriginRefreshDecision:
    company_key: str
    company_name: str
    card_count: int
    card_share: float
    action: OriginRefreshAction
    reason: str


@dataclass(frozen=True)
class CompanyTitleVocabularyEntry:
    company_key: str
    company_name: str
    raw_title: str
    normalized_title: str
    observation_count: int
    job_keys: tuple[str, ...]


def _aggregate_company_observations(
    observations: Iterable[BaselineCompanyObservation],
) -> tuple[BaselineCompanyObservation, ...]:
    grouped: dict[str, dict[str, object]] = {}
    for observation in observations:
        company_key = normalize_company_key(
            observation.company_key or observation.company_name
        )
        if not company_key or observation.card_count <= 0:
            continue
        entry = grouped.setdefault(
            company_key,
            {
                "company_name": observation.company_name,
                "card_count": 0,
                "first_position": observation.first_position,
            },
        )
        entry["card_count"] = int(entry["card_count"]) + observation.card_count
        entry["first_position"] = min(
            int(entry["first_position"]), observation.first_position
        )

    return tuple(
        BaselineCompanyObservation(
            company_key=company_key,
            company_name=str(entry["company_name"]),
            card_count=int(entry["card_count"]),
            first_position=int(entry["first_position"]),
        )
        for company_key, entry in grouped.items()
    )


def decide_stepstone_run_mode(
    *,
    state: BaselineCycleState,
    policy: DecoupledCyclePolicy,
    now: datetime,
    has_active_suppression_set: bool,
) -> StepStoneRunModeDecision:
    """Choose one request mode without scheduling a second StepStone call."""
    if state.last_baseline_at is None:
        return StepStoneRunModeDecision(
            mode="baseline",
            reason="no_valid_baseline_exists",
            uses_active_suppression_set=False,
        )
    if state.transport_health_degraded:
        return StepStoneRunModeDecision(
            mode="baseline",
            reason="transport_health_requires_recalibration",
            uses_active_suppression_set=False,
        )
    if state.vocabulary_refresh_due:
        return StepStoneRunModeDecision(
            mode="baseline",
            reason="company_vocabulary_refresh_due",
            uses_active_suppression_set=False,
        )
    if state.novelty_degraded:
        return StepStoneRunModeDecision(
            mode="baseline",
            reason="filtered_discovery_novelty_degraded",
            uses_active_suppression_set=False,
        )
    if (
        state.filtered_runs_since_baseline
        >= policy.max_filtered_runs_between_baselines
    ):
        return StepStoneRunModeDecision(
            mode="baseline",
            reason="maximum_filtered_runs_since_baseline_reached",
            uses_active_suppression_set=False,
        )
    if state.next_baseline_due_at is not None and now >= state.next_baseline_due_at:
        return StepStoneRunModeDecision(
            mode="baseline",
            reason="baseline_refresh_interval_elapsed",
            uses_active_suppression_set=False,
        )
    if not has_active_suppression_set:
        return StepStoneRunModeDecision(
            mode="baseline",
            reason="active_suppression_set_missing",
            uses_active_suppression_set=False,
        )
    return StepStoneRunModeDecision(
        mode="filtered",
        reason="reuse_last_valid_baseline_suppression_set",
        uses_active_suppression_set=True,
    )


def build_suppression_set_from_baseline(
    *,
    observations: Iterable[BaselineCompanyObservation],
    policy: DecoupledCyclePolicy,
    baseline_review_id: int | None = None,
) -> StableSuppressionSet:
    """Build one stable filter set only from the latest valid baseline."""
    aggregated = _aggregate_company_observations(observations)
    observed_count = sum(item.card_count for item in aggregated)
    ranked = sorted(
        aggregated,
        key=lambda item: (-item.card_count, item.first_position, item.company_key),
    )
    selected = ranked[: policy.requested_filter_count]
    items = tuple(
        SuppressionSetItem(
            company_key=item.company_key,
            company_name=item.company_name,
            filter_alias=company_not_alias(item.company_key, item.company_name),
            baseline_card_count=item.card_count,
            baseline_card_share=(
                item.card_count / observed_count if observed_count else 0.0
            ),
            first_position=item.first_position,
            selection_rank=rank,
        )
        for rank, item in enumerate(selected, start=1)
    )
    return StableSuppressionSet(
        baseline_review_id=baseline_review_id,
        baseline_observed_count=observed_count,
        baseline_distinct_company_count=len(aggregated),
        requested_filter_count=policy.requested_filter_count,
        selected_filter_count=len(items),
        policy_version=policy.policy_version,
        items=items,
    )


def plan_origin_refresh_decisions(
    *,
    baseline_observations: Iterable[BaselineCompanyObservation],
    connector_states: Iterable[OriginConnectorState],
    policy: DecoupledCyclePolicy,
    now: datetime,
) -> tuple[OriginRefreshDecision, ...]:
    """Create at most one deduplicated refresh decision per dominant company."""
    aggregated = _aggregate_company_observations(baseline_observations)
    observed_count = sum(item.card_count for item in aggregated)
    states = {
        normalize_company_key(state.company_key): state
        for state in connector_states
        if normalize_company_key(state.company_key)
    }

    decisions: list[OriginRefreshDecision] = []
    for item in sorted(
        aggregated,
        key=lambda current: (
            -current.card_count,
            current.first_position,
            current.company_key,
        ),
    ):
        share = item.card_count / observed_count if observed_count else 0.0
        if (
            item.card_count < policy.dominance_min_cards
            and share < policy.dominance_min_share
        ):
            continue
        state = states.get(item.company_key)
        if state is None or not state.has_origin_connector:
            action: OriginRefreshAction = "origin_discovery_signal"
            reason = "dominant_company_has_no_origin_connector"
        elif state.refresh_pending:
            action = "deduplicated_refresh_pending"
            reason = "origin_refresh_already_pending"
        elif (
            state.refresh_cooldown_until is not None
            and state.refresh_cooldown_until > now
        ):
            action = "deduplicated_refresh_cooldown"
            reason = "origin_refresh_cooldown_active"
        else:
            action = "trigger_origin_refresh"
            reason = "dominant_baseline_company_origin_refresh_due"
        decisions.append(
            OriginRefreshDecision(
                company_key=item.company_key,
                company_name=item.company_name,
                card_count=item.card_count,
                card_share=share,
                action=action,
                reason=reason,
            )
        )
    return tuple(decisions)


def _normalize_title(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def aggregate_company_title_vocabulary(
    observations: Iterable[StepStoneCardVocabularyObservation],
) -> tuple[CompanyTitleVocabularyEntry, ...]:
    """Aggregate compact company/title vocabulary without duplicating cards."""
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for observation in observations:
        company_key = normalize_company_key(
            observation.company_key or observation.company_name
        )
        raw_title = re.sub(r"\s+", " ", observation.raw_title).strip()
        normalized_title = _normalize_title(raw_title)
        if not company_key or not normalized_title:
            continue
        key = (company_key, normalized_title)
        entry = grouped.setdefault(
            key,
            {
                "company_name": observation.company_name,
                "raw_title": raw_title,
                "observation_count": 0,
                "job_keys": set(),
            },
        )
        entry["observation_count"] = int(entry["observation_count"]) + 1
        job_keys = entry["job_keys"]
        if isinstance(job_keys, set) and observation.job_key:
            job_keys.add(observation.job_key)

    entries = [
        CompanyTitleVocabularyEntry(
            company_key=company_key,
            company_name=str(entry["company_name"]),
            raw_title=str(entry["raw_title"]),
            normalized_title=normalized_title,
            observation_count=int(entry["observation_count"]),
            job_keys=tuple(sorted(str(value) for value in entry["job_keys"])),
        )
        for (company_key, normalized_title), entry in grouped.items()
    ]
    return tuple(
        sorted(
            entries,
            key=lambda item: (
                item.company_key,
                item.normalized_title,
            ),
        )
    )
