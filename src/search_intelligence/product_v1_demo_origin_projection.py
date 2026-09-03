from __future__ import annotations

from collections.abc import Iterable, Mapping

from src.search_intelligence.product_v1_demo_origin_guard import (
    evaluate_demo_origin_guard,
)


def _resolved_origin_url(job: Mapping[str, object]) -> tuple[str | None, bool]:
    """Return only explicitly verified resolved-origin transport evidence."""

    for key in ("verified_vacancy_url", "resolved_employer_origin_url"):
        value = str(job.get(key) or "").strip()
        if value:
            verified = (
                str(job.get("verification_outcome") or "") == "verified_active"
                or job.get("resolved_origin_verified") is True
                or str(job.get("opportunity_stage") or "") == "vacancy_verified_active"
            )
            return value, verified
    return None, False


def project_demo_origin_truth(
    jobs: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Expose discovery provenance while projecting one safe Product action URL."""

    projected: list[dict[str, object]] = []
    for job in jobs:
        copied = dict(job)
        discovery_url = str(job.get("source_url") or "").strip() or None
        resolved_url, resolved_verified = _resolved_origin_url(job)
        guard = evaluate_demo_origin_guard(
            source_url=discovery_url,
            source_name=str(job.get("source_name") or "") or None,
            canonical_source_type=str(job.get("canonical_source_type") or "") or None,
            lifecycle_status=str(job.get("lifecycle_status") or "") or None,
            origin_validation_status=str(job.get("origin_validation_status") or "") or None,
            product_readiness_status=str(job.get("product_readiness_status") or "") or None,
            resolved_employer_origin_url=resolved_url,
            resolved_origin_verified=resolved_verified,
        )
        copied["discovery_source_url"] = discovery_url
        copied["resolved_employer_origin_url"] = resolved_url
        copied["resolved_origin_verified"] = resolved_verified
        copied["demo_actionable"] = guard.eligible
        copied["demo_actionability_reason"] = guard.reason
        copied["employer_origin_url"] = guard.employer_origin_url
        # Legacy consumers use source_url as the clickable Product action target.
        copied["source_url"] = guard.employer_origin_url
        projected.append(copied)
    return projected


def filter_demo_actionable_jobs(
    jobs: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    return [row for row in project_demo_origin_truth(jobs) if row["demo_actionable"]]
