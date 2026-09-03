from __future__ import annotations

from collections.abc import Iterable, Mapping

from src.search_intelligence.product_v1_demo_origin_guard import (
    evaluate_demo_origin_guard,
)


def project_demo_origin_truth(
    jobs: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Expose discovery provenance without letting it masquerade as action truth."""

    projected: list[dict[str, object]] = []
    for job in jobs:
        copied = dict(job)
        discovery_url = str(job.get("source_url") or "").strip() or None
        guard = evaluate_demo_origin_guard(
            source_url=discovery_url,
            source_name=str(job.get("source_name") or "") or None,
            canonical_source_type=str(job.get("canonical_source_type") or "") or None,
            lifecycle_status=str(job.get("lifecycle_status") or "") or None,
            origin_validation_status=str(job.get("origin_validation_status") or "") or None,
            product_readiness_status=str(job.get("product_readiness_status") or "") or None,
        )
        copied["discovery_source_url"] = discovery_url
        copied["demo_actionable"] = guard.eligible
        copied["demo_actionability_reason"] = guard.reason
        copied["employer_origin_url"] = guard.employer_origin_url
        # Legacy consumers use source_url as the clickable Product action target.
        # Never leave an aggregator/discovery URL in that slot.
        copied["source_url"] = guard.employer_origin_url
        projected.append(copied)
    return projected


def filter_demo_actionable_jobs(
    jobs: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    return [row for row in project_demo_origin_truth(jobs) if row["demo_actionable"]]
