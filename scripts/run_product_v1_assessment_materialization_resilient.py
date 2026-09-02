"""Resilient entry point for generic Product V1 assessment materialization.

The canonical materializer already treats ``MaterializationStop`` and ``ValueError``
as per-candidate plan blockers. This adapter strengthens the read boundary in two
source-neutral ways:

1. when the latest exact-bound normalized observation already contains the current
   vacancy description, reuse that persisted evidence instead of issuing a redundant
   detail-page request;
2. when a network detail fallback is still required, translate
   ``DownstreamPreviewStop`` into the materializer's existing per-candidate
   ``MaterializationStop`` so one unavailable page cannot abort the whole batch.

No retry, alternate route, authority relaxation, assessment inference, or write
behavior is added. The canonical materializer still validates profile, lifecycle,
observation and URL authority before it invokes this detail boundary. Apply
semantics remain exactly those of the canonical runner.
"""
from __future__ import annotations

from typing import Mapping, Sequence

from scripts import run_product_v1_assessment_materialization as materializer
from src.search_intelligence.product_v1_downstream_preview import DownstreamPreviewStop


_CANONICAL_BUILD_PLAN = materializer.build_plan
_CANONICAL_FETCH = materializer.fetch_public_https_detail_text


def fetch_detail_isolated(url: str) -> tuple[str, str, str]:
    """Convert bounded detail-read stops into one candidate-local blocker."""

    try:
        return _CANONICAL_FETCH(url)
    except DownstreamPreviewStop as exc:
        raise materializer.MaterializationStop(str(exc)) from exc


def _bound_observation_detail(row: Mapping[str, object]) -> tuple[str, str] | None:
    """Return current persisted description/title only for exact URL-bound evidence.

    This helper grants no authority. The canonical materializer separately validates
    the row before requesting detail evidence. Here we merely refuse to reuse text
    unless the normalized observation, its nested job object and Silver all identify
    the exact same vacancy URL.
    """

    source_url = str(row.get("source_url") or "")
    normalized = row.get("latest_observation_evidence")
    if not source_url or not isinstance(normalized, Mapping):
        return None
    if str(row.get("latest_observation_source_url") or "") != source_url:
        return None
    if str(normalized.get("source_url") or "") != source_url:
        return None

    raw_evidence = normalized.get("raw_evidence")
    if not isinstance(raw_evidence, Mapping):
        return None
    job = raw_evidence.get("job")
    if not isinstance(job, Mapping) or str(job.get("source_url") or "") != source_url:
        return None

    description = str(job.get("description") or "").strip()
    if not description:
        return None
    title = str(job.get("title") or row.get("title") or "").strip()
    return title, description


def build_plan_isolated(*, rows, authorized_sources, policy_version):
    """Run canonical planning with exact observation text reuse and fetch isolation."""

    persisted_by_url: dict[str, tuple[str, str]] = {}
    conflicted_urls: set[str] = set()
    for row in rows:
        source_url = str(row.get("source_url") or "")
        detail = _bound_observation_detail(row)
        if not source_url or detail is None:
            continue
        previous = persisted_by_url.get(source_url)
        if previous is not None and previous != detail:
            conflicted_urls.add(source_url)
            persisted_by_url.pop(source_url, None)
            continue
        if source_url not in conflicted_urls:
            persisted_by_url[source_url] = detail

    counters = {"observation_reuse": 0, "network_fallback": 0}

    def detail_reader(url: str) -> tuple[str, str, str]:
        persisted = persisted_by_url.get(url)
        if persisted is not None:
            counters["observation_reuse"] += 1
            title, description = persisted
            return url, title, description
        counters["network_fallback"] += 1
        return fetch_detail_isolated(url)

    plan = _CANONICAL_BUILD_PLAN(
        rows=rows,
        authorized_sources=authorized_sources,
        policy_version=policy_version,
        fetch_detail=detail_reader,
    )
    boundaries = dict(plan.get("boundaries") or {})
    boundaries["network_exact_detail_targets"] = counters["network_fallback"]
    boundaries["current_observation_detail_reuse"] = counters["observation_reuse"]
    boundaries["network_retry_requests"] = 0
    return {**plan, "boundaries": boundaries}


def main(argv: Sequence[str] | None = None) -> int:
    """Delegate the full CLI after replacing only the batch planning boundary."""

    original = materializer.build_plan
    materializer.build_plan = build_plan_isolated
    try:
        return materializer.main(argv)
    finally:
        materializer.build_plan = original


if __name__ == "__main__":
    raise SystemExit(main())
