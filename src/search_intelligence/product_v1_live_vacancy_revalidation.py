"""Operator-triggered exact vacancy revalidation for F6.

The Product review list is based on persisted lifecycle authority. A fixed wall-clock
age is not a substitute for source cadence authority. When the operator explicitly
opens/prepares one application, JAP performs one bounded exact-detail lifecycle
probe for that exact Silver target before any vacancy evidence becomes drafting
authority.

Authoritative closure is persisted as lifecycle-health evidence so the Product
read model can converge immediately. A successful active probe remains read-only;
unverifiable network/content outcomes are never converted into active or closed
truth and perform no write.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.job_lifecycle_health import (
    JobLifecycleHealthRepository,
    OUTCOME_CLOSED,
    OUTCOME_SEEN_ACTIVE,
    classify_exact_detail,
    ensure_expected_target,
    fetch_exact_detail,
)


OBSERVED_BY = "product_v1_operator_prepare_application"


@dataclass(frozen=True)
class ProductV1VacancyRevalidation:
    status: str
    outcome: str
    evidence_reason: str
    observation_id: int | None
    http_requests: int
    health_observation_writes: int

    @property
    def active(self) -> bool:
        return self.outcome == OUTCOME_SEEN_ACTIVE

    @property
    def closed(self) -> bool:
        return self.outcome == OUTCOME_CLOSED


class ProductV1VacancyRevalidationStop(RuntimeError):
    """Fail closed when the exact vacancy cannot support F6 action authority."""


def revalidate_selected_vacancy(
    *,
    silver_job_id: int,
    expected_source_name: str,
    expected_source_url: str,
    repository: JobLifecycleHealthRepository | None = None,
    fetcher=fetch_exact_detail,
) -> ProductV1VacancyRevalidation:
    if silver_job_id <= 0:
        raise ProductV1VacancyRevalidationStop("silver_job_id must be positive")

    repo = repository or JobLifecycleHealthRepository()
    target = repo.load_target(silver_job_id)
    ensure_expected_target(
        target,
        expected_source_name=expected_source_name,
        expected_source_url=expected_source_url,
    )

    probe = fetcher(target.source_url)
    classification = classify_exact_detail(target, probe)

    if classification.outcome == OUTCOME_SEEN_ACTIVE:
        return ProductV1VacancyRevalidation(
            status="active",
            outcome=classification.outcome,
            evidence_reason=classification.evidence_reason,
            observation_id=None,
            http_requests=1,
            health_observation_writes=0,
        )

    if classification.outcome != OUTCOME_CLOSED:
        return ProductV1VacancyRevalidation(
            status="unverifiable",
            outcome=classification.outcome,
            evidence_reason=classification.evidence_reason,
            observation_id=None,
            http_requests=1,
            health_observation_writes=0,
        )

    observation_id = repo.append_health_observation(
        expected_target=target,
        classification=classification,
        observed_by=OBSERVED_BY,
    )
    return ProductV1VacancyRevalidation(
        status="closed",
        outcome=classification.outcome,
        evidence_reason=classification.evidence_reason,
        observation_id=observation_id,
        http_requests=1,
        health_observation_writes=1,
    )


__all__ = [
    "OBSERVED_BY",
    "ProductV1VacancyRevalidation",
    "ProductV1VacancyRevalidationStop",
    "revalidate_selected_vacancy",
]
