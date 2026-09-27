from src.search_intelligence.employer_discovery_census import (
    CORE_SENSORS,
    MarketJobObservation,
    build_employer_discovery_census,
    qualify_observation,
)


def job(**overrides):
    values = {
        "source": "gutejobs",
        "title": "Machine Learning Engineer",
        "company_name": "Example GmbH",
        "location": "Hannover",
        "observed_at_utc": "2026-09-27T19:00:00Z",
        "reference": "job-1",
    }
    values.update(overrides)
    return MarketJobObservation(**values)


def test_core_census_includes_old_and_new_boards():
    assert CORE_SENSORS == (
        "bundesagentur_fuer_arbeit",
        "stepstone",
        "gutejobs",
        "xing",
        "meinestadt",
        "get_in_it",
        "jobvector",
    )


def test_irrelevant_job_cannot_create_employer():
    report = build_employer_discovery_census(
        [job(title="Verkäufer", description="Einzelhandel")]
    )
    assert report["qualifying_job_count"] == 0
    assert report["employers"] == []


def test_unknown_employer_fails_closed():
    assert qualify_observation(job(company_name=None)) is None


def test_qualifying_job_creates_exactly_one_employer():
    report = build_employer_discovery_census([job()])
    assert report["employer_count"] == 1
    assert report["employers"][0]["matching_job_count"] == 1
    assert report["employers"][0]["origin_status"] == "novel"


def test_duplicate_company_across_boards_is_one_employer_with_two_jobs():
    report = build_employer_discovery_census(
        [
            job(reference="g-1"),
            job(
                source="stepstone",
                company_name="Example GmbH",
                reference="s-1",
                title="Data Engineer",
            ),
        ]
    )
    assert report["employer_count"] == 1
    row = report["employers"][0]
    assert row["matching_job_count"] == 2
    assert row["evidence_sources"] == ["gutejobs", "stepstone"]


def test_known_candidate_is_retained_as_evidence_but_not_novel():
    report = build_employer_discovery_census(
        [job()], known_company_keys=["Example GmbH"]
    )
    assert report["employers"][0]["origin_status"] == "known_candidate"
    assert report["novel_employer_count"] == 0
    assert report["source_metrics"]["gutejobs"]["novel_employers_vs_baseline"] == 0


def test_local_and_germany_remote_are_counted_separately():
    report = build_employer_discovery_census(
        [
            job(reference="local"),
            job(
                reference="remote",
                location="Deutschland remote",
                remote_signal=True,
                title="Data Platform Engineer",
            ),
        ]
    )
    row = report["employers"][0]
    assert row["local_matches"] == 1
    assert row["remote_de_matches"] == 1


def test_same_job_reference_is_deduplicated_for_matching_count():
    report = build_employer_discovery_census([job(), job()])
    assert report["employers"][0]["matching_job_count"] == 1
    assert report["qualifying_job_count"] == 1


def test_source_metrics_measure_jobs_not_raw_company_signals():
    report = build_employer_discovery_census(
        [
            job(reference="ok"),
            job(reference="bad", title="Verkäufer", company_name="Noise AG"),
            job(reference="unknown", company_name=None),
        ]
    )
    metrics = report["source_metrics"]["gutejobs"]
    assert metrics["observed_jobs"] == 3
    assert metrics["qualifying_jobs"] == 1
    assert metrics["unique_qualifying_employers"] == 1
    assert metrics["employer_attribution_rate"] == 2 / 3
