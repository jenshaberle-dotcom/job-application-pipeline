from __future__ import annotations

from src.search_intelligence.origin_source_discovery_agent import OriginDiscoveryResult
from src.search_intelligence.product_v1_transient_origin import (
    classify_transient_origin_result,
    should_attempt_transient_origin,
)


def discovery_result(
    *,
    decision: str,
    selected_url: str | None = None,
) -> OriginDiscoveryResult:
    return OriginDiscoveryResult(
        company_key="example",
        company_name="Example GmbH",
        decision=decision,
        selected_url=selected_url,
        selected_domain="jobs.example.test" if selected_url else None,
        confidence_score=0.9,
        risk_level="low",
        reason="test",
        candidate_count=3,
        assessed_count=3,
        alternatives=(),
        rejected=(),
    )


def test_transient_fallback_only_runs_for_missing_persisted_candidate() -> None:
    assert should_attempt_transient_origin("origin_candidate_required") is True
    assert should_attempt_transient_origin("origin_source_url_required") is False
    assert should_attempt_transient_origin("ambiguous_origin_candidate_identity") is False
    assert should_attempt_transient_origin("ready_for_bounded_detail_discovery") is False


def test_selected_https_origin_root_can_continue_to_detail_discovery() -> None:
    result = classify_transient_origin_result(
        discovery_result(
            decision="origin_url_candidate_selected",
            selected_url="https://jobs.example.test/",
        )
    )
    assert result.status == "ready_for_bounded_detail_discovery"
    assert result.selected_url == "https://jobs.example.test/"


def test_selected_non_https_origin_root_fails_closed() -> None:
    result = classify_transient_origin_result(
        discovery_result(
            decision="origin_url_candidate_selected",
            selected_url="http://jobs.example.test/",
        )
    )
    assert result.status == "transient_origin_invalid_selected_url"


def test_manual_review_origin_result_fails_closed() -> None:
    result = classify_transient_origin_result(
        discovery_result(decision="manual_review_required")
    )
    assert result.status == "transient_origin_manual_review_required"
    assert result.selected_url is None


def test_not_found_origin_result_fails_closed() -> None:
    result = classify_transient_origin_result(discovery_result(decision="not_found"))
    assert result.status == "transient_origin_not_found"
    assert result.selected_url is None
