from __future__ import annotations

import pytest

from src.search_intelligence.ml_foundation import (
    DEVELOPMENT_MATURITY_ORDER,
    LLM_RESIDUAL_REASONS,
    RECURRING_RUNTIME_ORDER,
    ResidualRoutingInput,
    ShadowMlSignal,
    TrainingDatasetContract,
    route_llm_residual,
    validate_training_dataset_contract,
)


def test_development_and_runtime_orders_are_intentionally_different() -> None:
    assert DEVELOPMENT_MATURITY_ORDER == (
        "deterministic_generics",
        "llm_booster_shadow",
        "ml_training_evaluation",
    )
    assert RECURRING_RUNTIME_ORDER == (
        "deterministic_core",
        "ml_broad_signal",
        "conditional_llm_residual",
        "product_contract_authority",
    )


def test_training_dataset_contract_requires_reproducible_provenance() -> None:
    contract = TrainingDatasetContract(
        dataset_version="jobs-v1",
        feature_contract_version="features-v1",
        product_contract_version="prd-v1",
        source_snapshot="postgres://snapshot/2026-08-23T14:30:00Z",
        code_commit="0123456789abcdef",
        split_strategy="grouped-by-job-family-v1",
        label_provenance="operator-reviewed-v1",
    )

    assert validate_training_dataset_contract(contract) == []


def test_training_dataset_contract_rejects_unversioned_or_non_kaggle_input() -> None:
    contract = TrainingDatasetContract(
        dataset_version="",
        feature_contract_version="features-v1",
        product_contract_version="prd-v1",
        source_snapshot="",
        code_commit="0123456789abcdef",
        split_strategy="grouped-v1",
        label_provenance="operator-reviewed-v1",
        training_platform="local-notebook",
    )

    violations = validate_training_dataset_contract(contract)

    assert "dataset_version must be non-empty." in violations
    assert "source_snapshot must be non-empty." in violations
    assert "training_platform must be 'kaggle' for ML-LEARN-001 foundation experiments." in violations


def test_shadow_ml_signal_cannot_claim_product_authority() -> None:
    with pytest.raises(ValueError, match="may not claim product authority"):
        ShadowMlSignal(
            signal_name="job_profile_fit",
            artifact_id="candidate-model-001",
            feature_contract_version="features-v1",
            input_evidence_fingerprint="sha256:abc",
            value=0.91,
            value_semantics="relative_fit_0_to_1",
            product_authority=True,
        )


def test_confident_ml_path_does_not_call_llm_residual() -> None:
    decision = route_llm_residual(
        ResidualRoutingInput(
            ml_signal_available=True,
            ml_confident=True,
        )
    )

    assert decision.escalate_to_llm is False
    assert decision.reasons == ()


def test_uncertain_ml_path_routes_to_llm_with_machine_readable_reason() -> None:
    decision = route_llm_residual(
        ResidualRoutingInput(
            ml_signal_available=True,
            ml_confident=False,
        )
    )

    assert decision.escalate_to_llm is True
    assert decision.reasons == ("ml_uncertain",)


def test_novel_or_conflicting_case_can_route_to_llm_even_when_ml_is_confident() -> None:
    decision = route_llm_residual(
        ResidualRoutingInput(
            ml_signal_available=True,
            ml_confident=True,
            novel_pattern=True,
            evidence_conflict=True,
        )
    )

    assert decision.escalate_to_llm is True
    assert decision.reasons == ("novel_pattern", "evidence_conflict")
    assert set(decision.reasons).issubset(set(LLM_RESIDUAL_REASONS))
