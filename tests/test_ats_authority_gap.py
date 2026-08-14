from __future__ import annotations

from src.search_intelligence.ats_authority_gap import (
    ATSAuthorityAttemptOutcome,
    analyze_ats_authority_gap,
    ats_authority_request_fingerprint,
    build_ats_authority_attempt_observation,
)
from src.search_intelligence.ats_delegation_evidence import (
    ValidatedATSAuthority,
    analyze_ats_delegation,
)
from src.search_intelligence.llm_booster_policy import BoosterStage, TavilyState


PERSONIO = "https://bridgingit.jobs.personio.de/"
PERSONIO_XML = "https://bridgingit.jobs.personio.de/xml"


def personio_unresolved():  # type: ignore[no-untyped-def]
    return analyze_ats_delegation(
        candidate_urls=(PERSONIO,),
        employer_backed_urls=(PERSONIO,),
    )


def personio_429():  # type: ignore[no-untyped-def]
    return build_ats_authority_attempt_observation(
        provider="personio",
        employer_identity="BridgingIT GmbH",
        target_url=PERSONIO,
        evidence_url=PERSONIO_XML,
        validation_contract="personio_target_authority.v1",
        outcome=ATSAuthorityAttemptOutcome.HTTP_RATE_LIMITED,
        http_status=429,
        final_url="https://www.personio.com/",
    )


def test_known_provider_requires_deterministic_attempt_before_booster() -> None:
    decision = analyze_ats_authority_gap(
        delegation_evidence=personio_unresolved(),
        tavily_state=TavilyState.AVAILABLE,
    )

    assert decision.classification == "ats_deterministic_authority_attempt_required"
    assert decision.external_information_gap is False
    assert decision.semantic_booster_eligible is False
    assert decision.deterministic_request_replay_blocked is False
    assert decision.next_action == "validate_personio_target_authority"
    assert all(not stage.eligible for stage in decision.booster_plan.stages[1:]) is False
    assert decision.booster_plan.stages[1].stage == BoosterStage.TAVILY
    assert decision.booster_plan.stages[1].eligible is False
    assert decision.booster_plan.stages[1].reason_code == "external_search_not_indicated"
    assert decision.product_authority is False


def test_exact_429_attempt_is_replay_blocked_and_opens_alternate_evidence_gap() -> None:
    decision = analyze_ats_authority_gap(
        delegation_evidence=personio_unresolved(),
        tavily_state=TavilyState.AVAILABLE,
        authority_attempt=personio_429(),
    )

    assert decision.classification == "ats_authority_external_evidence_gap"
    assert decision.external_information_gap is True
    assert decision.semantic_booster_eligible is True
    assert decision.deterministic_request_replay_blocked is True
    assert decision.next_action == "search_for_alternate_ats_authority_evidence"
    assert decision.booster_plan.stages[1].stage == BoosterStage.TAVILY
    assert decision.booster_plan.stages[1].eligible is True
    assert [stage.stage for stage in decision.booster_plan.stages] == [
        BoosterStage.DETERMINISTIC,
        BoosterStage.TAVILY,
        BoosterStage.LUNA_MEDIUM,
        BoosterStage.TERRA_MEDIUM,
        BoosterStage.SOL_MEDIUM,
        BoosterStage.LUNA_MAX,
        BoosterStage.DEEP_EVIDENCE,
    ]
    assert decision.tenant_authority is False
    assert decision.delegation_permitted is False
    assert decision.product_authority is False


def test_unchanged_authority_gap_spends_nothing_again() -> None:
    first = analyze_ats_authority_gap(
        delegation_evidence=personio_unresolved(),
        tavily_state=TavilyState.AVAILABLE,
        authority_attempt=personio_429(),
    )
    second = analyze_ats_authority_gap(
        delegation_evidence=personio_unresolved(),
        tavily_state=TavilyState.AVAILABLE,
        authority_attempt=personio_429(),
        previous_gap_fingerprint=first.evidence_fingerprint,
    )

    assert second.classification == "ats_authority_gap_unchanged"
    assert second.unchanged_gap_skip is True
    assert second.semantic_booster_eligible is False
    assert second.deterministic_request_replay_blocked is True
    assert second.next_action == "await_changed_authority_evidence"


def test_tavily_shortage_never_blocks_luna_after_exhausted_authority_attempt() -> None:
    decision = analyze_ats_authority_gap(
        delegation_evidence=personio_unresolved(),
        tavily_state=TavilyState.INSUFFICIENT_BUDGET,
        authority_attempt=personio_429(),
    )

    stages = {stage.stage: stage for stage in decision.booster_plan.stages}
    assert stages[BoosterStage.TAVILY].eligible is False
    assert stages[BoosterStage.LUNA_MEDIUM].eligible is True
    assert stages[BoosterStage.TERRA_MEDIUM].eligible is True
    assert stages[BoosterStage.SOL_MEDIUM].eligible is True
    assert stages[BoosterStage.LUNA_MAX].eligible is True


def test_validated_authority_suppresses_every_external_stage() -> None:
    evidence = analyze_ats_delegation(
        candidate_urls=(PERSONIO,),
        employer_backed_urls=(PERSONIO,),
        validated_authority=ValidatedATSAuthority(
            provider="personio",
            target_key="bridgingit",
            employer_identity_bound=True,
            evidence_ref="fixture://bridgingit/personio-authority",
        ),
    )
    decision = analyze_ats_authority_gap(
        delegation_evidence=evidence,
        tavily_state=TavilyState.AVAILABLE,
    )

    assert decision.classification == "ats_authority_resolved"
    assert decision.delegation_permitted is True
    assert decision.tenant_authority is True
    assert decision.semantic_booster_eligible is False
    assert all(not stage.eligible for stage in decision.booster_plan.stages[1:])
    assert decision.product_authority is False


def test_unknown_provider_is_external_gap_but_never_authority() -> None:
    evidence = analyze_ats_delegation(
        candidate_urls=("https://careers.unknown-example.test/jobs",),
    )
    decision = analyze_ats_authority_gap(
        delegation_evidence=evidence,
        tavily_state=TavilyState.AVAILABLE,
    )

    assert decision.classification == "ats_provider_external_information_gap"
    assert decision.external_information_gap is True
    assert decision.semantic_booster_eligible is True
    assert decision.delegation_permitted is False
    assert decision.product_authority is False


def test_request_fingerprint_ignores_tracking_but_preserves_functional_query() -> None:
    base = ats_authority_request_fingerprint(
        provider="personio",
        employer_identity="BridgingIT GmbH",
        target_url=PERSONIO,
        evidence_url=PERSONIO_XML + "?utm_source=test&id=42",
        validation_contract="personio_target_authority.v1",
    )
    tracking_changed = ats_authority_request_fingerprint(
        provider="PERSONIO",
        employer_identity=" bridgingit   gmbh ",
        target_url=PERSONIO,
        evidence_url=PERSONIO_XML + "?id=42&utm_source=other",
        validation_contract="personio_target_authority.v1",
    )
    functional_changed = ats_authority_request_fingerprint(
        provider="personio",
        employer_identity="BridgingIT GmbH",
        target_url=PERSONIO,
        evidence_url=PERSONIO_XML + "?id=43",
        validation_contract="personio_target_authority.v1",
    )

    assert base == tracking_changed
    assert base != functional_changed


def test_attempt_provider_mismatch_fails_closed() -> None:
    attempt = build_ats_authority_attempt_observation(
        provider="greenhouse",
        employer_identity="BridgingIT GmbH",
        target_url="https://boards.greenhouse.io/bridgingit",
        evidence_url="https://boards.greenhouse.io/bridgingit",
        validation_contract="greenhouse_board_authority.v1",
        outcome=ATSAuthorityAttemptOutcome.ACCESS_BLOCKED,
    )

    try:
        analyze_ats_authority_gap(
            delegation_evidence=personio_unresolved(),
            tavily_state=TavilyState.AVAILABLE,
            authority_attempt=attempt,
        )
    except ValueError as error:
        assert "provider must match" in str(error)
    else:
        raise AssertionError("provider mismatch must fail closed")
