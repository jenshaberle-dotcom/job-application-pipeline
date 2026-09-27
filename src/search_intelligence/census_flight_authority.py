"""Explicit authority for job-first Census external-index flights."""
from __future__ import annotations

from dataclasses import dataclass

from src.search_intelligence.public_web_search import BACKEND_POLICIES


DEFAULT_CENSUS_EXTERNAL_INDEX_BACKEND = "none"
CENSUS_EXTERNAL_INDEX_BACKENDS = ("none", "tavily")


@dataclass(frozen=True)
class CensusFlightAuthority:
    provider: str
    status: str
    external_requests_authorized: bool
    paid_external_tool: bool
    reason: str


def resolve_census_flight_authority(
    *,
    provider: str,
    allow_paid_external_provider: bool = False,
) -> CensusFlightAuthority:
    """Resolve transport authority without granting direct board automation."""
    if provider not in CENSUS_EXTERNAL_INDEX_BACKENDS:
        raise ValueError(f"Unsupported Census external-index backend: {provider}")

    if provider == "none":
        return CensusFlightAuthority(
            provider="none",
            status="plan_only",
            external_requests_authorized=False,
            paid_external_tool=False,
            reason="default_zero_request_mode",
        )

    policy = BACKEND_POLICIES[provider]
    if policy.paid_external_tool and not allow_paid_external_provider:
        return CensusFlightAuthority(
            provider=provider,
            status="operator_authorization_required",
            external_requests_authorized=False,
            paid_external_tool=True,
            reason="paid_external_provider_requires_explicit_opt_in",
        )

    return CensusFlightAuthority(
        provider=provider,
        status="authorized",
        external_requests_authorized=True,
        paid_external_tool=policy.paid_external_tool,
        reason="explicit_operator_selected_external_index_transport",
    )
