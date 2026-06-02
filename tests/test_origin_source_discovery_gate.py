from src.search_intelligence.origin_source_discovery import (
    CandidateUrlEvidence,
    assess_url,
    decide_origin_source,
    normalize_url,
)


def test_normalize_url_defaults_to_https_and_removes_query() -> None:
    assert normalize_url("careers.example.com/jobs?foo=bar#x") == "https://careers.example.com/jobs"


def test_assess_url_rejects_non_https_private_and_invalid_urls() -> None:
    http_result = assess_url(CandidateUrlEvidence("http://example.com/jobs", "test"))
    assert http_result.decision == "reject"
    assert http_result.risk_level == "high"

    private_result = assess_url(CandidateUrlEvidence("https://127.0.0.1/jobs", "test"))
    assert private_result.decision == "reject"
    assert private_result.risk_level == "blocked"

    invalid_result = assess_url(CandidateUrlEvidence("javascript:alert(1)", "test"))
    assert invalid_result.decision == "reject"
    assert invalid_result.normalized_url is None


def test_decision_selects_https_career_like_origin_url() -> None:
    decision = decide_origin_source(
        company_key="demo",
        company_name="Demo AG",
        url_evidence=[CandidateUrlEvidence("https://demo.example/careers/jobs", "candidate")],
    )

    assert decision.discovery_status == "selected"
    assert decision.decision == "continue_to_connector_feasibility"
    assert decision.selected_origin_url == "https://demo.example/careers/jobs"
    assert decision.selected_source_type == "employer_origin_career_site"
    assert decision.risk_level == "low"


def test_decision_requires_manual_review_for_homepage_only() -> None:
    decision = decide_origin_source(
        company_key="demo",
        company_name="Demo AG",
        url_evidence=[CandidateUrlEvidence("https://demo.example", "candidate")],
    )

    assert decision.discovery_status == "manual_review_required"
    assert decision.decision == "manual_review_required"
    assert decision.blocker_code == "origin_url_not_concrete_enough"
    assert decision.selected_origin_url is None


def test_decision_blocks_when_only_unsafe_urls_exist() -> None:
    decision = decide_origin_source(
        company_key="demo",
        company_name="Demo AG",
        url_evidence=[CandidateUrlEvidence("http://demo.example/jobs", "candidate")],
    )

    assert decision.discovery_status == "blocked_unsafe_url"
    assert decision.decision == "abort_documented"
    assert decision.blocker_code == "only_unsafe_origin_url_evidence"


def test_decision_requires_review_for_multiple_plausible_domains() -> None:
    decision = decide_origin_source(
        company_key="demo",
        company_name="Demo AG",
        url_evidence=[
            CandidateUrlEvidence("https://jobs.demo.example/careers", "candidate", 10),
            CandidateUrlEvidence("https://demo.recruiting.example/jobs", "aggregator", 20),
        ],
    )

    assert decision.discovery_status == "manual_review_required"
    assert decision.blocker_code == "ambiguous_multiple_origin_domains"

def test_known_aggregator_url_is_not_origin_candidate() -> None:
    result = assess_url(
        CandidateUrlEvidence(
            "https://www.stepstone.de/stellenangebote--Platform-Engineer-Azure-Hannover-HDI-AG--14025074-inline.html",
            "aggregator_novelty_items.evidence_url",
        )
    )

    assert result.decision == "reject"
    assert result.source_type == "aggregator_job_board_evidence"
    assert result.safe_to_probe_later is False


def test_decision_selects_origin_candidate_and_rejects_aggregator_evidence() -> None:
    decision = decide_origin_source(
        company_key="hdi",
        company_name="HDI Group",
        url_evidence=[
            CandidateUrlEvidence(
                "https://careers.hdi.group/en/your_career_opportunities/job_board",
                "employer_origin_source_candidates.candidate_url",
                10,
            ),
            CandidateUrlEvidence(
                "https://www.stepstone.de/stellenangebote--Platform-Engineer-Azure-Hannover-HDI-AG--14025074-inline.html",
                "aggregator_novelty_items.evidence_url",
                40,
            ),
        ],
    )

    assert decision.discovery_status == "selected"
    assert decision.selected_origin_url == "https://careers.hdi.group/en/your_career_opportunities/job_board"
    assert decision.selected_domain == "careers.hdi.group"
    assert decision.rejected_urls
    assert decision.rejected_urls[0].source_type == "aggregator_job_board_evidence"

def test_decision_routes_only_aggregator_market_evidence_to_origin_gap_not_unsafe() -> None:
    decision = decide_origin_source(
        company_key="deutsche_bahn",
        company_name="Deutsche Bahn AG",
        url_evidence=[
            CandidateUrlEvidence(
                "https://www.stepstone.de/stellenangebote--Data-Engineer-Deutsche-Bahn--123-inline.html",
                "aggregator_novelty_items.evidence_url",
            )
        ],
    )

    assert decision.discovery_status == "not_found"
    assert decision.decision == "manual_review_required"
    assert decision.blocker_code == "market_evidence_without_origin_url"
    assert decision.selected_origin_url is None
    assert decision.rejected_urls
    assert decision.rejected_urls[0].source_type == "aggregator_job_board_evidence"


def test_selected_origin_url_allows_auto_assignment_only_for_low_risk_career_url() -> None:
    decision = decide_origin_source(
        company_key="demo",
        company_name="Demo AG",
        url_evidence=[CandidateUrlEvidence("https://demo.example/careers/jobs", "candidate")],
    )

    assert decision.candidate_url_auto_assignment_allowed is True
    assert "trusted persisted HTTPS" in decision.candidate_url_auto_assignment_reason


def test_homepage_origin_url_does_not_allow_auto_assignment() -> None:
    decision = decide_origin_source(
        company_key="demo",
        company_name="Demo AG",
        url_evidence=[CandidateUrlEvidence("https://demo.example", "candidate")],
    )

    assert decision.candidate_url_auto_assignment_allowed is False

