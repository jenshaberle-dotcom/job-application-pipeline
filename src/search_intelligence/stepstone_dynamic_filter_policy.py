"""Deterministic n-1 company-filter selection and capacity planning.

This module performs no network or database I/O. It separates three concepts:

- suppression selection: companies to exclude in the next StepStone run;
- reselection cooldown: rotation pressure after a company was filtered;
- dominance override: immediate reselection when a cooled company again crowds
  the current page-one observation.

The policy is intentionally inactive until a permutation-invariant StepStone
query transport has been validated and approved.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Literal

from src.normalization.company_keys import normalize_company_key
from src.search_intelligence.stepstone_company_discovery_cycle import company_not_alias

TransportStatus = Literal["unvalidated", "candidate", "validated"]


@dataclass(frozen=True)
class PreviousRunCompanyObservation:
    company_key: str
    company_name: str
    card_count: int
    first_position: int


@dataclass(frozen=True)
class CompanyReselectionState:
    company_key: str
    cooldown_until: datetime | None
    last_filtered_at: datetime | None = None


@dataclass(frozen=True)
class DynamicFilterPolicy:
    requested_filter_count: int
    dominance_override_min_cards: int
    dominance_override_min_share: float
    policy_version: str

    def __post_init__(self) -> None:
        if self.requested_filter_count < 1:
            raise ValueError("requested_filter_count must be positive")
        if self.dominance_override_min_cards < 1:
            raise ValueError("dominance_override_min_cards must be positive")
        if not 0 < self.dominance_override_min_share <= 1:
            raise ValueError("dominance_override_min_share must be in (0, 1]")
        if not self.policy_version.strip():
            raise ValueError("policy_version must not be empty")


@dataclass(frozen=True)
class DynamicFilterSelectionItem:
    company_key: str
    company_name: str
    filter_alias: str
    card_count: int
    card_share: float
    first_position: int
    cooldown_active: bool
    dominance_override_applied: bool
    selected_for_next_run: bool
    selection_rank: int | None
    selection_reason: str


@dataclass(frozen=True)
class DynamicFilterSelection:
    predecessor_observed_count: int
    predecessor_distinct_company_count: int
    requested_filter_count: int
    selected_filter_count: int
    policy_version: str
    items: tuple[DynamicFilterSelectionItem, ...]

    @property
    def selected_items(self) -> tuple[DynamicFilterSelectionItem, ...]:
        return tuple(item for item in self.items if item.selected_for_next_run)

    @property
    def selected_company_keys(self) -> tuple[str, ...]:
        return tuple(item.company_key for item in self.selected_items)

    @property
    def selected_aliases(self) -> tuple[str, ...]:
        return tuple(item.filter_alias for item in self.selected_items)


@dataclass(frozen=True)
class FilterCapacityTrial:
    filter_count: int
    permutation_name: str
    company_keys: tuple[str, ...]
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class FilterCapacityExperimentPlan:
    transport_name: str
    transport_status: TransportStatus
    maximum_filter_count: int
    filtered_request_count: int
    required_total_request_count: int
    trials: tuple[FilterCapacityTrial, ...]


def _aggregate_observations(
    observations: Iterable[PreviousRunCompanyObservation],
) -> tuple[PreviousRunCompanyObservation, ...]:
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
        PreviousRunCompanyObservation(
            company_key=company_key,
            company_name=str(entry["company_name"]),
            card_count=int(entry["card_count"]),
            first_position=int(entry["first_position"]),
        )
        for company_key, entry in grouped.items()
    )


def select_next_run_filters(
    *,
    observations: Iterable[PreviousRunCompanyObservation],
    reselection_states: Iterable[CompanyReselectionState],
    policy: DynamicFilterPolicy,
    now: datetime,
) -> DynamicFilterSelection:
    """Select filters exclusively from the immediately previous run.

    Active reselection cooldowns normally rotate a company out. A company is
    nevertheless selected when its current n-1 card count or page share reaches
    the configured dominance override. Historical companies absent from n-1 can
    never enter the selection.
    """
    aggregated = _aggregate_observations(observations)
    observed_count = sum(item.card_count for item in aggregated)
    cooldowns = {
        normalize_company_key(state.company_key): state
        for state in reselection_states
        if normalize_company_key(state.company_key)
    }

    ranked = sorted(
        aggregated,
        key=lambda item: (-item.card_count, item.first_position, item.company_key),
    )
    candidates: list[tuple[PreviousRunCompanyObservation, float, bool, bool]] = []
    for item in ranked:
        share = item.card_count / observed_count if observed_count else 0.0
        state = cooldowns.get(item.company_key)
        cooldown_active = bool(
            state and state.cooldown_until and state.cooldown_until > now
        )
        override = cooldown_active and (
            item.card_count >= policy.dominance_override_min_cards
            or share >= policy.dominance_override_min_share
        )
        eligible = not cooldown_active or override
        if eligible:
            candidates.append((item, share, cooldown_active, override))

    selected_keys = {
        item.company_key
        for item, _, _, _ in candidates[: policy.requested_filter_count]
    }
    selection_ranks = {
        item.company_key: index
        for index, (item, _, _, _) in enumerate(
            candidates[: policy.requested_filter_count], start=1
        )
    }

    result_items: list[DynamicFilterSelectionItem] = []
    candidate_metadata = {
        item.company_key: (share, cooldown_active, override)
        for item, share, cooldown_active, override in candidates
    }
    for item in ranked:
        share = item.card_count / observed_count if observed_count else 0.0
        state = cooldowns.get(item.company_key)
        cooldown_active = bool(
            state and state.cooldown_until and state.cooldown_until > now
        )
        _, _, override = candidate_metadata.get(
            item.company_key, (share, cooldown_active, False)
        )
        selected = item.company_key in selected_keys
        if selected and override:
            reason = "selected_by_nminus1_dominance_override"
        elif selected:
            reason = "selected_by_nminus1_displacement_rank"
        elif cooldown_active:
            reason = "rotated_out_by_reselection_cooldown"
        else:
            reason = "below_current_filter_capacity"
        result_items.append(
            DynamicFilterSelectionItem(
                company_key=item.company_key,
                company_name=item.company_name,
                filter_alias=company_not_alias(item.company_key, item.company_name),
                card_count=item.card_count,
                card_share=share,
                first_position=item.first_position,
                cooldown_active=cooldown_active,
                dominance_override_applied=override,
                selected_for_next_run=selected,
                selection_rank=selection_ranks.get(item.company_key),
                selection_reason=reason,
            )
        )

    return DynamicFilterSelection(
        predecessor_observed_count=observed_count,
        predecessor_distinct_company_count=len(aggregated),
        requested_filter_count=policy.requested_filter_count,
        selected_filter_count=len(selected_keys),
        policy_version=policy.policy_version,
        items=tuple(result_items),
    )


def build_filter_capacity_experiment_plan(
    *,
    selection: DynamicFilterSelection,
    transport_name: str,
    transport_status: TransportStatus,
    maximum_filter_count: int,
    request_budget: int,
    include_baseline_controls: bool = True,
) -> FilterCapacityExperimentPlan:
    """Plan a cardinality experiment without performing requests.

    Each cardinality uses the same n-1-derived prefix in forward and reverse
    order. Cardinality one has only one unique permutation. A transport must be
    validated before such an experiment can be planned.
    """
    if transport_status != "validated":
        raise ValueError("filter-capacity experiments require a validated transport")
    if maximum_filter_count < 1:
        raise ValueError("maximum_filter_count must be positive")
    if maximum_filter_count > selection.selected_filter_count:
        raise ValueError("maximum_filter_count exceeds the n-1 selection")
    if not transport_name.strip():
        raise ValueError("transport_name must not be empty")

    selected = selection.selected_items[:maximum_filter_count]
    trials: list[FilterCapacityTrial] = []
    for filter_count in range(1, maximum_filter_count + 1):
        prefix = selected[:filter_count]
        orders = [("forward", prefix)]
        reverse = tuple(reversed(prefix))
        if tuple(item.company_key for item in reverse) != tuple(
            item.company_key for item in prefix
        ):
            orders.append(("reverse", reverse))
        for permutation_name, ordered in orders:
            trials.append(
                FilterCapacityTrial(
                    filter_count=filter_count,
                    permutation_name=permutation_name,
                    company_keys=tuple(item.company_key for item in ordered),
                    aliases=tuple(item.filter_alias for item in ordered),
                )
            )

    baseline_requests = 2 if include_baseline_controls else 0
    required_total = len(trials) + baseline_requests
    if request_budget < required_total:
        raise ValueError(
            f"request_budget={request_budget} is below required_total={required_total}"
        )

    return FilterCapacityExperimentPlan(
        transport_name=transport_name,
        transport_status=transport_status,
        maximum_filter_count=maximum_filter_count,
        filtered_request_count=len(trials),
        required_total_request_count=required_total,
        trials=tuple(trials),
    )
