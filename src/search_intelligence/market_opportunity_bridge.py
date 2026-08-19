from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from src.search_intelligence.product_v1_origin_vacancy_bridge import SilverContender


REMOTE_SIGNALS = {"remote_possible", "remote_first"}
RISK_BLOCKING_GATE_STATES = {"failed", "manual_review_required", "deferred"}


@dataclass(frozen=True)
class MarketOpportunity:
    opportunity_id: int
    company_name: str
    title: str
    observation_channel: str
    evidence_url: str | None
    observed_at: str | None
    location: str | None
    remote_signal: str


def opportunity_geography(opportunity: MarketOpportunity) -> tuple[str | None, str | None, str]:
    location = (opportunity.location or "").strip()
    folded = location.casefold()
    if "hannover" in folded or "hanover" in folded:
        return "Hannover", "Deutschland", "hannover_explicit"
    if opportunity.remote_signal in REMOTE_SIGNALS and (
        "deutschland" in folded or "germany" in folded or not location
    ):
        return None, "Deutschland", "germany_remote"
    if "deutschland" in folded or "germany" in folded:
        return None, "Deutschland", "commute_or_geography_review_required"
    return None, None, "commute_or_geography_review_required"


def opportunity_to_contender(opportunity: MarketOpportunity) -> SilverContender:
    city, country, geography_bucket = opportunity_geography(opportunity)
    return SilverContender(
        inspection_priority=opportunity.opportunity_id,
        silver_job_id=opportunity.opportunity_id,
        title=opportunity.title,
        company_name=opportunity.company_name,
        city=city,
        country=country,
        source_name=opportunity.observation_channel,
        source_url=opportunity.evidence_url or "",
        canonical_source_type=None,
        lifecycle_status="unverifiable",
        geography_bucket=geography_bucket,
    )


def risk_gate_blocks(
    *,
    candidate_risk_level: str | None,
    risk_gate: Mapping[str, object] | None,
) -> bool:
    if str(candidate_risk_level or "").casefold() in {"high", "blocked"}:
        return True
    if not risk_gate:
        return False
    return str(risk_gate.get("gate_status") or "") in RISK_BLOCKING_GATE_STATES


def bridge_outcome_from_exact_status(status: str | None) -> tuple[str, str]:
    if status == "current_vacancy_confirmed":
        return "verified_active", "Exact employer-origin vacancy title and current activity were confirmed."
    if status == "inactive_vacancy_confirmed":
        return "verified_closed", "Exact employer-origin vacancy title was confirmed and the vacancy is closed."
    if status == "no_concrete_detail_candidates":
        return "detail_candidate_required", "No concrete employer-origin detail candidate was found within the bounded discovery envelope."
    return "unverifiable", "Bounded exact-vacancy verification did not establish authoritative current vacancy state."


def product_authority_boundary() -> dict[str, bool]:
    return {
        "market_evidence_remains_observational": True,
        "provider_output_is_hypothesis_only": True,
        "deterministic_exact_title_revalidation_required": True,
        "deterministic_geography_revalidation_required_for_active": True,
        "risk_gate_never_overridden": True,
        "silver_write": False,
        "ranking_authority": False,
        "application_authority": False,
        "source_activation": False,
    }
