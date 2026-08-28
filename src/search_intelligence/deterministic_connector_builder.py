"""Evidence-driven deterministic connector-builder layer model.

This module contains no network, database, provider, connector-registration or
product side effects. It models one candidate as an ordered set of deterministic
layers and makes optionality explicit: a layer may be ``skipped`` only when
observed evidence says it is not required for the current surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping, Sequence


class LayerState(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    SKIPPED = "skipped"
    NOT_REACHED = "not_reached"


LAYER_ORDER = (
    "identity",
    "origin",
    "origin_reachability",
    "delegation",
    "provider",
    "inventory",
    "detail",
    "proof",
    "recipe",
)


@dataclass(frozen=True)
class LayerResult:
    layer: str
    state: LayerState
    required: bool | None
    reason: str
    evidence: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.layer not in LAYER_ORDER:
            raise ValueError(f"unknown connector-builder layer: {self.layer}")
        if self.state == LayerState.FAIL and self.required is not True:
            raise ValueError("only evidence-required layers may FAIL")
        if self.state == LayerState.PASS and self.required is not True:
            raise ValueError("PASS is reserved for evidence-required layers")
        if self.state == LayerState.SKIPPED and self.required is not False:
            raise ValueError("SKIPPED requires evidence that the layer is not required")
        if self.state == LayerState.NOT_REACHED and self.required is not None:
            raise ValueError("NOT_REACHED requires undecided necessity")

    def to_json(self) -> dict[str, object]:
        return {
            "layer": self.layer,
            "state": self.state.value,
            "required": self.required,
            "reason": self.reason,
            "evidence": dict(self.evidence),
        }


@dataclass(frozen=True)
class ConnectorBuilderAssessment:
    candidate_id: int
    company_key: str
    company_name: str
    layers: tuple[LayerResult, ...]

    def __post_init__(self) -> None:
        names = tuple(item.layer for item in self.layers)
        if names != LAYER_ORDER:
            raise ValueError(f"layer order mismatch: {names!r}")

    @property
    def first_failure(self) -> LayerResult | None:
        return next((item for item in self.layers if item.state == LayerState.FAIL), None)

    @property
    def recipe_ready(self) -> bool:
        return self.layers[-1].state == LayerState.PASS

    def to_json(self) -> dict[str, object]:
        failure = self.first_failure
        return {
            "candidate_id": self.candidate_id,
            "company_key": self.company_key,
            "company_name": self.company_name,
            "recipe_ready": self.recipe_ready,
            "first_failure_layer": failure.layer if failure else None,
            "first_failure_reason": failure.reason if failure else None,
            "layers": [item.to_json() for item in self.layers],
        }


def passed(layer: str, reason: str, **evidence: object) -> LayerResult:
    return LayerResult(layer, LayerState.PASS, True, reason, evidence)


def skipped(layer: str, reason: str, **evidence: object) -> LayerResult:
    return LayerResult(layer, LayerState.SKIPPED, False, reason, evidence)


def failed(layer: str, reason: str, **evidence: object) -> LayerResult:
    return LayerResult(layer, LayerState.FAIL, True, reason, evidence)


def not_reached(layer: str, reason: str, **evidence: object) -> LayerResult:
    return LayerResult(layer, LayerState.NOT_REACHED, None, reason, evidence)


def complete_after_failure(
    prefix: Sequence[LayerResult],
    *,
    failed_layer: str,
    failure_reason: str,
    failure_evidence: Mapping[str, object] | None = None,
) -> tuple[LayerResult, ...]:
    """Finish a layer chain after the first evidence-required failure.

    Later layer necessity is deliberately left undecided. Without upstream
    evidence, declaring those layers either required or optional would itself be
    an unsupported inference.
    """

    results = list(prefix)
    expected = LAYER_ORDER[len(results)]
    if expected != failed_layer:
        raise ValueError(f"expected next layer {expected!r}, got {failed_layer!r}")
    results.append(
        LayerResult(
            failed_layer,
            LayerState.FAIL,
            True,
            failure_reason,
            dict(failure_evidence or {}),
        )
    )
    for layer in LAYER_ORDER[len(results) :]:
        results.append(
            not_reached(
                layer,
                f"not evaluated because required upstream layer {failed_layer} failed",
                blocked_by=failed_layer,
            )
        )
    return tuple(results)


def summarize_assessments(
    assessments: Sequence[ConnectorBuilderAssessment],
) -> dict[str, object]:
    first_failures: dict[str, int] = {}
    layer_states: dict[str, dict[str, int]] = {
        layer: {state.value: 0 for state in LayerState}
        for layer in LAYER_ORDER
    }
    ready = 0

    for assessment in assessments:
        if assessment.recipe_ready:
            ready += 1
        failure = assessment.first_failure
        if failure is not None:
            first_failures[failure.layer] = first_failures.get(failure.layer, 0) + 1
        for result in assessment.layers:
            layer_states[result.layer][result.state.value] += 1

    total = len(assessments)
    return {
        "candidate_count": total,
        "recipe_ready_count": ready,
        "recipe_ready_rate": round(ready / total, 4) if total else 0.0,
        "first_failure_counts": dict(sorted(first_failures.items())),
        "layer_state_counts": layer_states,
    }


__all__ = [
    "ConnectorBuilderAssessment",
    "LAYER_ORDER",
    "LayerResult",
    "LayerState",
    "complete_after_failure",
    "failed",
    "not_reached",
    "passed",
    "skipped",
    "summarize_assessments",
]
