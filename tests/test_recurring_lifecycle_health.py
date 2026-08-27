from __future__ import annotations

from src.connectors.base import RawJobRecord
from src.ingestion.recurring_lifecycle_health import (
    RECURRING_HEALTH_OBSERVER,
    reconcile_recurring_exact_detail_health,
)
from src.job_lifecycle_health import (
    OUTCOME_CLOSED,
    OUTCOME_SEEN_ACTIVE,
    HttpProbeResult,
    JobHealthTarget,
)


def target(
    *,
    silver_job_id: int = 1,
    external_job_id: str = "job-1",
    source_url: str = "https://jobs.example.com/job/1",
    title: str = "Data Engineer",
) -> JobHealthTarget:
    return JobHealthTarget(
        silver_job_id=silver_job_id,
        raw_job_id=100 + silver_job_id,
        ingestion_run_id=200 + silver_job_id,
        source_name="example:origin",
        external_job_id=external_job_id,
        source_url=source_url,
        title=title,
        canonical_source_type="employer_origin_career_site",
        raw_source_type="employer_origin_career_site",
    )


def record(
    *,
    external_job_id: str = "job-1",
    source_url: str = "https://jobs.example.com/job/1",
) -> RawJobRecord:
    return RawJobRecord(
        source_name="example:origin",
        source_url=source_url,
        external_job_id=external_job_id,
        raw_data={"job": {"title": "Data Engineer"}},
    )


class FakeHealthRepository:
    def __init__(self, targets: list[JobHealthTarget]) -> None:
        self.targets = targets
        self.writes: list[tuple[JobHealthTarget, object, str, int | None]] = []

    def load_active_targets_for_source(
        self,
        source_name: str,
    ) -> list[JobHealthTarget]:
        assert source_name == "example:origin"
        return list(self.targets)

    def append_health_observation(
        self,
        *,
        expected_target: JobHealthTarget,
        classification,
        observed_by: str,
        ingestion_run_id: int | None = None,
    ) -> int:
        self.writes.append(
            (
                expected_target,
                classification,
                observed_by,
                ingestion_run_id,
            )
        )
        return 900 + len(self.writes)


def test_currently_observed_target_is_not_reprobed() -> None:
    repository = FakeHealthRepository([target()])
    fetch_calls = 0

    def forbidden_fetcher(url: str, *, timeout_seconds: float):
        nonlocal fetch_calls
        fetch_calls += 1
        raise AssertionError("observed target must not be re-probed")

    summary = reconcile_recurring_exact_detail_health(
        health_repository=repository,
        source_name="example:origin",
        observed_records=[record()],
        ingestion_run_id=700,
        fetcher=forbidden_fetcher,
    )

    assert fetch_calls == 0
    assert repository.writes == []
    assert summary.target_count == 1
    assert summary.observed_target_count == 1
    assert summary.missing_target_count == 0
    assert summary.probe_count == 0


def test_exact_url_match_counts_as_observed_even_when_external_id_drifted() -> None:
    repository = FakeHealthRepository([target()])
    fetch_calls = 0

    def forbidden_fetcher(url: str, *, timeout_seconds: float):
        nonlocal fetch_calls
        fetch_calls += 1
        raise AssertionError("same exact URL is observed")

    summary = reconcile_recurring_exact_detail_health(
        health_repository=repository,
        source_name="example:origin",
        observed_records=[
            record(
                external_job_id="new-provider-id",
                source_url="https://jobs.example.com/job/1",
            )
        ],
        ingestion_run_id=701,
        fetcher=forbidden_fetcher,
    )

    assert fetch_calls == 0
    assert summary.observed_target_count == 1


def test_missing_target_with_explicit_2xx_closure_writes_closed() -> None:
    repository = FakeHealthRepository([target()])

    def closed_fetcher(url: str, *, timeout_seconds: float) -> HttpProbeResult:
        assert url == "https://jobs.example.com/job/1"
        assert timeout_seconds > 0
        return HttpProbeResult(
            status_code=200,
            final_url=url,
            response_text=(
                "You can't view this job because it's not available at this time."
            ),
            redirect_count=0,
        )

    summary = reconcile_recurring_exact_detail_health(
        health_repository=repository,
        source_name="example:origin",
        observed_records=[],
        ingestion_run_id=702,
        fetcher=closed_fetcher,
    )

    assert summary.probe_count == 1
    assert summary.closed_write_count == 1
    assert summary.seen_active_write_count == 0
    assert summary.unverifiable_count == 0
    assert len(repository.writes) == 1

    _, classification, observed_by, ingestion_run_id = repository.writes[0]
    assert classification.outcome == OUTCOME_CLOSED
    assert observed_by == RECURRING_HEALTH_OBSERVER
    assert ingestion_run_id == 702


def test_missing_target_still_active_writes_positive_exact_health() -> None:
    repository = FakeHealthRepository([target()])

    def active_fetcher(url: str, *, timeout_seconds: float) -> HttpProbeResult:
        return HttpProbeResult(
            status_code=200,
            final_url=url,
            response_text="<h1>Data Engineer</h1><p>Apply now</p>",
            redirect_count=0,
        )

    summary = reconcile_recurring_exact_detail_health(
        health_repository=repository,
        source_name="example:origin",
        observed_records=[],
        ingestion_run_id=703,
        fetcher=active_fetcher,
    )

    assert summary.seen_active_write_count == 1
    assert summary.closed_write_count == 0
    assert len(repository.writes) == 1
    assert repository.writes[0][1].outcome == OUTCOME_SEEN_ACTIVE


def test_unverifiable_probe_never_supersedes_positive_truth() -> None:
    repository = FakeHealthRepository([target()])

    def not_found_fetcher(url: str, *, timeout_seconds: float) -> HttpProbeResult:
        return HttpProbeResult(
            status_code=404,
            final_url=url,
            response_text="Not found",
            redirect_count=0,
        )

    summary = reconcile_recurring_exact_detail_health(
        health_repository=repository,
        source_name="example:origin",
        observed_records=[],
        ingestion_run_id=704,
        fetcher=not_found_fetcher,
    )

    assert summary.unverifiable_count == 1
    assert summary.closed_write_count == 0
    assert summary.seen_active_write_count == 0
    assert repository.writes == []


def test_bulk_miss_above_probe_cap_fails_before_network_or_write() -> None:
    targets = [
        target(
            silver_job_id=index,
            external_job_id=f"job-{index}",
            source_url=f"https://jobs.example.com/job/{index}",
        )
        for index in (1, 2, 3)
    ]
    repository = FakeHealthRepository(targets)
    fetch_calls = 0

    def forbidden_fetcher(
        url: str,
        *,
        timeout_seconds: float,
    ) -> HttpProbeResult:
        nonlocal fetch_calls
        fetch_calls += 1
        raise AssertionError("bulk miss must fail before exact-detail probes")

    import pytest

    with pytest.raises(
        RuntimeError,
        match="bulk miss exceeds bounded probe cap",
    ):
        reconcile_recurring_exact_detail_health(
            health_repository=repository,
            source_name="example:origin",
            observed_records=[],
            ingestion_run_id=705,
            fetcher=forbidden_fetcher,
            max_probes=2,
        )

    assert fetch_calls == 0
    assert repository.writes == []
