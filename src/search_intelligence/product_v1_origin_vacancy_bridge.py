from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Mapping, Sequence
from urllib.parse import urlsplit

from src.job_lifecycle_health import (
    HttpProbeResult,
    JobHealthTarget,
    classify_exact_detail,
    normalize_url_identity,
    title_is_confirmed,
)
from src.search_intelligence.origin_seed_pool import normalize_company_key
from src.search_intelligence.product_v1_geography_identity import (
    assess_current_geography_identity,
)


SUPPORTED_ORIGIN_SOURCE_TYPES = {
    "employer_origin_career_site",
    "employer_origin_ats_backed_career_site",
}
TERMINAL_ORIGIN_CANDIDATE_STATUSES = {
    "deprecated",
    "disabled",
    "abort_documented",
}


@dataclass(frozen=True)
class SilverContender:
    inspection_priority: int
    silver_job_id: int
    title: str
    company_name: str
    city: str | None
    country: str | None
    source_name: str
    source_url: str
    canonical_source_type: str | None
    lifecycle_status: str
    geography_bucket: str


@dataclass(frozen=True)
class OriginCandidateSnapshot:
    candidate_id: int
    company_key: str
    company_name: str
    candidate_url: str | None
    source_name_candidate: str
    source_family_candidate: str
    source_target_candidate: str | None
    source_type_candidate: str
    status: str
    risk_level: str


@dataclass(frozen=True)
class OriginCandidateResolution:
    status: str
    candidate: OriginCandidateSnapshot | None
    matching_candidate_ids: tuple[int, ...]
    reason: str


@dataclass(frozen=True)
class ExactDetailAttempt:
    url: str
    link_text: str
    probe: HttpProbeResult


def contender_from_manifest_row(row: Mapping[str, object]) -> SilverContender:
    return SilverContender(
        inspection_priority=int(row["inspection_priority"]),
        silver_job_id=int(row["silver_job_id"]),
        title=str(row.get("title") or ""),
        company_name=str(row.get("company_name") or ""),
        city=str(row.get("city") or "") or None,
        country=str(row.get("country") or "") or None,
        source_name=str(row.get("source_name") or ""),
        source_url=str(row.get("source_url") or ""),
        canonical_source_type=(
            str(row.get("canonical_source_type"))
            if row.get("canonical_source_type") is not None
            else None
        ),
        lifecycle_status=str(row.get("lifecycle_status") or ""),
        geography_bucket=str(row.get("geography_bucket") or ""),
    )


def origin_candidate_from_row(row: Mapping[str, object]) -> OriginCandidateSnapshot:
    return OriginCandidateSnapshot(
        candidate_id=int(row["id"]),
        company_key=str(row.get("company_key") or ""),
        company_name=str(row.get("company_name") or ""),
        candidate_url=str(row.get("candidate_url") or "").strip() or None,
        source_name_candidate=str(row.get("source_name_candidate") or ""),
        source_family_candidate=str(row.get("source_family_candidate") or ""),
        source_target_candidate=(
            str(row.get("source_target_candidate"))
            if row.get("source_target_candidate") is not None
            else None
        ),
        source_type_candidate=str(row.get("source_type_candidate") or ""),
        status=str(row.get("status") or ""),
        risk_level=str(row.get("risk_level") or ""),
    )


def _absolute_http_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlsplit(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def resolve_origin_candidate(
    contender: SilverContender,
    candidates: Iterable[OriginCandidateSnapshot],
) -> OriginCandidateResolution:
    employer_key = normalize_company_key(contender.company_name)
    if not employer_key:
        return OriginCandidateResolution(
            status="blocked_missing_employer_identity",
            candidate=None,
            matching_candidate_ids=(),
            reason="The Silver contender has no usable normalized employer identity.",
        )

    matches: list[OriginCandidateSnapshot] = []
    for candidate in candidates:
        if candidate.status in TERMINAL_ORIGIN_CANDIDATE_STATUSES:
            continue
        if candidate.source_type_candidate not in SUPPORTED_ORIGIN_SOURCE_TYPES:
            continue
        candidate_keys = {
            normalize_company_key(candidate.company_key),
            normalize_company_key(candidate.company_name),
        }
        if employer_key in candidate_keys:
            matches.append(candidate)

    matches.sort(key=lambda item: item.candidate_id)
    match_ids = tuple(item.candidate_id for item in matches)
    if not matches:
        return OriginCandidateResolution(
            status="origin_candidate_required",
            candidate=None,
            matching_candidate_ids=(),
            reason=(
                "No non-terminal generic employer-origin candidate matches the "
                "normalized Silver employer identity."
            ),
        )
    if len(matches) > 1:
        return OriginCandidateResolution(
            status="ambiguous_origin_candidate_identity",
            candidate=None,
            matching_candidate_ids=match_ids,
            reason=(
                "Multiple non-terminal employer-origin candidate rows match the "
                "same normalized Silver employer identity; fail closed."
            ),
        )

    candidate = matches[0]
    if not _absolute_http_url(candidate.candidate_url):
        return OriginCandidateResolution(
            status="origin_source_url_required",
            candidate=candidate,
            matching_candidate_ids=match_ids,
            reason=(
                "The unique employer-origin candidate has no absolute persisted "
                "HTTP(S) source/root URL. CAND-001 remains the URL persistence boundary."
            ),
        )

    return OriginCandidateResolution(
        status="ready_for_bounded_detail_discovery",
        candidate=candidate,
        matching_candidate_ids=match_ids,
        reason=(
            "Exactly one non-terminal employer-origin candidate with a persisted "
            "source/root URL matches the Silver employer identity."
        ),
    )


def _transient_health_target(contender: SilverContender, url: str) -> JobHealthTarget:
    return JobHealthTarget(
        silver_job_id=contender.silver_job_id,
        raw_job_id=0,
        ingestion_run_id=None,
        source_name="product_v1_origin_vacancy_bridge",
        external_job_id=None,
        source_url=url,
        title=contender.title,
        canonical_source_type="employer_origin_career_site",
        raw_source_type=None,
    )


def evaluate_exact_detail_attempts(
    contender: SilverContender,
    attempts: Sequence[ExactDetailAttempt],
) -> dict[str, object]:
    assessments: list[dict[str, object]] = []
    identity_confirmed_by_url: dict[str, dict[str, object]] = {}
    active_title_matches_blocked_by_geography: list[dict[str, object]] = []

    for attempt in attempts:
        target = _transient_health_target(contender, attempt.url)
        classification = classify_exact_detail(target, attempt.probe)
        link_title_match = title_is_confirmed(contender.title, attempt.link_text)
        page_title_match = bool(classification.evidence.get("title_match"))
        title_identity_confirmed = link_title_match or page_title_match
        geography = assess_current_geography_identity(
            city=contender.city,
            country=contender.country,
            geography_bucket=contender.geography_bucket,
            response_text=attempt.probe.response_text,
        )
        geography_required = classification.outcome == "seen_active"
        geography_identity_confirmed = geography.status == "compatible"
        identity_confirmed = bool(
            title_identity_confirmed
            and (not geography_required or geography_identity_confirmed)
        )

        assessment = {
            "url": attempt.url,
            "link_text": attempt.link_text,
            "link_title_match": link_title_match,
            "page_title_match": page_title_match,
            "title_identity_confirmed": title_identity_confirmed,
            "geography_required_for_active_confirmation": geography_required,
            "geography_identity": geography.to_json(),
            "exact_vacancy_identity_confirmed": identity_confirmed,
            "health_outcome": classification.outcome,
            "health_coverage": classification.coverage,
            "health_evidence_reason": classification.evidence_reason,
            "health_evidence": classification.evidence,
        }
        assessments.append(assessment)
        if (
            title_identity_confirmed
            and geography_required
            and not geography_identity_confirmed
        ):
            active_title_matches_blocked_by_geography.append(assessment)
        if identity_confirmed:
            identity_confirmed_by_url.setdefault(
                normalize_url_identity(attempt.url),
                assessment,
            )

    confirmed = list(identity_confirmed_by_url.values())
    if not confirmed:
        if active_title_matches_blocked_by_geography:
            statuses = {
                str(item["geography_identity"]["status"])
                for item in active_title_matches_blocked_by_geography
            }
            if "evidence_required" in statuses:
                return {
                    "status": "exact_vacancy_current_state_unverifiable",
                    "resolved_url": None,
                    "health_outcome": None,
                    "reason": (
                        "A current employer-origin detail confirmed the persisted Silver "
                        "title, but current geography identity evidence is insufficient."
                    ),
                    "assessments": assessments,
                }
            return {
                "status": "exact_vacancy_not_found",
                "resolved_url": None,
                "health_outcome": None,
                "reason": (
                    "Current employer-origin detail title evidence was found, but its "
                    "explicit geography conflicts with the persisted Silver vacancy."
                ),
                "assessments": assessments,
            }

        return {
            "status": (
                "exact_vacancy_not_found"
                if attempts
                else "no_concrete_detail_candidates"
            ),
            "resolved_url": None,
            "health_outcome": None,
            "reason": (
                "Concrete employer-origin detail candidates were checked, but none "
                "confirmed the exact persisted Silver vacancy title."
                if attempts
                else "Bounded employer-origin discovery produced no concrete detail candidates."
            ),
            "assessments": assessments,
        }

    if len(confirmed) > 1:
        return {
            "status": "ambiguous_exact_vacancy_identity",
            "resolved_url": None,
            "health_outcome": None,
            "reason": (
                "More than one distinct employer-origin detail URL confirms the "
                "persisted Silver vacancy title; fail closed."
            ),
            "assessments": assessments,
        }

    selected = confirmed[0]
    outcome = str(selected["health_outcome"])
    if outcome == "seen_active":
        status = "current_vacancy_confirmed"
    elif outcome == "closed":
        status = "inactive_vacancy_confirmed"
    else:
        status = "exact_vacancy_current_state_unverifiable"

    return {
        "status": status,
        "resolved_url": selected["url"],
        "health_outcome": outcome,
        "reason": selected["health_evidence_reason"],
        "assessments": assessments,
    }


def resolution_payload(resolution: OriginCandidateResolution) -> dict[str, object]:
    return {
        "status": resolution.status,
        "matching_candidate_ids": list(resolution.matching_candidate_ids),
        "reason": resolution.reason,
        "candidate": asdict(resolution.candidate) if resolution.candidate else None,
    }
