from src.search_intelligence.origin_source_discovery_agent import (
    OriginDiscoveryProbeResult,
    OriginDiscoveryCandidate,
    company_identity_score,
    discover_origin_source,
    generate_company_url_candidates,
)


def accepted_probe(url: str) -> OriginDiscoveryProbeResult:
    return OriginDiscoveryProbeResult(
        url=url,
        final_url=url,
        status_code=200,
        reachable=True,
        career_like=True,
        reason="fake accepted career page",
    )


def selective_probe(url: str) -> OriginDiscoveryProbeResult:
    career_like = "jobs" in url or "karriere" in url or "careers" in url
    return OriginDiscoveryProbeResult(
        url=url,
        final_url=url,
        status_code=200,
        reachable=True,
        career_like=career_like,
        reason="fake selective page",
    )


def test_company_identity_guard_rejects_hannover_city_jobs_for_hannover_ruck() -> None:
    score, reasons = company_identity_score(
        url="https://jobs.hannover.de/",
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        source_family_candidate="hannover_ruck",
    )

    assert score < 0.45
    assert any("only locality token" in reason for reason in reasons)


def test_hannover_ruck_generation_contains_company_specific_domains() -> None:
    urls = [item.url for item in generate_company_url_candidates(
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        source_family_candidate="hannover_ruck",
        max_candidates=80,
    )]

    assert any("hannover-rueck" in url or "hannover-ruck" in url for url in urls)
    assert "https://jobs.hannover.de/" not in urls


def test_eon_grid_solution_uses_eon_identity_not_plain_grid_only() -> None:
    urls = [item.url for item in generate_company_url_candidates(
        company_key="e_on_grid_solutions",
        company_name="E.ON Grid Solutions GmbH",
        source_family_candidate="e_on_grid_solutions",
        max_candidates=80,
    )]

    assert any("e-on-grid" in url or "eon-grid" in url or "eon" in url for url in urls)
    assert "https://jobs.grid.de/" not in urls


def test_discovery_selects_company_matched_career_url_and_rejects_city_url() -> None:
    result = discover_origin_source(
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        source_family_candidate="hannover_ruck",
        search_result_candidates=(
            OriginDiscoveryCandidate("https://jobs.hannover.de/", "test", "wrong city portal", 1),
            OriginDiscoveryCandidate("https://www.hannover-rueck.de/karriere", "test", "company career page", 2),
        ),
        probe=accepted_probe,
        max_generated_candidates=0,
    )

    assert result.decision == "origin_url_candidate_selected"
    assert result.selected_url == "https://www.hannover-rueck.de/karriere"
    assert all(item.domain != "jobs.hannover.de" for item in result.alternatives if item.decision == "select_candidate")


def test_discovery_requires_manual_review_when_only_weak_company_page_exists() -> None:
    result = discover_origin_source(
        company_key="demo_company",
        company_name="Demo Company GmbH",
        search_result_candidates=(
            OriginDiscoveryCandidate("https://www.demo-company.de/ueber-uns", "test", "company page but not career", 1),
        ),
        probe=selective_probe,
        max_generated_candidates=0,
    )

    assert result.decision in {"manual_review_required", "not_found"}
    assert result.selected_url is None


def test_aggregator_market_evidence_is_never_selected() -> None:
    result = discover_origin_source(
        company_key="hdi",
        company_name="HDI Group",
        market_evidence_urls=(
            "https://www.stepstone.de/stellenangebote--Platform-Engineer-Azure-Hannover-HDI-AG--14025074-inline.html",
        ),
        probe=accepted_probe,
        max_generated_candidates=0,
    )

    assert result.decision == "not_found"
    assert result.selected_url is None
    assert result.rejected
    assert any("known aggregator domain" in reason for item in result.rejected for reason in item.reasons)


def test_search_result_context_can_select_known_ats_provider_url() -> None:
    result = discover_origin_source(
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        source_family_candidate="hannover_ruck",
        search_results=(
            {
                "url": "https://wd3.myworkdayjobs.com/HannoverRe_Careers",
                "title": "Hannover Rück Karriere - Jobs",
                "snippet": "Offizielle Stellenangebote der Hannover Rück SE",
                "query": "\"Hannover Rück SE\" Karriere Jobs",
                "provider": "test_search",
            },
        ),
        probe=accepted_probe,
        max_generated_candidates=0,
    )

    assert result.decision == "origin_url_candidate_selected"
    assert result.selected_url == "https://wd3.myworkdayjobs.com/HannoverRe_Careers"
    assert any("search result context" in reason for item in result.alternatives for reason in item.reasons)


def test_search_result_context_does_not_accept_wrong_city_portal() -> None:
    result = discover_origin_source(
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        source_family_candidate="hannover_ruck",
        search_results=(
            {
                "url": "https://jobs.hannover.de/",
                "title": "Jobs in Hannover",
                "snippet": "Stellenangebote der Stadt Hannover",
                "query": "\"Hannover Rück SE\" Karriere Jobs",
                "provider": "test_search",
            },
        ),
        probe=accepted_probe,
        max_generated_candidates=0,
    )

    assert result.decision == "not_found"
    assert result.selected_url is None


def test_search_result_mapping_is_supported_as_input() -> None:
    result = discover_origin_source(
        company_key="e_on_grid_solutions",
        company_name="E.ON Grid Solutions GmbH",
        source_family_candidate="e_on_grid_solutions",
        search_results=(
            {
                "link": "https://eon.com/de/karriere/jobs.html",
                "title": "E.ON Grid Solutions Jobs",
                "snippet": "Karriere bei E.ON Grid Solutions",
                "provider": "json",
            },
        ),
        probe=accepted_probe,
        max_generated_candidates=0,
    )

    assert result.decision == "origin_url_candidate_selected"
    assert result.selected_url == "https://eon.com/de/karriere/jobs.html"


def test_hannover_re_alias_search_result_can_be_selected() -> None:
    result = discover_origin_source(
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        source_family_candidate="hannover_ruck",
        search_results=(
            {
                "url": "https://jobs.hannover-re.com/",
                "title": "Careers | Hannover Re",
                "snippet": "Jobs and careers at Hannover Re",
                "query": "\"hannover re\" Karriere Jobs Hannover",
                "provider": "test_search",
            },
        ),
        probe=accepted_probe,
        max_generated_candidates=0,
    )

    assert result.decision == "origin_url_candidate_selected"
    assert result.selected_url == "https://jobs.hannover-re.com/"


def test_eo002d_domain_alias_generation_prioritizes_hannover_re_domains() -> None:
    urls = [item.url for item in generate_company_url_candidates(
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        source_family_candidate="hannover_ruck",
        max_candidates=30,
    )]

    assert any("hannover-re.com" in url for url in urls)
    assert any(url == "https://jobs.hannover-re.com/" for url in urls)
    assert all("jobs.hannover.de" not in url for url in urls)


def test_eo002d_hannover_re_alias_generation_can_select_jobs_portal() -> None:
    result = discover_origin_source(
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        source_family_candidate="hannover_ruck",
        probe=accepted_probe,
        max_generated_candidates=30,
    )

    assert result.decision == "origin_url_candidate_selected"
    assert result.selected_domain in {"jobs.hannover-re.com", "www.hannover-re.com", "hannover-re.com"}
    assert result.selected_url is not None
    assert "hannover-re.com" in result.selected_url


def test_eo002d_domain_alias_generation_prioritizes_eon_parent_brand_domains() -> None:
    urls = [item.url for item in generate_company_url_candidates(
        company_key="e_on_grid_solutions",
        company_name="E.ON Grid Solutions GmbH",
        source_family_candidate="e_on_grid_solutions",
        max_candidates=30,
    )]

    assert any("eon.com" in url for url in urls)
    assert any(url == "https://careers.eon.com/" for url in urls)
    assert all("jobs.grid.de" not in url for url in urls)


def test_eo002d_eon_alias_generation_can_select_parent_careers_portal() -> None:
    result = discover_origin_source(
        company_key="e_on_grid_solutions",
        company_name="E.ON Grid Solutions GmbH",
        source_family_candidate="e_on_grid_solutions",
        probe=accepted_probe,
        max_generated_candidates=30,
    )

    assert result.decision == "origin_url_candidate_selected"
    assert result.selected_domain in {"careers.eon.com", "www.eon.com", "eon.com"}
    assert result.selected_url is not None
    assert "eon.com" in result.selected_url
