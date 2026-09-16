"""Bounded exact-detail truth for reviewed Personio complete inventories.

A reviewed Personio XML inventory is useful source-level currentness evidence, but
it cannot prove that every concrete ``/job/<id>`` detail route is still usable.
The provider can temporarily keep an entry in the XML feed after the concrete job
URL has already become a Personio 404 page.

This module therefore performs one bounded exact-detail confirmation pass for the
already-reviewed Personio authority set after normal Employer-Origin ingestion.
It is provider-specific, never employer-specific, and grants no ranking, Fit,
Combined-score or application authority.

Only deterministic outcomes are written:
- normal exact-detail ``seen_active`` from the shared lifecycle classifier;
- normal exact-detail ``closed`` from the shared lifecycle classifier;
- Personio's explicit German 404 page (``Diese URL existiert nicht``) on the
  exact expected ``*.jobs.personio.de/job/...`` identity.

Generic 404s, redirects, transport failures and other ambiguous outcomes remain
unverifiable and do not overwrite positive truth.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Callable
from urllib.parse import urlsplit

from src.job_lifecycle_health import (
    COVERAGE_EXACT_DETAIL,
    OUTCOME_CLOSED,
    OUTCOME_SEEN_ACTIVE,
    OUTCOME_UNVERIFIABLE,
    REQUEST_TIMEOUT_SECONDS,
    HealthClassification,
    HttpProbeResult,
    JobHealthTarget,
    JobLifecycleHealthRepository,
    classify_exact_detail,
    ensure_expected_target_identity,
    fetch_exact_detail,
    normalize_url_identity,
)
from src.search_intelligence.personio_legacy_authority_bindings import (
    REVIEWED_LEGACY_PERSONIO_AUTHORITY_BINDINGS,
)
from src.search_intelligence.vacancy_page_signals import normalize_page_text


MAX_PERSONIO_DETAIL_PROBES_PER_SOURCE = 50
PERSONIO_DETAIL_HEALTH_OBSERVER = "scheduled_daily_reviewed_personio_exact_detail"
PERSONIO_NOT_FOUND_MARKER = "diese url existiert nicht"


@dataclass(frozen=True)
class PersonioDetailHealthSummary:
    source_name: str
    target_count: int
    probe_count: int
    seen_active_write_count: int
    closed_write_count: int
    unverifiable_count: int
    written_observation_ids: tuple[int, ...]

    def canonical_payload(self) -> dict[str, object]:
        return {
            "source_name": self.source_name,
            "target_count": self.target_count,
            "probe_count": self.probe_count,
            "seen_active_write_count": self.seen_active_write_count,
            "closed_write_count": self.closed_write_count,
            "unverifiable_count": self.unverifiable_count,
            "written_observation_ids": list(self.written_observation_ids),
        }


def _is_personio_job_detail(url: str) -> bool:
    parsed = urlsplit(str(url or "").strip())
    host = (parsed.hostname or "").casefold()
    path = parsed.path.rstrip("/")
    return bool(
        parsed.scheme in {"http", "https"}
        and host.endswith(".jobs.personio.de")
        and path.startswith("/job/")
        and len(path) > len("/job/")
    )


def classify_reviewed_personio_exact_detail(
    target: JobHealthTarget,
    probe: HttpProbeResult,
) -> HealthClassification:
    """Apply one narrow Personio closure contract around the shared classifier."""

    classification = classify_exact_detail(target, probe)
    if classification.outcome != OUTCOME_UNVERIFIABLE:
        return classification
    if probe.status_code != 404:
        return classification
    if not _is_personio_job_detail(target.source_url):
        return classification
    if normalize_url_identity(target.source_url) != normalize_url_identity(probe.final_url):
        return classification
    if PERSONIO_NOT_FOUND_MARKER not in normalize_page_text(probe.response_text):
        return classification

    evidence = dict(classification.evidence)
    evidence.update(
        {
            "provider": "personio",
            "provider_closure_contract": "personio_exact_job_404_v1",
            "provider_closure_marker": "personio_url_does_not_exist",
        }
    )
    return HealthClassification(
        outcome=OUTCOME_CLOSED,
        coverage=COVERAGE_EXACT_DETAIL,
        evidence_reason="personio_explicit_job_url_not_found",
        evidence=evidence,
    )


def reconcile_reviewed_personio_detail_health(
    *,
    health_repository: JobLifecycleHealthRepository,
    fetcher: Callable[..., HttpProbeResult] = fetch_exact_detail,
    timeout_seconds: float = REQUEST_TIMEOUT_SECONDS,
    max_probes_per_source: int = MAX_PERSONIO_DETAIL_PROBES_PER_SOURCE,
) -> tuple[PersonioDetailHealthSummary, ...]:
    """Confirm every currently-active target in the reviewed Personio authority set."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if max_probes_per_source <= 0:
        raise ValueError("max_probes_per_source must be positive")

    summaries: list[PersonioDetailHealthSummary] = []
    for target_key in sorted(REVIEWED_LEGACY_PERSONIO_AUTHORITY_BINDINGS):
        source_name = f"personio:{target_key}"
        targets = health_repository.load_active_targets_for_verified_complete_inventory_source(
            source_name
        )
        if len(targets) > max_probes_per_source:
            raise RuntimeError(
                "reviewed Personio exact-detail probe cap exceeded: "
                f"source={source_name} targets={len(targets)} "
                f"max={max_probes_per_source}"
            )

        seen_active_write_count = 0
        closed_write_count = 0
        unverifiable_count = 0
        written_ids: list[int] = []

        for target in targets:
            ensure_expected_target_identity(
                target,
                expected_source_name=source_name,
                expected_source_url=target.source_url,
            )
            probe = fetcher(target.source_url, timeout_seconds=timeout_seconds)
            classification = classify_reviewed_personio_exact_detail(target, probe)

            if classification.outcome not in {OUTCOME_SEEN_ACTIVE, OUTCOME_CLOSED}:
                unverifiable_count += 1
                continue

            observation_id = health_repository.append_health_observation(
                expected_target=target,
                classification=classification,
                observed_by=PERSONIO_DETAIL_HEALTH_OBSERVER,
                ingestion_run_id=None,
            )
            written_ids.append(observation_id)
            if classification.outcome == OUTCOME_CLOSED:
                closed_write_count += 1
            else:
                seen_active_write_count += 1

        summaries.append(
            PersonioDetailHealthSummary(
                source_name=source_name,
                target_count=len(targets),
                probe_count=len(targets),
                seen_active_write_count=seen_active_write_count,
                closed_write_count=closed_write_count,
                unverifiable_count=unverifiable_count,
                written_observation_ids=tuple(written_ids),
            )
        )

    return tuple(summaries)


def main() -> int:
    summaries = reconcile_reviewed_personio_detail_health(
        health_repository=JobLifecycleHealthRepository()
    )
    print(
        json.dumps(
            {
                "schema": "job_application_pipeline.reviewed_personio_detail_health.v1",
                "observer": PERSONIO_DETAIL_HEALTH_OBSERVER,
                "sources": [summary.canonical_payload() for summary in summaries],
                "boundary": {
                    "reviewed_personio_sources_only": True,
                    "employer_specific_branching": False,
                    "ranking_writes": False,
                    "fit_writes": False,
                    "combined_score_writes": False,
                    "application_writes": False,
                    "provider_or_llm_requests": 0,
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
