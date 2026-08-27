"""Bounded recurring exact-detail health reconciliation.

Absence from one recurring connector inventory is never closure authority.
A previously-current employer-origin vacancy that is not present in the current
full-fetch observation may only trigger one bounded exact-detail probe.

Only deterministic exact-detail outcomes are persisted:
- seen_active -> positive exact-detail health evidence;
- closed -> negative exact-detail health evidence;
- unverifiable -> no health write.

No TTL, listing absence, 404, redirect, transport failure, title mismatch or
sensor absence is promoted into closure authority.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from src.connectors.base import RawJobRecord
from src.job_lifecycle_health import (
    COVERAGE_EXACT_DETAIL,
    OUTCOME_CLOSED,
    OUTCOME_SEEN_ACTIVE,
    REQUEST_TIMEOUT_SECONDS,
    HttpProbeResult,
    JobHealthTarget,
    JobLifecycleHealthRepository,
    classify_exact_detail,
    ensure_expected_target,
    fetch_exact_detail,
    normalize_url_identity,
)


MAX_RECURRING_EXACT_DETAIL_PROBES = 20
RECURRING_HEALTH_OBSERVER = "recurring_ingestion_exact_detail_recheck"


@dataclass(frozen=True)
class RecurringLifecycleHealthSummary:
    target_count: int
    observed_target_count: int
    missing_target_count: int
    probe_count: int
    seen_active_write_count: int
    closed_write_count: int
    unverifiable_count: int
    probed_silver_job_ids: tuple[int, ...]
    written_observation_ids: tuple[int, ...]


def _normalized_url(value: str) -> str:
    if not value.strip():
        return ""
    return normalize_url_identity(value)


def _observed_identity_sets(
    *,
    source_name: str,
    records: Sequence[RawJobRecord],
) -> tuple[set[str], set[str]]:
    external_ids: set[str] = set()
    urls: set[str] = set()

    for record in records:
        if record.source_name != source_name:
            continue

        if record.external_job_id:
            external_ids.add(record.external_job_id)

        if record.source_url.strip():
            urls.add(_normalized_url(record.source_url))

    return external_ids, urls


def _target_observed(
    target: JobHealthTarget,
    *,
    observed_external_ids: set[str],
    observed_urls: set[str],
) -> bool:
    if (
        target.external_job_id
        and target.external_job_id in observed_external_ids
    ):
        return True

    return _normalized_url(target.source_url) in observed_urls


def reconcile_recurring_exact_detail_health(
    *,
    health_repository: JobLifecycleHealthRepository,
    source_name: str,
    observed_records: Sequence[RawJobRecord],
    ingestion_run_id: int,
    fetcher: Callable[..., HttpProbeResult] = fetch_exact_detail,
    timeout_seconds: float = REQUEST_TIMEOUT_SECONDS,
    max_probes: int = MAX_RECURRING_EXACT_DETAIL_PROBES,
) -> RecurringLifecycleHealthSummary:
    """Recheck missing current employer-origin vacancies fail-closed."""

    if not source_name.strip():
        raise ValueError("source_name must not be empty")
    if ingestion_run_id <= 0:
        raise ValueError("ingestion_run_id must be positive")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if max_probes <= 0:
        raise ValueError("max_probes must be positive")

    targets = health_repository.load_active_targets_for_source(
        source_name.strip()
    )

    observed_external_ids, observed_urls = _observed_identity_sets(
        source_name=source_name.strip(),
        records=observed_records,
    )

    missing_targets = [
        target
        for target in targets
        if not _target_observed(
            target,
            observed_external_ids=observed_external_ids,
            observed_urls=observed_urls,
        )
    ]

    if len(missing_targets) > max_probes:
        raise RuntimeError(
            "recurring lifecycle health bulk miss exceeds bounded probe cap: "
            f"missing={len(missing_targets)} max_probes={max_probes}"
        )

    selected_targets = missing_targets

    seen_active_write_count = 0
    closed_write_count = 0
    unverifiable_count = 0
    probed_ids: list[int] = []
    written_ids: list[int] = []

    for target in selected_targets:
        ensure_expected_target(
            target,
            expected_source_name=source_name.strip(),
            expected_source_url=target.source_url,
        )

        probe = fetcher(
            target.source_url,
            timeout_seconds=timeout_seconds,
        )
        classification = classify_exact_detail(target, probe)

        probed_ids.append(target.silver_job_id)

        if (
            classification.outcome == OUTCOME_CLOSED
            and classification.coverage == COVERAGE_EXACT_DETAIL
        ):
            observation_id = health_repository.append_health_observation(
                expected_target=target,
                classification=classification,
                observed_by=RECURRING_HEALTH_OBSERVER,
                ingestion_run_id=ingestion_run_id,
            )
            written_ids.append(observation_id)
            closed_write_count += 1
            continue

        if (
            classification.outcome == OUTCOME_SEEN_ACTIVE
            and classification.coverage == COVERAGE_EXACT_DETAIL
        ):
            observation_id = health_repository.append_health_observation(
                expected_target=target,
                classification=classification,
                observed_by=RECURRING_HEALTH_OBSERVER,
                ingestion_run_id=ingestion_run_id,
            )
            written_ids.append(observation_id)
            seen_active_write_count += 1
            continue

        unverifiable_count += 1

    return RecurringLifecycleHealthSummary(
        target_count=len(targets),
        observed_target_count=len(targets) - len(missing_targets),
        missing_target_count=len(missing_targets),
        probe_count=len(selected_targets),
        seen_active_write_count=seen_active_write_count,
        closed_write_count=closed_write_count,
        unverifiable_count=unverifiable_count,
        probed_silver_job_ids=tuple(probed_ids),
        written_observation_ids=tuple(written_ids),
    )
