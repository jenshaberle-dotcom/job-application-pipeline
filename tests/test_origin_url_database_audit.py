from __future__ import annotations

from scripts.run_origin_url_database_audit import request_accounting, result_row


def test_request_accounting_does_not_treat_searches_as_llm_calls() -> None:
    payload = {
        "default_repair": {
            "stages": [
                {"name": "deterministic_baseline", "provider_request_count": 0},
                {"name": "deterministic_symbol_brand", "provider_request_count": 0},
                {"name": "tavily_repair", "provider_request_count": 3},
                {
                    "name": "llm_search_hypothesis_repair",
                    "provider_request_count": 2,
                },
                {"name": "evidence_and_llm_repair", "provider_request_count": 1},
            ]
        },
        "early_llm_observation": {"request_attempted": True},
        "llm_observation": {
            "provider_result": {"request_attempted": True}
        },
    }

    assert request_accounting(payload) == {
        "external_provider_requests": 6,
        "web_search_requests": 4,
        "llm_requests": 2,
    }


def test_budget_guard_row_is_visible_and_has_no_fake_execution() -> None:
    company = {
        "id": 57,
        "company_key": "example",
        "company_name": "Example GmbH",
        "status": "candidate",
        "candidate_url": None,
        "risk_level": "R2",
    }

    row = result_row(company, None, budget_blocked=True)

    assert row["final_state"] == "not_run_budget_guard"
    assert row["provider_requests"] == 0
    assert row["web_search_requests"] == 0
    assert row["llm_requests"] == 0
    assert row["selected_url"] is None
    assert row["error"] is None
