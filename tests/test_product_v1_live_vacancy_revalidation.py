from __future__ import annotations

from dataclasses import replace

from src.job_lifecycle_health import (
    HttpProbeResult,
    JobHealthTarget,
)
from src.search_intelligence.product_v1_live_vacancy_revalidation import (
    OBSERVED_BY,
    revalidate_selected_vacancy,
)


URL = "https://karriere.accompio.com/de?id=7879f1"


def _target() -> JobHealthTarget:
    return JobHealthTarget(
        silver_job_id=626,
        raw_job_id=9001,
        ingestion_run_id=123,
        source_name="accompio:discovery",
        external_job_id="de:7879f1",
        source_url=URL,
        title="AI Automation Engineer (m/w/d)",
        canonical_source_type="employer_origin_career_site",
        raw_source_type="employer_origin_career_site",
    )


class FakeRepository:
    def __init__(self, target: JobHealthTarget) -> None:
        self.target = target
        self.writes: list[tuple[object, object, str]] = []

    def load_target(self, silver_job_id: int) -> JobHealthTarget:
        assert silver_job_id == self.target.silver_job_id
        return self.target

    def append_health_observation(self, *, expected_target, classification, observed_by):
        self.writes.append((expected_target, classification, observed_by))
        return 77


def test_active_exact_probe_is_read_only() -> None:
    repo = FakeRepository(_target())

    result = revalidate_selected_vacancy(
        silver_job_id=626,
        expected_source_name="accompio:discovery",
        expected_source_url=URL,
        repository=repo,
        fetcher=lambda _url: HttpProbeResult(
            status_code=200,
            final_url=URL,
            response_text="<h1>AI Automation Engineer (m/w/d)</h1><p>Python automation</p>",
            redirect_count=0,
        ),
    )

    assert result.status == "active"
    assert result.active is True
    assert result.closed is False
    assert result.http_requests == 1
    assert result.health_observation_writes == 0
    assert repo.writes == []


def test_accompio_explicit_missing_vacancy_page_is_persisted_as_closed() -> None:
    repo = FakeRepository(_target())

    result = revalidate_selected_vacancy(
        silver_job_id=626,
        expected_source_name="accompio:discovery",
        expected_source_url=URL,
        repository=repo,
        fetcher=lambda _url: HttpProbeResult(
            status_code=200,
            final_url=URL,
            response_text=(
                "<html><body><h1>Die Stellenanzeige konnte nicht gefunden werden</h1>"
                "<p>Unter der angegebenen URL konnte keine Stellenanzeige gefunden werden.</p>"
                "</body></html>"
            ),
            redirect_count=0,
        ),
    )

    assert result.status == "closed"
    assert result.closed is True
    assert result.health_observation_writes == 1
    assert result.observation_id == 77
    assert len(repo.writes) == 1
    _target_written, classification, observed_by = repo.writes[0]
    assert classification.outcome == "closed"
    assert classification.evidence_reason == "explicit_vacancy_unavailable_on_exact_detail"
    assert classification.evidence["explicit_closure_marker"] == "stellenanzeige_nicht_gefunden"
    assert observed_by == OBSERVED_BY


def test_unverifiable_probe_never_changes_lifecycle_truth() -> None:
    repo = FakeRepository(_target())

    result = revalidate_selected_vacancy(
        silver_job_id=626,
        expected_source_name="accompio:discovery",
        expected_source_url=URL,
        repository=repo,
        fetcher=lambda _url: HttpProbeResult(
            status_code=None,
            final_url=URL,
            response_text="",
            redirect_count=0,
            error_type="Timeout",
            error_message="network unavailable",
        ),
    )

    assert result.status == "unverifiable"
    assert result.active is False
    assert result.closed is False
    assert result.health_observation_writes == 0
    assert repo.writes == []


def test_identity_drift_is_rejected_before_network_probe() -> None:
    repo = FakeRepository(replace(_target(), source_url="https://karriere.accompio.com/de?id=other"))
    called = False

    def fetcher(_url: str):
        nonlocal called
        called = True
        raise AssertionError("network must not run after identity drift")

    try:
        revalidate_selected_vacancy(
            silver_job_id=626,
            expected_source_name="accompio:discovery",
            expected_source_url=URL,
            repository=repo,
            fetcher=fetcher,
        )
    except ValueError as exc:
        assert "Source URL mismatch" in str(exc)
    else:
        raise AssertionError("identity drift must fail closed")

    assert called is False
