from __future__ import annotations

from src.search_intelligence.relevance_evidence_probe import (
    build_probe_url_queue,
    generated_search_urls,
    relevance_signals,
)


def test_relevance_signals_accept_deutschlandweit_data_analytics_detail_page() -> None:
    text = """
    Cloud Data Engineer Databricks (all genders)
    Standort: deutschlandweit
    Flexibilität: Hybrid, Vollzeit
    Berufsfeld: Data & Analytics
    """

    signals = relevance_signals(text, target_location="hannover", source_target="hannover")

    assert "data engineer" in signals.profile_hits
    assert "databricks" in signals.profile_hits
    assert "deutschlandweit" in signals.remote_hits
    assert signals.is_relevant is True


def test_relevance_signals_do_not_accept_unrelated_local_detail_page() -> None:
    text = """
    Software Engineer Java
    Standort: Aachen
    Flexibilität: Hybrid, Vollzeit
    Berufsfeld: Software Engineering
    """

    signals = relevance_signals(text, target_location="hannover", source_target="hannover")

    assert signals.has_target_or_remote_evidence is False
    assert signals.is_relevant is False


def test_probe_queue_keeps_bounded_job_search_urls_for_job_host() -> None:
    queue = build_probe_url_queue(
        candidate_url="https://jobs.adesso-group.com/",
        initial_body='<a href="/job/Aachen-Cloud-Data-Engineer-Databricks-%28all-genders%29-NW-52070/1145683555/">Job</a>',
        source_family_candidate="adesso",
        company_key="adesso",
        max_links=8,
    )

    assert "https://jobs.adesso-group.com/" == queue[0]
    assert "https://jobs.adesso-group.com/search/?q=Data+Engineer" in queue
    assert "https://jobs.adesso-group.com/job/Aachen-Cloud-Data-Engineer-Databricks-%28all-genders%29-NW-52070/1145683555/" in queue

from src.search_intelligence.relevance_evidence_probe import (
    RelevanceProbeResult,
    RelevanceSignals,
    extract_json_ld_job_urls,
    job_detail_url_pattern,
    learned_signals_from_result,
    relevance_confidence,
    relevance_decision,
)


def test_autonomous_probe_extracts_json_ld_job_urls() -> None:
    body = '''
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "JobPosting",
      "title": "Cloud Data Engineer Databricks",
      "url": "/job/Aachen-Cloud-Data-Engineer-Databricks/1145683555/"
    }
    </script>
    '''

    urls = extract_json_ld_job_urls(base_url="https://jobs.adesso-group.com/", body=body)

    assert urls == ("https://jobs.adesso-group.com/job/Aachen-Cloud-Data-Engineer-Databricks/1145683555/",)


def test_accepted_detail_evidence_produces_learned_signals() -> None:
    result = RelevanceProbeResult(
        url="https://jobs.adesso-group.com/job/Aachen-Cloud-Data-Engineer-Databricks/1145683555/",
        final_url="https://jobs.adesso-group.com/job/Aachen-Cloud-Data-Engineer-Databricks/1145683555/",
        status_code=200,
        accepted=True,
        reason="profile and target/remote evidence found",
        signals=RelevanceSignals(
            profile_hits=("data engineer", "databricks", "data & analytics"),
            location_hits=(),
            remote_hits=("deutschlandweit",),
            flexibility_hits=("hybrid",),
        ),
        title="Cloud Data Engineer Databricks",
        response_bytes=1200,
    )

    learned = learned_signals_from_result(result)

    assert any(item.signal_type == "profile" and item.signal_value == "data engineer" for item in learned)
    assert any(
        item.signal_type == "remote_or_germany"
        and item.signal_value == "deutschlandweit"
        and item.signal_strength == "strong"
        for item in learned
    )
    assert any(item.signal_type == "flexibility" and item.signal_value == "hybrid" and item.signal_strength == "weak" for item in learned)
    assert any(item.signal_type == "job_detail_path_pattern" and item.signal_value == "/job/..." for item in learned)


def test_relevance_decision_and_confidence_distinguish_insufficient_from_relevant() -> None:
    insufficient = RelevanceSignals(
        profile_hits=("data engineer",),
        location_hits=(),
        remote_hits=(),
        flexibility_hits=("hybrid",),
    )
    relevant = RelevanceSignals(
        profile_hits=("data engineer", "databricks"),
        location_hits=(),
        remote_hits=("deutschlandweit",),
        flexibility_hits=("hybrid",),
    )

    assert relevance_decision(insufficient) == "insufficient_evidence"
    assert relevance_decision(relevant) == "relevant"
    assert relevance_confidence(relevant) > relevance_confidence(insufficient)


def test_rejected_evidence_does_not_learn_signals() -> None:
    result = RelevanceProbeResult(
        url="https://example.com/jobs/java",
        final_url="https://example.com/jobs/java",
        status_code=200,
        accepted=False,
        reason="missing target-location or remote/Germany-wide evidence",
        signals=RelevanceSignals(
            profile_hits=("data",),
            location_hits=(),
            remote_hits=(),
            flexibility_hits=("hybrid",),
        ),
    )

    assert learned_signals_from_result(result) == ()


def test_job_detail_url_pattern_generalizes_job_paths() -> None:
    assert job_detail_url_pattern("https://jobs.adesso-group.com/job/Aachen-Cloud-Data-Engineer/1145683555/") == {
        "host": "jobs.adesso-group.com",
        "path_pattern": "/job/...",
    }


def test_relevance_signals_use_promoted_multi_location_signal_only_as_supporting_evidence() -> None:
    text = "Cloud Data Engineer Databricks Aachen, NW, DE, 52070 +29 weitere"

    without_promoted = relevance_signals(text, target_location="hannover", source_target="hannover")
    with_promoted = relevance_signals(
        text,
        target_location="hannover",
        source_target="hannover",
        promoted_location_terms=("+ weitere",),
    )

    assert without_promoted.is_relevant is False
    assert "+ weitere" in with_promoted.location_hits
    assert with_promoted.is_relevant is True


def test_probe_queue_prioritizes_visible_job_detail_links_before_generated_search_pages() -> None:
    queue = build_probe_url_queue(
        candidate_url="https://jobs.example.com/",
        initial_body='<a href="/job/cloud-data-engineer/123">Cloud Data Engineer</a>',
        source_family_candidate="example",
        company_key="example",
        max_links=8,
    )

    assert queue[0] == "https://jobs.example.com/"
    assert queue[1] == "https://jobs.example.com/job/cloud-data-engineer/123"


def test_generated_search_urls_use_promoted_search_path_families() -> None:
    urls = generated_search_urls(
        "https://karriere.example.com/",
        promoted_url_path_patterns=("/stellen/...",),
        max_urls=12,
    )

    assert "https://karriere.example.com/stellen/?q=Data+Engineer" in urls
    assert "https://karriere.example.com/stellenangebote/?q=Data+Engineer" in urls
