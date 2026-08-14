"""Shared policy contract for the LLM-BOOST-001 semantic booster cascade.

This module is deliberately pure. It plans bounded provider/model escalation but
performs no network, database, model, lifecycle, gate, ranking or application
operation itself.

Provider/model stages never become product authority. They may only produce
hypotheses or derived evidence for downstream deterministic validators.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
import hashlib
from typing import Iterable

BOOSTER_CONTRACT_VERSION = "LLM-BOOST-001.v1"


class BoosterSurface(StrEnum):
    ORIGIN_DISCOVERY = "origin_discovery"
    LISTING_DISCOVERY = "listing_discovery"
    ATS_DELEGATION = "ats_delegation"
    DETAIL_DISCOVERY = "detail_discovery"
    DETAIL_SEMANTICS = "detail_semantics"
    RECURRING_CONNECTOR = "recurring_connector"


class BoosterStage(StrEnum):
    DETERMINISTIC = "deterministic"
    TAVILY = "tavily"
    LUNA_MEDIUM = "luna_medium"
    TERRA_MEDIUM = "terra_medium"
    SOL_MEDIUM = "sol_medium"
    LUNA_MAX = "luna_max"
    DEEP_EVIDENCE = "deep_evidence_adjudication"


class TavilyState(StrEnum):
    AVAILABLE = "available"
    DISABLED = "disabled"
    MISSING_KEY = "missing_key"
    BUDGET_EXHAUSTED = "budget_exhausted"
    INSUFFICIENT_BUDGET = "insufficient_budget_for_next_request"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    UNKNOWN = "unknown"


CANONICAL_STAGE_ORDER = (
    BoosterStage.DETERMINISTIC,
    BoosterStage.TAVILY,
    BoosterStage.LUNA_MEDIUM,
    BoosterStage.TERRA_MEDIUM,
    BoosterStage.SOL_MEDIUM,
    BoosterStage.LUNA_MAX,
    BoosterStage.DEEP_EVIDENCE,
)

# Accepted planning observations from the 2026-08-12 GPT-5.6 origin campaigns.
# These are empirical means for the compact origin-hypothesis prompt family,
# not universal provider prices. Per-surface smoke campaigns must replace them
# with surface-specific observations before promotion.
EMPIRICAL_EXPECTED_COST_USD = {
    BoosterStage.LUNA_MEDIUM: 0.00494,
    BoosterStage.TERRA_MEDIUM: 0.01124,
    BoosterStage.SOL_MEDIUM: 0.02650,
    BoosterStage.LUNA_MAX: 0.01538,
}

# Existing conservative fail-closed ceilings remain intentionally wider than
# the empirical means until larger per-surface samples exist.
HARD_COST_CEILING_USD = {
    BoosterStage.LUNA_MEDIUM: 0.01,
    BoosterStage.TERRA_MEDIUM: 0.02,
    BoosterStage.SOL_MEDIUM: 0.05,
    BoosterStage.LUNA_MAX: 0.05,
}

# Ordered residual rates observed in the 17 deterministic misses used to form
# the accepted origin cascade. Luna ran on all 17, Terra on the 7 Luna misses,
# Sol on the 5 Luna+Terra misses, and max on the final 4 medium misses.
ORIGIN_EMPIRICAL_REACH_RATE = {
    BoosterStage.LUNA_MEDIUM: 1.0,
    BoosterStage.TERRA_MEDIUM: 7 / 17,
    BoosterStage.SOL_MEDIUM: 5 / 17,
    BoosterStage.LUNA_MAX: 4 / 17,
}

MODEL_CONFIG = {
    BoosterStage.LUNA_MEDIUM: ("gpt-5.6-luna", "medium"),
    BoosterStage.TERRA_MEDIUM: ("gpt-5.6-terra", "medium"),
    BoosterStage.SOL_MEDIUM: ("gpt-5.6-sol", "medium"),
    BoosterStage.LUNA_MAX: ("gpt-5.6-luna", "max"),
}

TAVILY_SKIP_REASON = {
    TavilyState.DISABLED: "tavily_disabled",
    TavilyState.MISSING_KEY: "tavily_missing_key",
    TavilyState.BUDGET_EXHAUSTED: "tavily_budget_exhausted",
    TavilyState.INSUFFICIENT_BUDGET: "tavily_insufficient_budget_for_next_request",
    TavilyState.PROVIDER_UNAVAILABLE: "tavily_provider_unavailable",
    TavilyState.UNKNOWN: "tavily_state_unknown",
}


@dataclass(frozen=True)
class PlannedStage:
    stage: BoosterStage
    eligible: bool
    reason_code: str
    provider: str | None = None
    model: str | None = None
    reasoning_effort: str | None = None
    empirical_expected_cost_usd: float | None = None
    hard_cost_ceiling_usd: float | None = None
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["stage"] = self.stage.value
        return payload


@dataclass(frozen=True)
class BoosterPlan:
    contract_version: str
    surface: BoosterSurface
    stages: tuple[PlannedStage, ...]
    deterministic_resolved: bool
    external_information_gap: bool
    recurring_unchanged_fingerprint: bool
    provider_network_requests: int = 0
    llm_requests: int = 0
    database_requests: int = 0
    product_writes: int = 0
    product_authority: bool = False

    def to_json(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "surface": self.surface.value,
            "stage_order": [stage.stage.value for stage in self.stages],
            "stages": [stage.to_json() for stage in self.stages],
            "deterministic_resolved": self.deterministic_resolved,
            "external_information_gap": self.external_information_gap,
            "recurring_unchanged_fingerprint": self.recurring_unchanged_fingerprint,
            "provider_network_requests": self.provider_network_requests,
            "llm_requests": self.llm_requests,
            "database_requests": self.database_requests,
            "product_writes": self.product_writes,
            "product_authority": self.product_authority,
            "nominal_model_cost_if_all_eligible_reached_usd": round(
                nominal_model_cost_if_all_eligible_reached(self), 8
            ),
        }


def recurring_evidence_fingerprint(
    *,
    connector_id: str,
    source_job_identity: str,
    normalized_evidence_hash: str,
    contract_version: str = BOOSTER_CONTRACT_VERSION,
) -> str:
    """Build the stable recurring semantic-cache identity.

    The function intentionally hashes only already-normalized identifiers. It
    does not fetch, normalize or infer source truth.
    """

    parts = (
        connector_id.strip(),
        source_job_identity.strip(),
        normalized_evidence_hash.strip(),
        contract_version.strip(),
    )
    if any(not part for part in parts):
        raise ValueError("recurring booster fingerprint fields must be non-empty")
    payload = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def origin_empirical_expected_model_cost_usd() -> float:
    """Expected model cost after an origin deterministic miss.

    This is a planning observation from the accepted 17-case cascade, not a
    guaranteed future bill or a replacement for hard per-call ceilings.
    """

    return sum(
        EMPIRICAL_EXPECTED_COST_USD[stage] * ORIGIN_EMPIRICAL_REACH_RATE[stage]
        for stage in (
            BoosterStage.LUNA_MEDIUM,
            BoosterStage.TERRA_MEDIUM,
            BoosterStage.SOL_MEDIUM,
            BoosterStage.LUNA_MAX,
        )
    )


def nominal_model_cost_if_all_eligible_reached(plan: BoosterPlan) -> float:
    return sum(
        float(stage.empirical_expected_cost_usd or 0.0)
        for stage in plan.stages
        if stage.eligible and stage.stage in MODEL_CONFIG
    )


def _stage(
    stage: BoosterStage,
    *,
    eligible: bool,
    reason_code: str,
) -> PlannedStage:
    if stage == BoosterStage.TAVILY:
        return PlannedStage(
            stage=stage,
            eligible=eligible,
            reason_code=reason_code,
            provider="tavily",
        )
    model_config = MODEL_CONFIG.get(stage)
    if model_config is not None:
        model, reasoning = model_config
        return PlannedStage(
            stage=stage,
            eligible=eligible,
            reason_code=reason_code,
            provider="openai",
            model=model,
            reasoning_effort=reasoning,
            empirical_expected_cost_usd=EMPIRICAL_EXPECTED_COST_USD[stage],
            hard_cost_ceiling_usd=HARD_COST_CEILING_USD[stage],
        )
    return PlannedStage(stage=stage, eligible=eligible, reason_code=reason_code)


def _search_is_applicable(
    *,
    surface: BoosterSurface,
    external_information_gap: bool,
) -> bool:
    # Origin discovery is intrinsically an external-information discovery
    # surface. For already-known listings/ATS/details/connectors, Tavily should
    # not become a routine recurring fetch substitute: require a diagnosed gap.
    return surface == BoosterSurface.ORIGIN_DISCOVERY or external_information_gap


def build_booster_plan(
    *,
    surface: BoosterSurface,
    tavily_state: TavilyState,
    deterministic_resolved: bool = False,
    external_information_gap: bool = False,
    recurring_unchanged_fingerprint: bool = False,
) -> BoosterPlan:
    """Plan the canonical deterministic -> search -> model cascade.

    The plan describes eligibility only. It intentionally records zero provider,
    LLM, database and product-write requests because policy planning must remain
    side-effect free.
    """

    stages: list[PlannedStage] = [
        _stage(
            BoosterStage.DETERMINISTIC,
            eligible=True,
            reason_code="deterministic_authority_first",
        )
    ]

    if deterministic_resolved:
        stages.extend(
            _stage(stage, eligible=False, reason_code="deterministic_result_resolved")
            for stage in CANONICAL_STAGE_ORDER[1:]
        )
        return BoosterPlan(
            contract_version=BOOSTER_CONTRACT_VERSION,
            surface=surface,
            stages=tuple(stages),
            deterministic_resolved=True,
            external_information_gap=external_information_gap,
            recurring_unchanged_fingerprint=recurring_unchanged_fingerprint,
        )

    if surface == BoosterSurface.RECURRING_CONNECTOR and recurring_unchanged_fingerprint:
        stages.extend(
            _stage(
                stage,
                eligible=False,
                reason_code="unchanged_recurring_evidence_fingerprint",
            )
            for stage in CANONICAL_STAGE_ORDER[1:]
        )
        return BoosterPlan(
            contract_version=BOOSTER_CONTRACT_VERSION,
            surface=surface,
            stages=tuple(stages),
            deterministic_resolved=False,
            external_information_gap=external_information_gap,
            recurring_unchanged_fingerprint=True,
        )

    search_applicable = _search_is_applicable(
        surface=surface,
        external_information_gap=external_information_gap,
    )
    if not search_applicable:
        stages.append(
            _stage(
                BoosterStage.TAVILY,
                eligible=False,
                reason_code="external_search_not_indicated",
            )
        )
    elif tavily_state == TavilyState.AVAILABLE:
        stages.append(
            _stage(
                BoosterStage.TAVILY,
                eligible=True,
                reason_code="tavily_available_with_budget",
            )
        )
    else:
        stages.append(
            _stage(
                BoosterStage.TAVILY,
                eligible=False,
                reason_code=TAVILY_SKIP_REASON[tavily_state],
            )
        )

    # Tavily state is deliberately not consulted here. Search exhaustion,
    # disablement, missing credentials or provider failure must never block the
    # semantic model cascade after an unresolved deterministic result.
    for stage in (
        BoosterStage.LUNA_MEDIUM,
        BoosterStage.TERRA_MEDIUM,
        BoosterStage.SOL_MEDIUM,
        BoosterStage.LUNA_MAX,
    ):
        stages.append(
            _stage(
                stage,
                eligible=True,
                reason_code="eligible_after_prior_unresolved_stage",
            )
        )

    stages.append(
        _stage(
            BoosterStage.DEEP_EVIDENCE,
            eligible=True,
            reason_code="eligible_after_model_residual",
        )
    )

    return BoosterPlan(
        contract_version=BOOSTER_CONTRACT_VERSION,
        surface=surface,
        stages=tuple(stages),
        deterministic_resolved=False,
        external_information_gap=external_information_gap,
        recurring_unchanged_fingerprint=False,
    )


def stage_names(plan: BoosterPlan) -> tuple[str, ...]:
    return tuple(stage.stage.value for stage in plan.stages)


def eligible_stage_names(plan: BoosterPlan) -> tuple[str, ...]:
    return tuple(stage.stage.value for stage in plan.stages if stage.eligible)


def assert_canonical_order(stages: Iterable[BoosterStage]) -> None:
    values = tuple(stages)
    if values != CANONICAL_STAGE_ORDER:
        raise ValueError(
            "LLM-BOOST-001 stage order drift: "
            f"expected={tuple(item.value for item in CANONICAL_STAGE_ORDER)} "
            f"actual={tuple(item.value for item in values)}"
        )
