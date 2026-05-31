from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Iterable

UNRESOLVED_STATUSES = {
    "manual_review_required",
    "blocked",
    "candidate",
    "connector_candidate",
    "deferred",
    "watchlist",
    "degraded",
}
ACTIVE_STATUSES = {"active_controlled"}
IGNORED_STATUSES = {"deprecated", "disabled", "abort_documented", "not_actionable"}

TERM_STOPWORDS = {
    "and", "the", "for", "with", "und", "der", "die", "das", "ein", "eine",
    "senior", "junior", "m", "w", "d", "gn", "all", "gender", "remote",
    "hannover", "germany", "deutschland", "engineer", "developer", "manager",
}
TERM_SYNONYMS = {
    "analytics": "analytics",
    "analytic": "analytics",
    "analyse": "analytics",
    "business": "business intelligence",
    "intelligence": "business intelligence",
    "bi": "business intelligence",
    "data": "data",
    "daten": "data",
    "management": "data management",
    "reporting": "reporting",
    "warehouse": "data warehouse",
    "plattform": "data platform",
    "platform": "data platform",
    "automation": "automation",
    "risk": "risk data",
    "actuarial": "actuarial data",
}

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

@dataclass(frozen=True)
class CandidateMarketEvidenceSummary:
    candidate_id: int
    company_key: str
    company_name: str
    candidate_status: str
    candidate_risk_level: str
    sighting_count: int
    recent_sighting_count: int
    last_observed_at: str | None
    evidence_sources: tuple[str, ...]
    evidence_titles: tuple[str, ...]

@dataclass(frozen=True)
class FalseNegativeRiskAssessment:
    candidate_id: int
    company_key: str
    company_name: str
    risk_level: str
    sighting_count: int
    recent_sighting_count: int
    last_observed_at: str | None
    reason: str
    suggested_search_terms: tuple[str, ...]
    evidence_sources: tuple[str, ...]
    evidence_titles: tuple[str, ...]

    @property
    def sort_key(self) -> tuple[int, int, str]:
        return (RISK_ORDER.get(self.risk_level, 0), self.recent_sighting_count, self.company_name.lower())


def parse_observed_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def is_recent(value: str | None, *, now: datetime | None = None, days: int = 14) -> bool:
    parsed = parse_observed_at(value)
    if parsed is None:
        return False
    current = now or datetime.now(UTC)
    return parsed >= current - timedelta(days=days)


def title_tokens(titles: Iterable[str]) -> list[str]:
    tokens: list[str] = []
    for title in titles:
        for raw in re.findall(r"[A-Za-zÄÖÜäöüß&]+", title.lower()):
            token = raw.strip("&")
            if len(token) < 2 or token in TERM_STOPWORDS:
                continue
            tokens.append(TERM_SYNONYMS.get(token, token))
    return tokens


def suggested_search_terms_from_titles(titles: Iterable[str], *, limit: int = 6) -> tuple[str, ...]:
    counts: dict[str, int] = {}
    for token in title_tokens(titles):
        if token == "data":
            continue
        counts[token] = counts.get(token, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return tuple(term for term, _ in ordered[:limit])


def assess_false_negative_risk(
    summary: CandidateMarketEvidenceSummary,
    *,
    now: datetime | None = None,
) -> FalseNegativeRiskAssessment:
    status = summary.candidate_status
    recent = summary.recent_sighting_count
    total = summary.sighting_count
    recent_last_seen = is_recent(summary.last_observed_at, now=now, days=14)

    if status in ACTIVE_STATUSES:
        risk = "low"
        reason = "candidate has an active controlled employer-origin source; aggregator sightings are monitoring evidence"
    elif status in IGNORED_STATUSES:
        risk = "low" if total == 0 else "medium"
        reason = "candidate is in an ignored/hard-stop lifecycle state; sightings are retained as market evidence"
    elif status in UNRESOLVED_STATUSES and recent >= 5 and recent_last_seen:
        risk = "critical"
        reason = "unresolved employer-origin candidate has five or more recent aggregator sightings"
    elif status in UNRESOLVED_STATUSES and (recent >= 1 or total >= 3):
        risk = "high"
        reason = "unresolved employer-origin candidate still appears in market evidence"
    elif total > 0:
        risk = "medium"
        reason = "candidate has market evidence but no strong recent unresolved signal"
    else:
        risk = "low"
        reason = "no market evidence currently indicates a false-negative risk"

    return FalseNegativeRiskAssessment(
        candidate_id=summary.candidate_id,
        company_key=summary.company_key,
        company_name=summary.company_name,
        risk_level=risk,
        sighting_count=total,
        recent_sighting_count=recent,
        last_observed_at=summary.last_observed_at,
        reason=reason,
        suggested_search_terms=suggested_search_terms_from_titles(summary.evidence_titles),
        evidence_sources=summary.evidence_sources,
        evidence_titles=summary.evidence_titles,
    )


def assess_many(summaries: Iterable[CandidateMarketEvidenceSummary]) -> list[FalseNegativeRiskAssessment]:
    assessments = [assess_false_negative_risk(summary) for summary in summaries]
    return sorted(assessments, key=lambda item: item.sort_key, reverse=True)
