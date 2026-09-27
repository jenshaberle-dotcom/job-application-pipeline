from src.search_intelligence.employer_discovery_census import (
    build_employer_discovery_census,
    qualify_observation,
)
from src.search_intelligence.external_index_job_sensors import (
    EXTERNAL_INDEX_SOURCES,
    FIXTURE_QUALIFIED_SOURCES,
    accept_external_index_result,
    build_external_index_queries,
    classify_external_index_result_shape,
)


OBSERVED = "2026-09-27T20:30:00Z"


def test_external_index_cohort_is_explicit_and_parser_authority_is_narrower():
    assert EXTERNAL_INDEX_SOURCES == (
        "goodjobs",
        "xing",
        "get_in_it",
        "meinestadt",
        "jobvector",
    )
    assert FIXTURE_QUALIFIED_SOURCES == ("goodjobs", "xing", "get_in_it")


def test_query_builder_is_site_bounded_but_does_not_execute_transport():
    queries = build_external_index_queries(
        source="goodjobs",
        search_terms=["Data Engineer"],
        location_signals=["Hannover"],
    )
    assert len(queries) == 1
    assert '"goodjobs.eu/jobs/"' in queries[0].query
    assert '"Data Engineer"' in queries[0].query
    assert '"Hannover"' in queries[0].query
    assert "Germany" in queries[0].query


def test_goodjobs_index_result_becomes_minimised_remote_evidence():
    raw_url = (
        "https://goodjobs.eu/jobs/"
        "senior-data-engineer-in-renewable-energie-encavis-gmbh"
    )
    observation = accept_external_index_result(
        source="goodjobs",
        provider="fixture",
        url=raw_url,
        title="(Senior) Data Engineer in Renewable Energie - Encavis GmbH",
        snippet="Hamburg | 100% Remote · Vollzeit · Job online bis 30.09.2026",
        observed_at_utc=OBSERVED,
    )
    assert observation is not None
    assert observation.title == "(Senior) Data Engineer in Renewable Energie"
    assert observation.company_name == "Encavis GmbH"
    assert observation.remote_signal is True
    assert observation.location == "Remote"
    assert observation.description == ""
    assert raw_url not in observation.reference
    assert observation.reference.startswith("external-index:")

    qualified = qualify_observation(observation)
    assert qualified is not None
    assert qualified.remote_de_match is False
    assert qualified.location_confidence == "uncertain"
    assert qualified.location_reason == "remote_hint_needs_origin_qualification"


def test_xing_detail_result_requires_explicit_company_metadata():
    raw_url = "https://www.xing.com/jobs/hannover-data-engineer-germany-158080692"
    observation = accept_external_index_result(
        source="xing",
        provider="fixture",
        url=raw_url,
        title="Data Engineer - Germany in Hannover | XING Jobs",
        snippet="Hornetsecurity GmbH · Hannover · Hybrid · Data Engineer",
        observed_at_utc=OBSERVED,
    )
    assert observation is not None
    assert observation.title == "Data Engineer - Germany"
    assert observation.company_name == "Hornetsecurity GmbH"
    assert observation.location == "Hannover"
    assert qualify_observation(observation) is not None

    unattributed = accept_external_index_result(
        source="xing",
        provider="fixture",
        url=raw_url,
        title="Data Engineer - Germany in Hannover | XING Jobs",
        snippet="Hannover · Hybrid · Data Engineering role",
        observed_at_utc=OBSERVED,
    )
    assert unattributed is None


def test_xing_listing_page_is_not_mistaken_for_job_detail():
    assert classify_external_index_result_shape(
        source="xing",
        url="https://www.xing.com/jobs/data-engineer-jobs-in-hannover",
    ) == "unexpected_path"


def test_get_in_it_explicit_title_company_structure_is_supported():
    observation = accept_external_index_result(
        source="get_in_it",
        provider="fixture",
        url="https://www.get-in-it.de/jobsuche/p999999",
        title="Data Platform Engineer (m/w/d) | Finanz Informatik | get in IT",
        snippet="Frankfurt, Hannover oder Münster · Home-Office möglich",
        observed_at_utc=OBSERVED,
    )
    assert observation is not None
    assert observation.company_name == "Finanz Informatik"
    assert observation.title == "Data Platform Engineer (m/w/d)"
    assert observation.location == "Hannover remote"
    assert observation.remote_signal is True
    qualified = qualify_observation(observation)
    assert qualified is not None
    assert qualified.local_match is True


def test_shape_only_sources_cannot_create_observation_before_parser_proof():
    for source, url in (
        ("meinestadt", "https://jobs.meinestadt.de/hannover/standard?id=123"),
        ("jobvector", "https://www.jobvector.de/stellenangebote/123"),
    ):
        assert classify_external_index_result_shape(source=source, url=url) == (
            "shape_only_unqualified"
        )
        assert accept_external_index_result(
            source=source,
            provider="fixture",
            url=url,
            title="Data Engineer - Example GmbH",
            snippet="Hannover",
            observed_at_utc=OBSERVED,
        ) is None


def test_external_index_duplicate_reference_still_deduplicates_in_census():
    kwargs = dict(
        source="goodjobs",
        provider="fixture",
        url="https://goodjobs.eu/jobs/data-engineer-example-gmbh",
        title="Data Engineer - Example GmbH",
        snippet="Hannover",
        observed_at_utc=OBSERVED,
    )
    one = accept_external_index_result(**kwargs)
    two = accept_external_index_result(**kwargs)
    assert one is not None and two is not None
    report = build_employer_discovery_census([one, two])
    assert report["qualifying_job_count"] == 1
    assert report["employers"][0]["matching_job_count"] == 1


def test_remote_only_signal_survives_but_is_not_promoted_to_germany_remote():
    observation = accept_external_index_result(
        source="goodjobs",
        provider="fixture",
        url="https://goodjobs.eu/jobs/data-engineer-example-gmbh",
        title="Data Engineer - Example GmbH",
        snippet="100% Remote",
        observed_at_utc=OBSERVED,
    )
    assert observation is not None
    qualified = qualify_observation(observation)
    assert qualified is not None
    assert qualified.remote_de_match is False
    assert qualified.location_confidence == "uncertain"


def test_external_index_adapter_has_no_direct_board_transport_or_write_authority():
    import src.search_intelligence.external_index_job_sensors as sensor

    source = open(sensor.__file__, encoding="utf-8").read().casefold()
    for forbidden in (
        "import requests",
        "requests.get",
        "requests.post",
        "psycopg",
        "insert into",
        "delete from",
        "commit(",
    ):
        assert forbidden not in source
