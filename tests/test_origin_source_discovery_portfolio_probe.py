from scripts.run_origin_source_discovery_gate_agent import summarize_portfolio_results


def test_summarize_portfolio_results_counts_statuses_and_blockers() -> None:
    results = [
        {
            "discovery_status": "selected",
            "decision": "continue_to_connector_feasibility",
            "blocker_code": None,
        },
        {
            "discovery_status": "manual_review_required",
            "decision": "manual_review_required",
            "blocker_code": "ambiguous_multiple_origin_domains",
        },
        {
            "discovery_status": "blocked_unsafe_url",
            "decision": "abort_documented",
            "blocker_code": "only_unsafe_origin_url_evidence",
        },
        {
            "discovery_status": "not_found",
            "decision": "manual_review_required",
            "blocker_code": "market_evidence_without_origin_url",
        },
    ]

    summary = summarize_portfolio_results(results)

    assert summary["candidate_count"] == 4
    assert summary["selected_count"] == 1
    assert summary["manual_review_count"] == 2
    assert summary["blocked_count"] == 1
    assert summary["status_counts"] == {
        "blocked_unsafe_url": 1,
        "manual_review_required": 1,
        "not_found": 1,
        "selected": 1,
    }
    assert summary["blocker_counts"] == {
        "ambiguous_multiple_origin_domains": 1,
        "market_evidence_without_origin_url": 1,
        "none": 1,
        "only_unsafe_origin_url_evidence": 1,
    }
