from __future__ import annotations

from scripts.run_origin_url_database_audit import result_row, stage_counts


def test_stage_counts_separate_total_provider_and_llm_requests() -> None:
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
        }
    }

    assert stage_counts(payload) == (6, 3)


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
    assert row["llm_requests"] == 0
    assert row["selected_url"] is None
    assert row["error"] is None
