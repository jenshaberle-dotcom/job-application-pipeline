from __future__ import annotations

from src.search_intelligence.origin_explicit_llm_disable_contract import (
    normalize_explicit_llm_disable_outcome,
)


def _stage(
    name: str,
    *,
    attempted: bool,
    status: str,
    blocker: str | None = None,
) -> dict[str, object]:
    return {
        "name": name,
        "attempted": attempted,
        "status": status,
        "decision": "not_found" if attempted else None,
        "selected_url": None,
        "recommended_url": None,
        "confidence_score": 0.0,
        "candidate_count": 0,
        "provider_request_count": 0,
        "reason": "test stage",
        "blocker": blocker,
    }


def _payload(*, blocker: str) -> dict[str, object]:
    return {
        "company_key": "ivv",
        "company_name": "IVV",
        "decision": "repair_configuration_blocked",
        "selected_url": None,
        "default_repair": {
            "company_key": "ivv",
            "company_name": "IVV",
            "final_state": "repair_configuration_blocked",
            "selected_url": None,
            "recommended_url": None,
            "selected_stage": None,
            "operator_review_required": True,
            "repair_exhausted": False,
            "configuration_blocked": True,
            "stages": [
                _stage(
                    "deterministic_baseline",
                    attempted=True,
                    status="not_found",
                ),
                _stage(
                    "deterministic_symbol_brand",
                    attempted=True,
                    status="not_found",
                ),
                _stage("tavily_repair", attempted=True, status="not_found"),
                _stage(
                    "llm_search_hypothesis_repair",
                    attempted=False,
                    status="configuration_blocked",
                    blocker=blocker,
                ),
                _stage(
                    "evidence_and_llm_repair",
                    attempted=True,
                    status="configuration_blocked",
                    blocker=blocker,
                ),
            ],
            "boundary": {},
        },
        "evidence_review": {
            "manual_review_required": True,
            "llm_eligible": True,
        },
    }


def test_explicit_llm_disable_becomes_operator_review_not_config_error() -> None:
    normalized = normalize_explicit_llm_disable_outcome(
        _payload(blocker="llm_disabled_diagnostic_override"),
        llm_disabled=True,
    )

    repair = normalized["default_repair"]
    assert repair["final_state"] == "operator_review_required"
    assert repair["configuration_blocked"] is False
    assert repair["operator_review_required"] is True
    assert normalized["decision"] == "manual_review_required"
    assert normalized["llm_disabled_by_explicit_policy"] is True

    stages = {item["name"]: item for item in repair["stages"]}
    assert stages["llm_search_hypothesis_repair"]["status"] == "skipped"
    assert stages["llm_search_hypothesis_repair"]["blocker"] is None
    assert stages["evidence_and_llm_repair"]["status"] == "manual_review"
    assert stages["evidence_and_llm_repair"]["blocker"] is None


def test_real_llm_configuration_error_remains_blocked() -> None:
    normalized = normalize_explicit_llm_disable_outcome(
        _payload(blocker="missing_openai_api_key"),
        llm_disabled=True,
    )

    repair = normalized["default_repair"]
    assert repair["final_state"] == "repair_configuration_blocked"
    assert repair["configuration_blocked"] is True
    assert "llm_disable_semantics_normalized" not in normalized


def test_no_normalization_when_llm_is_enabled() -> None:
    original = _payload(blocker="llm_disabled_diagnostic_override")
    normalized = normalize_explicit_llm_disable_outcome(
        original,
        llm_disabled=False,
    )

    assert normalized["default_repair"]["final_state"] == (
        "repair_configuration_blocked"
    )
