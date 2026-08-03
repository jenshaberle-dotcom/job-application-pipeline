from __future__ import annotations

import scripts.run_origin_url_database_audit as audit
import scripts.run_origin_url_default_repair as default


def test_database_audit_uses_stable_default_runtime() -> None:
    assert audit.run_default_repair_for_company is default.run_default_repair_for_company


def test_request_accounting_separates_search_and_llm_calls() -> None:
    payload = {
        "default_repair": {
            "stages": [
                {
                    "name": "deterministic_baseline",
                    "provider_request_count": 0,
                },
                {
                    "name": "deterministic_symbol_brand",
                    "provider_request_count": 0,
                },
                {"name": "tavily_repair", "provider_request_count": 7},
                {
                    "name": "llm_search_hypothesis_repair",
                    "provider_request_count": 5,
                },
                {
                    "name": "evidence_and_llm_repair",
                    "provider_request_count": 1,
                },
            ]
        },
        "early_llm_observation": {"request_attempted": True},
        "llm_observation": {
            "provider_result": {"request_attempted": True}
        },
    }

    assert audit.request_accounting(payload) == {
        "external_provider_requests": 13,
        "web_search_requests": 11,
        "llm_requests": 2,
    }


def test_result_row_exposes_selected_url_and_host() -> None:
    company = {
        "id": 1,
        "company_key": "1_1",
        "company_name": "1&1",
        "status": "candidate",
        "candidate_url": None,
        "risk_level": "low",
    }
    payload = {
        "default_repair": {
            "final_state": "selected_deterministic_symbol_brand",
            "selected_stage": "deterministic_symbol_brand",
            "selected_url": "https://career.1and1.org/",
            "recommended_url": None,
            "operator_review_required": False,
            "configuration_blocked": False,
            "repair_exhausted": False,
            "stages": [],
        },
        "adaptive_search": {
            "attempted_queries": [],
            "attempted_urls": ["https://career.1and1.org/"],
            "repeated_state_detected": False,
        },
    }

    row = audit.result_row(company, payload)

    assert row["selected_url"] == "https://career.1and1.org/"
    assert row["selected_host"] == "career.1and1.org"
    assert row["web_search_requests"] == 0
    assert row["llm_requests"] == 0
