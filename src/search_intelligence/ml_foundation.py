from __future__ import annotations

from dataclasses import dataclass
from typing import Final


DEVELOPMENT_MATURITY_ORDER: Final[tuple[str, ...]] = (
    "deterministic_generics",
    "llm_booster_shadow",
    "ml_training_evaluation",
)

RECURRING_RUNTIME_ORDER: Final[tuple[str, ...]] = (
    "deterministic_core",
    "ml_broad_signal",
    "conditional_llm_residual",
    "product_contract_authority",
)

TRAINING_PLATFORM: Final[str] = "kaggle"

LLM_RESIDUAL_REASONS: Final[tuple[str, ...]] = (
    "ml_uncertain",
    "novel_pattern",
    "evidence_conflict",
    "missing_semantics",
    "high_value_adjudication",
)


@dataclass(frozen=True)
class TrainingDatasetContract:
    dataset_version: str
    feature_contract_version: str
    product_contract_version: str
    source_snapshot: str
    code_commit: str
    split_strategy: str
    label_provenance: str
    training_platform: str = TRAINING_PLATFORM


@dataclass(frozen=True)
class ShadowMlSignal:
    signal_name: str
    artifact_id: str
    feature_contract_version: str
    input_evidence_fingerprint: str
    value: float
    value_semantics: str
    product_authority: bool = False

    def __post_init__(self) -> None:
        if self.product_authority:
            raise ValueError("ML shadow signals may not claim product authority.")


@dataclass(frozen=True)
class ResidualRoutingInput:
    ml_signal_available: bool
    ml_confident: bool
    novel_pattern: bool = False
    evidence_conflict: bool = False
    missing_semantics: bool = False
    high_value_adjudication: bool = False


@dataclass(frozen=True)
class ResidualRoutingDecision:
    escalate_to_llm: bool
    reasons: tuple[str, ...]


def validate_training_dataset_contract(contract: TrainingDatasetContract) -> list[str]:
    violations: list[str] = []
    required_values = {
        "dataset_version": contract.dataset_version,
        "feature_contract_version": contract.feature_contract_version,
        "product_contract_version": contract.product_contract_version,
        "source_snapshot": contract.source_snapshot,
        "code_commit": contract.code_commit,
        "split_strategy": contract.split_strategy,
        "label_provenance": contract.label_provenance,
    }
    for field_name, value in required_values.items():
        if not value.strip():
            violations.append(f"{field_name} must be non-empty.")
    if contract.training_platform != TRAINING_PLATFORM:
        violations.append(f"training_platform must be {TRAINING_PLATFORM!r} for ML-LEARN-001 foundation experiments.")
    return violations


def route_llm_residual(inputs: ResidualRoutingInput) -> ResidualRoutingDecision:
    reasons: list[str] = []

    if inputs.ml_signal_available and not inputs.ml_confident:
        reasons.append("ml_uncertain")
    if inputs.novel_pattern:
        reasons.append("novel_pattern")
    if inputs.evidence_conflict:
        reasons.append("evidence_conflict")
    if inputs.missing_semantics:
        reasons.append("missing_semantics")
    if inputs.high_value_adjudication:
        reasons.append("high_value_adjudication")

    return ResidualRoutingDecision(escalate_to_llm=bool(reasons), reasons=tuple(reasons))
