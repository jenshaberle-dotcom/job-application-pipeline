from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


DEFAULT_MAX_HEALTH_AGE_MINUTES = 30


@dataclass(frozen=True)
class DemoLiveScopeDecision:
    eligible: bool
    reason: str


def _parse_timestamp(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def evaluate_demo_live_scope(
    job: Mapping[str, object],
    *,
    now: datetime | None = None,
    max_health_age_minutes: int = DEFAULT_MAX_HEALTH_AGE_MINUTES,
) -> DemoLiveScopeDecision:
    """Decide whether already-authoritative Product truth is fresh enough for demo action.

    This function creates no lifecycle authority. It only tightens the demo surface
    on top of persisted exact-detail/complete-inventory observations.
    """

    if not bool(job.get("demo_actionable")):
        return DemoLiveScopeDecision(False, "employer_origin_actionability_required")
    if str(job.get("lifecycle_status") or "") != "active_confirmed":
        return DemoLiveScopeDecision(False, "active_confirmed_required")

    observed_at = _parse_timestamp(job.get("last_health_checked_at"))
    if observed_at is None:
        observed_at = _parse_timestamp(job.get("latest_health_observed_at"))
    if observed_at is None:
        return DemoLiveScopeDecision(False, "fresh_health_timestamp_required")

    reference = (now or datetime.now(UTC)).astimezone(UTC)
    if observed_at > reference + timedelta(minutes=5):
        return DemoLiveScopeDecision(False, "health_timestamp_is_in_future")
    if reference - observed_at > timedelta(minutes=max_health_age_minutes):
        return DemoLiveScopeDecision(False, "live_health_refresh_required")
    return DemoLiveScopeDecision(True, "fresh_current_employer_origin_truth")


def project_demo_live_scope(
    jobs: Iterable[Mapping[str, object]],
    *,
    now: datetime | None = None,
    max_health_age_minutes: int = DEFAULT_MAX_HEALTH_AGE_MINUTES,
) -> list[dict[str, object]]:
    projected: list[dict[str, object]] = []
    for job in jobs:
        copied = dict(job)
        decision = evaluate_demo_live_scope(
            copied,
            now=now,
            max_health_age_minutes=max_health_age_minutes,
        )
        copied["demo_live_verified"] = decision.eligible
        copied["demo_live_reason"] = decision.reason
        projected.append(copied)
    return projected
