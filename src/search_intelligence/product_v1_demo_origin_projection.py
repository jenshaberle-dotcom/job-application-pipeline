from __future__ import annotations

from collections.abc import Iterable, Mapping

from src.search_intelligence.product_v1_demo_origin_guard import (
    evaluate_demo_origin_guard,
)


def project_demo_origin_truth(
    jobs: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    projected: list[dict[str, object]] = []
    for job in jobs:
        copied = dict(job)
        guard = evaluate_demo_origin_guard(
            source_url=str(job.get("source_url") or "") or None,
            canonical_source_type=str(job.get("canonical_source_type") or "") or None,
            lifecycle_status=str(job.get("lifecycle_status") or "") or None,
            origin_validation_status=str(job.get("origin_validation_status") or "") or None,
            product_readiness_status=str(job.get("product_readiness_status") or "") or None,
        )
        copied["demo_actionable"] = guard.eligible
        copied["demo_actionability_reason"] = guard.reason
        copied["employer_origin_url"] = guard.employer_origin_url
        projected.append(copied)
    return projected


def filter_demo_actionable_jobs(
    jobs: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    return [row for row in project_demo_origin_truth(jobs) if row["demo_actionable"]]
