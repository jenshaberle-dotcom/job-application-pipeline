"""Shared policy for aggregator discovery suppression and candidate rechecks.

Aggregators are discovery sources, not lifecycle owners. Once an employer is known as
an employer-origin candidate, repeated aggregator sightings should not create a new
candidate path. Known but inactive candidates are rechecked through the
employer-origin lifecycle/queue instead.
"""

from __future__ import annotations

from typing import Any
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from src.normalization.company_keys import (
    company_key_matches,
    normalize_company_key,
)


RECHECK_INTERVAL_DAYS = 30

ACTIVE_CONNECTOR_STATUSES = {"active_controlled"}
HARD_STOP_STATUSES = {"deprecated", "disabled", "abort_documented"}
INACTIVE_RECHECK_STATUSES = {
    "candidate",
    "discovery",
    "deferred",
    "manual_review_required",
    "connector_candidate",
    "watchlist",
    "degraded",
}

# Rechecks are intentionally limited to business/domain relevance gates.
# Operational repair gates such as detail_evidence_gate and technical reachability
# must keep their existing queue semantics; otherwise the queue would hide concrete
# repair work behind a generic employer-origin recheck action and confuse later agents.
RECHECKABLE_GATE_NAMES = {
    "domain_relevance_gate",
    "professional_relevance_gate",
    "source_scope_gate",
}

RECHECKABLE_REASON_PATTERNS = (
    "missing fachliche relevanz",
    "fehlende fachliche relevanz",
    "missing domain relevance",
    "low domain relevance",
    "unclear domain relevance",
    "missing professional relevance",
    "unclear professional relevance",
    "insufficient current jobs",
    "temporary no matching jobs",
    "no matching jobs",
)

NON_RECHECKABLE_REASON_PATTERNS = (
    "robots",
    "terms hard block",
    "legal hard block",
    "written permission",
    "manual stop",
    "explicit stop",
    "do not recheck",
    "no career site",
    "irrelevant industry",
)

@dataclass(frozen=True)
class KnownEmployerCandidate:
    candidate_id: int
    company_key: str
    company_name: str
    source_name_candidate: str
    source_family_candidate: str
    status: str
    risk_level: str
    latest_gate_name: str | None = None
    latest_gate_status: str | None = None
    latest_stop_reason: str | None = None
    latest_reviewed_at: str | None = None


@dataclass(frozen=True)
class AggregatorCompanySignal:
    """One company signal from an aggregator/discovery source.

    StepStone is currently the main producer for this path. The signal is derived
    from Silver rows, not from live HTTP or export files.
    """

    source_name: str
    company: str
    silver_job_count: int
    first_seen_at: str | None = None
    last_seen_at: str | None = None


@dataclass(frozen=True)
class AggregatorSuppressionDecision:
    company: str
    normalized_company_key: str
    decision: str
    reason: str
    aggregator_source_name: str | None = None
    silver_job_count: int = 0
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    known_candidate_id: int | None = None
    known_candidate_status: str | None = None
    known_candidate_source_name: str | None = None
    recheck_eligible: bool = False
    recheck_reason: str | None = None

    @property
    def suppressed(self) -> bool:
        return self.decision.startswith("suppress_")

    @property
    def observed(self) -> bool:
        return self.decision.startswith("observe_")

    @property
    def handoff_action(self) -> str:
        if self.recheck_eligible:
            return "queue_employer_origin_recheck"
        if self.suppressed:
            return "suppress_from_aggregator_discovery"
        if self.observed:
            return "observe_as_market_evidence"
        return "keep_for_new_candidate_discovery"



def reason_text(gate_name: str | None, stop_reason: str | None, evidence: dict[str, Any] | None = None) -> str:
    fragments = [gate_name or "", stop_reason or ""]
    if evidence:
        for key in ("interpretation", "recheck_reason", "gate_reason", "reason"):
            value = evidence.get(key)
            if isinstance(value, str):
                fragments.append(value)
    return " ".join(fragment.lower() for fragment in fragments if fragment)


def is_recheckable_gate_reason(
    *,
    gate_name: str | None,
    stop_reason: str | None,
    evidence: dict[str, Any] | None = None,
) -> bool:
    text = reason_text(gate_name, stop_reason, evidence)

    if any(pattern in text for pattern in NON_RECHECKABLE_REASON_PATTERNS):
        return False

    if gate_name in RECHECKABLE_GATE_NAMES:
        return True

    return any(pattern in text for pattern in RECHECKABLE_REASON_PATTERNS)


def parse_reviewed_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def is_recheck_due(reviewed_at: str | None, *, now: datetime | None = None, interval_days: int = RECHECK_INTERVAL_DAYS) -> bool:
    parsed = parse_reviewed_at(reviewed_at)
    if parsed is None:
        return True
    current = now or datetime.now(UTC)
    return parsed <= current - timedelta(days=interval_days)


def candidate_recheck_decision(
    candidate: KnownEmployerCandidate,
    *,
    now: datetime | None = None,
    interval_days: int = RECHECK_INTERVAL_DAYS,
) -> tuple[bool, str | None]:
    if candidate.status in ACTIVE_CONNECTOR_STATUSES:
        return False, "active source is monitored through lifecycle tracking"

    if candidate.status in HARD_STOP_STATUSES:
        return False, "candidate status is a hard stop and is not automatically rechecked"

    if candidate.risk_level == "blocked":
        return False, "candidate risk level is blocked"

    if candidate.status not in INACTIVE_RECHECK_STATUSES:
        return False, "candidate status is not part of the recheck lifecycle"

    if not is_recheckable_gate_reason(
        gate_name=candidate.latest_gate_name,
        stop_reason=candidate.latest_stop_reason,
    ):
        return False, "latest gate reason is not recheckable by policy"

    if not is_recheck_due(candidate.latest_reviewed_at, now=now, interval_days=interval_days):
        return False, "candidate was reviewed recently"

    return True, "inactive candidate has a recheckable gate reason and is due for lifecycle review"


def build_known_candidate_index(
    candidates: list[KnownEmployerCandidate],
) -> dict[str, KnownEmployerCandidate]:
    index: dict[str, KnownEmployerCandidate] = {}
    for candidate in candidates:
        keys = {
            normalize_company_key(candidate.company_key),
            normalize_company_key(candidate.company_name),
            normalize_company_key(candidate.source_family_candidate),
        }
        for key in keys:
            if key and key not in index:
                index[key] = candidate
    return index


def find_known_candidate_for_company_key(
    normalized_company_key: str,
    known_candidates: list[KnownEmployerCandidate],
) -> KnownEmployerCandidate | None:
    index = build_known_candidate_index(known_candidates)

    exact = index.get(normalized_company_key)
    if exact is not None:
        return exact

    for candidate_key in sorted(index, key=len, reverse=True):
        if company_key_matches(normalized_company_key, candidate_key):
            return index[candidate_key]

    return None


def suppress_aggregator_signal(
    signal: AggregatorCompanySignal,
    known_candidates: list[KnownEmployerCandidate],
    *,
    now: datetime | None = None,
) -> AggregatorSuppressionDecision:
    decision = suppress_aggregator_company(
        signal.company,
        known_candidates,
        now=now,
    )

    return AggregatorSuppressionDecision(
        company=decision.company,
        normalized_company_key=decision.normalized_company_key,
        decision=decision.decision,
        reason=decision.reason,
        aggregator_source_name=signal.source_name,
        silver_job_count=signal.silver_job_count,
        first_seen_at=signal.first_seen_at,
        last_seen_at=signal.last_seen_at,
        known_candidate_id=decision.known_candidate_id,
        known_candidate_status=decision.known_candidate_status,
        known_candidate_source_name=decision.known_candidate_source_name,
        recheck_eligible=decision.recheck_eligible,
        recheck_reason=decision.recheck_reason,
    )


def suppress_aggregator_company(
    company: str,
    known_candidates: list[KnownEmployerCandidate],
    *,
    now: datetime | None = None,
) -> AggregatorSuppressionDecision:
    normalized = normalize_company_key(company)
    if not normalized:
        return AggregatorSuppressionDecision(
            company=company,
            normalized_company_key=normalized,
            decision="keep_for_discovery_review",
            reason="company name is empty or not normalizable",
        )

    candidate = find_known_candidate_for_company_key(normalized, known_candidates)
    if candidate is None:
        return AggregatorSuppressionDecision(
            company=company,
            normalized_company_key=normalized,
            decision="keep_for_discovery_review",
            reason="company is not known as employer-origin candidate",
        )

    recheck_eligible, recheck_reason = candidate_recheck_decision(candidate, now=now)

    if candidate.status in ACTIVE_CONNECTOR_STATUSES:
        decision = "suppress_active_connector_candidate"
        reason = "company already has an active controlled employer-origin source"
    elif candidate.status in HARD_STOP_STATUSES:
        decision = "suppress_known_hard_stop_candidate"
        reason = "company is already known with a hard-stop lifecycle status"
    else:
        decision = "observe_known_connector_candidate"
        reason = (
            "company is already known but not sufficiently controlled; keep aggregator "
            "sightings as market evidence for false-negative risk review"
        )

    return AggregatorSuppressionDecision(
        company=company,
        normalized_company_key=normalized,
        decision=decision,
        reason=reason,
        known_candidate_id=candidate.candidate_id,
        known_candidate_status=candidate.status,
        known_candidate_source_name=candidate.source_name_candidate,
        recheck_eligible=recheck_eligible,
        recheck_reason=recheck_reason,
    )
