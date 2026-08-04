from __future__ import annotations

from src.search_intelligence.origin_selection_scope_contract import (
    normalize_selection_scope_outcome,
)
from src.search_intelligence.origin_url_default_repair import (
    RepairStage,
    compatibility_payload,
    finalize_outcome,
)


def _selected_payload(
    *,
    company_key: str,
    company_name: str,
    selected_url: str,
) -> dict[str, object]:
    stage = RepairStage(
        name="tavily_repair",
        attempted=True,
        status="selected",
        decision="origin_url_candidate_selected",
        selected_url=selected_url,
        recommended_url=None,
        confidence_score=0.9,
        candidate_count=3,
        provider_request_count=4,
        reason="provider selected a reachable career source",
    )
    outcome = finalize_outcome(
        company_key=company_key,
        company_name=company_name,
        stages=(stage,),
    )
    return compatibility_payload(
        outcome,
        last_discovery_payload={
            "company_key": company_key,
            "company_name": company_name,
            "decision": "origin_url_candidate_selected",
            "selected_url": selected_url,
            "confidence_score": 0.9,
        },
    )


def test_conflicting_ats_tenant_country_requires_review() -> None:
    payload = _selected_payload(
        company_key="deloitte",
        company_name="Deloitte GmbH",
        selected_url="https://careers.smartrecruiters.com/DeloitteAT/deloitte-jobs",
    )

    result = normalize_selection_scope_outcome(payload, target_locale="de-DE")

    assert result["repair_final_state"] == "operator_review_required"
    assert result["selected_url"] is None
    assert result["recommended_url"] == (
        "https://careers.smartrecruiters.com/DeloitteAT/deloitte-jobs"
    )
    assert result["selection_scope_review_required"] is True
    assert "ATS tenant country suffix at" in str(result["selection_scope_reason"])


def test_conflicting_country_path_requires_review() -> None:
    payload = _selected_payload(
        company_key="gft_technologies",
        company_name="GFT Technologies SE",
        selected_url="https://www.gft.com/us/en/career",
    )

    result = normalize_selection_scope_outcome(payload, target_locale="de-DE")

    assert result["repair_final_state"] == "operator_review_required"
    assert "leading country path us" in str(result["selection_scope_reason"])


def test_short_brand_on_unusual_tld_requires_exact_entity_review() -> None:
    payload = _selected_payload(
        company_key="e_on_digital_technology",
        company_name="E.ON Digital Technology GmbH",
        selected_url="https://eon.xyz/careers",
    )

    result = normalize_selection_scope_outcome(payload, target_locale="de-DE")

    assert result["repair_final_state"] == "operator_review_required"
    assert result["selected_url"] is None
    assert "short brand" in str(result["selection_scope_reason"])
    assert ".xyz" in str(result["selection_scope_reason"])


def test_correct_global_and_tenant_origins_remain_selected() -> None:
    cases = (
        (
            "computer_futures",
            "Computer Futures",
            "https://careers.smartrecruiters.com/ComputerFutures3",
        ),
        (
            "deloitte",
            "Deloitte GmbH",
            "https://www.deloitte.com/de/de/careers.html",
        ),
        (
            "x1f",
            "X1F GmbH",
            "https://www.x1f.one/en/jobs/",
        ),
        (
            "1_1",
            "1&1",
            "https://career.1and1.org/",
        ),
    )

    for company_key, company_name, selected_url in cases:
        payload = _selected_payload(
            company_key=company_key,
            company_name=company_name,
            selected_url=selected_url,
        )
        result = normalize_selection_scope_outcome(payload, target_locale="de-DE")
        assert result["repair_final_state"].startswith("selected_"), result
        assert result["selected_url"] == selected_url
