"""StepStone company-discovery cycle planning.

This module keeps StepStone discovery focused on company blocks rather than
permanent company blacklists or search-term mutation. It plans a bounded,
reviewable fetch-time NOT probe for whitelisted search terms and temporary
company cooldowns.

Boundaries:
- no external requests
- no DB writes
- no Bronze/Silver writes
- no candidate creation
- no connector/source activation
- no scheduler mutation
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable

from src.normalization.company_keys import normalize_company_key


DEFAULT_NOT_ENABLED_SEARCH_TERMS = frozenset({"data engineer", "analytics engineer"})
DEFAULT_MIN_INTERVAL_DAYS = 1
DEFAULT_MAX_INTERVAL_DAYS = 14
DEFAULT_START_INTERVAL_DAYS = 3
DEFAULT_MAX_NOT_TERMS_PER_REQUEST = 6
DEFAULT_EXCLUSION_WAVE_INDEX = 0
DEFAULT_COOLDOWN_DAYS = 7
DEFAULT_DOMINANT_COMPANY_THRESHOLD = 2

SAFE_COMPANY_NOT_ALIASES = {
    "adesso": "adesso",
    "deutsche_bahn": "Deutsche Bahn",
    "enercity": "enercity",
    "finanz_informatik": "Finanz Informatik",
    "hdi": "HDI",
    "hdi_global": "HDI",
    "hdi_group": "HDI",
    "ratiodata": "Ratiodata",
}

LEGAL_SUFFIX_TOKENS = (
    " gmbh & co. kg",
    " gmbh & co kg",
    " gmbh",
    " ag",
    " se",
    " group",
    " holding",
)

RELEVANCE_TOKENS = frozenset(
    {
        "data",
        "daten",
        "analytics",
        "analyst",
        "engineer",
        "entwickler",
        "etl",
        "warehouse",
        "business intelligence",
        "bi",
        "sql",
        "python",
        "cloud",
        "azure",
        "aws",
        "ml",
        "ki",
        "ai",
        "mlops",
        "devops",
        "database",
        "datenbank",
        "platform",
        "plattform",
        "migration",
        "reporting",
    }
)

DRIFT_TOKENS = frozenset(
    {
        "bauleiter",
        "gleisbau",
        "lager",
        "logistik",
        "transportarbeiter",
        "duales studium",
        "verkauf",
        "teilzeit",
        "vertrieb",
        "sales manager",
        "monteur",
    }
)


@dataclass(frozen=True)
class CompanyCooldown:
    company_key: str
    company_name: str
    source_name: str
    search_profile_name: str
    search_term: str
    cooldown_until: datetime
    reason: str
    evidence_count: int = 0


@dataclass(frozen=True)
class SearchTermCycleState:
    source_name: str
    search_profile_name: str
    search_term: str
    current_interval_days: int = DEFAULT_START_INTERVAL_DAYS
    min_interval_days: int = DEFAULT_MIN_INTERVAL_DAYS
    max_interval_days: int = DEFAULT_MAX_INTERVAL_DAYS
    last_run_at: datetime | None = None
    next_due_at: datetime | None = None
    quality_score: float | None = None
    is_not_exclusion_enabled: bool = False


@dataclass(frozen=True)
class CompanyObservation:
    company_key: str
    company_name: str
    title: str
    source_url: str | None = None


@dataclass(frozen=True)
class StepStoneCompanyDiscoveryPlan:
    source_name: str
    search_profile_name: str
    search_term: str
    base_query: str
    planned_query: str
    not_company_names: tuple[str, ...]
    not_company_keys: tuple[str, ...]
    action: str
    reason: str
    boundary: dict[str, object]


@dataclass(frozen=True)
class CompanyCooldownProposal:
    company_key: str
    company_name: str
    evidence_count: int
    cooldown_days: int
    reason: str
    sample_titles: tuple[str, ...]


@dataclass(frozen=True)
class StepStoneDiscoveryAssessment:
    search_term: str
    observed_count: int
    distinct_company_count: int
    known_cooldown_hit_count: int
    new_company_count: int
    relevance_hits: int
    drift_hits: int
    quality_score: float
    recommended_interval_days: int
    cooldown_proposals: tuple[CompanyCooldownProposal, ...]
    reason: str


def utc_now() -> datetime:
    return datetime.now(UTC)


def _lower(value: str | None) -> str:
    return (value or "").strip().lower()


def company_not_alias(company_key: str, company_name: str) -> str:
    """Return a short, StepStone-friendly company NOT token.

    Validation showed that long legal names such as
    ``Finanz Informatik GmbH & Co. KG`` can collapse the result page, while
    short aliases such as ``Finanz Informatik`` remain useful. This function
    therefore normalizes only the NOT token. It does not change canonical
    company identity and does not make suppression permanent.
    """
    normalized_key = normalize_company_key(company_key or company_name)
    if normalized_key in SAFE_COMPANY_NOT_ALIASES:
        return SAFE_COMPANY_NOT_ALIASES[normalized_key]

    value = str(company_name or company_key or "").strip().replace('"', "")
    lower_value = value.lower()
    for suffix in LEGAL_SUFFIX_TOKENS:
        if lower_value.endswith(suffix):
            value = value[: -len(suffix)].strip(" ,.-")
            break
    return value


def normalize_cooldown_for_not(cooldown: CompanyCooldown) -> CompanyCooldown:
    alias = company_not_alias(cooldown.company_key, cooldown.company_name)
    return CompanyCooldown(
        company_key=cooldown.company_key,
        company_name=alias,
        source_name=cooldown.source_name,
        search_profile_name=cooldown.search_profile_name,
        search_term=cooldown.search_term,
        cooldown_until=cooldown.cooldown_until,
        reason=cooldown.reason,
        evidence_count=cooldown.evidence_count,
    )


def is_not_exclusion_supported_for_term(
    search_term: str,
    enabled_terms: Iterable[str] = DEFAULT_NOT_ENABLED_SEARCH_TERMS,
) -> bool:
    normalized = _lower(search_term)
    return normalized in {_lower(term) for term in enabled_terms}


def active_cooldowns(
    cooldowns: Iterable[CompanyCooldown],
    *,
    source_name: str,
    search_profile_name: str,
    search_term: str,
    now: datetime | None = None,
) -> tuple[CompanyCooldown, ...]:
    reference = now or utc_now()
    return tuple(
        cooldown
        for cooldown in cooldowns
        if cooldown.source_name == source_name
        and cooldown.search_profile_name == search_profile_name
        and _lower(cooldown.search_term) == _lower(search_term)
        and cooldown.cooldown_until > reference
    )


def build_not_query(search_term: str, company_names: Iterable[str]) -> str:
    """Append NOT clauses for company names only.

    Search terms are deliberately not negated. Company exclusions are temporary
    visibility controls, not search-term learning or permanent blacklist logic.
    """
    cleaned_companies: list[str] = []
    for company_name in company_names:
        value = str(company_name or "").strip()
        if not value:
            continue
        if value.upper().startswith("NOT "):
            raise ValueError("Company names must not include NOT clauses.")
        cleaned_companies.append(value.replace('"', ""))

    if not cleaned_companies:
        return search_term

    return f"{search_term} " + " ".join(f'NOT "{company_name}"' for company_name in cleaned_companies)


def build_company_discovery_plan(
    *,
    source_name: str,
    search_profile_name: str,
    search_term: str,
    cooldowns: Iterable[CompanyCooldown],
    enabled_terms: Iterable[str] = DEFAULT_NOT_ENABLED_SEARCH_TERMS,
    max_not_terms_per_request: int | None = DEFAULT_MAX_NOT_TERMS_PER_REQUEST,
    exclusion_wave_index: int = DEFAULT_EXCLUSION_WAVE_INDEX,
    now: datetime | None = None,
) -> StepStoneCompanyDiscoveryPlan:
    boundary = {
        "company_cooldowns_are_temporary": True,
        "search_terms_are_not_negated": True,
        "no_pagination": True,
        "no_detail_pages": True,
        "no_candidate_creation": True,
        "no_connector_activation": True,
        "no_bronze_or_silver_write": True,
        "no_scheduler_mutation": True,
        "logical_cooldown_pool_is_not_capped": True,
        "not_terms_are_request_budgeted": True,
        "exclusion_wave_index": exclusion_wave_index,
        "max_not_terms_per_request": max_not_terms_per_request,
        "cooldown_pool_size": 0,
        "selected_wave_size": 0,
        "wave_start_index": 0,
        "wave_end_index": 0,
    }

    if not is_not_exclusion_supported_for_term(search_term, enabled_terms):
        return StepStoneCompanyDiscoveryPlan(
            source_name=source_name,
            search_profile_name=search_profile_name,
            search_term=search_term,
            base_query=search_term,
            planned_query=search_term,
            not_company_names=(),
            not_company_keys=(),
            action="run_baseline_only",
            reason="NOT exclusion is not enabled for this search term; keep baseline query only.",
            boundary=boundary,
        )

    cooldown_pool = tuple(
        normalize_cooldown_for_not(cooldown)
        for cooldown in sorted(
            active_cooldowns(
                cooldowns,
                source_name=source_name,
                search_profile_name=search_profile_name,
                search_term=search_term,
                now=now,
            ),
            key=lambda item: (-item.evidence_count, item.company_key),
        )
        if company_not_alias(cooldown.company_key, cooldown.company_name)
    )

    if max_not_terms_per_request is None or max_not_terms_per_request <= 0:
        start = 0
        end = len(cooldown_pool)
        eligible_cooldowns = cooldown_pool
    else:
        start = max(0, exclusion_wave_index) * max_not_terms_per_request
        end = start + max_not_terms_per_request
        eligible_cooldowns = cooldown_pool[start:end]

    boundary.update(
        {
            "cooldown_pool_size": len(cooldown_pool),
            "selected_wave_size": len(eligible_cooldowns),
            "wave_start_index": start,
            "wave_end_index": min(end, len(cooldown_pool)),
        }
    )

    company_names = tuple(cooldown.company_name for cooldown in eligible_cooldowns)
    company_keys = tuple(cooldown.company_key for cooldown in eligible_cooldowns)
    planned_query = build_not_query(search_term, company_names)

    if not company_names:
        if cooldown_pool:
            return StepStoneCompanyDiscoveryPlan(
                source_name=source_name,
                search_profile_name=search_profile_name,
                search_term=search_term,
                base_query=search_term,
                planned_query=search_term,
                not_company_names=(),
                not_company_keys=(),
                action="skip_empty_exclusion_wave",
                reason=(
                    "The logical cooldown pool exists, but the selected request wave is empty; "
                    "skip this probe instead of falling back to a duplicate baseline fetch."
                ),
                boundary=boundary,
            )

        return StepStoneCompanyDiscoveryPlan(
            source_name=source_name,
            search_profile_name=search_profile_name,
            search_term=search_term,
            base_query=search_term,
            planned_query=planned_query,
            not_company_names=(),
            not_company_keys=(),
            action="run_baseline_learning",
            reason="No active company cooldowns exist for this search term yet.",
            boundary=boundary,
        )

    return StepStoneCompanyDiscoveryPlan(
        source_name=source_name,
        search_profile_name=search_profile_name,
        search_term=search_term,
        base_query=search_term,
        planned_query=planned_query,
        not_company_names=company_names,
        not_company_keys=company_keys,
        action="run_fetch_time_company_not_probe",
        reason="Active temporary company cooldowns can be used as a bounded NOT request wave to reveal another company block.",
        boundary=boundary,
    )


def _contains_any(value: str, tokens: Iterable[str]) -> bool:
    lower = value.lower()
    return any(token in lower for token in tokens)


def build_cooldown_proposals(
    observations: Iterable[CompanyObservation],
    *,
    cooldown_days: int = DEFAULT_COOLDOWN_DAYS,
    dominant_company_threshold: int = DEFAULT_DOMINANT_COMPANY_THRESHOLD,
) -> tuple[CompanyCooldownProposal, ...]:
    grouped: dict[str, dict[str, object]] = {}
    for observation in observations:
        company_key = normalize_company_key(observation.company_key or observation.company_name)
        if not company_key:
            continue
        entry = grouped.setdefault(
            company_key,
            {"company_name": observation.company_name, "count": 0, "titles": []},
        )
        entry["count"] = int(entry["count"]) + 1
        titles = entry["titles"]
        if isinstance(titles, list) and observation.title and observation.title not in titles and len(titles) < 5:
            titles.append(observation.title)

    proposals: list[CompanyCooldownProposal] = []
    for company_key, entry in grouped.items():
        count = int(entry["count"])
        if count < dominant_company_threshold:
            continue
        proposals.append(
            CompanyCooldownProposal(
                company_key=company_key,
                company_name=str(entry["company_name"]),
                evidence_count=count,
                cooldown_days=cooldown_days,
                reason="company produced enough observations in this search space; temporarily suppress to reveal the next company block",
                sample_titles=tuple(str(title) for title in entry["titles"]),
            )
        )
    return tuple(sorted(proposals, key=lambda item: (-item.evidence_count, item.company_key)))


def adapt_interval_days(
    *,
    current_interval_days: int,
    quality_score: float,
    min_interval_days: int = DEFAULT_MIN_INTERVAL_DAYS,
    max_interval_days: int = DEFAULT_MAX_INTERVAL_DAYS,
) -> int:
    if quality_score >= 0.70:
        return max(min_interval_days, current_interval_days - 1)
    if quality_score <= 0.30:
        return min(max_interval_days, current_interval_days + 2)
    if quality_score <= 0.50:
        return min(max_interval_days, current_interval_days + 1)
    return current_interval_days


def assess_discovery_observations(
    *,
    search_term: str,
    observations: Iterable[CompanyObservation],
    cooldown_company_keys: Iterable[str],
    current_interval_days: int = DEFAULT_START_INTERVAL_DAYS,
    min_interval_days: int = DEFAULT_MIN_INTERVAL_DAYS,
    max_interval_days: int = DEFAULT_MAX_INTERVAL_DAYS,
) -> StepStoneDiscoveryAssessment:
    observation_list = list(observations)
    cooldown_keys = {normalize_company_key(key) for key in cooldown_company_keys if key}
    company_keys = {normalize_company_key(obs.company_key or obs.company_name) for obs in observation_list}
    company_keys.discard("")
    known_hits = sum(
        1
        for obs in observation_list
        if normalize_company_key(obs.company_key or obs.company_name) in cooldown_keys
    )
    relevance_hits = sum(1 for obs in observation_list if _contains_any(obs.title, RELEVANCE_TOKENS))
    drift_hits = sum(1 for obs in observation_list if _contains_any(obs.title, DRIFT_TOKENS))
    new_company_count = len(company_keys - cooldown_keys)

    if not observation_list:
        quality_score = 0.0
        assessment_reason = (
            "no results after company-cooldown query; this is a valid cycle signal "
            "and may mean the search space is exhausted for the current NOT wave "
            "or the query is over-constrained"
        )
    else:
        relevance_ratio = relevance_hits / len(observation_list)
        drift_penalty = drift_hits / len(observation_list)
        known_penalty = known_hits / len(observation_list)
        novelty_bonus = min(new_company_count / 10, 1) * 0.25
        quality_score = max(0.0, min(1.0, relevance_ratio - drift_penalty - known_penalty + novelty_bonus))
        assessment_reason = (
            "adaptive company-discovery assessment; high-quality spaces get shorter cycles, "
            "low-yield spaces get longer cycles, max interval prevents starvation"
        )

    recommended_interval = adapt_interval_days(
        current_interval_days=current_interval_days,
        quality_score=quality_score,
        min_interval_days=min_interval_days,
        max_interval_days=max_interval_days,
    )

    return StepStoneDiscoveryAssessment(
        search_term=search_term,
        observed_count=len(observation_list),
        distinct_company_count=len(company_keys),
        known_cooldown_hit_count=known_hits,
        new_company_count=new_company_count,
        relevance_hits=relevance_hits,
        drift_hits=drift_hits,
        quality_score=round(quality_score, 2),
        recommended_interval_days=recommended_interval,
        cooldown_proposals=build_cooldown_proposals(observation_list),
        reason=assessment_reason,
    )
