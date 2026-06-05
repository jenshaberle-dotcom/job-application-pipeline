from __future__ import annotations

from src.search_intelligence.origin_job_observation import (
    AdaptiveObservationLoop,
    JobPageObservation,
    ObservationConfig,
    PageObservationInput,
    build_observation,
    extract_job_like_urls,
)


def observation(value: float) -> JobPageObservation:
    return JobPageObservation(
        source_url="https://example.com/jobs",
        final_url="https://example.com/jobs",
        host="example.com",
        source_family_guess=None,
        status_code=200,
        page_type_guess="search_listing",
        title="Jobs",
        ats_family_guess=None,
        has_json_ld_jobposting=False,
        visible_job_link_count=0,
        detail_url_patterns=(),
        location_signal_candidates=(),
        remote_signal_candidates=(),
        profile_signal_candidates=(),
        structural_markers=(),
        learning_value=value,
        novelty_reasons=(),
        storage_class="discard_after_run",
    )


def test_build_observation_extracts_structure_and_learning_value() -> None:
    html = """
    <html>
      <head>
        <title>Cloud Data Engineer - Jobs</title>
        <script type="application/ld+json">{"@type":"JobPosting","url":"/job/123"}</script>
      </head>
      <body>
        <a href="/job/123">Cloud Data Engineer</a>
        Standort: deutschlandweit. Homeoffice und mobiles Arbeiten möglich.
      </body>
    </html>
    """

    result = build_observation(
        PageObservationInput(
            source_url="https://careers.example.com/jobs",
            final_url="https://careers.example.com/jobs",
            status_code=200,
            title=None,
            body=html,
            source_family_guess="example",
        ),
        known_patterns=set(),
    )

    assert result.page_type_guess == "job_detail"
    assert result.has_json_ld_jobposting is True
    assert "/job/..." in result.detail_url_patterns
    assert "deutschlandweit" in result.location_signal_candidates
    assert "homeoffice" in result.remote_signal_candidates
    assert "data engineer" in result.profile_signal_candidates
    assert result.learning_value > 0.5
    assert result.storage_class == "full_observation"


def test_build_observation_scores_redundant_pages_low() -> None:
    html = "<html><title>Jobs</title><body><a href='/job/123'>Job</a></body></html>"
    known = {
        ("page_type", "search_listing"),
        ("url_path_pattern", "/job/..."),
        ("structural_marker", "visible_job_links"),
        ("url_path_pattern", "/search/..."),
        ("structural_marker", "page_type:search_listing"),
    }

    result = build_observation(
        PageObservationInput(
            source_url="https://careers.example.com/search/?q=data",
            final_url="https://careers.example.com/search/?q=data",
            status_code=200,
            title="Jobs",
            body=html,
        ),
        known_patterns=known,
    )

    assert result.learning_value < 0.20


def test_adaptive_observation_loop_stops_after_learning_saturation() -> None:
    loop = AdaptiveObservationLoop(
        ObservationConfig(
            min_observations=5,
            soft_cap=10,
            hard_cap=20,
            saturation_window=3,
            low_learning_threshold=0.10,
        )
    )

    for value in (0.7, 0.6, 0.5, 0.02, 0.01):
        loop.record(observation(value))

    assert loop.should_continue() is True
    loop.record(observation(0.01))
    assert loop.should_continue() is False
    assert loop.stop_reason == "learning_saturation"


def test_adaptive_observation_loop_extends_after_late_high_novelty() -> None:
    loop = AdaptiveObservationLoop(
        ObservationConfig(
            min_observations=3,
            soft_cap=5,
            hard_cap=12,
            saturation_window=2,
            high_learning_threshold=0.60,
            extension_size=4,
        )
    )

    for value in (0.5, 0.4, 0.2, 0.7):
        loop.record(observation(value))

    assert loop.current_cap == 9
    assert loop.should_continue() is True


def test_extract_job_like_urls_expands_same_host_job_links() -> None:
    html = """
    <a href="/job/123-cloud-data-engineer">Job</a>
    <a href="https://other.example.com/job/999">Other host</a>
    <a href="/about">About</a>
    """

    assert extract_job_like_urls(base_url="https://jobs.example.com/search/?q=data", body=html) == (
        "https://jobs.example.com/job/123-cloud-data-engineer",
    )


def test_seed_observation_decision_skips_duplicate_and_known_urls() -> None:
    from src.search_intelligence.origin_job_observation import decide_seed_observation, canonical_url_key

    url = "https://jobs.example.com/job/123/"
    duplicate = decide_seed_observation(
        url,
        seen_url_keys={canonical_url_key("https://jobs.example.com/job/123")},
        known_url_keys=set(),
        saturated_hosts=set(),
    )
    known = decide_seed_observation(
        url,
        seen_url_keys=set(),
        known_url_keys={canonical_url_key(url)},
        saturated_hosts=set(),
    )

    assert duplicate.should_observe is False
    assert duplicate.reason == "duplicate_in_run"
    assert known.should_observe is False
    assert known.reason == "known_seed_url"


def test_seed_observation_decision_limits_saturated_provider_hosts() -> None:
    from src.search_intelligence.origin_job_observation import decide_seed_observation

    allowed_sample = decide_seed_observation(
        "https://jobs.example.com/job/123",
        seen_url_keys=set(),
        known_url_keys=set(),
        saturated_hosts={"jobs.example.com"},
        saturated_host_counts={"jobs.example.com": 0},
        saturated_host_budget=1,
    )
    skipped_after_budget = decide_seed_observation(
        "https://jobs.example.com/job/456",
        seen_url_keys=set(),
        known_url_keys=set(),
        saturated_hosts={"jobs.example.com"},
        saturated_host_counts={"jobs.example.com": 1},
        saturated_host_budget=1,
    )
    revalidation = decide_seed_observation(
        "https://jobs.example.com/job/456",
        seen_url_keys=set(),
        known_url_keys={"https://jobs.example.com/job/456"},
        saturated_hosts={"jobs.example.com"},
        saturated_host_counts={"jobs.example.com": 1},
        saturated_host_budget=1,
        revalidate_known=True,
    )

    assert allowed_sample.should_observe is True
    assert skipped_after_budget.should_observe is False
    assert skipped_after_budget.reason == "saturated_provider_host"
    assert revalidation.should_observe is True


def test_observation_run_insert_statement_has_unique_boundary_column() -> None:
    import inspect

    from scripts import run_origin_job_structure_observation_agent as agent

    source = inspect.getsource(agent.create_run)

    assert "boundary,\n                boundary" not in source
    assert "seed_source_type_counts" in source


def test_run_local_host_saturation_after_repeated_low_value_pages() -> None:
    from scripts.run_origin_job_structure_observation_agent import update_run_local_host_saturation

    saturated_hosts: set[str] = set()
    low_value_counts: dict[str, int] = {}

    for _ in range(4):
        assert (
            update_run_local_host_saturation(
                saturated_hosts,
                low_value_counts,
                host="jobs.example.com",
                learning_value=0.0,
                min_observations=5,
                low_value_threshold=0.15,
            )
            is False
        )

    assert (
        update_run_local_host_saturation(
            saturated_hosts,
            low_value_counts,
            host="jobs.example.com",
            learning_value=0.0,
            min_observations=5,
            low_value_threshold=0.15,
        )
        is True
    )
    assert "jobs.example.com" in saturated_hosts


def test_run_local_host_saturation_resets_after_high_value_page() -> None:
    from scripts.run_origin_job_structure_observation_agent import update_run_local_host_saturation

    saturated_hosts: set[str] = set()
    low_value_counts: dict[str, int] = {}

    for value in (0.0, 0.0, 0.5, 0.0, 0.0):
        update_run_local_host_saturation(
            saturated_hosts,
            low_value_counts,
            host="jobs.example.com",
            learning_value=value,
            min_observations=3,
            low_value_threshold=0.15,
        )

    assert "jobs.example.com" not in saturated_hosts
    assert low_value_counts["jobs.example.com"] == 2
