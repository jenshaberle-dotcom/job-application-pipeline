from __future__ import annotations

from src.search_intelligence.detail_discovery_gap import analyze_detail_discovery_gap
from src.search_intelligence.llm_booster_policy import (
    BoosterStage,
    TavilyState,
)


def evidence(
    *,
    attempted: bool = True,
    search_enabled: bool = False,
    candidates: tuple[str, ...] = (),
    supported: tuple[str, ...] = (),
    checked_statuses: tuple[str, ...] = ("checked_no_detail_candidates",),
) -> dict[str, object]:
    return {
        "repair_attempted": attempted,
        "search_discovery_enabled": search_enabled,
        "detail_link_discovery_version": "DETAIL-004B",
        "detail_url_shape_version": "test-v1",
        "decision_taxonomy": "accepted" if supported else "manual_review_required",
        "preliminary_detail_candidates": [
            {"url": url, "reason": "fixture candidate"} for url in candidates
        ],
        "authoritative_detail_assessments": [
            {
                "url": url,
                "decision": "manual_review_required",
                "failure_reason": "detail_page_extracted_but_no_target_signal",
            }
            for url in candidates
        ],
        "supported_detail_evidence": [
            {"url": url, "final_url": url, "status_code": 200}
            for url in supported
        ],
        "checked_origin_candidates": [
            {
                "url": f"https://jobs.example.com/{index}",
                "final_url": f"https://jobs.example.com/{index}",
                "status": status,
                "status_code": None if status == "fetch_error" else 200,
                "rejection_reasons": [],
            }
            for index, status in enumerate(checked_statuses, start=1)
        ],
    }


def decide(
    deterministic_evidence: dict[str, object],
    *,
    tavily_state: TavilyState = TavilyState.AVAILABLE,
    previous_gap_fingerprint: str | None = None,
):
    return analyze_detail_discovery_gap(
        candidate_id=42,
        company_key="example",
        candidate_url="https://jobs.example.com/",
        deterministic_evidence=deterministic_evidence,
        tavily_state=tavily_state,
        previous_gap_fingerprint=previous_gap_fingerprint,
    )


def stage(decision, target: BoosterStage):  # type: ignore[no-untyped-def]
    return next(item for item in decision.booster_plan.stages if item.stage == target)


def test_local_d0_success_suppresses_all_booster_stages() -> None:
    url = "https://jobs.example.com/jobs/123-data-engineer"
    decision = decide(evidence(candidates=(url,), supported=(url,)))

    assert decision.classification == "detail_discovery_resolved"
    assert decision.deterministic_resolved is True
    assert decision.semantic_booster_eligible is False
    assert decision.detail_authority is False
    assert decision.product_authority is False
    assert all(not item.eligible for item in decision.booster_plan.stages[1:])


def test_external_search_must_not_be_mixed_into_d0() -> None:
    decision = decide(evidence(search_enabled=True))

    assert decision.classification == "detail_d0_external_search_not_isolated"
    assert decision.semantic_booster_eligible is False
    assert decision.next_action == "rerun_detail_d0_without_external_search"
    assert all(not item.eligible for item in decision.booster_plan.stages[1:])


def test_unexecuted_d0_blocks_all_semantic_stages() -> None:
    decision = decide(evidence(attempted=False, checked_statuses=()))

    assert decision.classification == "detail_d0_required"
    assert decision.deterministic_attempted is False
    assert decision.semantic_booster_eligible is False
    assert all(not item.eligible for item in decision.booster_plan.stages[1:])


def test_reachable_d0_without_candidates_opens_search_first_gap() -> None:
    decision = decide(evidence())

    assert decision.classification == "detail_external_information_gap"
    assert decision.external_information_gap is True
    assert decision.semantic_booster_eligible is True
    assert stage(decision, BoosterStage.TAVILY).eligible is True
    assert stage(decision, BoosterStage.LUNA_MEDIUM).eligible is True


def test_tavily_disabled_still_allows_model_fallback_after_external_gap() -> None:
    decision = decide(evidence(), tavily_state=TavilyState.DISABLED)

    assert decision.external_information_gap is True
    assert stage(decision, BoosterStage.TAVILY).eligible is False
    assert stage(decision, BoosterStage.TAVILY).reason_code == "tavily_disabled"
    assert stage(decision, BoosterStage.LUNA_MEDIUM).eligible is True
    assert stage(decision, BoosterStage.TERRA_MEDIUM).eligible is True
    assert stage(decision, BoosterStage.SOL_MEDIUM).eligible is True
    assert stage(decision, BoosterStage.LUNA_MAX).eligible is True


def test_candidate_validation_gap_skips_tavily_but_allows_models() -> None:
    url = "https://jobs.example.com/jobs/123-data-engineer"
    decision = decide(evidence(candidates=(url,)))

    assert decision.classification == "detail_candidate_validation_gap"
    assert decision.external_information_gap is False
    assert decision.semantic_booster_eligible is True
    assert stage(decision, BoosterStage.TAVILY).eligible is False
    assert stage(decision, BoosterStage.TAVILY).reason_code == "external_search_not_indicated"
    assert stage(decision, BoosterStage.LUNA_MEDIUM).eligible is True


def test_operational_fetch_only_gap_does_not_spend() -> None:
    decision = decide(
        evidence(checked_statuses=("fetch_error", "fetch_error"))
    )

    assert decision.classification == "detail_d0_operational_fetch_gap"
    assert decision.operational_gap is True
    assert decision.external_information_gap is False
    assert decision.semantic_booster_eligible is False
    assert all(not item.eligible for item in decision.booster_plan.stages[1:])


def test_unchanged_gap_fingerprint_suppresses_all_external_spend() -> None:
    first = decide(evidence())
    second = decide(
        evidence(),
        previous_gap_fingerprint=first.evidence_fingerprint,
    )

    assert second.classification == "detail_external_information_gap_unchanged"
    assert second.unchanged_gap_skip is True
    assert second.semantic_booster_eligible is False
    assert second.next_action == "await_changed_detail_evidence"
    assert all(not item.eligible for item in second.booster_plan.stages[1:])


def test_gap_fingerprint_changes_when_candidate_evidence_changes() -> None:
    first = decide(evidence())
    second = decide(
        evidence(candidates=("https://jobs.example.com/jobs/123-data-engineer",))
    )

    assert first.evidence_fingerprint != second.evidence_fingerprint


def test_decision_never_grants_detail_or_product_authority() -> None:
    decision = decide(evidence())

    assert decision.detail_authority is False
    assert decision.product_authority is False
    assert decision.booster_plan.product_authority is False
    assert decision.booster_plan.product_writes == 0
