from scripts.evaluate_aggregator_discovery_candidates import (
    CANDIDATES,
    JobMatch,
    csv_safe_row,
    jobs_to_matches,
    matched_terms_for_job,
    parse_adzuna_jobs,
    parse_arbeitnow_jobs,
    parse_remotive_jobs,
    summarize_matches,
)


def test_commercial_platforms_are_not_probed_by_default() -> None:
    strategies = {candidate.platform: candidate.probe_strategy for candidate in CANDIDATES}

    assert strategies["linkedin"] == "none_hard_gated"
    assert strategies["xing"] == "none_hard_gated"
    assert strategies["indeed"] == "none_hard_gated"
    assert strategies["glassdoor"] == "none_hard_gated"


def test_api_friendly_candidates_have_bounded_probe_strategies() -> None:
    strategies = {candidate.platform: candidate.probe_strategy for candidate in CANDIDATES}

    assert strategies["arbeitnow"] == "arbeitnow_public_api"
    assert strategies["adzuna"] == "adzuna_search_api"
    assert strategies["jooble"] == "jooble_rest_api"
    assert strategies["remotive"] == "remotive_public_api"


def test_matched_terms_support_phrase_and_token_matching() -> None:
    job = {
        "title": "Senior Analytics Engineer",
        "description": "Build Python based data platform pipelines.",
        "company": "Example GmbH",
        "location": "Remote Germany",
    }

    assert matched_terms_for_job(
        job,
        ("Analytics Engineer", "Python SQL", "Data Platform"),
    ) == ("Analytics Engineer", "Data Platform")


def test_parse_arbeitnow_jobs_keeps_minimal_fields() -> None:
    payload = {
        "data": [
            {
                "slug": "data-engineer-1",
                "title": "Data Engineer",
                "company_name": "Example GmbH",
                "location": "Hannover",
                "remote": True,
                "url": "https://example.test/job/1",
                "description": "<p>Python SQL</p>",
                "tags": ["IT", "Remote"],
            }
        ]
    }

    jobs = parse_arbeitnow_jobs(payload)

    assert jobs == [
        {
            "source_job_id": "data-engineer-1",
            "title": "Data Engineer",
            "company": "Example GmbH",
            "location": "Hannover",
            "remote": True,
            "url": "https://example.test/job/1",
            "description": "Python SQL",
            "tags": "IT Remote",
        }
    ]


def test_parse_remotive_jobs_keeps_minimal_fields() -> None:
    payload = {
        "jobs": [
            {
                "id": 123,
                "title": "Data Platform Engineer",
                "company_name": "Remote Corp",
                "candidate_required_location": "Germany",
                "url": "https://remotive.com/remote-jobs/123",
                "description": "ETL",
                "category": "Data",
            }
        ]
    }

    jobs = parse_remotive_jobs(payload)

    assert jobs[0]["source_job_id"] == "123"
    assert jobs[0]["company"] == "Remote Corp"
    assert jobs[0]["remote"] is True


def test_parse_adzuna_jobs_supports_nested_company_and_location() -> None:
    payload = {
        "results": [
            {
                "id": "abc",
                "title": "Analytics Engineer",
                "company": {"display_name": "Adzuna Example"},
                "location": {"display_name": "Hannover, Niedersachsen"},
                "redirect_url": "https://example.test",
                "description": "Data Warehouse",
            }
        ]
    }

    jobs = parse_adzuna_jobs(payload)

    assert jobs[0]["company"] == "Adzuna Example"
    assert jobs[0]["location"] == "Hannover, Niedersachsen"


def test_summarize_matches_counts_companies_terms_and_location_signals() -> None:
    matches = [
        JobMatch(
            platform="arbeitnow",
            query="local_filter_page=1",
            title="Data Engineer",
            company="Example GmbH",
            location="Hannover",
            remote_signal="unknown",
            url="https://example.test/1",
            source_job_id="1",
            matched_terms=("Data Engineer",),
        ),
        JobMatch(
            platform="remotive",
            query="Analytics Engineer",
            title="Analytics Engineer",
            company="Example GmbH",
            location="Germany",
            remote_signal="remote",
            url="https://example.test/2",
            source_job_id="2",
            matched_terms=("Analytics Engineer",),
        ),
    ]

    company_count, matched_terms, location_signals = summarize_matches(matches)

    assert company_count == 1
    assert matched_terms == "Analytics Engineer=1; Data Engineer=1"
    assert location_signals == "hannover=1; remote,germany=1"


def test_match_export_formats_matched_terms_as_reviewable_string() -> None:
    row = csv_safe_row(
        JobMatch(
            platform="arbeitnow",
            query="local_filter_page=1",
            title="Data Engineer",
            company="Example GmbH",
            location="Hannover",
            remote_signal="unknown",
            url="https://example.test/1",
            source_job_id="1",
            matched_terms=("Data Engineer", "ETL"),
        )
    )

    assert row["matched_terms"] == "Data Engineer; ETL"


def test_jobs_to_matches_respects_zero_remaining_limit() -> None:
    matches = jobs_to_matches(
        platform="arbeitnow",
        query="local_filter_page=1",
        jobs=[{"title": "Data Engineer", "company": "Example GmbH"}],
        search_terms=("Data Engineer",),
        max_matches_per_source=0,
    )

    assert matches == []
