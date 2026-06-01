"""Aggregator novelty loop assessment for bounded exploration sources.

The novelty loop answers a deliberately narrow question: is a bounded
aggregator/source-result run still producing truly new company or vocabulary
evidence, or are repeated known companies/terms dominating the limited result
window?

Important terminology:
- "unregistered" means the company is not yet an employer-origin candidate.
- "newly observed" means the company/term was not present in the previous
  persisted novelty snapshot for the same source/search scope.

This distinction matters for defensive sources such as StepStone: a company can
be unregistered but still not be new across cycles. The loop therefore measures
cycle novelty separately from the candidate backlog.

It does not fetch external pages, mutate search profiles, activate sources,
write Bronze records or change schedules.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from src.normalization.company_keys import company_key_matches, normalize_company_key
from src.search_intelligence.company_vocabulary import extract_vocabulary_terms


@dataclass(frozen=True)
class KnownCompanyCandidate:
    candidate_id: int
    company_key: str
    company_name: str
    status: str
    source_family_candidate: str | None = None


@dataclass(frozen=True)
class PreviousNoveltySnapshot:
    snapshot_id: int
    company_keys: frozenset[str]
    company_term_keys: frozenset[str]


@dataclass(frozen=True)
class AggregatorEvidenceRow:
    evidence_id: int | None
    source_name: str
    company_key: str
    company_name: str
    title: str
    search_profile_name: str | None = None
    search_term: str | None = None
    evidence_url: str | None = None
    observed_at: str | None = None


@dataclass(frozen=True)
class AggregatorNoveltyItem:
    item_type: str
    novelty_state: str
    source_name: str
    company_key: str | None
    company_name: str | None
    title: str | None = None
    search_profile_name: str | None = None
    search_term: str | None = None
    observed_term: str | None = None
    known_candidate_id: int | None = None
    known_candidate_status: str | None = None
    evidence_url: str | None = None
    observed_at: str | None = None
    evidence: dict[str, object] | None = None


@dataclass(frozen=True)
class AggregatorNoveltySnapshot:
    source_name: str
    search_profile_name: str | None
    search_term: str | None
    cycle_scope: str
    previous_snapshot_id: int | None
    observed_since: str | None
    observed_until: str | None
    evidence_count: int
    distinct_company_count: int
    unregistered_company_count: int
    known_candidate_company_count: int
    newly_observed_company_count: int
    repeated_observed_company_count: int
    reassessment_company_count: int
    new_vocabulary_term_count: int
    known_vocabulary_term_count: int
    newly_observed_term_count: int
    repeated_observed_term_count: int
    novelty_score: Decimal
    saturation_level: str
    recommended_action: str
    reason: str
    items: tuple[AggregatorNoveltyItem, ...]
    evidence: dict[str, object]


REASSESSMENT_STATUSES = {
    "manual_review_required",
    "candidate",
    "connector_candidate",
    "watchlist",
    "blocked",
    "deferred",
    "degraded",
}


CYCLE_SCOPE = "bounded_aggregator_market_evidence"


def _round_score(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _candidate_key_values(candidate: KnownCompanyCandidate) -> tuple[str, ...]:
    values = [candidate.company_key]
    if candidate.source_family_candidate:
        values.append(candidate.source_family_candidate)
    values.append(candidate.company_name)
    return tuple(key for key in (normalize_company_key(value) for value in values) if key)


def _match_candidate(
    company_key: str,
    candidates: Iterable[KnownCompanyCandidate],
) -> KnownCompanyCandidate | None:
    normalized = normalize_company_key(company_key)
    if not normalized:
        return None

    for candidate in candidates:
        for candidate_key in _candidate_key_values(candidate):
            if company_key_matches(normalized, candidate_key):
                return candidate
    return None


def _known_terms_for_company(
    *,
    company_key: str,
    known_vocabulary_terms: dict[str, set[str]],
) -> set[str]:
    normalized = normalize_company_key(company_key)
    terms: set[str] = set()
    for known_company_key, known_terms in known_vocabulary_terms.items():
        if company_key_matches(normalized, normalize_company_key(known_company_key)):
            terms.update(known_terms)
    return terms


def _company_term_key(company_key: str, term: str) -> str:
    return f"{normalize_company_key(company_key)}::{term}"


def _previous_company_keys(previous_snapshot: PreviousNoveltySnapshot | None) -> set[str]:
    return set(previous_snapshot.company_keys) if previous_snapshot else set()


def _previous_company_term_keys(previous_snapshot: PreviousNoveltySnapshot | None) -> set[str]:
    return set(previous_snapshot.company_term_keys) if previous_snapshot else set()


def build_aggregator_novelty_snapshot(
    *,
    rows: Iterable[AggregatorEvidenceRow],
    known_candidates: Iterable[KnownCompanyCandidate],
    known_vocabulary_terms: dict[str, set[str]],
    source_name: str,
    search_profile_name: str | None = None,
    search_term: str | None = None,
    previous_snapshot: PreviousNoveltySnapshot | None = None,
) -> AggregatorNoveltySnapshot:
    evidence_rows = list(rows)
    candidates = list(known_candidates)
    items: list[AggregatorNoveltyItem] = []

    company_states: dict[str, tuple[str, str, KnownCompanyCandidate | None]] = {}
    observed_terms_by_company: dict[str, set[str]] = {}
    current_company_term_keys: set[str] = set()
    known_vocabulary_term_count = 0
    new_vocabulary_term_count = 0

    previous_companies = _previous_company_keys(previous_snapshot)
    previous_terms = _previous_company_term_keys(previous_snapshot)

    observed_times = [row.observed_at for row in evidence_rows if row.observed_at]
    observed_since = min(observed_times) if observed_times else None
    observed_until = max(observed_times) if observed_times else None

    for row in evidence_rows:
        normalized_company_key = normalize_company_key(row.company_key or row.company_name)
        if not normalized_company_key:
            continue

        candidate = _match_candidate(normalized_company_key, candidates)
        registry_state = "known_candidate_company" if candidate else "unregistered_company"
        cycle_state = (
            "repeated_observed_company"
            if normalized_company_key in previous_companies
            else "newly_observed_company"
        )
        company_states.setdefault(normalized_company_key, (registry_state, cycle_state, candidate))

        items.append(
            AggregatorNoveltyItem(
                item_type="company",
                novelty_state=registry_state,
                source_name=row.source_name,
                company_key=normalized_company_key,
                company_name=row.company_name,
                title=row.title,
                search_profile_name=row.search_profile_name,
                search_term=row.search_term,
                known_candidate_id=candidate.candidate_id if candidate else None,
                known_candidate_status=candidate.status if candidate else None,
                evidence_url=row.evidence_url,
                observed_at=row.observed_at,
                evidence={
                    "evidence_id": row.evidence_id,
                    "cycle_novelty_state": cycle_state,
                },
            )
        )

        if candidate and candidate.status in REASSESSMENT_STATUSES:
            items.append(
                AggregatorNoveltyItem(
                    item_type="candidate_reassessment",
                    novelty_state="known_candidate_reassessment",
                    source_name=row.source_name,
                    company_key=normalized_company_key,
                    company_name=row.company_name,
                    title=row.title,
                    search_profile_name=row.search_profile_name,
                    search_term=row.search_term,
                    known_candidate_id=candidate.candidate_id,
                    known_candidate_status=candidate.status,
                    evidence_url=row.evidence_url,
                    observed_at=row.observed_at,
                    evidence={
                        "evidence_id": row.evidence_id,
                        "cycle_novelty_state": cycle_state,
                    },
                )
            )

        known_terms = _known_terms_for_company(
            company_key=normalized_company_key,
            known_vocabulary_terms=known_vocabulary_terms,
        )
        for term in extract_vocabulary_terms(row.title):
            term_key = _company_term_key(normalized_company_key, term)
            current_company_term_keys.add(term_key)
            observed_terms_by_company.setdefault(normalized_company_key, set()).add(term)
            vocabulary_state = "known_vocabulary_term" if term in known_terms else "new_vocabulary_term"
            cycle_term_state = (
                "repeated_observed_term"
                if term_key in previous_terms
                else "newly_observed_term"
            )
            if vocabulary_state == "known_vocabulary_term":
                known_vocabulary_term_count += 1
            else:
                new_vocabulary_term_count += 1
            items.append(
                AggregatorNoveltyItem(
                    item_type="term",
                    novelty_state=vocabulary_state,
                    source_name=row.source_name,
                    company_key=normalized_company_key,
                    company_name=row.company_name,
                    title=row.title,
                    search_profile_name=row.search_profile_name,
                    search_term=row.search_term,
                    observed_term=term,
                    known_candidate_id=candidate.candidate_id if candidate else None,
                    known_candidate_status=candidate.status if candidate else None,
                    evidence_url=row.evidence_url,
                    observed_at=row.observed_at,
                    evidence={
                        "evidence_id": row.evidence_id,
                        "term_key": term_key,
                        "cycle_novelty_state": cycle_term_state,
                    },
                )
            )

    distinct_company_count = len(company_states)
    unregistered_company_count = sum(
        1 for registry_state, _, _ in company_states.values() if registry_state == "unregistered_company"
    )
    known_candidate_company_count = sum(
        1 for registry_state, _, _ in company_states.values() if registry_state == "known_candidate_company"
    )
    newly_observed_company_count = sum(
        1 for _, cycle_state, _ in company_states.values() if cycle_state == "newly_observed_company"
    )
    repeated_observed_company_count = sum(
        1 for _, cycle_state, _ in company_states.values() if cycle_state == "repeated_observed_company"
    )
    reassessment_company_count = len(
        {
            item.company_key
            for item in items
            if item.novelty_state == "known_candidate_reassessment" and item.company_key
        }
    )
    newly_observed_term_count = sum(
        1 for term_key in current_company_term_keys if term_key not in previous_terms
    )
    repeated_observed_term_count = sum(
        1 for term_key in current_company_term_keys if term_key in previous_terms
    )

    total_cycle_units = distinct_company_count + len(current_company_term_keys)
    cycle_novelty_units = newly_observed_company_count + newly_observed_term_count
    novelty_score = _round_score(cycle_novelty_units / total_cycle_units) if total_cycle_units else Decimal("0.00")

    saturation_level = _classify_saturation(
        evidence_count=len(evidence_rows),
        previous_snapshot=previous_snapshot,
        newly_observed_company_count=newly_observed_company_count,
        newly_observed_term_count=newly_observed_term_count,
        novelty_score=novelty_score,
    )
    recommended_action, reason = _recommend_action(
        saturation_level=saturation_level,
        previous_snapshot=previous_snapshot,
        newly_observed_company_count=newly_observed_company_count,
        unregistered_company_count=unregistered_company_count,
        reassessment_company_count=reassessment_company_count,
        new_vocabulary_term_count=new_vocabulary_term_count,
        evidence_count=len(evidence_rows),
    )

    return AggregatorNoveltySnapshot(
        source_name=source_name,
        search_profile_name=search_profile_name,
        search_term=search_term,
        cycle_scope=CYCLE_SCOPE,
        previous_snapshot_id=previous_snapshot.snapshot_id if previous_snapshot else None,
        observed_since=observed_since,
        observed_until=observed_until,
        evidence_count=len(evidence_rows),
        distinct_company_count=distinct_company_count,
        unregistered_company_count=unregistered_company_count,
        known_candidate_company_count=known_candidate_company_count,
        newly_observed_company_count=newly_observed_company_count,
        repeated_observed_company_count=repeated_observed_company_count,
        reassessment_company_count=reassessment_company_count,
        new_vocabulary_term_count=new_vocabulary_term_count,
        known_vocabulary_term_count=known_vocabulary_term_count,
        newly_observed_term_count=newly_observed_term_count,
        repeated_observed_term_count=repeated_observed_term_count,
        novelty_score=novelty_score,
        saturation_level=saturation_level,
        recommended_action=recommended_action,
        reason=reason,
        items=tuple(items),
        evidence={
            "boundary": {
                "no_pagination": True,
                "no_limit_circumvention": True,
                "no_search_profile_mutation": True,
                "no_source_activation": True,
                "no_bronze_write": True,
                "no_scheduler_change": True,
            },
            "novelty_semantics": {
                "unregistered_company": "not yet present in employer_origin_source_candidates",
                "newly_observed_company": "not present in the previous persisted novelty snapshot for the same scope",
                "new_vocabulary_term": "not yet present in company_vocabulary_observations for the matched company",
                "newly_observed_term": "company-term pair not present in the previous persisted novelty snapshot for the same scope",
            },
            "observed_company_terms": {
                company_key: sorted(terms)
                for company_key, terms in sorted(observed_terms_by_company.items())
            },
            "current_company_keys": sorted(company_states),
            "current_company_term_keys": sorted(current_company_term_keys),
        },
    )


def _classify_saturation(
    *,
    evidence_count: int,
    previous_snapshot: PreviousNoveltySnapshot | None,
    newly_observed_company_count: int,
    newly_observed_term_count: int,
    novelty_score: Decimal,
) -> str:
    if evidence_count == 0:
        return "unknown"
    if previous_snapshot is None:
        return "baseline"
    if newly_observed_company_count == 0 and newly_observed_term_count == 0:
        return "saturated"
    if novelty_score >= Decimal("0.50"):
        return "fresh"
    if novelty_score >= Decimal("0.25"):
        return "mixed"
    return "saturating"


def _recommend_action(
    *,
    saturation_level: str,
    previous_snapshot: PreviousNoveltySnapshot | None,
    newly_observed_company_count: int,
    unregistered_company_count: int,
    reassessment_company_count: int,
    new_vocabulary_term_count: int,
    evidence_count: int,
) -> tuple[str, str]:
    if evidence_count == 0:
        return "manual_review", "no bounded aggregator evidence is available for this cycle"
    if previous_snapshot is None:
        return (
            "persist_baseline_then_rerun",
            "first novelty snapshot for this scope; persist baseline before judging cycle saturation",
        )
    if newly_observed_company_count > 0:
        return "review_newly_observed_companies", "bounded exploration still finds companies not seen in the previous cycle"
    if reassessment_company_count > 0:
        return (
            "rerun_gate_reassessment_for_known_candidates",
            "known unresolved candidates still appear in repeated bounded market evidence",
        )
    if unregistered_company_count > 0:
        return (
            "review_unregistered_company_backlog",
            "bounded exploration repeats companies that are not yet employer-origin candidates",
        )
    if new_vocabulary_term_count > 0:
        return "try_reviewed_trial_terms", "bounded exploration finds vocabulary not yet learned for observed companies"
    if saturation_level == "saturated":
        return "pause_or_retire_current_query", "bounded exploration repeats observed companies and observed vocabulary"
    return "continue_bounded_exploration", "bounded exploration still has mixed cycle-novelty signals"
