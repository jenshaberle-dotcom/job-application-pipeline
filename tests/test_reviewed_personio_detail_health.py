from __future__ import annotations

import pytest

from scripts.reconcile_reviewed_personio_detail_health import (
    PERSONIO_DETAIL_HEALTH_OBSERVER,
    classify_reviewed_personio_exact_detail,
    reconcile_reviewed_personio_detail_health,
)
from src.job_lifecycle_health import (
    OUTCOME_CLOSED,
    OUTCOME_SEEN_ACTIVE,
    OUTCOME_UNVERIFIABLE,
    HttpProbeResult,
    JobHealthTarget,
)


def target(
    *,
    silver_job_id: int = 1,
    source_name: str = "personio:1komma5grad",
    source_url: str = "https://1komma5grad.jobs.personio.de/job/2731150?language=de",
    title: str = "(Junior) Data Engineer - Data Platform (m/f/d)",
) -> JobHealthTarget:
    return JobHealthTarget(
        silver_job_id=silver_job_id,
        raw_job_id=100 + silver_job_id,
        ingestion_run_id=200 + silver_job_id,
        source_name=source_name,
        external_job_id=str(2731150 + silver_job_id),
        source_url=source_url,
        title=title,
        canonical_source_type="employer_origin_ats_backed_career_site",
        raw_source_type="employer_origin_ats_backed_career_site",
    )


class FakeRepository:
    def __init__(self, targets_by_source: dict[str, list[JobHealthTarget]]) -> None:
        self.targets_by_source = targets_by_source
        self.writes: list[tuple[JobHealthTarget, object, str, int | None]] = []

    def load_active_targets_for_verified_complete_inventory_source(
        self,
        source_name: str,
    ) -> list[JobHealthTarget]:
        return list(self.targets_by_source.get(source_name, []))

    def append_health_observation(
        self,
        *,
        expected_target: JobHealthTarget,
        classification,
        observed_by: str,
        ingestion_run_id: int | None = None,
    ) -> int:
        self.writes.append(
            (expected_target, classification, observed_by, ingestion_run_id)
        )
        return 900 + len(self.writes)


def test_personio_exact_job_404_template_is_closed() -> None:
    current = target()
    result = classify_reviewed_personio_exact_detail(
        current,
        HttpProbeResult(
            status_code=404,
            final_url=current.source_url,
            response_text=(
                "<html><h1>404</h1><p>Diese URL existiert nicht</p>"
                "<a>Zurück zu allen Stellen</a></html>"
            ),
            redirect_count=0,
        ),
    )

    assert result.outcome == OUTCOME_CLOSED
    assert result.evidence_reason == "personio_explicit_job_url_not_found"
    assert result.evidence["provider"] == "personio"
    assert result.evidence["provider_closure_contract"] == "personio_exact_job_404_v1"


def test_generic_404_stays_unverifiable() -> None:
    current = target(
        source_name="generic_origin:example",
        source_url="https://jobs.example.test/job/123",
    )
    result = classify_reviewed_personio_exact_detail(
        current,
        HttpProbeResult(
            status_code=404,
            final_url=current.source_url,
            response_text="Diese URL existiert nicht",
            redirect_count=0,
        ),
    )

    assert result.outcome == OUTCOME_UNVERIFIABLE
    assert result.evidence_reason == "http_404_requires_source_specific_closure_validation"


def test_reviewed_personio_current_feed_target_is_exact_detail_rechecked() -> None:
    dead = target()
    alive = target(
        silver_job_id=2,
        source_name="personio:eraneos",
        source_url="https://eraneos.jobs.personio.de/job/555?language=de",
        title="Data Engineer",
    )
    repository = FakeRepository(
        {
            "personio:1komma5grad": [dead],
            "personio:eraneos": [alive],
        }
    )
    fetched: list[str] = []

    def fetcher(url: str, *, timeout_seconds: float) -> HttpProbeResult:
        fetched.append(url)
        assert timeout_seconds > 0
        if "1komma5grad" in url:
            return HttpProbeResult(
                status_code=404,
                final_url=url,
                response_text="404 Diese URL existiert nicht Zurück zu allen Stellen",
                redirect_count=0,
            )
        return HttpProbeResult(
            status_code=200,
            final_url=url,
            response_text="<h1>Data Engineer</h1><p>Apply now</p>",
            redirect_count=0,
        )

    summaries = reconcile_reviewed_personio_detail_health(
        health_repository=repository,
        fetcher=fetcher,
    )

    assert len(fetched) == 2
    by_source = {summary.source_name: summary for summary in summaries}
    assert by_source["personio:1komma5grad"].closed_write_count == 1
    assert by_source["personio:eraneos"].seen_active_write_count == 1
    assert len(repository.writes) == 2
    assert repository.writes[0][2] == PERSONIO_DETAIL_HEALTH_OBSERVER
    assert repository.writes[0][3] is None
    assert {write[1].outcome for write in repository.writes} == {
        OUTCOME_CLOSED,
        OUTCOME_SEEN_ACTIVE,
    }


def test_probe_cap_fails_before_network_or_write() -> None:
    too_many = [
        target(
            silver_job_id=index,
            source_url=f"https://1komma5grad.jobs.personio.de/job/{1000 + index}?language=de",
        )
        for index in range(1, 4)
    ]
    repository = FakeRepository({"personio:1komma5grad": too_many})
    fetch_calls = 0

    def forbidden_fetcher(url: str, *, timeout_seconds: float) -> HttpProbeResult:
        nonlocal fetch_calls
        fetch_calls += 1
        raise AssertionError("cap must fail before network")

    with pytest.raises(RuntimeError, match="probe cap exceeded"):
        reconcile_reviewed_personio_detail_health(
            health_repository=repository,
            fetcher=forbidden_fetcher,
            max_probes_per_source=2,
        )

    assert fetch_calls == 0
    assert repository.writes == []
