"""Market-sensor to employer-origin candidate funnel analysis.

EO-001 is an audit layer. It quantifies how many companies discovered by
market sensors enter the employer-origin connector candidate funnel. It does
not create candidates, browse external sources, activate connectors, write
Bronze/Silver data, or change scheduler state.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class MarketSensorItem:
    """One company observation promoted into candidate-expansion review state."""

    item_id: int
    company_key: str
    company_name: str
    source_name: str
    decision: str
    priority: int
    evidence_count: int
    distinct_search_term_count: int = 0
    sample_title_count: int = 0
    known_candidate_id: int | None = None
    known_candidate_status: str | None = None
    recommended_next_action: str = ""
    reason: str = ""


@dataclass(frozen=True)
class ConnectorCandidate:
    """One modeled employer-origin source candidate."""

    candidate_id: int
    company_key: str
    company_name: str
    status: str
    candidate_url: str | None = None


@dataclass(frozen=True)
class FunnelSummary:
    """Top-level funnel counts."""

    market_sensor_companies: int
    connector_candidate_companies: int
    with_connector_candidate: int
    without_connector_candidate: int

    @property
    def connector_candidate_share_percent(self) -> float:
        if self.market_sensor_companies == 0:
            return 0.0
        return round(100.0 * self.with_connector_candidate / self.market_sensor_companies, 2)


@dataclass(frozen=True)
class CompanyFunnelGap:
    """A market-observed company that has not reached the connector funnel."""

    company_key: str
    company_name: str
    item_count: int
    max_priority: int
    evidence_count: int
    distinct_search_term_count: int
    sample_title_count: int
    decisions: tuple[str, ...]
    recommended_next_actions: tuple[str, ...]
    suggested_funnel_action: str


def distinct_market_company_keys(items: Iterable[MarketSensorItem]) -> set[str]:
    return {item.company_key for item in items if item.company_key}


def distinct_connector_company_keys(candidates: Iterable[ConnectorCandidate]) -> set[str]:
    return {candidate.company_key for candidate in candidates if candidate.company_key}


def summarize_funnel(
    market_items: Iterable[MarketSensorItem],
    connector_candidates: Iterable[ConnectorCandidate],
) -> FunnelSummary:
    market_keys = distinct_market_company_keys(market_items)
    connector_keys = distinct_connector_company_keys(connector_candidates)
    with_candidate = market_keys & connector_keys
    return FunnelSummary(
        market_sensor_companies=len(market_keys),
        connector_candidate_companies=len(connector_keys),
        with_connector_candidate=len(with_candidate),
        without_connector_candidate=len(market_keys - connector_keys),
    )


def count_market_companies_by_decision(items: Iterable[MarketSensorItem]) -> dict[str, int]:
    by_decision: dict[str, set[str]] = defaultdict(set)
    for item in items:
        by_decision[item.decision].add(item.company_key)
    return {decision: len(company_keys) for decision, company_keys in sorted(by_decision.items())}


def count_connector_companies_by_status(candidates: Iterable[ConnectorCandidate]) -> dict[str, int]:
    by_status: dict[str, set[str]] = defaultdict(set)
    for candidate in candidates:
        by_status[candidate.status].add(candidate.company_key)
    return {status: len(company_keys) for status, company_keys in sorted(by_status.items())}


def suggested_funnel_action_for_decisions(decisions: Iterable[str]) -> str:
    decision_set = set(decisions)
    if "create_candidate_recommended" in decision_set:
        return "promotion_gap_create_candidate_recommended"
    if "manual_review_required" in decision_set:
        return "promotion_gap_manual_review_required"
    if "insufficient_evidence" in decision_set:
        return "observe_more_before_promotion"
    if "already_known" in decision_set or "active_candidate_monitoring" in decision_set:
        return "check_stale_known_candidate_linkage"
    if "suppress_as_noise" in decision_set:
        return "suppressed_as_noise"
    return "review_unclassified_market_sensor_state"


def companies_without_connector_candidate(
    market_items: Iterable[MarketSensorItem],
    connector_candidates: Iterable[ConnectorCandidate],
) -> list[CompanyFunnelGap]:
    connector_keys = distinct_connector_company_keys(connector_candidates)
    grouped: dict[str, list[MarketSensorItem]] = defaultdict(list)
    for item in market_items:
        if item.company_key not in connector_keys:
            grouped[item.company_key].append(item)

    gaps: list[CompanyFunnelGap] = []
    for company_key, items in grouped.items():
        decisions = tuple(sorted({item.decision for item in items}))
        recommended_actions = tuple(
            sorted({item.recommended_next_action for item in items if item.recommended_next_action})
        )
        gaps.append(
            CompanyFunnelGap(
                company_key=company_key,
                company_name=sorted({item.company_name for item in items})[0],
                item_count=len(items),
                max_priority=max(item.priority for item in items),
                evidence_count=sum(item.evidence_count for item in items),
                distinct_search_term_count=sum(item.distinct_search_term_count for item in items),
                sample_title_count=sum(item.sample_title_count for item in items),
                decisions=decisions,
                recommended_next_actions=recommended_actions,
                suggested_funnel_action=suggested_funnel_action_for_decisions(decisions),
            )
        )
    gaps.sort(
        key=lambda gap: (
            gap.suggested_funnel_action != "promotion_gap_create_candidate_recommended",
            -gap.max_priority,
            -gap.evidence_count,
            gap.company_key,
        )
    )
    return gaps
