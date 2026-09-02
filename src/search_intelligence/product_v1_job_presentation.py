"""Source-grounded presentation semantics for Product V1 job review.

This module improves operator-facing identity, schedule and geography evidence without
creating ranking, hard-filter or application authority. It deliberately separates an
ATS tenant's reviewed employer brand from a legal/subcompany value exposed by the
feed, and it preserves qualitative schedule evidence without inventing numeric hours.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from src.search_intelligence.personio_legacy_authority_bindings import (
    reviewed_personio_authority_binding,
)


_REMOTE_RE = re.compile(
    r"(?:^|\b)(?:remote|home\s*office|homeoffice|bundesweit|deutschlandweit)(?:\b|$)",
    re.IGNORECASE,
)
_FULL_TIME_RE = re.compile(r"\b(?:full[- ]?time|vollzeit)\b", re.IGNORECASE)
_PART_TIME_RE = re.compile(r"\b(?:part[- ]?time|teilzeit)\b", re.IGNORECASE)

# These are deliberately only unambiguous long-distance cities for the current
# Hannover/remote-Germany product profile. Nearby/unknown locations remain reviewable
# until structured commute or radius evidence exists.
_CLEARLY_OUTSIDE_HANNOVER_RADIUS = frozenset(
    {
        "berlin",
        "hamburg",
        "munchen",
        "muenchen",
        "munich",
        "dusseldorf",
        "duesseldorf",
        "düsseldorf",
        "frankfurt",
        "frankfurt am main",
        "koln",
        "koeln",
        "köln",
        "stuttgart",
    }
)


@dataclass(frozen=True)
class ReviewGeography:
    eligible: bool
    bucket: str
    reason: str


def _text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _normalized(value: object) -> str:
    value = _text(value).casefold()
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
    }
    for source, replacement in replacements.items():
        value = value.replace(source, replacement)
    return value


def personio_target_key(source_name: object) -> str | None:
    value = _text(source_name)
    if not value.startswith("personio:"):
        return None
    target = value.split(":", 1)[1].strip()
    return target or None


def authoritative_employer_name(source_name: object, fallback: object) -> str:
    """Return reviewed employer brand where one exists, otherwise the row value."""

    target = personio_target_key(source_name)
    if target:
        binding = reviewed_personio_authority_binding(target)
        if binding is not None:
            return binding.company_name
    return _text(fallback)


def canonical_employment_schedule(value: object) -> str:
    text = _text(value)
    if _FULL_TIME_RE.search(text):
        return "full_time"
    if _PART_TIME_RE.search(text):
        return "part_time"
    return "unknown"


def observation_job(normalized_evidence: object) -> Mapping[str, object]:
    if not isinstance(normalized_evidence, Mapping):
        return {}
    raw = normalized_evidence.get("raw_evidence")
    if not isinstance(raw, Mapping):
        return {}
    job = raw.get("job")
    return job if isinstance(job, Mapping) else {}


def classify_review_geography(row: Mapping[str, object]) -> ReviewGeography:
    """Classify current Hannover/remote-Germany review eligibility.

    This is a review-list presentation boundary, not hard-filter or ranking authority.
    Remote evidence is intentionally preserved. Clear far-away city-only vacancies are
    hidden from the normal review list; ambiguous or nearby locations stay reviewable.
    """

    city = _text(row.get("city"))
    work_model = _normalized(row.get("work_model"))
    commute = row.get("commute_minutes")
    city_normalized = _normalized(city)

    if "hannover" in city_normalized or "hanover" in city_normalized:
        return ReviewGeography(True, "hannover_explicit", "structured_hannover_signal")

    if _REMOTE_RE.search(city) or work_model == "remote":
        return ReviewGeography(True, "remote_explicit", "explicit_remote_signal")

    if isinstance(commute, int) and commute <= 45:
        return ReviewGeography(True, "commute_observed_acceptable", "observed_commute_at_or_below_45_minutes")

    # Multi-location text is excluded only when every explicit city is clearly outside
    # the current local radius and no remote signal exists.
    tokens = {
        _normalized(part)
        for part in re.split(r"[,;|/]", city)
        if _normalized(part)
    }
    if tokens and tokens.issubset({_normalized(item) for item in _CLEARLY_OUTSIDE_HANNOVER_RADIUS}):
        return ReviewGeography(False, "explicit_outside_target", "explicit_far_city_without_remote_or_commute")

    return ReviewGeography(True, "geography_review_required", "location_not_precise_enough_for_safe_exclusion")


def decorate_job_for_operator(
    row: Mapping[str, object],
    *,
    normalized_observation_evidence: object = None,
) -> dict[str, object]:
    """Decorate a Product V1 row with read-only operator presentation evidence."""

    result = dict(row)
    job = observation_job(normalized_observation_evidence)

    legal_entity = _text(job.get("legal_entity_name") or job.get("company_name"))
    display_company = authoritative_employer_name(
        result.get("source_name"),
        result.get("company_name"),
    )
    schedule_observed = _text(
        job.get("employment_schedule")
        or job.get("schedule")
    )
    schedule = canonical_employment_schedule(schedule_observed)
    geography = classify_review_geography(result)

    result.update(
        {
            "display_company_name": display_company or _text(result.get("company_name")),
            "legal_entity_name": legal_entity or None,
            "employment_schedule": schedule,
            "employment_schedule_observed_value": schedule_observed or None,
            "employment_schedule_evidence_status": "observed" if schedule != "unknown" else "unknown",
            "numeric_weekly_hours_inferred_from_schedule": False,
            "profile_geography_eligible": geography.eligible,
            "profile_geography_bucket": geography.bucket,
            "profile_geography_reason": geography.reason,
            "presentation_authority": False,
        }
    )
    return result


__all__ = [
    "ReviewGeography",
    "authoritative_employer_name",
    "canonical_employment_schedule",
    "classify_review_geography",
    "decorate_job_for_operator",
    "observation_job",
    "personio_target_key",
]
