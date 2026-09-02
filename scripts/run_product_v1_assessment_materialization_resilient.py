"""Resilient entry point for generic Product V1 assessment materialization.

The canonical materializer already treats ``MaterializationStop`` and ``ValueError``
as per-candidate plan blockers. Its bounded public-detail reader, however, reports
HTTP/DNS/transport failures as ``DownstreamPreviewStop``. This adapter translates
only that transport/read boundary into the materializer's existing fail-closed
candidate blocker so one unavailable detail page cannot abort the whole batch.

No retry, alternate route, authority relaxation, assessment inference, or write
behavior is added. Apply semantics remain exactly those of the canonical runner.
"""
from __future__ import annotations

from typing import Sequence

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


def build_plan_isolated(*, rows, authorized_sources, policy_version):
    """Run the canonical plan while isolating detail-fetch failures per job."""

    return _CANONICAL_BUILD_PLAN(
        rows=rows,
        authorized_sources=authorized_sources,
        policy_version=policy_version,
        fetch_detail=fetch_detail_isolated,
    )


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
