from __future__ import annotations

from src.search_intelligence.detail_semantics_booster_execution import (
    DetailSemanticsHypothesisObservation,
    DetailSemanticsValidationObservation,
    execute_detail_semantics_booster,
)
from src.search_intelligence.detail_semantics_gap import (
    SemanticEvidenceReference,
    analyze_detail_semantics_gap,
)
from src.search_intelligence.llm_booster_policy import BoosterStage, TavilyState

DETAIL_URL = "https://jobs.example.com/jobs/42-data-engineer"


def decision(
    *,
    requested: tuple[str, ...] = ("role", "location"),
    fields: dict[str, object] | None = None,
    profile: bool = False,
    geography: bool = False,
    previous_semantic_fingerprint: str | None = None,
):
    return analyze_detail_semantics_gap(
        candidate_id=42,
        company_key="example",
        detail_url=DETAIL_URL,
        deterministic_attempted=True,
        detail_supported=True,
        profile_contract_satisfied=profile,
        geography_contract_satisfied=geography,
        requested_semantic_fields=requested,
        deterministic_semantic_fields=fields or {},
        tavily_state=TavilyState.AVAILABLE,
        previous_semantic_fingerprint=previous_semantic_fingerprint,
    )


def reference(
    field: str,
    evidence: str,
    *,
    source_url: str = DETAIL_URL,
    value: str | None = None,
    span_start: int | None = 10,
    span_end: int | None = 30,
) -> SemanticEvidenceReference:
    return SemanticEvidenceReference(
        field=field,
        source_url=source_url,
        evidence=evidence,
        value=value,
        span_start=span_start,
        span_end=span_end,
    )


def hypothesis(
    *,
    fields: dict[str, object],
    references: tuple[SemanticEvidenceReference, ...],
    cost: float = 0.001,
    product_authority: bool = False,
) -> DetailSemanticsHypothesisObservation:
    return DetailSemanticsHypothesisObservation(
        status="completed",
        request_attempted=True,
        semantic_fields=fields,
        evidence_references=references,
        estimated_cost_usd=cost,
        product_authority=product_authority,
    )


def validation(
    observation: DetailSemanticsHypothesisObservation,
    *,
    accepted: bool,
    profile: bool = False,
    geography: bool = False,
    classification: str = "validated_semantic_evidence",
    product_authority: bool = False,
    accepted_fields: dict[str, object] | None = None,
    accepted_references: tuple[SemanticEvidenceReference, ...] | None = None,
) -> DetailSemanticsValidationObservation:
    return DetailSemanticsValidationObservation(
        accepted=accepted,
        classification=classification,
        profile_contract_satisfied=profile,
        geography_contract_satisfied=geography,
        accepted_semantic_fields=(
            accepted_fields
            if accepted_fields is not None
            else (dict(observation.semantic_fields) if accepted else {})
        ),
        accepted_evidence_references=(
            accepted_references
            if accepted_references is not None
            else (observation.evidence_references if accepted else ())
        ),
        failure_reason=None if accepted else "deterministic_semantic_validation_rejected",
        product_authority=product_authority,
    )


def no_model(stage, fields, references, ledger):  # type: ignore[no-untyped-def]
    raise AssertionError(f"model must not run: {stage}")


def test_deterministic_semantic_resolution_calls_no_model_even_if_product_support_false() -> None:
    validate_calls: list[str] = []
    initial = {"role": "Data Engineer", "location": "Hannover"}

    result = execute_detail_semantics_booster(
        detail_url=DETAIL_URL,
        decision=decision(fields=initial, profile=False, geography=False),
        initial_semantic_fields=initial,
        initial_evidence_references=(),
        model=no_model,
        validate=lambda observation: validate_calls.append("called")
        or validation(observation, accepted=True),
    )

    assert validate_calls == []
    assert result.resolved is True
    assert result.missing_semantic_fields == ()
    assert result.profile_contract_satisfied is False
    assert result.geography_contract_satisfied is False
    assert result.provider_requests == 0
    assert result.llm_requests == 0
    assert all(not item.attempted for item in result.stages[1:])


def test_product_support_alone_does_not_resolve_missing_semantics() -> None:
    model_calls: list[BoosterStage] = []

    def model(stage, fields, references, ledger):  # type: ignore[no-untyped-def]
        model_calls.append(stage)
        return hypothesis(
            fields={"role": "Data Engineer", "location": "Hannover"},
            references=(
                reference("role", "Data Engineer", value="Data Engineer"),
                reference("location", "Arbeitsort Hannover", value="Hannover"),
            ),
        )

    result = execute_detail_semantics_booster(
        detail_url=DETAIL_URL,
        decision=decision(profile=True, geography=True),
        initial_semantic_fields={},
        initial_evidence_references=(),
        model=model,
        validate=lambda observation: validation(
            observation,
            accepted=True,
            profile=True,
            geography=True,
        ),
    )

    assert model_calls == [BoosterStage.LUNA_MEDIUM]
    assert result.resolved is True
    assert result.semantic_fields == {"role": "Data Engineer", "location": "Hannover"}
    assert result.product_authority is False


def test_semantic_ambiguity_starts_luna_without_tavily_and_requires_validation() -> None:
    model_calls: list[BoosterStage] = []
    validate_calls: list[dict[str, object]] = []

    def model(stage, fields, references, ledger):  # type: ignore[no-untyped-def]
        model_calls.append(stage)
        return hypothesis(
            fields={"role": "Data Engineer", "location": "Hannover"},
            references=(
                reference("role", "Data Engineer", value="Data Engineer"),
                reference("location", "Arbeitsort Hannover", value="Hannover"),
            ),
        )

    def validate(observation):  # type: ignore[no-untyped-def]
        validate_calls.append(dict(observation.semantic_fields))
        return validation(observation, accepted=True)

    result = execute_detail_semantics_booster(
        detail_url=DETAIL_URL,
        decision=decision(),
        initial_semantic_fields={},
        initial_evidence_references=(),
        model=model,
        validate=validate,
    )

    assert model_calls == [BoosterStage.LUNA_MEDIUM]
    assert validate_calls == [{"role": "Data Engineer", "location": "Hannover"}]
    assert result.resolved is True
    assert result.provider_requests == 1
    assert result.llm_requests == 1
    tavily = next(item for item in result.stages if item.stage == BoosterStage.TAVILY)
    assert tavily.attempted is False
    assert tavily.reason_code == "external_search_not_indicated"


def test_partial_validated_semantic_progress_is_reused_by_next_model_stage() -> None:
    model_calls: list[BoosterStage] = []
    terra_context: list[dict[str, object]] = []

    def model(stage, fields, references, ledger):  # type: ignore[no-untyped-def]
        model_calls.append(stage)
        if stage == BoosterStage.LUNA_MEDIUM:
            return hypothesis(
                fields={"role": "Data Engineer"},
                references=(reference("role", "Data Engineer", value="Data Engineer"),),
            )
        terra_context.append(dict(fields))
        return hypothesis(
            fields={"location": "Hannover"},
            references=(reference("location", "Arbeitsort Hannover", value="Hannover"),),
        )

    result = execute_detail_semantics_booster(
        detail_url=DETAIL_URL,
        decision=decision(),
        initial_semantic_fields={},
        initial_evidence_references=(),
        model=model,
        validate=lambda observation: validation(observation, accepted=True),
    )

    assert model_calls == [BoosterStage.LUNA_MEDIUM, BoosterStage.TERRA_MEDIUM]
    assert terra_context == [{"role": "Data Engineer"}]
    assert result.resolved is True
    assert result.semantic_fields == {"role": "Data Engineer", "location": "Hannover"}


def test_unrequested_semantic_field_does_not_fake_resolution() -> None:
    stages: list[BoosterStage] = []

    def model(stage, fields, references, ledger):  # type: ignore[no-untyped-def]
        stages.append(stage)
        return hypothesis(
            fields={"seniority": "Senior"},
            references=(reference("seniority", "Senior Data Engineer", value="Senior"),),
        )

    result = execute_detail_semantics_booster(
        detail_url=DETAIL_URL,
        decision=decision(requested=("role",)),
        initial_semantic_fields={},
        initial_evidence_references=(),
        model=model,
        validate=lambda observation: validation(observation, accepted=True),
    )

    assert stages == [
        BoosterStage.LUNA_MEDIUM,
        BoosterStage.TERRA_MEDIUM,
        BoosterStage.SOL_MEDIUM,
        BoosterStage.LUNA_MAX,
    ]
    assert result.resolved is False
    assert result.missing_semantic_fields == ("role",)


def test_duplicate_semantic_hypothesis_is_deterministically_validated_once() -> None:
    validate_calls: list[BoosterStage] = []
    current_stage: list[BoosterStage] = []

    def model(stage, fields, references, ledger):  # type: ignore[no-untyped-def]
        current_stage[:] = [stage]
        return hypothesis(
            fields={"seniority": "Senior"},
            references=(reference("seniority", "Senior Data Engineer", value="Senior"),),
        )

    def validate(observation):  # type: ignore[no-untyped-def]
        validate_calls.append(current_stage[0])
        return validation(observation, accepted=False)

    result = execute_detail_semantics_booster(
        detail_url=DETAIL_URL,
        decision=decision(requested=("seniority",)),
        initial_semantic_fields={},
        initial_evidence_references=(),
        model=model,
        validate=validate,
    )

    assert validate_calls == [BoosterStage.LUNA_MEDIUM]
    assert result.resolved is False
    duplicate_records = [
        item for item in result.stages if item.status == "duplicate_no_progress"
    ]
    assert len(duplicate_records) == 3
    assert result.llm_requests == 4


def test_missing_model_evidence_span_fails_closed_then_allows_next_stage() -> None:
    model_calls: list[BoosterStage] = []
    validate_calls: list[BoosterStage] = []
    current_stage: list[BoosterStage] = []

    def model(stage, fields, references, ledger):  # type: ignore[no-untyped-def]
        model_calls.append(stage)
        current_stage[:] = [stage]
        if stage == BoosterStage.LUNA_MEDIUM:
            return hypothesis(
                fields={"role": "Data Engineer"},
                references=(
                    reference(
                        "role",
                        "Data Engineer",
                        span_start=None,
                        span_end=None,
                    ),
                ),
            )
        return hypothesis(
            fields={"role": "Data Engineer"},
            references=(reference("role", "Data Engineer", value="Data Engineer"),),
        )

    def validate(observation):  # type: ignore[no-untyped-def]
        validate_calls.append(current_stage[0])
        return validation(observation, accepted=True)

    result = execute_detail_semantics_booster(
        detail_url=DETAIL_URL,
        decision=decision(requested=("role",)),
        initial_semantic_fields={},
        initial_evidence_references=(),
        model=model,
        validate=validate,
    )

    assert model_calls == [BoosterStage.LUNA_MEDIUM, BoosterStage.TERRA_MEDIUM]
    assert validate_calls == [BoosterStage.TERRA_MEDIUM]
    luna = next(item for item in result.stages if item.stage == BoosterStage.LUNA_MEDIUM)
    assert luna.status == "failed_closed"
    assert luna.reason_code == "evidence_span_required"
    assert result.resolved is True


def test_cross_detail_evidence_reference_never_reaches_validator() -> None:
    validate_calls: list[str] = []

    def model(stage, fields, references, ledger):  # type: ignore[no-untyped-def]
        return hypothesis(
            fields={"remote": True},
            references=(
                reference(
                    "remote",
                    "Remote möglich",
                    source_url="https://jobs.other.example/jobs/99",
                    value="true",
                ),
            ),
        )

    result = execute_detail_semantics_booster(
        detail_url=DETAIL_URL,
        decision=decision(requested=("remote",)),
        initial_semantic_fields={},
        initial_evidence_references=(),
        model=model,
        validate=lambda observation: validate_calls.append("called")
        or validation(observation, accepted=True),
    )

    assert validate_calls == []
    assert result.resolved is False


def test_attractive_model_semantics_cannot_resolve_when_validator_rejects() -> None:
    def model(stage, fields, references, ledger):  # type: ignore[no-untyped-def]
        return hypothesis(
            fields={"role": "Data Engineer", "location": "Hannover"},
            references=(
                reference("role", "Data Engineer", value="Data Engineer"),
                reference("location", "Hannover", value="Hannover"),
            ),
        )

    result = execute_detail_semantics_booster(
        detail_url=DETAIL_URL,
        decision=decision(),
        initial_semantic_fields={},
        initial_evidence_references=(),
        model=model,
        validate=lambda observation: validation(observation, accepted=False),
    )

    assert result.resolved is False
    assert result.semantic_fields == {}
    assert result.product_authority is False
    assert result.semantic_authority is False
    assert result.product_writes == 0


def test_validator_cannot_broaden_model_hypothesis() -> None:
    calls: list[BoosterStage] = []

    def model(stage, fields, references, ledger):  # type: ignore[no-untyped-def]
        calls.append(stage)
        return hypothesis(
            fields={"role": "Data Engineer"},
            references=(reference("role", "Data Engineer", value="Data Engineer"),),
        )

    result = execute_detail_semantics_booster(
        detail_url=DETAIL_URL,
        decision=decision(requested=("role",)),
        initial_semantic_fields={},
        initial_evidence_references=(),
        model=model,
        validate=lambda observation: validation(
            observation,
            accepted=True,
            accepted_fields={"role": "Data Engineer", "location": "Hannover"},
        ),
    )

    assert calls == [BoosterStage.LUNA_MEDIUM]
    luna = next(item for item in result.stages if item.stage == BoosterStage.LUNA_MEDIUM)
    assert luna.status == "failed_closed"
    assert luna.reason_code == "validator_broadened_semantic_hypothesis"
    assert result.resolved is False


def test_validator_cannot_broaden_evidence_references() -> None:
    extra = reference("role", "Another Data Engineer", span_start=40, span_end=61)

    def model(stage, fields, references, ledger):  # type: ignore[no-untyped-def]
        return hypothesis(
            fields={"role": "Data Engineer"},
            references=(reference("role", "Data Engineer", value="Data Engineer"),),
        )

    result = execute_detail_semantics_booster(
        detail_url=DETAIL_URL,
        decision=decision(requested=("role",)),
        initial_semantic_fields={},
        initial_evidence_references=(),
        model=model,
        validate=lambda observation: validation(
            observation,
            accepted=True,
            accepted_references=observation.evidence_references + (extra,),
        ),
    )

    luna = next(item for item in result.stages if item.stage == BoosterStage.LUNA_MEDIUM)
    assert luna.status == "failed_closed"
    assert luna.reason_code == "validator_broadened_evidence_reference"
    assert result.resolved is False


def test_model_cost_ceiling_exceedance_stops_later_stages() -> None:
    model_calls: list[BoosterStage] = []
    validate_calls: list[str] = []

    def model(stage, fields, references, ledger):  # type: ignore[no-untyped-def]
        model_calls.append(stage)
        return hypothesis(
            fields={"role": "Data Engineer"},
            references=(reference("role", "Data Engineer", value="Data Engineer"),),
            cost=0.011,
        )

    result = execute_detail_semantics_booster(
        detail_url=DETAIL_URL,
        decision=decision(requested=("role",)),
        initial_semantic_fields={},
        initial_evidence_references=(),
        model=model,
        validate=lambda observation: validate_calls.append("called")
        or validation(observation, accepted=True),
    )

    assert model_calls == [BoosterStage.LUNA_MEDIUM]
    assert validate_calls == []
    luna = next(item for item in result.stages if item.stage == BoosterStage.LUNA_MEDIUM)
    assert luna.status == "failed_closed"
    assert luna.reason_code == "model_cost_ceiling_exceeded"
    assert result.resolved is False


def test_model_product_authority_claim_stops_later_stages() -> None:
    model_calls: list[BoosterStage] = []

    def model(stage, fields, references, ledger):  # type: ignore[no-untyped-def]
        model_calls.append(stage)
        return hypothesis(
            fields={"role": "Data Engineer"},
            references=(reference("role", "Data Engineer", value="Data Engineer"),),
            product_authority=True,
        )

    result = execute_detail_semantics_booster(
        detail_url=DETAIL_URL,
        decision=decision(requested=("role",)),
        initial_semantic_fields={},
        initial_evidence_references=(),
        model=model,
        validate=lambda observation: validation(observation, accepted=True),
    )

    assert model_calls == [BoosterStage.LUNA_MEDIUM]
    luna = next(item for item in result.stages if item.stage == BoosterStage.LUNA_MEDIUM)
    assert luna.status == "failed_closed"
    assert luna.reason_code == "model_product_authority_claim_rejected"
    assert result.product_authority is False
    assert result.product_writes == 0


def test_unchanged_semantic_gap_calls_nothing() -> None:
    first = decision(requested=("role",))
    unchanged = analyze_detail_semantics_gap(
        candidate_id=42,
        company_key="example",
        detail_url=DETAIL_URL,
        deterministic_attempted=True,
        detail_supported=True,
        profile_contract_satisfied=False,
        geography_contract_satisfied=False,
        requested_semantic_fields=("role",),
        deterministic_semantic_fields={},
        tavily_state=TavilyState.AVAILABLE,
        previous_semantic_fingerprint=first.evidence_fingerprint,
    )

    result = execute_detail_semantics_booster(
        detail_url=DETAIL_URL,
        decision=unchanged,
        initial_semantic_fields={},
        initial_evidence_references=(),
        model=no_model,
        validate=lambda observation: validation(observation, accepted=True),
    )

    assert result.unchanged_evidence_skip is True
    assert result.provider_requests == 0
    assert result.llm_requests == 0
    assert all(not item.attempted for item in result.stages[1:])


def test_stage_order_has_no_pro_mode() -> None:
    def model(stage, fields, references, ledger):  # type: ignore[no-untyped-def]
        return DetailSemanticsHypothesisObservation(
            status="completed",
            request_attempted=True,
            semantic_fields={},
            evidence_references=(),
            estimated_cost_usd=0.001,
        )

    result = execute_detail_semantics_booster(
        detail_url=DETAIL_URL,
        decision=decision(requested=("role",)),
        initial_semantic_fields={},
        initial_evidence_references=(),
        model=model,
        validate=lambda observation: validation(observation, accepted=False),
    )

    assert [item.stage for item in result.stages] == [
        BoosterStage.DETERMINISTIC,
        BoosterStage.TAVILY,
        BoosterStage.LUNA_MEDIUM,
        BoosterStage.TERRA_MEDIUM,
        BoosterStage.SOL_MEDIUM,
        BoosterStage.LUNA_MAX,
        BoosterStage.DEEP_EVIDENCE,
    ]
    assert all("pro" not in item.stage.value for item in result.stages)
